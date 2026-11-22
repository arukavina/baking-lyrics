"""
Serving of the lyrics model bundle (see ml/BUNDLE.md) for the generation endpoints.

Where the bundle comes from:
- MODEL_DIR: a local bundle directory (development and tests); S3 is not used.
- otherwise s3://MODEL_BUCKET/MODEL_PREFIX/<version>/, where <version> is MODEL_VERSION when set, else the
  version named by MODEL_PREFIX/latest.json. Files are downloaded once into MODEL_CACHE_DIR/<version>/
  (/tmp/models on Lambda, the only writable path) and verified against the sha256 values of config.json.
  A later cold start in the same execution environment reuses the verified files.
- no MODEL_DIR and no MODEL_BUCKET: generation is disabled (503).

Loading is lazy: the first generation request downloads and loads the model, so the cold start and the Lambda
Web Adapter readiness check (/api/v1/general/ping) stay fast. MODEL_PRELOAD=true starts the same load in a
background thread when the app is created. A failed load never crashes the app: the endpoints answer 503, the
failure is logged once, and the load is retried at most every MODEL_RETRY_SECONDS.

Thread safety: `ml.generate.LyricsGenerator` reuses its input buffers and is not thread safe, while gunicorn runs
a few threads. The process keeps a single generator (one ONNX session, about the model size in memory) and
serialises generations with a lock. On Lambda an execution environment receives one request at a time, so the
lock never waits there; locally concurrent requests simply queue for the 1 to 3 seconds a song takes.

Bundle file names come from config.json, so they are checked before anything is downloaded or read: a name must
be a plain file name (no `/`, `\\`, `..` or absolute path), which keeps every file inside the bundle directory.

boto3: the S3 client is built from its own boto3.session.Session, never from boto3's shared default session,
whose lazy creation is not thread safe (MODEL_PRELOAD loads in a thread while a request may be building the
DynamoDB resource).

Nothing here imports torch: only `ml.generate` and `ml.tokenizer` (numpy, onnxruntime) are loaded, lazily.
"""

# Generic
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger('baking-api')

EXTENSION_KEY = 'lyrics_model'
REQUIRED_FILES = ('model.onnx', 'vocab.json', 'artists.json', 'config.json')
DEFAULT_NAME = 'lyrics-lstm'

# onnxruntime intra op threads when MODEL_THREADS is not set. Lambda at 2048 MB gets about 1.16 vCPU of CPU time
# while os.cpu_count() reports 2, so a second thread mostly competes with the first (and with gunicorn) for the
# same share; batch 1 LSTM steps are too small to gain from it.
DEFAULT_THREADS = 1


class ModelUnavailable(Exception):
    """The model bundle could not be resolved, downloaded, verified or loaded."""


@dataclass(frozen=True)
class ModelSettings:
    bucket: str | None = None
    prefix: str = 'models/lyrics-lstm'
    version: str | None = None
    local_dir: str | None = None
    cache_dir: str | None = None
    region: str | None = None
    threads: int | None = None
    preload: bool = False
    retry_seconds: float = 300.0

    @classmethod
    def from_config(cls, config):
        def _int(value):
            return int(value) if value not in (None, '') else None

        return cls(bucket=config.get('MODEL_BUCKET') or None,
                   prefix=(config.get('MODEL_PREFIX') or 'models/lyrics-lstm').strip('/'),
                   version=config.get('MODEL_VERSION') or None,
                   local_dir=config.get('MODEL_DIR') or None,
                   cache_dir=config.get('MODEL_CACHE_DIR') or None,
                   region=config.get('AWS_REGION') or None,
                   threads=_int(config.get('MODEL_THREADS')),
                   preload=_truthy(config.get('MODEL_PRELOAD')),
                   retry_seconds=float(config.get('MODEL_RETRY_SECONDS', 300)))

    @property
    def enabled(self):
        return bool(self.local_dir or self.bucket)

    @property
    def cache_root(self):
        if self.cache_dir:
            return Path(self.cache_dir)
        # /tmp is the only writable path on Lambda; elsewhere use the platform temp dir
        return Path('/tmp/models') if os.name == 'posix' else Path(tempfile.gettempdir()) / 'baking-models'


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def is_safe_file_name(name):
    """True for a plain file name that stays inside the bundle directory (no separators, `..` or drive)."""
    return (isinstance(name, str) and name not in ('', '.', '..') and '/' not in name and '\\' not in name
            and '..' not in name and ':' not in name and not Path(name).is_absolute())


