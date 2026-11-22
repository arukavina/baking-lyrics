"""
/api/v1/artificial_songs and /api/v1/artificial_titles without the ML models.

In testing, app.extensions['ml_available'] is False: read endpoints work on the seeded artificial
songs/titles (6 of each), and generation endpoints answer 503 after validating their inputs.
"""

# Libs
import pytest

# Own
from baking.tests.conftest import add_artists

ML_UNAVAILABLE = {'message': 'ML models are not loaded'}

SEED_SONG = '/api/v1/artificial_songs/generate/{lang}/seed/{seed}/words/{words}/artist/{artist}/'
NO_SEED_SONG = '/api/v1/artificial_songs/generate/{lang}/words/{words}/artist/{artist}/'
TITLE = '/api/v1/artificial_titles/generate/{lang}/song/{song}/'


def test_ml_is_not_available_in_testing(app):
    assert app.extensions['ml_available'] is False


# Read endpoints

def test_all_artificial_songs_get(client):
    response = client.get('/api/v1/artificial_songs/')

    assert response.status_code == 200
    assert len(response.json) == 6
    assert response.json[0]['base_artist']['id'] == 1
    assert response.json[0]['artificial_title']['title'] == 'ego-remix'


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
    assert len(response.json) == 6


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


# Generation endpoints with (stubbed) models: the song and its title are stored

@pytest.fixture
def ml_client(app, monkeypatch):
    from baking.main.v1.endpoints import artificial_songs

    app.extensions['ml_available'] = True
    calls = []

    def fake_generate_song(input_texts, artist, genre, title, word_count=None):
        calls.append({'artist': artist, 'genre': genre, 'title': title, 'word_count': word_count})
        return 'brand new lyrics'

    monkeypatch.setattr(artificial_songs, 'generate_song', fake_generate_song)
    client = app.test_client()
    client.calls = calls
    return client


@pytest.mark.parametrize('url', [
    SEED_SONG.format(lang='en', seed='hello', words=50, artist=1),
    NO_SEED_SONG.format(lang='en', words=50, artist=1),
])
def test_generate_song_stores_song_and_title(app_repo, ml_client, url):
    response = ml_client.get(url)

    assert response.status_code == 200
    assert response.json['id'] == 7
    assert response.json['lyrics'] == 'brand new lyrics'
    assert response.json['model'] == 'lyrics_skth_v0_20_40_300_5000_100'
    assert response.json['artificial_title']['id'] == 7
    assert response.json['artificial_title']['title'] == 'Ego Remix(Artificial)'
    assert response.json['base_artist']['id'] == 1
    assert ml_client.calls == [{'artist': 'beyonce-knowles', 'genre': 'Pop', 'title': 'xseqstart ego remix xseqend',
                               'word_count': 50}]
    assert ml_client.get('/api/v1/artificial_songs/7').json == response.json
    assert len(ml_client.get('/api/v1/artificial_titles/').json) == 7
    assert app_repo.get_stats()['songs_generated'] == 7


def test_artificial_song_shape(client):
    response = client.get('/api/v1/artificial_songs/1')

    assert set(response.json) == {'id', 'artificial_title', 'lyrics', 'model', 'creation_date', 'user', 'base_artist'}
    assert set(response.json['artificial_title']) == {'id', 'title', 'creation_date'}
    assert response.json['user'] == {'id': None, 'name': None, 'email': None, 'auth_method': None,
                                     'member_since': None}
    assert response.json['base_artist'] == {'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles',
                                            'cover': False, 'country': 'US',
                                            'formation_date': '1986-06-28T00:00:00', 'genre': 'Pop'}
