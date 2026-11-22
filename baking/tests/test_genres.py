"""
/api/v1/genres endpoints. Seed data: one genre (id 1, "Pop") with one artist.
"""

# Libs
from flask_restx import marshal


def test_genre_get(app, client):
    from baking.main.database.models import Genre
    from baking.main.v1.serializers import genre

    with app.app_context():
        expected = marshal(Genre.query.filter(Genre.id == 1).one(), genre)

    response = client.get('/api/v1/genres/1')

    assert response.status_code == 200
    assert response.json == expected
    assert response.json == {'id': 1, 'name': 'Pop'}


def test_genre_get_unknown_is_404(client):
    response = client.get('/api/v1/genres/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Genre not found.'}


def test_genre_list_includes_artists(client):
    response = client.get('/api/v1/genres/')

    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]['name'] == 'Pop'
    assert [a['id'] for a in response.json[0]['artists']] == [1]