def bundle_file_names(config):
    """
    The file names listed in config.json `files`. Raises ModelUnavailable when one could escape the bundle
    directory (path traversal), before any of them is downloaded or read.
    """
    files = config.get('files', {})
    if not isinstance(files, dict):
        raise ModelUnavailable('config.json `files` must be an object')
    unsafe = [name for name in files if not is_safe_file_name(name)]
    if unsafe:
        raise ModelUnavailable(f'config.json lists unsafe file names: {", ".join(map(repr, unsafe))}')
    return list(files)


def verify_bundle(bundle_dir):
    """
    Checks the file names, the required files and the sha256 of every file listed in config.json `files`.
    Returns the parsed config.json. Raises ModelUnavailable on any problem.
    """
    bundle_dir = Path(bundle_dir)
    missing = [name for name in REQUIRED_FILES if not (bundle_dir / name).is_file()]
    if missing:
        raise ModelUnavailable(f'{bundle_dir}: missing {", ".join(missing)}')
    config = json.loads((bundle_dir / 'config.json').read_text(encoding='utf-8'))
    bundle_file_names(config)
    for name, info in config.get('files', {}).items():
        path = bundle_dir / name
        if not path.is_file():
            raise ModelUnavailable(f'{bundle_dir}: {name} is listed in config.json but missing')
        if sha256_of(path) != info.get('sha256'):
            raise ModelUnavailable(f'{bundle_dir}: {name} does not match its sha256 in config.json')
    return config


@dataclass
class LoadedModel:
    generator: object  # ml.generate.LyricsGenerator (or a test double with the same methods)
    version: str
    label: str  # stored as the `model` of generated songs, e.g. lyrics-lstm/2026.11.0
    path: Path
    load_seconds: float


class S3BundleSource:
    """Resolves the bundle version on S3 and downloads it into the local cache, verifying every file."""

    def __init__(self, settings, client=None):
        self.settings = settings
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3.session

            # A dedicated session: the default one is shared with the request threads and not thread safe
            self._client = boto3.session.Session().client('s3', region_name=self.settings.region)
        return self._client

    def _key(self, *parts):
        return '/'.join([self.settings.prefix, *parts]) if self.settings.prefix else '/'.join(parts)

    def resolve_version(self):
        """MODEL_VERSION when pinned, else the version named by latest.json. Returns (version, key prefix)."""
        if self.settings.version:
            return self.settings.version, self._key(self.settings.version) + '/'
        key = self._key('latest.json')
        body = self.client.get_object(Bucket=self.settings.bucket, Key=key)['Body'].read()
        latest = json.loads(body)
        version = latest['version']
        prefix = latest.get('prefix') or self._key(version) + '/'
        return version, prefix if prefix.endswith('/') else prefix + '/'

    def _download(self, key, target):
        part = target.with_name(target.name + '.part')
        self.client.download_file(self.settings.bucket, key, str(part))
        os.replace(part, target)

    def fetch(self):
        """Returns the local directory of a verified bundle, downloading only what is missing or corrupt."""
        version, prefix = self.resolve_version()
        if not is_safe_file_name(str(version)):
            raise ModelUnavailable(f'invalid model version {version!r}')
        target = self.settings.cache_root / version
        target.mkdir(parents=True, exist_ok=True)
        try:
            return target, verify_bundle(target)  # cached by an earlier process of this environment
        except (ModelUnavailable, ValueError, OSError):
            pass

        started = time.perf_counter()
        config_path = target / 'config.json'
        self._download(prefix + 'config.json', config_path)
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if str(config.get('version')) != str(version):
            raise ModelUnavailable(f'config.json of {prefix} is version {config.get("version")!r}, not {version!r}')
        names = set(bundle_file_names(config)) | set(REQUIRED_FILES)
        names.discard('config.json')
        for name in sorted(names):
            path = target / name
            expected = config.get('files', {}).get(name, {}).get('sha256')
            if path.is_file() and expected and sha256_of(path) == expected:
                continue
            self._download(prefix + name, path)
        config = verify_bundle(target)
        size = sum(p.stat().st_size for p in target.iterdir() if p.is_file())
        logger.info('Downloaded model bundle s3://%s/%s (%.1f MB) in %.2f s', self.settings.bucket, prefix,
                    size / 1e6, time.perf_counter() - started)
        return target, config


