"""
Shared pytest fixtures.

Every test gets its own Flask app backed by a fresh SQLite file under ``tmp_path``, seeded from
``baking/resources/lyrics_4_tests.csv`` (6 songs, 1 artist, 1 genre, 6 artificial songs/titles).
Nothing is shared between tests, so they are order independent.
"""

# Generic
import importlib

# Libs
import boto3
import pytest
from moto import mock_aws

TESTING_CONFIG = 'config/testing.py'
TABLE_PREFIX = 'baking-lyrics-test'
REGION = 'us-east-1'


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """
    Keeps tests independent from the developer machine: a local `.env` file must not leak values
    into os.environ, and APP_CONFIG_FILE must never be needed.
    """
    import baking.main

    monkeypatch.setattr(baking.main, 'load_dotenv', lambda *args, **kwargs: False)
    monkeypatch.delenv('APP_CONFIG_FILE', raising=False)


@pytest.fixture
def aws(monkeypatch):
    """
    Mocked AWS (moto) with fake credentials and every table of the schema created under TABLE_PREFIX.
    No request ever leaves the process.
    """
    from baking.main.repository import schema

    for name, value in {'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing',
                        'AWS_SECURITY_TOKEN': 'testing', 'AWS_SESSION_TOKEN': 'testing',
                        'AWS_DEFAULT_REGION': REGION, 'AWS_REGION': REGION}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv('AWS_PROFILE', raising=False)
    monkeypatch.delenv('DYNAMODB_ENDPOINT_URL', raising=False)

    with mock_aws():
        schema.create_tables(boto3.client('dynamodb', region_name=REGION), prefix=TABLE_PREFIX)
        yield


@pytest.fixture
def repo(aws):
    """An empty DynamoDB repository on the mocked tables, without artist cache."""
    from baking.main.repository import DynamoRepository

    return DynamoRepository(prefix=TABLE_PREFIX, region=REGION, cache_seconds=0)


@pytest.fixture
def config_env(monkeypatch):
    """
    config/default.py reads SECRET_KEY and DATABASE_URL from the environment at import time and is
    cached in sys.modules, so monkeypatching the environment alone has no effect on create_app.

    Returns ``set_env(**variables)``: sets (or, for None, removes) the variables and reloads
    config.default. On teardown the environment is restored first and config.default is reloaded
    again, so no value leaks into other tests.
    """
    import config.default

    def set_env(**variables):
        for name, value in variables.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        importlib.reload(config.default)

    yield set_env

    monkeypatch.undo()
    importlib.reload(config.default)


@pytest.fixture
def make_app(tmp_path):
    """
    Returns ``make_app(config_file='config/testing.py', **overrides)`` building an app whose SQLite
    file and log directory live under tmp_path. ``overrides`` go into create_app's test_config.
    Engines of every app built here are disposed on teardown.
    """
    from baking.main import create_app, db

    built = []

    def _make_app(config_file=TESTING_CONFIG, **overrides):
        test_config = {
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "test.db").as_posix()}',
            'LOG_DIR': str(tmp_path / 'logs'),
            'LOG_LEVEL': 3,  # WARNING: keeps the per-request INFO lines out of the test output
        }
        test_config.update(overrides)
        new_app = create_app(config_file, test_config=test_config)
        built.append(new_app)
        return new_app

    yield _make_app

    for built_app in built:
        with built_app.app_context():
            db.session.remove()
            db.engine.dispose()  # release the SQLite file so tmp_path can be removed on Windows


@pytest.fixture
def app(make_app):
    """A testing app with a freshly created and seeded database."""
    from baking.main import db
    from baking.refresh_database import create_artificial, load_song_data, refresh

    app = make_app()

    with app.app_context():
        db.create_all()
        song_data = load_song_data(app)
        refresh(app, song_data)
        create_artificial(song_data)

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app_ctx(app):
    """An application context for tests that query the database directly."""
    with app.app_context():
        yield app
