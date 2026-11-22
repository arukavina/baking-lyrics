#!/usr/bin/env python

# Generics
import datetime
import importlib.util
import logging
import os
import traceback
from pathlib import Path

# Libs
from dotenv import load_dotenv
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.engine import make_url
from sqlalchemy.exc import NoResultFound

# Own
from baking.main.util import build_info, log_utils

# Repository root (the folder holding `baking/`, `config/` and `migrations/`).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Development/testing only fallback; production must provide SECRET_KEY via the environment.
_DEV_SECRET_KEY = 'dev-insecure-secret-key'

db = SQLAlchemy()

migrate = Migrate(directory=str(REPO_ROOT / 'migrations'))

flask_bcrypt = Bcrypt()

api = Api(version='1.0', title='Baking-Lyrics API',
          description='A funny lyrics generator Flask RESTX powered API')

# No global limits: only endpoints that write public counters are limited (see SHARE_RATE_LIMIT)
limiter = Limiter(key_func=get_remote_address, default_limits=[])

_logger = logging.getLogger('baking-api')


@api.errorhandler
def default_error_handler(error):
    message = 'An unhandled exception occurred.'
    _logger.error('%s: %s', message, error, exc_info=error)
    return {'message': message}, 500


@api.errorhandler(NoResultFound)
def database_not_found_error_handler(error):
    _logger.warning('NoResultFound: %s\n%s', error, traceback.format_exc())
    return {'message': 'A database result was required but none was found.'}, 404


def resolve_path(path):
    """
    Resolves `path` against the repository root when it is relative.
    :param path: str or Path
    :return: absolute Path
    """
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _load_ml_models(app, logger):
    """
    Loads the tokenizer and the Keras models. Returns True when the models are ready to be used.
    Missing optional dependencies (TensorFlow/Keras) or missing model files only produce a warning.
    """
    if importlib.util.find_spec('keras') is None or importlib.util.find_spec('keras_self_attention') is None:
        logger.warning('Keras / keras-self-attention are not installed (optional `ml` extra). '
                       'Generation endpoints will answer 503.')
        return False

    from baking.main.v1.models import machine_learning as ml

    logger.info('Instantiating AI models')

    model_name_str = app.config['MODEL_NAME_STR']
    aws = app.config['AWS']
    # On AWS the paths are S3 object keys and must stay relative.
    model_path = app.config['MODELS_PATH'] if aws else str(resolve_path(app.config['MODELS_PATH']))

    logger.info('AWS: %s', aws)

    try:
        tokenizer = ml.Tokenizer(
            model_name=model_name_str,
            artist_genre_tokenizer_path=os.path.join(model_path, model_name_str + '.artist_genre_tokenizer.npz'),
            tokenizer_path=os.path.join(model_path, model_name_str + '.tokenizer.pickle'),
            embedded_matrix_path=os.path.join(model_path, model_name_str + '.embmat.npz'),
            from_aws=aws
        )
        tokenizer.load()

        ml_model = ml.LyricsSkthModel(
            decoder_model_path=os.path.join(model_path, model_name_str + '.model.generator_word.h5'),
            gen_model_context_path=os.path.join(model_path, model_name_str + '.model.generator_context.h5'),
            model_verse_emb_context_path=os.path.join(model_path, model_name_str + '.model.verse_emb_context.h5'),
            model_stv_encoder_path=os.path.join(model_path, model_name_str + '.model.skipthought.h5'),
            tokenizer=tokenizer,
            from_aws=aws
        )
        ml_model.load_model()
    except Exception:  # any failure here must not prevent the API from booting
        logger.warning('Could not load the ML models; generation endpoints will answer 503.', exc_info=True)
        return False

    return True


def create_app(app_config_file=None, test_config=None):
    """
    Application factory.

    :param app_config_file: Python config file (absolute, or relative to the repo root). When None, the
        APP_CONFIG_FILE environment variable is used.
    :param test_config: Optional dict applied last, after every config file (meant for tests).
    :return: Flask app
    """

    load_dotenv(REPO_ROOT / '.env')

    app = Flask(__name__,
                static_folder=str(REPO_ROOT / 'baking' / 'static' / 'dist'),
                template_folder=str(REPO_ROOT / 'baking' / 'static'))

    # Load the default configuration
    app.config.from_object('config.default')

    # Load the file specified by the argument or the APP_CONFIG_FILE environment variable.
    # Variables defined there override those in the default configuration.
    if app_config_file is None:
        app_config_file = os.getenv('APP_CONFIG_FILE')
        if app_config_file is None:
            raise OSError('APP_CONFIG_FILE variable is not set')

    app.config.from_pyfile(str(resolve_path(app_config_file)))

    if test_config is not None:
        app.config.update(test_config)

    if not app.config.get('SECRET_KEY'):
        if app.config.get('ENV') in ('development', 'testing'):
            app.config['SECRET_KEY'] = _DEV_SECRET_KEY
        else:
            raise RuntimeError('SECRET_KEY environment variable must be set outside development/testing')

    # Setting up logger
    time_stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')
    log_utils.setup_logging('baking-api', time_stamp, app.config)
    logger = log_utils.get_logger('baking-api')
    log_utils.print_imports_versions(logger)

    if app.config['ENV'] == 'production':
        logger.info('Starting {} server at http://{}/api/v1'.format(app.config['ENV'], app.config['SERVER_NAME_LOG']))
    else:
        logger.info('Starting {} server at http://{}:{}/api/v1'.format(app.config['ENV'],
                                                                       app.config['SERVER_NAME_LOG'],
                                                                       os.getenv('FLASK_RUN_PORT', '9090')))

    db_url = make_url(app.config['SQLALCHEMY_DATABASE_URI']).render_as_string(hide_password=True)
    logger.info(f'Using DB: {db_url}')

    # Igniting DB
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Bcrypt
    flask_bcrypt.init_app(app)

    # Build info, resolved once and served by /general/version
    build = build_info.resolve_build_info(REPO_ROOT)
    app.config['BUILD_VERSION'] = build['version']
    app.config['BUILD_COMMIT'] = build['commit']
    app.config['BUILD_COMMIT_DATE'] = build['date']
    logger.info('Build: version=%s commit=%s date=%s', build['version'], build['commit'], build['date'])

    from baking.main import v1

    app = v1.init_app(app, api)

    app.extensions['ml_available'] = False
    if app.config['ENV'] != 'testing':
        with app.app_context():
            app.extensions['ml_available'] = _load_ml_models(app, logger)

    return app
