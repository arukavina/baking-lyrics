"""
CORS on /api/*: only the configured origins, methods GET/POST/OPTIONS and the Content-Type header.
"""

# Libs
import pytest

ORIGIN = 'https://bakinglyrics.example'
OTHER = 'https://evil.example'


@pytest.fixture
def cors_client(make_app):
    return make_app(ALLOWED_ORIGINS=[ORIGIN, 'http://localhost:3000']).test_client()


def test_default_allowed_origins_is_localhost(config_env):
    config_env(ALLOWED_ORIGINS=None)
    import config.default

    assert config.default.ALLOWED_ORIGINS == ['http://localhost:3000']


def test_allowed_origins_are_read_from_the_environment(config_env):
    config_env(ALLOWED_ORIGINS=' https://a.example, https://b.example ,,')
    import config.default

    assert config.default.ALLOWED_ORIGINS == ['https://a.example', 'https://b.example']


def test_allowed_origin_gets_cors_headers(cors_client):
    response = cors_client.get('/api/v1/general/ping', headers={'Origin': ORIGIN})

    assert response.status_code == 200
    assert response.headers['Access-Control-Allow-Origin'] == ORIGIN


def test_other_origin_gets_no_cors_headers(cors_client):
    response = cors_client.get('/api/v1/general/ping', headers={'Origin': OTHER})

    assert response.status_code == 200
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_preflight_for_json_post(cors_client):
    response = cors_client.options('/api/v1/general/ping', headers={
        'Origin': ORIGIN,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
    })

    assert response.status_code == 200
    assert response.headers['Access-Control-Allow-Origin'] == ORIGIN
    allowed_methods = {m.strip() for m in response.headers['Access-Control-Allow-Methods'].split(',')}
    assert allowed_methods == {'GET', 'POST', 'OPTIONS'}
    assert response.headers['Access-Control-Allow-Headers'].lower() == 'content-type'


def test_preflight_for_disallowed_method(cors_client):
    response = cors_client.options('/api/v1/general/ping', headers={
        'Origin': ORIGIN,
        'Access-Control-Request-Method': 'DELETE',
    })

    assert 'Access-Control-Allow-Methods' not in response.headers


def test_cors_only_applies_to_the_api(cors_client):
    response = cors_client.get('/swaggerui/missing', headers={'Origin': ORIGIN})

    assert 'Access-Control-Allow-Origin' not in response.headers


def test_error_responses_get_cors_headers(cors_client):
    # The frontend reads error bodies (404, 503...), so they need the header too.
    response = cors_client.get('/api/v1/does-not-exist', headers={'Origin': ORIGIN})

    assert response.status_code == 404
    assert response.headers['Access-Control-Allow-Origin'] == ORIGIN
