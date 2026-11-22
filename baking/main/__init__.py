#!/usr/bin/env python

# Generics
import datetime
import logging
import os
from pathlib import Path

# Libs
from dotenv import load_dotenv
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_restx import Api

# Own
from baking.main.util import build_info, log_utils

# Repository root (the folder holding `baking/` and `config/`).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Development/testing only fallback; production must provide SECRET_KEY via the environment.
_DEV_SECRET_KEY = 'dev-insecure-secret-key'

flask_bcrypt = Bcrypt()

api = Api(version='1.0', title='Baking-Lyrics API',
          description='A funny lyrics generator Flask RESTX powered API')

_logger = logging.getLogger('baking-api')


@api.errorhandler
def default_error_handler(error):
    message = 'An unhandled exception occurred.'
    _logger.error('%s: %s', message, error, exc_info=error)
    return {'message': message}, 500


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

    # Data: DynamoDB tables, reached lazily on first use
    from baking.main.repository import EXTENSION_KEY, repository_from_config

    app.extensions[EXTENSION_KEY] = repository_from_config(app.config)
    logger.info('Using DynamoDB tables %s-* in %s%s', app.config['BAKING_TABLE_PREFIX'], app.config['AWS_REGION'],
                f" at {app.config['DYNAMODB_ENDPOINT_URL']}" if app.config.get('DYNAMODB_ENDPOINT_URL') else '')

    # Bcrypt
    flask_bcrypt.init_app(app)

    # CORS, only for the API and only from the configured origins
    CORS(app, resources={r'/api/*': {'origins': app.config['ALLOWED_ORIGINS']}},
         methods=['GET', 'POST', 'OPTIONS'], allow_headers=['Content-Type'])

    # Build info, resolved once and served by /general/version
    build = build_info.resolve_build_info(REPO_ROOT)
    app.config['BUILD_VERSION'] = build['version']
    app.config['BUILD_COMMIT'] = build['commit']
    app.config['BUILD_COMMIT_DATE'] = build['date']
    logger.info('Build: version=%s commit=%s date=%s', build['version'], build['commit'], build['date'])

    from baking.main import v1

    app = v1.init_app(app, api)

    # Lyrics model: loaded on the first generation request, or now in the background with MODEL_PRELOAD=true
    from baking.main.v1.models import generator

    generator.init_app(app)

    return app
