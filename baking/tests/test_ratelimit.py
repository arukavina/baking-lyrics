"""
DynamoDB fixed window rate limit (baking.main.ratelimit) and its use on POST /artificial_songs/<id>/shares and
on the generation routes.
"""

# Generic
import json

# Libs
import boto3
import pytest
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

# Own
from baking.main import ratelimit
from baking.main.repository import schema
from baking.tests.conftest import REGION, TABLE_PREFIX, install_fake_model, seed

SHARES = '/api/v1/artificial_songs/{}/shares'
TOO_MANY = {'message': 'Too many shares from this address, try again later.'}
NOW = 1_700_000_000  # an epoch second in the middle of a minute window


@pytest.fixture
def table(aws):
    return boto3.resource('dynamodb', region_name=REGION).Table(schema.table_name(TABLE_PREFIX, schema.RATELIMIT))


def request_with(headers=None, remote_addr='127.0.0.1'):
    builder = EnvironBuilder(path='/', headers=headers or {}, environ_base={'REMOTE_ADDR': remote_addr})
    return Request(builder.get_environ())


# Limits

@pytest.mark.parametrize('spec, expected', [
    ('10 per minute;100 per day', [(10, 60), (100, 86400)]),
    ('3 per minute', [(3, 60)]),
    ('5/second; 2 per hours', [(5, 1), (2, 3600)]),
])
def test_parse_limits(spec, expected):
    assert ratelimit.parse_limits(spec) == expected


def test_parse_limits_rejects_garbage():
    with pytest.raises(ValueError):
        ratelimit.parse_limits('lots per fortnight')


# Client IP

def test_client_ip_uses_left_most_forwarded_for():
    request = request_with({'X-Forwarded-For': '203.0.113.7, 10.0.0.1'})

    assert ratelimit.client_ip(request) == '203.0.113.7'


def test_client_ip_uses_the_lambda_request_context():
    context = {'http': {'method': 'POST', 'path': '/api/v1/x', 'sourceIp': '198.51.100.4'}}
    request = request_with({'X-Amzn-Request-Context': json.dumps(context)})

    assert ratelimit.client_ip(request) == '198.51.100.4'


def test_client_ip_prefers_request_context_over_forwarded_for():
    context = {'http': {'sourceIp': '198.51.100.4'}}
    request = request_with({'X-Forwarded-For': '203.0.113.7', 'X-Amzn-Request-Context': json.dumps(context)})

    # A client can put anything in X-Forwarded-For; the adapter always sets the request context itself
    assert ratelimit.client_ip(request) == '198.51.100.4'


@pytest.mark.parametrize('context', ['not json', '[]', '{"http": {}}'])
def test_client_ip_falls_back_to_remote_addr(context):
    request = request_with({'X-Amzn-Request-Context': context}, remote_addr='192.0.2.1')

    assert ratelimit.client_ip(request) == '192.0.2.1'


# Windows

def test_limit_per_window(table):
    limits = [(3, 60)]

    results = [ratelimit.is_rate_limited(table, '1.1.1.1', 'shares', limits, now=NOW) for _ in range(4)]

    assert results == [False, False, False, True]
    # another client, another route and the next window are counted apart
    assert ratelimit.is_rate_limited(table, '2.2.2.2', 'shares', limits, now=NOW) is False
    assert ratelimit.is_rate_limited(table, '1.1.1.1', 'other', limits, now=NOW) is False
    assert ratelimit.is_rate_limited(table, '1.1.1.1', 'shares', limits, now=NOW + 60) is False


def test_items_expire_through_ttl(table):
    ratelimit.is_rate_limited(table, '1.1.1.1', 'shares', [(3, 60)], now=NOW)

    [item] = table.scan()['Items']
    window = NOW // 60
    assert item['pk'] == f'1.1.1.1#shares#60#{window}'
    assert item['request_count'] == 1
    assert item['ttl'] == (window + 1) * 60 + ratelimit.TTL_MARGIN_SECONDS


def test_counter_stops_at_the_limit(table):
    for _ in range(5):
        ratelimit.is_rate_limited(table, '1.1.1.1', 'shares', [(2, 60)], now=NOW)

    assert table.scan()['Items'][0]['request_count'] == 2


def test_daily_limit(table):
    limits = [(10, 60), (3, 86400)]

    results = [ratelimit.is_rate_limited(table, '1.1.1.1', 'shares', limits, now=NOW + 60 * i) for i in range(4)]

    assert results == [False, False, False, True]


def test_no_ip_is_never_limited(table):
    assert ratelimit.is_rate_limited(table, None, 'shares', [(0, 60)], now=NOW) is False


def test_fails_open_when_the_table_is_missing(aws):
    missing = boto3.resource('dynamodb', region_name=REGION).Table('does-not-exist')

    assert ratelimit.is_rate_limited(missing, '1.1.1.1', 'shares', [(0, 60)], now=NOW) is False


# Shares endpoint

@pytest.fixture
def limited_client(aws, make_app):
    app = make_app(RATELIMIT_ENABLED=True, SHARE_RATE_LIMIT='3 per minute')
    seed(app)
    return app.test_client()


