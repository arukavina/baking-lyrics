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
    assert [s['id'] for s in response.json] == [1, 2, 3, 4, 5, 6]


