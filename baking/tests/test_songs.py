"""
/api/v1/songs endpoints. Seed data: 6 songs (ids 1..6) by artist 1.
"""

# Libs
from flask_restx import marshal

GLORIA = ("gloria patri et filio et spiritui sancto, sicut erat in principio et nunc et semper "
          "et in saecula saeculorum amen")


def _max_song_id(app):
    from baking.main import db
    from baking.main.database.models import Song

    with app.app_context():
        return db.session.query(db.func.max(Song.id)).scalar()


def test_song_create(app, client):
    from baking.main.database.models import Song

    data = {"title": "gloria",
            "lyrics": GLORIA,
            "pub_date": "1987-12-05T00:00:00",
            "artist_id": 1,
            "country": "US"}

    response = client.post('/api/v1/songs/', json=data)

    assert response.status_code == 201
    with app.app_context():
        created = Song.query.filter(Song.title == 'gloria').one()
        assert created.artist_id == 1
        assert created.publication_date.isoformat() == '1987-12-05T00:00:00'


def test_song_create_unknown_artist_is_404(client):
    data = {"title": "gloria", "lyrics": GLORIA, "artist_id": 999}

    assert client.post('/api/v1/songs/', json=data).status_code == 404


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


def test_song_update(app, client):
    from baking.main import db
    from baking.main.database.models import Song

    data = {"artist_id": 1, "title": "Amen", "lyrics": "I heard from a friend of a friend"}
    id_testing = _max_song_id(app)

    response = client.put(f'/api/v1/songs/{id_testing}', json=data)

    assert response.status_code == 204
    with app.app_context():
        updated = db.session.get(Song, id_testing)
        assert updated.title == 'Amen'
        assert updated.lyrics == 'I heard from a friend of a friend'


def test_song_update_unknown_is_404(client):
    data = {"artist_id": 1, "title": "Amen", "lyrics": "I heard from a friend of a friend"}

    assert client.put('/api/v1/songs/999', json=data).status_code == 404


def test_song_delete(app, client):
    id_testing = _max_song_id(app)

    response = client.delete(f'/api/v1/songs/{id_testing}')

    assert response.status_code == 204
    assert client.get(f'/api/v1/songs/{id_testing}').status_code == 404


def test_song_delete_unknown_is_404(client):
    assert client.delete('/api/v1/songs/999').status_code == 404


def test_song_update_with_publication_date(app, client):
    from baking.main import db
    from baking.main.database.models import Song

    data = {"artist_id": 1, "title": "Amen", "lyrics": "la la la", "publication_date": "2000-01-01T00:00:00"}

    response = client.put('/api/v1/songs/1', json=data)

    assert response.status_code == 204
    with app.app_context():
        assert db.session.get(Song, 1).publication_date.isoformat() == '2000-01-01T00:00:00'


def test_song_update_with_invalid_publication_date_is_400(client):
    data = {"artist_id": 1, "title": "Amen", "lyrics": "la la la", "publication_date": "not-a-date"}

    assert client.put('/api/v1/songs/1', json=data).status_code == 400