def post_share(client, headers=None):
    return client.post(SHARES.format(1), json={'network': 'facebook'}, headers=headers or {})


def test_shares_are_rate_limited_per_client(limited_client):
    statuses = [post_share(limited_client).status_code for _ in range(4)]

    assert statuses == [201, 201, 201, 429]
    response = post_share(limited_client)
    assert response.status_code == 429
    assert response.json == TOO_MANY


def test_rate_limit_key_comes_from_forwarded_for(limited_client):
    first = {'X-Forwarded-For': '203.0.113.7'}
    statuses = [post_share(limited_client, first).status_code for _ in range(4)]

    assert statuses == [201, 201, 201, 429]
    assert post_share(limited_client, {'X-Forwarded-For': '203.0.113.8'}).status_code == 201


def test_rate_limit_key_comes_from_the_lambda_request_context(limited_client):
    def context(ip):
        return {'X-Amzn-Request-Context': json.dumps({'http': {'sourceIp': ip}})}

    statuses = [post_share(limited_client, context('198.51.100.4')).status_code for _ in range(4)]

    assert statuses == [201, 201, 201, 429]
    assert post_share(limited_client, context('198.51.100.5')).status_code == 201


def test_rejected_shares_are_not_counted(aws, make_app):
    from baking.main.repository import EXTENSION_KEY

    app = make_app(RATELIMIT_ENABLED=True, SHARE_RATE_LIMIT='1 per minute')
    repository = seed(app)
    client = app.test_client()

    assert post_share(client).status_code == 201
    assert post_share(client).status_code == 429
    assert app.extensions[EXTENSION_KEY] is repository
    assert repository.get_stats()['shares'] == 1


def test_rate_limit_is_off_in_testing(client):
    assert all(post_share(client).status_code == 201 for _ in range(12))


def test_default_limits():
    import config.default

    assert config.default.RATELIMIT_ENABLED is True
    assert ratelimit.parse_limits(config.default.SHARE_RATE_LIMIT) == [(10, 60), (100, 86400)]
    assert ratelimit.parse_limits(config.default.GENERATION_RATE_LIMIT) == [(5, 60), (50, 86400)]


def test_generation_limit_comes_from_the_environment(config_env):
    config_env(GENERATION_RATE_LIMIT='2 per minute')
    import config.default

    assert config.default.GENERATION_RATE_LIMIT == '2 per minute'


# Generation endpoints

SEED_SONG = '/api/v1/artificial_songs/generate/en/seed/hello/words/20/artist/1/'
NO_SEED_SONG = '/api/v1/artificial_songs/generate/en/words/20/artist/1/'
TITLE = '/api/v1/artificial_titles/generate/en/song/1/'
TOO_MANY_GENERATIONS = {'message': 'Too many generations from this address, try again later.'}


@pytest.fixture
def generation_app(aws, make_app):
    app = make_app(RATELIMIT_ENABLED=True, GENERATION_RATE_LIMIT='3 per minute')
    seed(app)
    install_fake_model(app)
    return app


@pytest.mark.parametrize('url', [SEED_SONG, NO_SEED_SONG, TITLE])
def test_generation_is_rate_limited_per_client(generation_app, url):
    client = generation_app.test_client()
    statuses = [client.get(url).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]
    response = client.get(url)
    assert response.status_code == 429
    assert response.json == TOO_MANY_GENERATIONS
    assert client.get(url, headers={'X-Forwarded-For': '203.0.113.9'}).status_code == 200


def test_generation_routes_share_one_budget(generation_app):
    from baking.main.repository import EXTENSION_KEY

    client = generation_app.test_client()

    assert [client.get(url).status_code for url in (SEED_SONG, NO_SEED_SONG, TITLE, SEED_SONG, TITLE)] == [
        200, 200, 200, 429, 429]
    assert generation_app.extensions[EXTENSION_KEY].get_stats()['songs_generated'] == 8  # 6 seeded + 2


def test_invalid_generation_requests_are_not_counted(generation_app):
    client = generation_app.test_client()

    for _ in range(5):
        assert client.get('/api/v1/artificial_songs/generate/en/words/20/artist/999/').status_code == 400
        assert client.get('/api/v1/artificial_titles/generate/en/song/999/').status_code == 404

    assert client.get(SEED_SONG).status_code == 200


def test_generation_and_shares_have_separate_budgets(aws, make_app):
    app = make_app(RATELIMIT_ENABLED=True, GENERATION_RATE_LIMIT='1 per minute', SHARE_RATE_LIMIT='1 per minute')
    seed(app)
    install_fake_model(app)
    client = app.test_client()

    assert client.get(SEED_SONG).status_code == 200
    assert post_share(client).status_code == 201
    assert client.get(SEED_SONG).status_code == 429
    assert post_share(client).status_code == 429


def test_generation_rate_limit_is_off_in_testing(client, app):
    install_fake_model(app)

    assert all(client.get(SEED_SONG).status_code == 200 for _ in range(7))
