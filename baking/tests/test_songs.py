"""
/api/v1/songs endpoints. Seed data: 6 songs (ids 1..6) by artist 1.
"""

# Libs
from flask_restx import marshal


def test_song_get(app, client):
    from baking.main.database.models import Song
    from baking.main.v1.serializers import song

    with app.app_context():
        expected = marshal(Song.query.filter(Song.id == 1).one(), song)

    response = client.get('/api/v1/songs/1')

    assert response.status_code == 200
    assert response.json == expected
    assert response.json['title'] == 'Ego Remix'


def test_song_get_unknown_is_404(client):
    response = client.get('/api/v1/songs/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Song not found.'}


def test_song_list(client):
    response = client.get('/api/v1/songs/')

    assert response.status_code == 200
    assert [s['id'] for s in response.json] == [1, 2, 3, 4, 5, 6]


