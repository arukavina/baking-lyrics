"""
GET /api/v1/general/stats on an empty database and on seeded data.

The seeded database has 1 artist (id 1) with 6 artificial songs and no shares.
"""

# Libs
import pytest
from sqlalchemy import event

STATS = '/api/v1/general/stats'


@pytest.fixture
def empty_client(make_app):
    from baking.main import db

    app = make_app()
    with app.app_context():
        db.create_all()
    return app.test_client()


def add_artist(name, clean_name, generated):
    """Adds an artist with `generated` artificial songs. Must run inside an app context."""
    from baking.main import db
    from baking.main.database.models import ArtificialSong, ArtificialTitle, Artist, Genre

    artist = Artist(name, clean_name, 'AR', db.session.get(Genre, 1))
    db.session.add(artist)
    for i in range(generated):
        db.session.add(ArtificialSong(ArtificialTitle(f'{name} {i}'), 'la la la', 'Dummy', artist))
    db.session.commit()
    return artist.id


def test_stats_empty_database(empty_client):
    response = empty_client.get(STATS)

    assert response.status_code == 200
    assert response.json == {'artists': 0, 'songs_generated': 0, 'shares': 0, 'top_artists': []}


def test_stats_seeded(app, client):
    from baking.main import db
    from baking.main.database.models import Artist

    with app.app_context():
        seeded = db.session.get(Artist, 1)
        seeded_name = seeded.clean_name or seeded.name

    response = client.get(STATS)

    assert response.status_code == 200
    assert response.json == {
        'artists': 1,
        'songs_generated': 6,
        'shares': 0,
        'top_artists': [{'id': 1, 'name': seeded_name, 'songs_generated': 6}],
    }


def test_stats_counts_shares(client):
    for song_id, network in [(1, 'facebook'), (1, 'twitter'), (2, 'whatsapp')]:
        assert client.post(f'/api/v1/artificial_songs/{song_id}/shares', json={'network': network}).status_code == 201

    assert client.get(STATS).json['shares'] == 3


def test_stats_top_artists_ordering_and_limit(app, client):
    with app.app_context():
        many = add_artist('many', 'Many', 9)
        beta = add_artist('beta', 'Beta', 2)
        alpha = add_artist('zeta raw', 'Alpha', 2)  # tie with beta, sorted by (clean) name
        add_artist('one', 'One', 1)  # fourth place: cut by the limit
        add_artist('none', 'None', 0)  # no generated songs: never listed

    response = client.get(STATS)

    assert response.status_code == 200
    assert response.json['artists'] == 6
    assert response.json['songs_generated'] == 6 + 9 + 2 + 2 + 1
    assert [artist['id'] for artist in response.json['top_artists']] == [many, 1, alpha]
    assert response.json['top_artists'][0] == {'id': many, 'name': 'Many', 'songs_generated': 9}
    assert response.json['top_artists'][2] == {'id': alpha, 'name': 'Alpha', 'songs_generated': 2}
    assert beta not in [artist['id'] for artist in response.json['top_artists']]


def test_stats_name_falls_back_to_raw_name(make_app):
    from baking.main import db
    from baking.main.database.models import Genre

    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Genre('rock'))
        db.session.commit()
        no_clean = add_artist('raw name', None, 1)
        empty_clean = add_artist('other raw', '', 1)

    top = app.test_client().get(STATS).json['top_artists']

    assert top == [
        {'id': empty_clean, 'name': 'other raw', 'songs_generated': 1},
        {'id': no_clean, 'name': 'raw name', 'songs_generated': 1},
    ]


def test_stats_uses_constant_number_of_queries(app, client):
    from baking.main import db

    with app.app_context():
        for i in range(5):
            add_artist(f'artist {i}', f'Artist {i}', i + 1)
        engine = db.engine

    statements = []

    def count(*args, **kwargs):
        statements.append(args[2])

    event.listen(engine, 'before_cursor_execute', count)
    try:
        assert client.get(STATS).status_code == 200
    finally:
        event.remove(engine, 'before_cursor_execute', count)

    assert len(statements) == 2
