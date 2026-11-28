"""
/api/v1/songs endpoints. Seed data: 6 songs (ids 1..6) by artist 1.
"""

# Generic
import pandas as pd

# Own
from baking.tests.conftest import TEST_DATA

SEEDED_ARTIST = {'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles', 'cover': False,
                 'country': 'US', 'formation_date': '1986-06-28T00:00:00', 'genre': 'Pop'}


def test_song_get(client):
    response = client.get('/api/v1/songs/1')

    assert response.status_code == 200
    # Same shape as before the move to DynamoDB: `artist` is a list holding the song's artist
    assert response.json == {
        'id': 1,
        'title': 'Ego Remix',
        'lyrics': pd.read_csv(TEST_DATA)['lyrics'][0],
        'publication_date': '2009-01-01T00:00:00',
        'artist': [SEEDED_ARTIST],
    }


def test_song_get_unknown_is_404(client):
    response = client.get('/api/v1/songs/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Song not found.'}


def test_song_list(client):
    response = client.get('/api/v1/songs/')

    assert response.status_code == 200
    assert {key: response.json[key] for key in ('page', 'pages', 'per_page', 'total')} == {
        'page': 1, 'pages': 1, 'per_page': 10, 'total': 6}
    assert [s['id'] for s in response.json['items']] == [1, 2, 3, 4, 5, 6]
    assert response.json['items'][0]['artist'] == [SEEDED_ARTIST]


def test_song_list_paginates(client):
    pages = [client.get(f'/api/v1/songs/?page={page}&per_page=2').json for page in (0, 1, 2, 3, 4)]

    assert [[s['id'] for s in page['items']] for page in pages] == [[1, 2], [1, 2], [3, 4], [5, 6], []]
    assert [page['page'] for page in pages] == [1, 1, 2, 3, 4]
    assert {(page['total'], page['pages']) for page in pages} == {(6, 3)}


def test_song_list_reads_only_up_to_the_end_of_the_page(app_repo, client, monkeypatch):
    table = app_repo.table('catalog')
    limits = []
    query = table.query

    def spy(**kwargs):
        limits.append(kwargs.get('Limit'))
        return query(**kwargs)

    monkeypatch.setattr(table, 'query', spy)

    response = client.get('/api/v1/songs/?page=2&per_page=2')

    assert [s['id'] for s in response.json['items']] == [3, 4]
    assert limits == [4]


def test_song_list_rejects_unsupported_per_page(client):
    assert client.get('/api/v1/songs/?per_page=1000').status_code == 400


