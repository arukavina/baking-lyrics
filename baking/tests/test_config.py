"""
Configuration tests: each config file must produce the expected flags when passed to create_app.
"""

# Libs
import pytest

PROD_SECRET = 'a-real-production-secret'


def test_app_is_testing(make_app):
    app = make_app('config/testing.py')

    assert app is not None
    assert app.config['TESTING'] is True
    assert app.config['DEBUG'] is False
    assert app.config['ENV'] == 'testing'
    assert app.config['SECRET_KEY']
    assert app.config['SECRET_KEY'] != 'my_precious'
    assert app.extensions['ml_available'] is False


def test_testing_config_uses_its_own_table_prefix(tmp_path, config_env):
    from baking.main import create_app

    config_env(BAKING_TABLE_PREFIX='baking-lyrics')
    app = create_app('config/testing.py', test_config={'LOG_DIR': str(tmp_path)})

    assert app.config['BAKING_TABLE_PREFIX'] == 'baking-lyrics-test'


def test_app_is_development(tmp_path, config_env):
    from baking.main import create_app
    from baking.main.repository import EXTENSION_KEY, DynamoRepository

    config_env(SECRET_KEY=None, BAKING_TABLE_PREFIX=None, AWS_REGION=None, AWS_DEFAULT_REGION=None,
               DYNAMODB_ENDPOINT_URL=None)
    app = create_app('config/development.py', test_config={'LOG_DIR': str(tmp_path), 'LOG_LEVEL': 4})

    assert app.config['DEBUG'] is True
    assert app.config['TESTING'] is False
    assert app.config['ENV'] == 'development'
    # Development falls back to a dev-only key when SECRET_KEY is not set.
    assert app.config['SECRET_KEY']
    assert app.config['SECRET_KEY'] != 'my_precious'
    # Default tables: baking-lyrics-* in us-east-1, on AWS (no endpoint override)
    repository = app.extensions[EXTENSION_KEY]
    assert isinstance(repository, DynamoRepository)
    assert (repository.prefix, repository.region, repository.endpoint_url) == ('baking-lyrics', 'us-east-1', None)
    # Without TensorFlow / model files the app still boots; generation endpoints answer 503.
    assert app.extensions['ml_available'] is False


def test_dynamodb_settings_come_from_the_environment(tmp_path, config_env):
    from baking.main import create_app
    from baking.main.repository import EXTENSION_KEY

    config_env(BAKING_TABLE_PREFIX='baking-lyrics-dev', AWS_REGION='eu-west-1',
               DYNAMODB_ENDPOINT_URL='http://localhost:5000')
    app = create_app('config/development.py', test_config={'LOG_DIR': str(tmp_path), 'LOG_LEVEL': 4})

    repository = app.extensions[EXTENSION_KEY]
    assert (repository.prefix, repository.region, repository.endpoint_url) == (
        'baking-lyrics-dev', 'eu-west-1', 'http://localhost:5000')


@pytest.mark.parametrize('variables, expected', [
    ({'AWS_REGION': 'eu-west-1', 'AWS_DEFAULT_REGION': 'us-west-2'}, 'eu-west-1'),
    ({'AWS_REGION': None, 'AWS_DEFAULT_REGION': 'us-west-2'}, 'us-west-2'),
    ({'AWS_REGION': None, 'AWS_DEFAULT_REGION': None}, 'us-east-1'),
])
def test_aws_region_comes_from_the_environment(config_env, variables, expected):
    config_env(**variables)
    import config.default

    assert config.default.AWS_REGION == expected


@pytest.mark.parametrize('config_file', ['config/development.py', 'config/production.py', 'config/testing.py'])
def test_config_files_do_not_hard_code_the_region(config_file):
    from baking.main import REPO_ROOT

    assert 'AWS_REGION' not in (REPO_ROOT / config_file).read_text(encoding='utf-8')


def test_app_is_production(make_app, config_env):
    config_env(SECRET_KEY=PROD_SECRET)
    app = make_app('config/production.py')

    assert app.config['DEBUG'] is False
    assert app.config['TESTING'] is False
    assert app.config['ENV'] == 'production'
    assert app.config['SECRET_KEY'] == PROD_SECRET
    assert app.extensions['ml_available'] is False


def test_production_without_secret_key_raises(make_app, config_env):
    config_env(SECRET_KEY=None)

    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        make_app('config/production.py')


def test_create_app_requires_a_config_file(config_env):
    """Without an explicit file and without APP_CONFIG_FILE (removed by the autouse fixture) it fails."""
    from baking.main import create_app

    with pytest.raises(OSError, match='APP_CONFIG_FILE'):
        create_app()


def test_test_config_overrides_config_file(make_app):
    app = make_app('config/testing.py', SERVER_NAME_LOG='overridden')

    assert app.config['SERVER_NAME_LOG'] == 'overridden'
