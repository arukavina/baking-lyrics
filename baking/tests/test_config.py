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


def test_testing_config_defaults_to_in_memory_sqlite(tmp_path, config_env):
    from baking.main import create_app

    config_env(TEST_DATABASE_URL=None)
    app = create_app('config/testing.py', test_config={'LOG_DIR': str(tmp_path)})

    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'


def test_app_is_development(tmp_path, config_env):
    from baking.main import create_app, db

    config_env(DATABASE_URL=None, SECRET_KEY=None)
    # No database override: the development app must point at the default SQLite file.
    app = create_app('config/development.py', test_config={'LOG_DIR': str(tmp_path), 'LOG_LEVEL': 4})

    try:
        assert app.config['DEBUG'] is True
        assert app.config['TESTING'] is False
        assert app.config['ENV'] == 'development'
        # Development falls back to a dev-only key when SECRET_KEY is not set.
        assert app.config['SECRET_KEY']
        assert app.config['SECRET_KEY'] != 'my_precious'
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        assert uri.startswith('sqlite:///')
        assert uri.endswith('flask_bakinglyrics_main.db')
        # Without TensorFlow / model files the app still boots; generation endpoints answer 503.
        assert app.extensions['ml_available'] is False
    finally:
        with app.app_context():
            db.engine.dispose()


def test_database_url_heroku_scheme_is_rewritten(config_env):
    config_env(DATABASE_URL='postgres://user:pw@host:5432/db')
    import config.default

    assert config.default.SQLALCHEMY_DATABASE_URI == 'postgresql://user:pw@host:5432/db'


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
