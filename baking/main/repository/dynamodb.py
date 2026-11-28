"""
DynamoDB implementation of the repository (boto3 resource API). Table layout: see schema.py.

The catalog is small (at most 900 artists and 9,000 songs), so artists are read with one paginated Query
of the ``by_entity`` index and kept in memory for ``cache_seconds``; search, cover, archive and pagination
work on that list. Songs and generated songs are read item by item (GetItem) or by index Query, and
totals come from atomic counters, never from scans.

List pages read only what they show: a page of songs queries ``by_entity`` with Limit up to the end of the
page; generated songs and titles have dense ids (one sequence, never deleted), so a page of them, most recent
first, is one Query of an id range with ScanIndexForward=False.
"""

# Generic
import random
import time
import uuid
from datetime import UTC, date, datetime

# Libs
import boto3.session
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

# Own
from baking.main.repository import schema
from baking.main.repository.base import Repository

RANDOM_SONG_ATTEMPTS = 5

# Counters table layout
SEQ = 'SEQ'
STATS = 'STATS'
STATS_SK = 'totals'
ARTIST_GENERATED = 'ARTIST_GENERATED'
SONG_SHARES = 'SONG_SHARES'


def utcnow():
    """Current UTC time as a naive datetime (the API has always served naive ISO 8601 dates)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).isoformat()
    return str(value)


def _from_iso(value):
    return datetime.fromisoformat(value) if value else None


def _int(value, default=0):
    return int(value) if value is not None else default


def _clean(item):
    """Drops None values: DynamoDB items simply omit missing attributes."""
    return {key: value for key, value in item.items() if value is not None}


def _is_conditional_failure(error):
    return error.response['Error']['Code'] == 'ConditionalCheckFailedException'


class DynamoRepository(Repository):

    def __init__(self, prefix=schema.DEFAULT_PREFIX, region='us-east-1', endpoint_url=None, cache_seconds=60):
        """
        :param prefix: table name prefix (BAKING_TABLE_PREFIX)
        :param region: AWS region of the tables
        :param endpoint_url: optional endpoint (DynamoDB Local or a moto server)
        :param cache_seconds: how long the artist list is kept in memory (0 disables the cache)
        """
        self.prefix = prefix
        self.region = region
        self.endpoint_url = endpoint_url
        self.cache_seconds = cache_seconds
        self._resource = None
        self._tables = {}
        self._artists = None
        self._retired = frozenset()
        self._artists_loaded_at = 0.0

    # Plumbing

    @property
    def resource(self):
        # Created lazily: building the app must not need AWS credentials or network access. A dedicated session:
        # boto3's default session is shared with other threads (the MODEL_PRELOAD thread builds its S3 client
        # meanwhile) and its lazy creation is not thread safe.
        if self._resource is None:
            self._resource = boto3.session.Session().resource('dynamodb', region_name=self.region,
                                                              endpoint_url=self.endpoint_url)
        return self._resource

    def table(self, name):
        """The boto3 Table of one of schema.TABLES."""
        if name not in self._tables:
            self._tables[name] = self.resource.Table(schema.table_name(self.prefix, name))
        return self._tables[name]

    @staticmethod
    def _query_all(table, **kwargs):
        items = []
        while True:
            response = table.query(**kwargs)
            items.extend(response.get('Items', []))
            if 'LastEvaluatedKey' not in response:
                return items
            kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    @staticmethod
    def _count(table, **kwargs):
        total = 0
        while True:
            response = table.query(Select='COUNT', **kwargs)
            total += response['Count']
            if 'LastEvaluatedKey' not in response:
                return total
            kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    def _entities(self, table_name, entity, **kwargs):
        return self._query_all(self.table(table_name), IndexName=schema.BY_ENTITY_INDEX,
                               KeyConditionExpression=Key('entity').eq(entity), **kwargs)

    def _add(self, pk, sk, attribute, amount=1, extra_set=None):
        """Atomic counter: ADD `amount` to counters[pk, sk].attribute and return the new value."""
        expression = 'ADD #a :n'
        names = {'#a': attribute}
        values = {':n': amount}
        if extra_set:
            assignments = []
            for i, (name, value) in enumerate(extra_set.items()):
                names[f'#s{i}'] = name
                values[f':s{i}'] = value
                assignments.append(f'#s{i} = :s{i}')
            expression += ' SET ' + ', '.join(assignments)
        response = self.table(schema.COUNTERS).update_item(
            Key={'pk': pk, 'sk': sk}, UpdateExpression=expression,
            ExpressionAttributeNames=names, ExpressionAttributeValues=values, ReturnValues='UPDATED_NEW')
        return _int(response['Attributes'][attribute])

    # Item <-> record conversions

    @staticmethod
    def _genre(item):
        return {'id': _int(item['id']), 'name': item.get('name')}

    @staticmethod
    def _artist(item):
        genre_id = item.get('genre_id')
        return {
            'id': _int(item['id']),
            'name': item.get('name'),
            'clean_name': item.get('clean_name'),
            'cover': bool(item.get('cover', False)),
            'country': item.get('country'),
            'formation_date': _from_iso(item.get('formation_date')),
            'genre_id': _int(genre_id, None),
            'genre': {'id': _int(genre_id), 'name': item.get('genre_name')} if genre_id is not None else None,
            'wiki_title': item.get('wiki_title'),
            'image_url': item.get('image_url'),
        }

    def _song(self, item):
        artist_id = _int(item.get('artist_id'), None)
        return {
            'id': _int(item['id']),
            'title': item.get('title'),
            'lyrics': item.get('lyrics'),
            'publication_date': _from_iso(item.get('publication_date')),
            'artist_id': artist_id,
            'artist': self.get_artist(artist_id) if artist_id is not None else None,
        }

    @staticmethod
    def _title(item):
        return {'id': _int(item['id']), 'title': item.get('title'), 'creation_date': _from_iso(item.get('creation_date'))}

    def _generated_song(self, item):
        base_artist_id = _int(item.get('base_artist_id'), None)
        return {
            'id': _int(item['id']),
            'artificial_title': {
                'id': _int(item.get('title_id'), None),
                'title': item.get('title'),
                'creation_date': _from_iso(item.get('title_creation_date')),
            },
            'lyrics': item.get('lyrics'),
            'model': item.get('model'),
            'creation_date': _from_iso(item.get('creation_date')),
            'base_artist_id': base_artist_id,
            'base_artist': self.get_artist(base_artist_id) if base_artist_id is not None else None,
        }

    @staticmethod
    def _genre_item(genre):
        return _clean({'pk': f"GENRE#{genre['id']}", 'entity': 'GENRE', 'id': genre['id'], 'name': genre.get('name')})

    def _artist_item(self, artist, genre_names):
        genre_id = artist.get('genre_id')
        genre_name = genre_names.get(genre_id) if genre_id is not None else None
        if genre_id is not None and genre_name is None:
            genre = self.get_genre(genre_id)
            genre_name = genre['name'] if genre else None
        clean_name = artist.get('clean_name')
        return _clean({
            'pk': f"ARTIST#{artist['id']}",
            'entity': 'ARTIST',
            'id': artist['id'],
            'name': artist.get('name'),
            'clean_name': clean_name,
            'clean_name_lc': clean_name.lower() if clean_name else None,
            'cover': bool(artist.get('cover', False)),
            'country': artist.get('country'),
            'formation_date': _to_iso(artist.get('formation_date')),
            'genre_id': genre_id,
            'genre_name': genre_name,
            'wiki_title': artist.get('wiki_title'),
            'image_url': artist.get('image_url'),
        })

    @staticmethod
    def _song_item(song):
        return _clean({
            'pk': f"SONG#{song['id']}",
            'entity': 'SONG',
            'id': song['id'],
            'title': song.get('title'),
            'lyrics': song.get('lyrics'),
            'publication_date': _to_iso(song.get('publication_date')),
            'artist_id': song.get('artist_id'),
        })

    # Catalog reads

    def list_genres(self):
        return [self._genre(item) for item in self._entities(schema.CATALOG, 'GENRE')]

    def get_genre(self, genre_id):
        item = self.table(schema.CATALOG).get_item(Key={'pk': f'GENRE#{genre_id}'}).get('Item')
        return self._genre(item) if item else None

    def _artist_index(self):
        expired = time.monotonic() - self._artists_loaded_at >= self.cache_seconds
        if self._artists is None or expired:
            items = self._entities(schema.CATALOG, 'ARTIST')
            self._retired = frozenset(_int(item['id']) for item in items if item.get('retired'))
            self._artists = {artist['id']: artist for artist in map(self._artist, items)}
            self._artists_loaded_at = time.monotonic()
        return self._artists

    def invalidate_cache(self):
        self._artists = None

    def list_artists(self):
        index = self._artist_index()
        return [artist for artist_id, artist in index.items() if artist_id not in self._retired]

    def get_artist(self, artist_id):
        return self._artist_index().get(artist_id)

    def search_artists(self, text):
        text = text.lower()
        found = [a for a in self.list_artists() if a['clean_name'] and text in a['clean_name'].lower()]
        return sorted(found, key=lambda a: (a['clean_name'], a['id']))

    def cover_artists(self):
        return [artist for artist in self.list_artists() if artist['cover']]

    def list_songs(self):
        return [self._song(item) for item in self._entities(schema.CATALOG, 'SONG')]

    def _total(self, name):
        item = self.table(schema.COUNTERS).get_item(Key={'pk': STATS, 'sk': STATS_SK}).get('Item') or {}
        return _int(item.get(name))

    def _sequence_value(self, sequence):
        item = self.table(schema.COUNTERS).get_item(Key={'pk': SEQ, 'sk': sequence}).get('Item')
        return _int(item.get('value')) if item else 0

    def page_songs(self, page, per_page):
        skip = (max(page, 1) - 1) * per_page
        kwargs = {'IndexName': schema.BY_ENTITY_INDEX, 'KeyConditionExpression': Key('entity').eq('SONG')}
        items = []
        while len(items) < skip + per_page:
            response = self.table(schema.CATALOG).query(Limit=skip + per_page - len(items), **kwargs)
            items.extend(response.get('Items', []))
            if 'LastEvaluatedKey' not in response:
                break
            kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        return [self._song(item) for item in items[skip:skip + per_page]], self._total('songs')

    def _page_by_id_desc(self, entity, sequence, page, per_page):
        """Items of `entity` in the generated table with ids in the page's range, highest id first."""
        total = self._sequence_value(sequence)
        high = total - (max(page, 1) - 1) * per_page
        if high < 1:
            return [], total
        low = max(1, high - per_page + 1)
        items = self._query_all(self.table(schema.GENERATED), IndexName=schema.BY_ENTITY_INDEX,
                                KeyConditionExpression=Key('entity').eq(entity) & Key('id').between(low, high),
                                ScanIndexForward=False)
        return items, total

    def get_song(self, song_id):
        item = self.table(schema.CATALOG).get_item(Key={'pk': f'SONG#{song_id}'}).get('Item')
        return self._song(item) if item else None

    def first_song_of_artist(self, artist_id):
        response = self.table(schema.CATALOG).query(IndexName=schema.BY_ARTIST_INDEX,
                                                    KeyConditionExpression=Key('artist_id').eq(artist_id),
                                                    Limit=1)
        items = response.get('Items', [])
        return self._song(items[0]) if items else None

    def random_song(self):
        """Random ids up to the song sequence (ids are dense after seeding), then the first song as a fallback."""
        item = self.table(schema.COUNTERS).get_item(Key={'pk': SEQ, 'sk': 'song'}).get('Item')
        max_id = _int(item.get('value')) if item else 0
        for _ in range(RANDOM_SONG_ATTEMPTS if max_id > 0 else 0):
            song = self.get_song(random.randint(1, max_id))
            if song is not None:
                return song
        response = self.table(schema.CATALOG).query(IndexName=schema.BY_ENTITY_INDEX,
                                                    KeyConditionExpression=Key('entity').eq('SONG'), Limit=1)
        items = response.get('Items', [])
        return self._song(items[0]) if items else None

    # Catalog writes

    def catalog_keys(self):
        projections = {'GENRE': 'id, #n', 'ARTIST': 'id, #n', 'SONG': 'id, #n, artist_id'}
        attributes = {'GENRE': 'name', 'ARTIST': 'name', 'SONG': 'title'}
        items = {entity: self._entities(schema.CATALOG, entity, ProjectionExpression=projection,
                                        ExpressionAttributeNames={'#n': attributes[entity]})
                 for entity, projection in projections.items()}
        return {
            'genres': [{'id': _int(item['id']), 'name': item.get('name')} for item in items['GENRE']],
            'artists': [{'id': _int(item['id']), 'name': item.get('name')} for item in items['ARTIST']],
            'songs': [{'id': _int(item['id']), 'title': item.get('title'),
                       'artist_id': _int(item.get('artist_id'), None)} for item in items['SONG']],
        }

    def save_catalog(self, genres=(), artists=(), songs=(), totals=None):
        genres, artists, songs = list(genres), list(artists), list(songs)
        genre_names = {genre['id']: genre.get('name') for genre in genres}
        with self.table(schema.CATALOG).batch_writer(overwrite_by_pkeys=['pk']) as batch:
            for genre in genres:
                batch.put_item(Item=self._genre_item(genre))
            for artist in artists:
                batch.put_item(Item=self._artist_item(artist, genre_names))
            for song in songs:
                batch.put_item(Item=self._song_item(song))
        for sequence, records in (('genre', genres), ('artist', artists), ('song', songs)):
            if records:
                self._raise_sequence(sequence, max(record['id'] for record in records))
        self._set_catalog_totals(totals)
        self.invalidate_cache()

    def generated_artist_ids(self):
        """Ids of the artists that generated songs were made for (from the per artist counters)."""
        items = self._query_all(self.table(schema.COUNTERS), KeyConditionExpression=Key('pk').eq(ARTIST_GENERATED))
        return {_int(item.get('artist_id'), None) for item in items if _int(item.get('songs_generated')) > 0}

    def prune_catalog(self, genre_ids, artist_ids, song_ids, totals=None):
        keep = {'GENRE': set(genre_ids), 'ARTIST': set(artist_ids), 'SONG': set(song_ids)}
        referenced = self.generated_artist_ids()
        retire = []
        deleted = 0
        with self.table(schema.CATALOG).batch_writer() as batch:
            for entity, ids in keep.items():
                for item in self._entities(schema.CATALOG, entity, ProjectionExpression='pk, id'):
                    item_id = _int(item['id'])
                    if item_id in ids:
                        continue
                    if entity == 'ARTIST' and item_id in referenced:
                        retire.append(item['pk'])
                        continue
                    batch.delete_item(Key={'pk': item['pk']})
                    deleted += 1
        for pk in retire:
            # Off the artist lists and the front page, still readable as the base artist of its generated songs
            self.table(schema.CATALOG).update_item(Key={'pk': pk}, UpdateExpression='SET retired = :t, cover = :f',
                                                   ExpressionAttributeValues={':t': True, ':f': False})
        self._set_catalog_totals(totals)
        self.invalidate_cache()
        return deleted

    def _set_catalog_totals(self, totals=None):
        """Stores the catalog totals of the stats; counts the (not retired) artists and the songs when None."""
        if totals is None:
            catalog = self.table(schema.CATALOG)
            totals = {
                'artists': self._count(catalog, IndexName=schema.BY_ENTITY_INDEX,
                                       KeyConditionExpression=Key('entity').eq('ARTIST'),
                                       FilterExpression=Attr('retired').not_exists()),
                'songs': self._count(catalog, IndexName=schema.BY_ENTITY_INDEX,
                                     KeyConditionExpression=Key('entity').eq('SONG')),
            }
        self.table(schema.COUNTERS).update_item(
            Key={'pk': STATS, 'sk': STATS_SK}, UpdateExpression='SET artists = :a, songs = :s',
            ExpressionAttributeValues={':a': int(totals['artists']), ':s': int(totals['songs'])})

    def _raise_sequence(self, sequence, value):
        try:
            self.table(schema.COUNTERS).update_item(
                Key={'pk': SEQ, 'sk': sequence}, UpdateExpression='SET #v = :v',
                ConditionExpression='attribute_not_exists(#v) OR #v < :v',
                ExpressionAttributeNames={'#v': 'value'}, ExpressionAttributeValues={':v': value})
        except ClientError as error:
            if not _is_conditional_failure(error):
                raise

    def next_id(self, sequence):
        return self._add(SEQ, sequence, 'value')

    def next_ids(self, sequence, count):
        if count <= 0:
            return []
        last = self._add(SEQ, sequence, 'value', amount=count)
        return list(range(last - count + 1, last + 1))

    # Generated songs and titles

    def list_titles(self):
        return [self._title(item) for item in self._entities(schema.GENERATED, 'TITLE')]

    def page_titles(self, page, per_page):
        items, total = self._page_by_id_desc('TITLE', 'artificial_title', page, per_page)
        return [self._title(item) for item in items], total

    def create_title(self, title, creation_date=None):
        record = {'id': self.next_id('artificial_title'), 'title': title, 'creation_date': creation_date or utcnow()}
        self.table(schema.GENERATED).put_item(Item=_clean({
            'pk': f"TITLE#{record['id']}", 'entity': 'TITLE', 'id': record['id'], 'title': title,
            'creation_date': _to_iso(record['creation_date'])}))
        return record

    def list_generated_songs(self):
        return [self._generated_song(item) for item in self._entities(schema.GENERATED, 'SONG')]

    def page_generated_songs(self, page, per_page):
        items, total = self._page_by_id_desc('SONG', 'artificial_song', page, per_page)
        return [self._generated_song(item) for item in items], total

    def get_generated_song(self, song_id):
        item = self.table(schema.GENERATED).get_item(Key={'pk': f'SONG#{song_id}'}).get('Item')
        return self._generated_song(item) if item else None

    def create_generated_song(self, title, lyrics, model, base_artist_id, creation_date=None):
        creation_date = creation_date or utcnow()
        title_record = self.create_title(title, creation_date)
        song_id = self.next_id('artificial_song')
        item = _clean({
            'pk': f'SONG#{song_id}',
            'entity': 'SONG',
            'id': song_id,
            'title_id': title_record['id'],
            'title': title_record['title'],
            'title_creation_date': _to_iso(title_record['creation_date']),
            'lyrics': lyrics,
            'model': model,
            'creation_date': _to_iso(creation_date),
            'base_artist_id': base_artist_id,
        })
        self.table(schema.GENERATED).put_item(Item=item)
        self._add(STATS, STATS_SK, 'songs_generated')
        if base_artist_id is not None:
            self._add(ARTIST_GENERATED, str(base_artist_id), 'songs_generated',
                      extra_set={'artist_id': base_artist_id})
        return self._generated_song(item)

    # Shares and stats

    def add_share(self, artificial_song_id, network):
        song = self.table(schema.GENERATED).get_item(Key={'pk': f'SONG#{artificial_song_id}'},
                                                     ProjectionExpression='pk').get('Item')
        if song is None:
            return None
        created_at = utcnow()
        self.table(schema.SHARES).put_item(Item={
            'pk': f'SONG#{artificial_song_id}',
            'sk': f'{_to_iso(created_at)}#{uuid.uuid4().hex}',
            'artificial_song_id': artificial_song_id,
            'network': network,
            'created_at': _to_iso(created_at),
        })
        shares = self._add(SONG_SHARES, str(artificial_song_id), 'shares')
        self._add(STATS, STATS_SK, 'shares')
        return shares

    def list_shares(self, artificial_song_id):
        """Shares of a generated song, oldest first: ``{'artificial_song_id', 'network', 'created_at'}``."""
        items = self._query_all(self.table(schema.SHARES), KeyConditionExpression=Key('pk').eq(
            f'SONG#{artificial_song_id}'))
        return [{'artificial_song_id': _int(item['artificial_song_id']), 'network': item['network'],
                 'created_at': _from_iso(item['created_at'])} for item in items]

    def get_stats(self, top=3):
        totals = self.table(schema.COUNTERS).get_item(Key={'pk': STATS, 'sk': STATS_SK}).get('Item') or {}
        ranking = []
        for item in self._query_all(self.table(schema.COUNTERS), KeyConditionExpression=Key('pk').eq(ARTIST_GENERATED)):
            generated = _int(item.get('songs_generated'))
            artist = self.get_artist(_int(item.get('artist_id'), None))
            if generated > 0 and artist is not None:
                ranking.append({'id': artist['id'], 'name': artist['clean_name'] or artist['name'],
                                'songs_generated': generated})
        ranking.sort(key=lambda row: (-row['songs_generated'], row['name'] or '', row['id']))
        return {
            'artists': _int(totals.get('artists')),
            'songs_generated': _int(totals.get('songs_generated')),
            'shares': _int(totals.get('shares')),
            'top_artists': ranking[:top],
        }

