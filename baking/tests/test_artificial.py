"""
/api/v1/artificial_songs and /api/v1/artificial_titles without the ML models.

In testing no model is configured: read endpoints work on the seeded artificial songs/titles (6 of each),
and generation endpoints answer 503 after validating their inputs. With a fake generator installed the
generated songs and titles are stored.
"""

# Libs
import pytest

# Own
from baking.tests.conftest import add_artists, install_fake_model

ML_UNAVAILABLE = {'message': 'ML models are not loaded'}

SEED_SONG = '/api/v1/artificial_songs/generate/{lang}/seed/{seed}/words/{words}/artist/{artist}/'
NO_SEED_SONG = '/api/v1/artificial_songs/generate/{lang}/words/{words}/artist/{artist}/'
TITLE = '/api/v1/artificial_titles/generate/{lang}/song/{song}/'


def test_ml_is_not_available_in_testing(app):
    from baking.main.v1.models.generator import get_service

    assert get_service(app).status() == 'disabled'


# Read endpoints

def test_all_artificial_songs_get(client):
    response = client.get('/api/v1/artificial_songs/')

    assert response.status_code == 200
    assert {key: response.json[key] for key in ('page', 'pages', 'per_page', 'total')} == {
        'page': 1, 'pages': 1, 'per_page': 10, 'total': 6}
    # most recent first
    assert [song['id'] for song in response.json['items']] == [6, 5, 4, 3, 2, 1]
    assert response.json['items'][-1]['base_artist']['id'] == 1
    assert response.json['items'][-1]['artificial_title']['title'] == 'ego-remix'


@pytest.mark.parametrize('url', ['/api/v1/artificial_songs/', '/api/v1/artificial_titles/'])
def test_generated_lists_paginate_most_recent_first(client, url):
    pages = [client.get(f'{url}?page={page}&per_page=2').json for page in (1, 2, 3, 4)]

    assert [[item['id'] for item in page['items']] for page in pages] == [[6, 5], [4, 3], [2, 1], []]
    assert {(page['total'], page['pages'], page['per_page']) for page in pages} == {(6, 3, 2)}


@pytest.mark.parametrize('url', ['/api/v1/artificial_songs/', '/api/v1/artificial_titles/'])
def test_generated_lists_read_one_page(app_repo, client, url, monkeypatch):
    """A page is one bounded Query on the by_entity index, newest first, never a read of every item."""
    table = app_repo.table('generated')
    calls = []
    query = table.query

    def spy(**kwargs):
        calls.append(kwargs)
        return query(**kwargs)

    monkeypatch.setattr(table, 'query', spy)

    response = client.get(f'{url}?page=2&per_page=2')

    assert [item['id'] for item in response.json['items']] == [4, 3]
    assert len(calls) == 1
    assert calls[0]['IndexName'] == 'by_entity'
    assert calls[0]['ScanIndexForward'] is False


@pytest.mark.parametrize('url', ['/api/v1/artificial_songs/', '/api/v1/artificial_titles/'])
def test_generated_lists_reject_unsupported_per_page(client, url):
    assert client.get(f'{url}?per_page=1000').status_code == 400


def test_one_artificial_song_get(client):
    response = client.get('/api/v1/artificial_songs/1')

    assert response.status_code == 200
    assert response.json['id'] == 1
    assert response.json['model'] == 'Dummy'


def test_one_artificial_song_unknown_is_404(client):
    response = client.get('/api/v1/artificial_songs/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Lyric does not exist.'}


def test_all_artificial_titles_get(client):
    response = client.get('/api/v1/artificial_titles/')

    assert response.status_code == 200
    assert response.json['total'] == 6
    assert [title['id'] for title in response.json['items']] == [6, 5, 4, 3, 2, 1]


# Generation endpoints without ML

@pytest.mark.parametrize('url', [
    SEED_SONG.format(lang='en', seed='hello', words=100, artist=1),
    NO_SEED_SONG.format(lang='en', words=100, artist=1),
    TITLE.format(lang='en', song=1),
])
def test_generate_without_ml_is_503(app_repo, client, url):
    response = client.get(url)

    assert response.status_code == 503
    assert response.json == ML_UNAVAILABLE
    # nothing was persisted
    assert len(app_repo.list_generated_songs()) == 6
    assert len(app_repo.list_titles()) == 6
    assert app_repo.get_stats()['songs_generated'] == 6


