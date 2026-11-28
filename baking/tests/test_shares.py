"""
POST /api/v1/artificial_songs/<id>/shares on the seeded tables (6 generated songs).
"""

# Libs
import pytest

SHARES = '/api/v1/artificial_songs/{}/shares'


def test_share_is_created(app_repo, client):
    response = client.post(SHARES.format(1), json={'network': 'facebook'})

    assert response.status_code == 201
    assert response.json == {'artificial_song_id': 1, 'network': 'facebook', 'shares': 1}
    [share] = app_repo.list_shares(1)
    assert share['artificial_song_id'] == 1
    assert share['network'] == 'facebook'
    assert share['created_at'] is not None


def test_shares_are_counted_per_song(client):
    client.post(SHARES.format(1), json={'network': 'facebook'})
    client.post(SHARES.format(2), json={'network': 'twitter'})

    response = client.post(SHARES.format(1), json={'network': 'whatsapp'})

    assert response.status_code == 201
    assert response.json == {'artificial_song_id': 1, 'network': 'whatsapp', 'shares': 2}


@pytest.mark.parametrize('network', ['Twitter', 'TWITTER', ' twitter '])
def test_network_is_case_insensitive_and_stored_lowercase(app_repo, client, network):
    response = client.post(SHARES.format(3), json={'network': network})

    assert response.status_code == 201
    assert response.json['network'] == 'twitter'
    assert [share['network'] for share in app_repo.list_shares(3)] == ['twitter']


@pytest.mark.parametrize('payload', [
    {},
    {'network': None},
    {'network': ''},
    {'network': 42},
    {'network': 'myspace'},
    {'other': 'facebook'},
])
def test_missing_or_unknown_network_is_400(app_repo, client, payload):
    response = client.post(SHARES.format(1), json=payload)

    assert response.status_code == 400
    assert 'message' in response.json
    assert app_repo.list_shares(1) == []
    assert app_repo.get_stats()['shares'] == 0


def test_unknown_song_is_404(app_repo, client):
    response = client.post(SHARES.format(999), json={'network': 'facebook'})

    assert response.status_code == 404
    assert response.json == {'message': 'Lyric does not exist.'}
    assert app_repo.list_shares(999) == []
    assert app_repo.get_stats()['shares'] == 0


def test_shares_are_listed_per_song(app_repo, client):
    client.post(SHARES.format(4), json={'network': 'facebook'})

    assert len(app_repo.list_shares(4)) == 1
    assert app_repo.list_shares(5) == []

