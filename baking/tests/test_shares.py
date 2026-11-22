"""
POST /api/v1/artificial_songs/<id>/shares on the seeded database (6 artificial songs).
"""

# Libs
import pytest

SHARES = '/api/v1/artificial_songs/{}/shares'


def test_share_is_created(app, client):
    from baking.main.database.models import Share

    response = client.post(SHARES.format(1), json={'network': 'facebook'})

    assert response.status_code == 201
    assert response.json == {'artificial_song_id': 1, 'network': 'facebook', 'shares': 1}
    with app.app_context():
        share = Share.query.one()
        assert share.artificial_song_id == 1
        assert share.network == 'facebook'
        assert share.created_at is not None


def test_shares_are_counted_per_song(client):
    client.post(SHARES.format(1), json={'network': 'facebook'})
    client.post(SHARES.format(2), json={'network': 'twitter'})

    response = client.post(SHARES.format(1), json={'network': 'whatsapp'})

    assert response.status_code == 201
    assert response.json == {'artificial_song_id': 1, 'network': 'whatsapp', 'shares': 2}


@pytest.mark.parametrize('network', ['Twitter', 'TWITTER', ' twitter '])
def test_network_is_case_insensitive_and_stored_lowercase(app, client, network):
    from baking.main.database.models import Share

    response = client.post(SHARES.format(3), json={'network': network})

    assert response.status_code == 201
    assert response.json['network'] == 'twitter'
    with app.app_context():
        assert Share.query.one().network == 'twitter'


@pytest.mark.parametrize('payload', [
    {},
    {'network': None},
    {'network': ''},
    {'network': 42},
    {'network': 'myspace'},
    {'other': 'facebook'},
])
def test_missing_or_unknown_network_is_400(app, client, payload):
    from baking.main.database.models import Share

    response = client.post(SHARES.format(1), json=payload)

    assert response.status_code == 400
    assert 'message' in response.json
    with app.app_context():
        assert Share.query.count() == 0


def test_unknown_song_is_404(app, client):
    from baking.main.database.models import Share

    response = client.post(SHARES.format(999), json={'network': 'facebook'})

    assert response.status_code == 404
    assert response.json == {'message': 'Lyric does not exist.'}
    with app.app_context():
        assert Share.query.count() == 0


def test_shares_relationship(app_ctx, client):
    from baking.main import db
    from baking.main.database.models import ArtificialSong

    client.post(SHARES.format(4), json={'network': 'facebook'})

    assert db.session.get(ArtificialSong, 4).shares.count() == 1


def test_shares_are_rate_limited_per_client(make_app):
    from baking.main import db, limiter
    from baking.refresh_database import create_artificial, load_song_data, refresh

    app = make_app(RATELIMIT_ENABLED=True, SHARE_RATE_LIMIT='3 per minute')
    with app.app_context():
        db.create_all()
        song_data = load_song_data(app)
        refresh(app, song_data)
        create_artificial(song_data)
        limiter.reset()
    client = app.test_client()

    statuses = [client.post(SHARES.format(1), json={'network': 'facebook'}).status_code for _ in range(4)]

    assert statuses == [201, 201, 201, 429]
    with app.app_context():
        limiter.reset()
