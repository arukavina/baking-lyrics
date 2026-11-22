"""
DynamoRepository and the table schema, on moto.
"""

# Generic
from datetime import date, datetime

# Libs
import boto3
import pytest

# Own
from baking.main.repository import schema
from baking.tests.conftest import REGION, TABLE_PREFIX

POP = {'id': 1, 'name': 'Pop'}
ROCK = {'id': 2, 'name': 'Rock'}


def artist(artist_id, clean_name, genre_id=1, cover=False, formation_date=date(1986, 6, 28), name=None):
    return {'id': artist_id, 'name': name or clean_name.lower().replace(' ', '-'), 'clean_name': clean_name,
            'cover': cover, 'country': 'US', 'formation_date': formation_date, 'genre_id': genre_id}


def song(song_id, artist_id, title='Song'):
    return {'id': song_id, 'title': f'{title} {song_id}', 'lyrics': 'la la la ' * 5,
            'publication_date': date(2009, 1, 1), 'artist_id': artist_id}


@pytest.fixture
def seeded(repo):
    repo.save_catalog(genres=[POP, ROCK],
                      artists=[artist(1, 'Beyonce Knowles', cover=True), artist(2, 'Abba', genre_id=2),
                               artist(3, 'Beyonce Tribute')],
                      songs=[song(1, 1), song(2, 1), song(3, 2)])
    return repo


# Schema

def test_create_tables_is_idempotent(aws):
    client = boto3.client('dynamodb', region_name=REGION)

    assert schema.create_tables(client, prefix=TABLE_PREFIX) == []
    created = schema.create_tables(client, prefix='other', wait=True)

    assert sorted(created) == sorted(f'other-{table}' for table in schema.TABLES)
    assert schema.create_tables(client, prefix='other') == []


def test_tables_are_on_demand_with_expected_keys(aws):
    client = boto3.client('dynamodb', region_name=REGION)

    catalog = client.describe_table(TableName=f'{TABLE_PREFIX}-catalog')['Table']

    assert catalog['BillingModeSummary']['BillingMode'] == 'PAY_PER_REQUEST'
    assert catalog['KeySchema'] == [{'AttributeName': 'pk', 'KeyType': 'HASH'}]
    assert {index['IndexName'] for index in catalog['GlobalSecondaryIndexes']} == {'by_entity', 'by_artist'}


def test_ratelimit_table_has_ttl(aws):
    client = boto3.client('dynamodb', region_name=REGION)

    ttl = client.describe_time_to_live(TableName=f'{TABLE_PREFIX}-ratelimit')['TimeToLiveDescription']

    assert ttl == {'TimeToLiveStatus': 'ENABLED', 'AttributeName': 'ttl'}


def test_create_tables_cli(aws, capsys):
    from baking import create_tables

    created = create_tables.main(['--prefix', 'cli', '--wait'])

    assert len(created) == len(schema.TABLES)
    assert '5 table(s) created' in capsys.readouterr().out
    assert create_tables.main(['--prefix', 'cli']) == []


# Catalog

def test_empty_repository(repo):
    assert repo.list_artists() == []
    assert repo.list_genres() == []
    assert repo.list_songs() == []
    assert repo.random_song() is None
    assert repo.get_artist(1) is None
    assert repo.get_stats() == {'artists': 0, 'songs_generated': 0, 'shares': 0, 'top_artists': []}


def test_artist_record(seeded):
    assert seeded.get_artist(1) == {
        'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles', 'cover': True, 'country': 'US',
        'formation_date': datetime(1986, 6, 28), 'genre_id': 1, 'genre': {'id': 1, 'name': 'Pop'},
    }


def test_artist_without_optional_fields(repo):
    repo.save_catalog(artists=[{'id': 7, 'name': 'raw'}])

    assert repo.get_artist(7) == {'id': 7, 'name': 'raw', 'clean_name': None, 'cover': False, 'country': None,
                                  'formation_date': None, 'genre_id': None, 'genre': None}


def test_lists_are_ordered_by_id(seeded):
    assert [a['id'] for a in seeded.list_artists()] == [1, 2, 3]
    assert seeded.list_genres() == [POP, ROCK]
    assert [s['id'] for s in seeded.list_songs()] == [1, 2, 3]


def test_search_is_case_insensitive_and_ordered_by_clean_name(seeded):
    assert [a['id'] for a in seeded.search_artists('BEYONCE')] == [1, 3]
    assert [a['id'] for a in seeded.search_artists('tribu')] == [3]
    assert seeded.search_artists('metallica') == []


def test_cover_artists(seeded):
    assert [a['id'] for a in seeded.cover_artists()] == [1]


