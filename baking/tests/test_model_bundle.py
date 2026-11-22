"""
Model bundle resolution, download, verification, caching and loading (baking/main/v1/models/generator.py).

No torch or onnxruntime needed: bundles hold placeholder bytes and the loader is a stub returning a fake
generator. S3 is moto. Real ONNX bundles are covered by test_model_bundle_onnx.py.
"""

# Generic
import hashlib
import json
import subprocess
import sys
import threading

# Libs
import boto3
import pytest

# Own
from baking.main.v1.models import generator
from baking.main.v1.models.generator import ModelService, ModelSettings, ModelUnavailable, verify_bundle
from baking.tests.conftest import REGION, FakeGenerator

BUCKET = 'bakinglyrics-test'
PREFIX = 'models/lyrics-lstm'
SEED_SONG = '/api/v1/artificial_songs/generate/en/seed/hello/words/20/artist/1/'
TITLE = '/api/v1/artificial_titles/generate/en/song/1/'


def bundle_files(version, model_bytes=b'onnx-weights'):
    """The files of a fake bundle (placeholder model bytes), config.json listing the sha256 of the others."""
    files = {
        'model.onnx': model_bytes,
        'vocab.json': b'{"itos": []}',
        'artists.json': b'{"artists": {}}',
        'samples.md': b'# Samples\n',
    }
    config = {'format_version': 1, 'name': 'lyrics-lstm', 'version': version,
              'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                        for name, data in files.items()}}
    return {**files, 'config.json': json.dumps(config).encode()}, config


def write_bundle(path, version='1.0.0', **kwargs):
    files, _ = bundle_files(version, **kwargs)
    path.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (path / name).write_bytes(data)
    return path


class StubLoader:
    """Counts loads and returns a FakeGenerator; `error` makes every load fail."""

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, path, threads):
        self.calls.append((path, threads))
        if self.error is not None:
            raise self.error
        return FakeGenerator()


@pytest.fixture
def s3(aws):
    client = boto3.client('s3', region_name=REGION)
    client.create_bucket(Bucket=BUCKET)
    return client


def publish(client, version, latest=True, **kwargs):
    files, config = bundle_files(version, **kwargs)
    for name, data in files.items():
        client.put_object(Bucket=BUCKET, Key=f'{PREFIX}/{version}/{name}', Body=data)
    if latest:
        client.put_object(Bucket=BUCKET, Key=f'{PREFIX}/latest.json', Body=json.dumps(
            {'name': 'lyrics-lstm', 'version': version, 'prefix': f'{PREFIX}/{version}/', 'format_version': 1,
             'files': config['files']}).encode())
    return config


def s3_service(tmp_path, client, loader=None, **settings):
    values = {'bucket': BUCKET, 'prefix': PREFIX, 'cache_dir': str(tmp_path / 'cache'), 'region': REGION}
    values.update(settings)
    return ModelService(ModelSettings(**values), s3_client=client, loader=loader or StubLoader())


class CountingClient:
    """Wraps a boto3 S3 client and records the downloaded keys."""

    def __init__(self, client):
        self.client = client
        self.downloads = []

    def get_object(self, **kwargs):
        return self.client.get_object(**kwargs)

    def download_file(self, bucket, key, filename):
        self.downloads.append(key.rsplit('/', 1)[-1])
        return self.client.download_file(bucket, key, filename)


# Settings

def test_settings_from_config():
    settings = ModelSettings.from_config({'MODEL_BUCKET': 'b', 'MODEL_PREFIX': '/models/x/', 'MODEL_VERSION': '',
                                          'MODEL_PRELOAD': 'True', 'MODEL_THREADS': '2', 'AWS_REGION': 'eu-west-1'})

    assert (settings.bucket, settings.prefix, settings.version, settings.local_dir) == ('b', 'models/x', None, None)
    assert (settings.preload, settings.threads, settings.region, settings.enabled) == (True, 2, 'eu-west-1', True)
    assert ModelSettings.from_config({'MODEL_PRELOAD': 'false'}).preload is False
    assert ModelSettings.from_config({}).enabled is False


def test_disabled_service_never_loads():
    loader = StubLoader()
    service = ModelService(ModelSettings(), loader=loader)

    with pytest.raises(ModelUnavailable):
        service.get()
    assert service.status() == 'disabled'
    assert service.preload() is None
    assert loader.calls == []


# Local bundles (MODEL_DIR)