def _default_loader(path, threads):
    from ml.generate import LyricsGenerator

    return LyricsGenerator.from_bundle(path, threads=threads)


class ModelService:
    """
    One per process (stored in app.extensions[EXTENSION_KEY]). Loads the bundle once, lazily or on preload,
    and runs generations one at a time.
    """

    def __init__(self, settings, s3_client=None, loader=None):
        self.settings = settings
        self._s3_client = s3_client
        self._loader = loader or _default_loader
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._model = None
        self._error = None
        self._failed_at = None
        self._permanent = False

    # State

    @property
    def model(self):
        return self._model

    @property
    def error(self):
        return self._error

    def status(self):
        if self._model is not None:
            return 'ready'
        if not self.settings.enabled:
            return 'disabled'
        return 'failed' if self._error else 'not loaded'

    # Loading

    def _threads(self):
        # Always an explicit count: it also keeps onnxruntime from pinning threads to cores, which fails in some
        # containers. See DEFAULT_THREADS.
        return self.settings.threads or DEFAULT_THREADS

    def _load(self):
        started = time.perf_counter()
        if self.settings.local_dir:
            path = Path(self.settings.local_dir)
            config = verify_bundle(path)
            source = str(path)
        else:
            path, config = S3BundleSource(self.settings, self._s3_client).fetch()
            source = f's3://{self.settings.bucket}/{self.settings.prefix}'
        generator = self._loader(path, self._threads())
        version = str(config.get('version', path.name))
        model = LoadedModel(generator=generator, version=version,
                            label=f'{config.get("name") or DEFAULT_NAME}/{version}', path=path,
                            load_seconds=time.perf_counter() - started)
        logger.info('Lyrics model %s ready from %s in %.2f s (%d threads)', model.label, source,
                    model.load_seconds, self._threads())
        return model

    def get(self):
        """The loaded model, loading it on first use. Raises ModelUnavailable when it cannot be loaded."""
        if self._model is not None:
            return self._model
        if not self.settings.enabled:
            raise ModelUnavailable('no MODEL_DIR or MODEL_BUCKET configured')
        with self._load_lock:
            if self._model is not None:
                return self._model
            if self._error is not None and (
                    self._permanent or time.monotonic() - self._failed_at < self.settings.retry_seconds):
                raise ModelUnavailable(self._error)
            try:
                self._model = self._load()
                self._error = None
                return self._model
            except Exception as exc:  # any failure leaves generation unavailable, never the whole app
                self._error = f'{type(exc).__name__}: {exc}'
                self._failed_at = time.monotonic()
                # onnxruntime/numpy missing (no `ml` extra) will not fix itself: do not retry
                self._permanent = isinstance(exc, ImportError)
                logger.error('Could not load the lyrics model; generation endpoints answer 503 (%s)',
                             self._error, exc_info=not isinstance(exc, ModelUnavailable))
                raise ModelUnavailable(self._error) from exc

    def preload(self):
        """Starts loading in a daemon thread (MODEL_PRELOAD=true). Returns the thread, or None when disabled."""
        if not self.settings.enabled:
            return None

        def _run():
            try:
                self.get()
            except ModelUnavailable:
                pass  # already logged

        thread = threading.Thread(target=_run, name='lyrics-model-preload', daemon=True)
        thread.start()
        return thread

    # Generation

    def generate(self, artist, seed_text, number_words):
        """Lyrics and title. Returns (Generation, LoadedModel)."""
        model = self.get()
        with self._run_lock:
            result = model.generator.generate(artist=artist, seed_text=seed_text, number_words=number_words,
                                              seed=None)
        return result, model

    def generate_title(self, lyrics, artist):
        """A title for existing lyrics. Returns (title, LoadedModel)."""
        model = self.get()
        with self._run_lock:
            title = model.generator.generate_title(lyrics, artist=artist)
        return title, model


def init_app(app):
    """Creates the process wide ModelService and, with MODEL_PRELOAD=true, starts loading it."""
    service = ModelService(ModelSettings.from_config(app.config))
    app.extensions[EXTENSION_KEY] = service
    if not service.settings.enabled:
        logger.warning('No MODEL_DIR or MODEL_BUCKET configured: generation endpoints will answer 503.')
    elif service.settings.preload:
        service.preload()
    return service


def get_service(app):
    return app.extensions[EXTENSION_KEY]
