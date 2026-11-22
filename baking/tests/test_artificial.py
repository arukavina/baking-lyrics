"""
/api/v1/artificial_songs and /api/v1/artificial_titles without the ML models.

In testing, app.extensions['ml_available'] is False: read endpoints work on the seeded artificial
songs/titles (6 of each), and generation endpoints answer 503 after validating their inputs.
"""

# Libs
import pytest

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
def test_generate_without_ml_is_503(app, client, url):
    from baking.main.database.models import ArtificialSong, ArtificialTitle

    response = client.get(url)

    assert response.status_code == 503
    assert response.json == ML_UNAVAILABLE
    with app.app_context():  # nothing was persisted
        assert ArtificialSong.query.count() == 6
        assert ArtificialTitle.query.count() == 6


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
def test_generate_song_artist_without_songs_is_404(app, client, url):
    from baking.main import db
    from baking.main.database.models import Artist, Genre

    with app.app_context():
        db.session.add(Artist('no-songs', 'No Songs', 'US', db.session.get(Genre, 1)))
        db.session.commit()

    assert client.get(url).status_code == 404


def test_generate_title_unknown_song_is_404(client):
    assert client.get(TITLE.format(lang='en', song=999)).status_code == 404


def test_generate_title_unsupported_language_is_400(client):
    assert client.get(TITLE.format(lang='es', song=1)).status_code == 400