def test_verify_bundle(tmp_path):
    bundle = write_bundle(tmp_path / 'b')

    assert verify_bundle(bundle)['version'] == '1.0.0'

    (bundle / 'model.onnx').write_bytes(b'tampered')
    with pytest.raises(ModelUnavailable, match='sha256'):
        verify_bundle(bundle)

    (bundle / 'vocab.json').unlink()
    with pytest.raises(ModelUnavailable, match='missing vocab.json'):
        verify_bundle(bundle)


def test_local_bundle_loads_once(tmp_path):
    loader = StubLoader()
    service = ModelService(ModelSettings(local_dir=str(write_bundle(tmp_path / 'b', '2.1.0')), threads=2),
                           loader=loader)

    model = service.get()

    assert (model.version, model.label, service.status()) == ('2.1.0', 'lyrics-lstm/2.1.0', 'ready')
    assert service.get() is model
    assert loader.calls == [(tmp_path / 'b', 2)]


def test_concurrent_first_requests_load_once(tmp_path):
    loader = StubLoader()
    service = ModelService(ModelSettings(local_dir=str(write_bundle(tmp_path / 'b'))), loader=loader)
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.get())) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(loader.calls) == 1
    assert len({id(model) for model in results}) == 1


def test_generations_are_serialised(tmp_path):
    """The generator is not thread safe: the service never runs two generations at once."""
    active, peak = [0], [0]
    lock = threading.Lock()

    class SlowGenerator(FakeGenerator):
        def generate(self, *args, **kwargs):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            threading.Event().wait(0.02)
            with lock:
                active[0] -= 1
            return super().generate(*args, **kwargs)

    service = ModelService(ModelSettings(local_dir=str(write_bundle(tmp_path / 'b'))),
                           loader=lambda path, threads: SlowGenerator())
    threads = [threading.Thread(target=service.generate, args=('x', '', 5)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak[0] == 1


def test_failed_load_is_remembered_then_retried(tmp_path):
    bundle = write_bundle(tmp_path / 'b')
    (bundle / 'model.onnx').write_bytes(b'tampered')
    loader = StubLoader()
    service = ModelService(ModelSettings(local_dir=str(bundle), retry_seconds=3600), loader=loader)

    for _ in range(2):
        with pytest.raises(ModelUnavailable, match='sha256'):
            service.get()
    assert service.status() == 'failed'

    # repaired bundle, but the retry interval has not elapsed
    write_bundle(bundle)
    with pytest.raises(ModelUnavailable):
        service.get()

    service.settings = ModelSettings(local_dir=str(bundle), retry_seconds=0)
    assert service.get().version == '1.0.0'
    assert len(loader.calls) == 1


def test_missing_runtime_is_not_retried(tmp_path):
    loader = StubLoader(error=ImportError('No module named onnxruntime'))
    service = ModelService(ModelSettings(local_dir=str(write_bundle(tmp_path / 'b')), retry_seconds=0),
                           loader=loader)

    for _ in range(3):
        with pytest.raises(ModelUnavailable, match='onnxruntime'):
            service.get()
    assert len(loader.calls) == 1


def test_preload_loads_in_the_background(tmp_path):
    loader = StubLoader()
    service = ModelService(ModelSettings(local_dir=str(write_bundle(tmp_path / 'b')), preload=True), loader=loader)

    service.preload().join(5)

    assert service.status() == 'ready'
    assert len(loader.calls) == 1


# S3 bundles

def test_s3_latest_is_downloaded_and_verified(tmp_path, s3):
    publish(s3, '2026.11.0')
    client = CountingClient(s3)
    loader = StubLoader()
    service = s3_service(tmp_path, client, loader)

    model = service.get()

    assert model.label == 'lyrics-lstm/2026.11.0'
    assert model.path == tmp_path / 'cache' / '2026.11.0'
    assert sorted(client.downloads) == ['artists.json', 'config.json', 'model.onnx', 'samples.md', 'vocab.json']
    assert verify_bundle(model.path)['version'] == '2026.11.0'
    assert not list(model.path.glob('*.part'))
    assert loader.calls == [(model.path, service._threads())]


def test_s3_pinned_version_wins_over_latest(tmp_path, s3):
    publish(s3, '1.0.0', latest=False)
    publish(s3, '2.0.0')

    model = s3_service(tmp_path, s3, version='1.0.0').get()

    assert model.version == '1.0.0'


def test_s3_cache_is_reused_by_the_next_process(tmp_path, s3):
    publish(s3, '1.0.0')
    s3_service(tmp_path, s3).get()
    # the objects are gone, only latest.json remains: the verified local copy is used
    for name in ('model.onnx', 'vocab.json', 'artists.json', 'config.json', 'samples.md'):
        s3.delete_object(Bucket=BUCKET, Key=f'{PREFIX}/1.0.0/{name}')
    client = CountingClient(s3)

    assert s3_service(tmp_path, client).get().version == '1.0.0'
    assert client.downloads == []


def test_s3_corrupt_cached_file_is_downloaded_again(tmp_path, s3):
    publish(s3, '1.0.0')
    path = s3_service(tmp_path, s3).get().path
    (path / 'model.onnx').write_bytes(b'truncated')
    client = CountingClient(s3)

    s3_service(tmp_path, client).get()

    assert client.downloads == ['config.json', 'model.onnx']
    assert verify_bundle(path)['version'] == '1.0.0'


def test_s3_object_not_matching_its_sha256_is_rejected(tmp_path, s3):
    publish(s3, '1.0.0')
    s3.put_object(Bucket=BUCKET, Key=f'{PREFIX}/1.0.0/model.onnx', Body=b'replaced')
    service = s3_service(tmp_path, s3)

    with pytest.raises(ModelUnavailable, match='model.onnx does not match its sha256'):
        service.get()
    assert service.status() == 'failed'


def test_s3_config_of_another_version_is_rejected(tmp_path, s3):
    files, _ = bundle_files('9.9.9')
    publish(s3, '1.0.0')
    s3.put_object(Bucket=BUCKET, Key=f'{PREFIX}/1.0.0/config.json', Body=files['config.json'])

    with pytest.raises(ModelUnavailable, match='version'):
        s3_service(tmp_path, s3).get()


@pytest.mark.parametrize('setup', ['no latest', 'no bucket'])
def test_s3_missing_objects_leave_the_model_unavailable(tmp_path, s3, setup):
    bucket = 'missing-bucket' if setup == 'no bucket' else BUCKET
    service = s3_service(tmp_path, s3, bucket=bucket)

    with pytest.raises(ModelUnavailable):
        service.get()
    assert service.status() == 'failed'


# Endpoints with a model that cannot be loaded, or loaded from S3

def test_endpoints_answer_503_when_the_bundle_is_broken(tmp_path, aws, make_app):
    from baking.tests.conftest import seed

    bundle = write_bundle(tmp_path / 'b')
    (bundle / 'model.onnx').write_bytes(b'tampered')
    app = make_app(MODEL_DIR=str(bundle))
    repository = seed(app)
    client = app.test_client()

    for url in (SEED_SONG, TITLE):
        response = client.get(url)
        assert response.status_code == 503
        assert response.json == {'message': 'ML models are not loaded'}
    assert len(repository.list_generated_songs()) == 6
    assert len(repository.list_titles()) == 6
    # the app itself is fine
    assert client.get('/api/v1/general/ping').status_code == 200


def test_endpoints_generate_with_the_model_from_s3(tmp_path, s3, make_app, monkeypatch):
    from baking.tests.conftest import seed

    publish(s3, '2026.11.0')
    fake = FakeGenerator()
    monkeypatch.setattr(generator, '_default_loader', lambda path, threads: fake)
    app = make_app(MODEL_BUCKET=BUCKET, MODEL_PREFIX=PREFIX, MODEL_CACHE_DIR=str(tmp_path / 'cache'))
    seed(app)
    client = app.test_client()

    assert generator.get_service(app).status() == 'not loaded'  # nothing happens before the first request
    song = client.get(SEED_SONG)
    title = client.get(TITLE)

    assert song.status_code == 200
    assert song.json['model'] == 'lyrics-lstm/2026.11.0'
    assert song.json['lyrics'] == 'hello brand new lyrics'
    assert title.status_code == 200
    assert [call[0] for call in fake.calls] == ['generate', 'generate_title']


def test_preload_on_app_creation(tmp_path, aws, make_app, monkeypatch):
    loader = StubLoader()
    monkeypatch.setattr(generator, '_default_loader', loader)
    app = make_app(MODEL_DIR=str(write_bundle(tmp_path / 'b')), MODEL_PRELOAD='true')
    service = generator.get_service(app)

    service.get()  # waits for the background load (same lock)

    assert service.status() == 'ready'
    assert len(loader.calls) == 1


def test_serving_never_imports_torch():
    """The Lambda image has no torch: the app and the serving path must not import it."""
    code = (
        'import sys\n'
        'from baking.main import create_app\n'
        'import baking.main.v1.models.generator\n'
        'import ml.generate, ml.tokenizer\n'
        'create_app("config/testing.py", test_config={"LOG_DIR": None})\n'
        'assert "torch" not in sys.modules, "torch was imported"\n'
    )
    from baking.main import REPO_ROOT

    result = subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT, capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr
