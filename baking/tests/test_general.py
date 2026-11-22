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



@pytest.mark.parametrize('method, url', [
    ('post', '/api/v1/artists/'),
    ('put', '/api/v1/artists/1'),
    ('delete', '/api/v1/artists/1'),
    ('post', '/api/v1/genres/'),
    ('put', '/api/v1/genres/1'),
    ('delete', '/api/v1/genres/1'),
    ('post', '/api/v1/songs/'),
    ('put', '/api/v1/songs/1'),
    ('delete', '/api/v1/songs/1'),
])
def test_catalog_is_read_only(client, method, url):
    assert getattr(client, method)(url, json={'name': 'x'}).status_code == 405
