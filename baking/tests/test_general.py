"""
/api/v1/general endpoints.
"""

# Generic
from pathlib import Path

# Libs
import pytest


def test_random(client):
    response = client.get('/api/v1/general/random')

    assert response.status_code == 200
    assert 1 <= response.json['id'] <= 6
    assert response.json['title']
    assert response.json['lyrics']


def test_ping_get(client):
    response = client.get('/api/v1/general/ping')

    assert response.status_code == 200
    assert response.json == 'pong!'


def test_ping_post(client):
    response = client.post('/api/v1/general/ping')

    assert response.status_code == 200
    assert response.json == 'pong!'


def test_unknown_route_is_404(client):
    assert client.get('/api/v1/does-not-exist').status_code == 404


def test_swagger_spec_is_served(client):
    response = client.get('/api/v1/swagger.json')

    assert response.status_code == 200
    assert '/artists/' in response.json['paths']


def test_index(app, client):
    if not (Path(app.template_folder) / 'index.html').is_file():
        pytest.skip('Frontend not built: baking/static/index.html is missing')

    assert client.get('/api/v1/general/').status_code == 200


def test_random_after_deleting_songs(client):
    for song_id in range(1, 6):
        assert client.delete(f'/api/v1/songs/{song_id}').status_code == 204

    response = client.get('/api/v1/general/random')

    assert response.status_code == 200
    assert response.json['id'] == 6
