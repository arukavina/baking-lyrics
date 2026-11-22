"""
/api/v1/genres endpoints. Seed data: one genre (id 1, "Pop") with one artist.
"""

# Libs
from flask_restx import marshal


def _max_genre_id(app):
    from baking.main import db
    from baking.main.database.models import Genre

    with app.app_context():
        return db.session.query(db.func.max(Genre.id)).scalar()


def test_genre_create(app, client):
    from baking.main import db
    from baking.main.database.models import Genre

    id_testing = _max_genre_id(app) + 1

    response = client.post('/api/v1/genres/', json={"id": id_testing, "name": "Death Metal"})

    assert response.status_code == 201
    with app.app_context():
        assert db.session.get(Genre, id_testing).name == 'Death Metal'


def test_genre_create_without_id(app, client):
    from baking.main.database.models import Genre

    response = client.post('/api/v1/genres/', json={"name": "Jazz"})

    assert response.status_code == 201
    with app.app_context():
        assert Genre.query.filter(Genre.name == 'Jazz').count() == 1


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


def test_genre_update(app, client):
    from baking.main import db
    from baking.main.database.models import Genre

    id_testing = _max_genre_id(app)

    response = client.put(f'/api/v1/genres/{id_testing}', json={"name": "country"})

    assert response.status_code == 204
    with app.app_context():
        assert db.session.get(Genre, id_testing).name == 'country'


def test_genre_update_unknown_is_404(client):
    assert client.put('/api/v1/genres/999', json={"name": "country"}).status_code == 404


def test_genre_delete(app, client):
    id_testing = _max_genre_id(app)

    response = client.delete(f'/api/v1/genres/{id_testing}')

    assert response.status_code == 204
    assert client.get(f'/api/v1/genres/{id_testing}').status_code == 404


def test_genre_delete_unknown_is_404(client):
    assert client.delete('/api/v1/genres/999').status_code == 404