def test_song_record_includes_its_artist(seeded):
    found = seeded.get_song(3)

    assert found['title'] == 'Song 3'
    assert found['publication_date'] == datetime(2009, 1, 1)
    assert found['artist']['clean_name'] == 'Abba'
    assert seeded.get_song(99) is None


def test_first_song_of_artist(seeded):
    assert seeded.first_song_of_artist(1)['id'] == 1
    assert seeded.first_song_of_artist(2)['id'] == 3
    assert seeded.first_song_of_artist(3) is None


def test_random_song(seeded):
    assert {seeded.random_song()['id'] for _ in range(20)} <= {1, 2, 3}


def test_random_song_falls_back_when_ids_have_gaps(seeded):
    seeded.prune_catalog(genre_ids=[1, 2], artist_ids=[1, 2, 3], song_ids=[3])

    assert seeded.random_song()['id'] == 3


def test_save_catalog_overwrites_and_moves_sequences(seeded):
    seeded.save_catalog(artists=[artist(2, 'ABBA Renamed', genre_id=2)])

    assert seeded.get_artist(2)['clean_name'] == 'ABBA Renamed'
    assert seeded.get_artist(2)['genre'] == {'id': 2, 'name': 'Rock'}  # genre name looked up
    assert seeded.next_id('artist') == 4
    assert seeded.next_id('song') == 4
    assert seeded.next_id('genre') == 3
    assert seeded.get_stats()['artists'] == 3


def test_prune_catalog(seeded):
    deleted = seeded.prune_catalog(genre_ids=[1], artist_ids=[1], song_ids=[1, 2])

    assert deleted == 4  # genre 2, artists 2 and 3, song 3
    assert [a['id'] for a in seeded.list_artists()] == [1]
    assert seeded.get_stats()['artists'] == 1


def test_artist_cache(aws):
    from baking.main.repository import DynamoRepository

    cached = DynamoRepository(prefix=TABLE_PREFIX, region=REGION, cache_seconds=3600)
    writer = DynamoRepository(prefix=TABLE_PREFIX, region=REGION, cache_seconds=0)
    writer.save_catalog(genres=[POP], artists=[artist(1, 'One')])
    assert len(cached.list_artists()) == 1

    writer.save_catalog(artists=[artist(2, 'Two')])

    assert len(cached.list_artists()) == 1  # still cached
    cached.invalidate_cache()
    assert len(cached.list_artists()) == 2


# Generated songs, titles, shares and stats

def test_create_generated_song(seeded):
    created = seeded.create_generated_song('Ego (Artificial)', 'new lyrics', 'model-x', 1)

    assert created['id'] == 1
    assert created['artificial_title']['id'] == 1
    assert created['artificial_title']['title'] == 'Ego (Artificial)'
    assert created['base_artist']['id'] == 1
    assert seeded.get_generated_song(1) == created
    assert [t['title'] for t in seeded.list_titles()] == ['Ego (Artificial)']
    assert seeded.get_stats()['songs_generated'] == 1


def test_generated_ids_are_sequential(seeded):
    seeded.create_title('lonely title')
    first = seeded.create_generated_song('a', 'x', 'm', 1)
    second = seeded.create_generated_song('b', 'y', 'm', 2)

    assert (first['id'], second['id']) == (1, 2)
    assert [t['id'] for t in seeded.list_titles()] == [1, 2, 3]
    assert [s['id'] for s in seeded.list_generated_songs()] == [1, 2]


def test_shares(seeded):
    seeded.create_generated_song('a', 'x', 'm', 1)
    seeded.create_generated_song('b', 'y', 'm', 1)

    assert seeded.add_share(1, 'facebook') == 1
    assert seeded.add_share(1, 'twitter') == 2
    assert seeded.add_share(2, 'whatsapp') == 1
    assert seeded.add_share(99, 'facebook') is None
    assert [s['network'] for s in seeded.list_shares(1)] == ['facebook', 'twitter']
    assert seeded.get_stats()['shares'] == 3


def test_stats_top_artists(seeded):
    for artist_id, count in ((2, 3), (1, 1), (3, 1)):
        for _ in range(count):
            seeded.create_generated_song('t', 'l', 'm', artist_id)

    stats = seeded.get_stats(top=2)

    assert stats['artists'] == 3
    assert stats['songs_generated'] == 5
    assert stats['top_artists'] == [
        {'id': 2, 'name': 'Abba', 'songs_generated': 3},
        {'id': 1, 'name': 'Beyonce Knowles', 'songs_generated': 1},  # tie with Beyonce Tribute, by name
    ]
