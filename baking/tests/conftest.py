"""
Shared pytest fixtures.

Every test gets its own mocked AWS (moto) with freshly created DynamoDB tables and its own Flask app,
seeded from ``baking/resources/lyrics_4_tests.csv`` (6 songs, 1 artist, 1 genre, 6 artificial songs/titles).
Nothing is shared between tests, so they are order independent, and no request reaches real AWS.
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
TEST_DATA = 'baking/resources/lyrics_4_tests.csv'


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
    config/default.py reads SECRET_KEY, AWS_REGION, BAKING_TABLE_PREFIX... from the environment at import
    time and is cached in sys.modules, so monkeypatching the environment alone has no effect on create_app.

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
    Returns ``make_app(config_file='config/testing.py', **overrides)`` building an app on the test tables
    (TABLE_PREFIX in REGION) whose log directory lives under tmp_path. ``overrides`` go into create_app's
    test_config. Building an app makes no AWS call; use the `aws` fixture before sending requests.
    """
    from baking.main import create_app

    def _make_app(config_file=TESTING_CONFIG, **overrides):
        test_config = {
            'BAKING_TABLE_PREFIX': TABLE_PREFIX,
            'AWS_REGION': REGION,
            'DYNAMODB_ENDPOINT_URL': None,
            'LOG_DIR': str(tmp_path / 'logs'),
            'LOG_LEVEL': 3,  # WARNING: keeps the per-request INFO lines out of the test output
        }
        test_config.update(overrides)
        return create_app(config_file, test_config=test_config)

    return _make_app


def seed(app, cover_artists=0):
    """
    Loads the test CSV into the app's tables plus 6 "Dummy" generated songs. The seeded artist is not a
    cover artist unless `cover_artists` says so.
    """
    from baking.main.repository import EXTENSION_KEY
    from baking.refresh_database import create_artificial, read_song_data, refresh

    repository = app.extensions[EXTENSION_KEY]
    song_data = read_song_data(TEST_DATA)
    refresh(repository, song_data, cover_artists=cover_artists)
    create_artificial(repository, song_data)
    return repository


@pytest.fixture
def app(aws, make_app):
    """A testing app on freshly created and seeded tables."""
    app = make_app()
    seed(app)
    return app


@pytest.fixture
def app_repo(app):
    """The repository of the `app` fixture."""
    from baking.main.repository import EXTENSION_KEY

    return app.extensions[EXTENSION_KEY]


@pytest.fixture
def client(app):
    return app.test_client()


def add_artists(repository, count, cover=False, formation_date=None, genre_id=1, names=None):
    """Adds `count` artists to the catalog and returns their ids."""
    ids = []
    artists = []
    for i in range(count):
        artist_id = repository.next_id('artist')
        name, clean_name = names[i] if names else (f'artist-{artist_id}', f'Artist {artist_id}')
        artists.append({'id': artist_id, 'name': name, 'clean_name': clean_name, 'country': 'US', 'cover': cover,
                        'formation_date': formation_date, 'genre_id': genre_id})
        ids.append(artist_id)
    repository.save_catalog(artists=artists)
    return ids


class FakeGenerator:
    """
    Stands in for ml.generate.LyricsGenerator (no onnxruntime needed): records the calls and returns fixed
    lyrics and titles. Only the artists in `known` have a style; others use the generic one (artist None).
    """

    def __init__(self, lyrics='brand new lyrics', title='Brand New Title', known=('beyonce-knowles',)):
        self.lyrics = lyrics
        self.title = title
        self.known = set(known)
        self.calls = []

    def generate(self, artist=None, seed_text='', number_words=150, *, seed=None, **kwargs):
        from ml.generate import Generation

        self.calls.append(('generate', artist, seed_text, number_words, seed))
        lyrics = (seed_text + ' ' + self.lyrics).strip()
        return Generation(lyrics=lyrics, title=self.title, artist=artist if artist in self.known else None,
                          words=number_words, seed=seed)

    def generate_title(self, lyrics, artist=None, *, seed=None, **kwargs):
        self.calls.append(('generate_title', artist, lyrics))
        return self.title


def install_fake_model(app, generator=None, version='9.9.9'):
    """Replaces the app's model service by one whose model is already loaded with `generator`."""
    from pathlib import Path

    from baking.main.v1.models.generator import EXTENSION_KEY, LoadedModel, ModelService, ModelSettings

    generator = generator or FakeGenerator()
    service = ModelService(ModelSettings(local_dir='fake-bundle'))
    service._model = LoadedModel(generator=generator, version=version, label=f'lyrics-lstm/{version}',
                                 path=Path('fake-bundle'), load_seconds=0.0)
    app.extensions[EXTENSION_KEY] = service
    return generator