@pytest.mark.parametrize('url', [
    SEED_SONG.format(lang='en', seed='hello', words=100, artist=999),
    NO_SEED_SONG.format(lang='en', words=100, artist=999),
])
def test_generate_song_unknown_artist_is_400(client, url):
    response = client.get(url)

    assert response.status_code == 400
    assert response.json == {'message': 'Artist ID = 999 does not exist.'}


@pytest.mark.parametrize('url', [
    SEED_SONG.format(lang='es', seed='hola', words=100, artist=1),
    NO_SEED_SONG.format(lang='es', words=100, artist=1),
])
def test_generate_song_unsupported_language_is_501(client, url):
    assert client.get(url).status_code == 501


@pytest.mark.parametrize('url', [
    SEED_SONG.format(lang='en', seed='hello', words=100, artist=2),
    NO_SEED_SONG.format(lang='en', words=100, artist=2),
])
def test_generate_song_artist_without_songs_is_404(app_repo, client, url):
    assert add_artists(app_repo, 1, names=[('no-songs', 'No Songs')]) == [2]

    assert client.get(url).status_code == 404


def test_generate_title_unknown_song_is_404(client):
    assert client.get(TITLE.format(lang='en', song=999)).status_code == 404


def test_generate_title_unsupported_language_is_400(client):
    assert client.get(TITLE.format(lang='es', song=1)).status_code == 400


# Generation endpoints with a fake generator: the song and its title are stored

@pytest.fixture
def fake(app):
    return install_fake_model(app)


@pytest.mark.parametrize('url, seed_text', [
    (SEED_SONG.format(lang='en', seed='hello', words=50, artist=1), 'hello'),
    (NO_SEED_SONG.format(lang='en', words=50, artist=1), ''),
])
def test_generate_song_stores_song_and_title(app_repo, client, fake, url, seed_text):
    response = client.get(url)

    assert response.status_code == 200
    assert response.json['id'] == 7
    assert response.json['lyrics'] == (seed_text + ' brand new lyrics').strip()
    assert response.json['model'] == 'lyrics-lstm/9.9.9'
    assert response.json['artificial_title']['id'] == 7
    assert response.json['artificial_title']['title'] == 'Brand New Title'
    assert response.json['base_artist']['id'] == 1
    assert fake.calls == [('generate', 'beyonce-knowles', seed_text, 50, None)]
    assert client.get('/api/v1/artificial_songs/7').json == response.json
    assert client.get('/api/v1/artificial_songs/').json['items'][0] == response.json
    assert client.get('/api/v1/artificial_titles/').json['total'] == 7
    assert app_repo.get_stats()['songs_generated'] == 7


@pytest.mark.parametrize('words, expected', [(0, 1), (10, 10), (100000, 500)])
def test_generate_song_bounds_the_word_count(client, fake, words, expected):
    assert client.get(NO_SEED_SONG.format(lang='en', words=words, artist=1)).status_code == 200
    assert fake.calls[-1][3] == expected


def test_generate_title_stores_title(app_repo, client, fake):
    lyrics = app_repo.get_generated_song(1)['lyrics']

    response = client.get(TITLE.format(lang='en', song=1))

    assert response.status_code == 200
    assert set(response.json) == {'id', 'title', 'creation_date'}
    assert response.json['id'] == 7
    assert response.json['title'] == 'Brand New Title'
    assert fake.calls == [('generate_title', 'beyonce-knowles', lyrics)]
    assert client.get('/api/v1/artificial_titles/').json['items'][0] == response.json
    # a title on its own is not a generated song
    assert app_repo.get_stats()['songs_generated'] == 6


def test_artificial_song_shape(client):
    response = client.get('/api/v1/artificial_songs/1')

    assert set(response.json) == {'id', 'artificial_title', 'lyrics', 'model', 'creation_date', 'user', 'base_artist'}
    assert set(response.json['artificial_title']) == {'id', 'title', 'creation_date'}
    assert response.json['user'] == {'id': None, 'name': None, 'email': None, 'auth_method': None,
                                     'member_since': None}
    assert response.json['base_artist'] == {'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles',
                                            'cover': False, 'country': 'US',
                                            'formation_date': '1986-06-28T00:00:00', 'genre': 'Pop'}
