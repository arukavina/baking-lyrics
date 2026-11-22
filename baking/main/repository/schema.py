"""
DynamoDB table definitions: the single source of truth for table names, keys, indexes and TTL.

Every table is on-demand (PAY_PER_REQUEST) and named ``{prefix}-{suffix}`` (prefix from
BAKING_TABLE_PREFIX, default ``baking-lyrics``):

- ``catalog``: genres, artists and songs (items ``GENRE#<id>``, ``ARTIST#<id>``, ``SONG#<id>``).
  GSI ``by_entity`` (entity, id) lists one kind of item ordered by id; sparse GSI ``by_artist``
  (artist_id, id) lists the songs of an artist (only songs have ``artist_id``).
- ``generated``: generated songs and titles (items ``SONG#<id>``, ``TITLE#<id>``), GSI ``by_entity``.
- ``shares``: one item per share, pk ``SONG#<artificial song id>``, sk ``<created_at>#<uuid>``.
- ``counters``: id sequences (pk ``SEQ``), totals (pk ``STATS``), generated songs per artist
  (pk ``ARTIST_GENERATED``) and shares per generated song (pk ``SONG_SHARES``), all with atomic ADD.
- ``ratelimit``: fixed window counters, pk ``<ip>#<route>#<window>``, expired by TTL on ``ttl``.
"""

# Libs
from botocore.exceptions import ClientError

DEFAULT_PREFIX = 'baking-lyrics'

CATALOG = 'catalog'
GENERATED = 'generated'
SHARES = 'shares'
COUNTERS = 'counters'
RATELIMIT = 'ratelimit'

TABLES = (CATALOG, GENERATED, SHARES, COUNTERS, RATELIMIT)

BY_ENTITY_INDEX = 'by_entity'
BY_ARTIST_INDEX = 'by_artist'

TTL_ATTRIBUTE = 'ttl'

# Tables whose items expire through DynamoDB TTL
TTL_TABLES = {RATELIMIT: TTL_ATTRIBUTE}


def table_name(prefix, table):
    """
    :param prefix: table name prefix, e.g. baking-lyrics
    :param table: one of TABLES
    :return: full table name, e.g. baking-lyrics-catalog
    """
    return f'{prefix}-{table}'


def _attributes(**types):
    return [{'AttributeName': name, 'AttributeType': kind} for name, kind in types.items()]


def _keys(hash_key, range_key=None):
    keys = [{'AttributeName': hash_key, 'KeyType': 'HASH'}]
    if range_key:
        keys.append({'AttributeName': range_key, 'KeyType': 'RANGE'})
    return keys


def _index(name, hash_key, range_key):
    return {'IndexName': name, 'KeySchema': _keys(hash_key, range_key), 'Projection': {'ProjectionType': 'ALL'}}


def table_definitions(prefix=DEFAULT_PREFIX):
    """
    CreateTable arguments of every table.
    :param prefix: table name prefix
    :return: dict table -> kwargs for DynamoDB.Client.create_table
    """
    definitions = {
        CATALOG: {
            'AttributeDefinitions': _attributes(pk='S', entity='S', id='N', artist_id='N'),
            'KeySchema': _keys('pk'),
            'GlobalSecondaryIndexes': [_index(BY_ENTITY_INDEX, 'entity', 'id'),
                                       _index(BY_ARTIST_INDEX, 'artist_id', 'id')],
        },
        GENERATED: {
            'AttributeDefinitions': _attributes(pk='S', entity='S', id='N'),
            'KeySchema': _keys('pk'),
            'GlobalSecondaryIndexes': [_index(BY_ENTITY_INDEX, 'entity', 'id')],
        },
        SHARES: {
            'AttributeDefinitions': _attributes(pk='S', sk='S'),
            'KeySchema': _keys('pk', 'sk'),
        },
        COUNTERS: {
            'AttributeDefinitions': _attributes(pk='S', sk='S'),
            'KeySchema': _keys('pk', 'sk'),
        },
        RATELIMIT: {
            'AttributeDefinitions': _attributes(pk='S'),
            'KeySchema': _keys('pk'),
        },
    }
    for table, definition in definitions.items():
        definition['TableName'] = table_name(prefix, table)
        definition['BillingMode'] = 'PAY_PER_REQUEST'
    return definitions


def _table_exists(client, name):
    try:
        client.describe_table(TableName=name)
    except ClientError as error:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        raise
    return True


def _enable_ttl(client, name, attribute):
    """Enables TTL on `attribute` unless it is already enabled (or being enabled). Returns True if changed."""
    description = client.describe_time_to_live(TableName=name)['TimeToLiveDescription']
    if description.get('TimeToLiveStatus') in ('ENABLED', 'ENABLING'):
        return False
    client.update_time_to_live(TableName=name,
                               TimeToLiveSpecification={'Enabled': True, 'AttributeName': attribute})
    return True


def create_tables(client, prefix=DEFAULT_PREFIX, wait=False, log=None):
    """
    Creates the missing tables and enables TTL where needed. Idempotent: existing tables are left as they are.

    TTL can only be enabled on an ACTIVE table, so tables with TTL are always waited for.
    :param client: boto3 DynamoDB client
    :param prefix: table name prefix
    :param wait: wait until every created table is ACTIVE
    :param log: optional callable receiving progress messages
    :return: list of the table names that were created
    """
    log = log or (lambda message: None)
    created = []
    for table, definition in table_definitions(prefix).items():
        name = definition['TableName']
        if _table_exists(client, name):
            log(f'exists   {name}')
        else:
            client.create_table(**definition)
            created.append(name)
            log(f'created  {name}')
        if wait or table in TTL_TABLES:
            client.get_waiter('table_exists').wait(TableName=name)
        if table in TTL_TABLES and _enable_ttl(client, name, TTL_TABLES[table]):
            log(f'ttl on   {name}.{TTL_TABLES[table]}')
    return created
