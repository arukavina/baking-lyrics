#!/usr/bin/env python

# Generics
import datetime
import traceback
import os

# Libs
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_restplus import Api

from sqlalchemy.orm.exc import NoResultFound
from config import default

# Own
from api.util import log_utils

db = SQLAlchemy()
flask_bcrypt = Bcrypt()

api = Api(version='1.0', title='Baking-Lyrics API',
          description='A funny lyrics generator Flask RestPlus powered API')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


@api.errorhandler
def default_error_handler():
    message = 'An unhandled exception occurred.'
    print(message)

    if not default.FLASK_DEBUG:
        return {'message': message}, 500


@api.errorhandler(NoResultFound)
def database_not_found_error_handler():
    print(traceback.format_exc())
    return {'message': 'A database result was required but none was found.'}, 404


def create_app(app_config_file):

    print('Current wd={}'.format(os.getcwd()))
    app = Flask("baking-lyrics",
                static_folder="static/dist",
                template_folder="static")

    # Configure

    # Load the default configuration
    app.config.from_object('config.default')

    # Load the file specified by the APP_CONFIG_FILE environment variable
    # Variables defined here will override those in the default configuration
    if app_config_file is None:
        if os.getenv('APP_CONFIG_FILE') is not None:
            app.config.from_envvar('APP_CONFIG_FILE')
    else:
        app.config.from_pyfile(app_config_file)

    # Setting up logger
    time_stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')
    log_utils.setup_logging('baking-api', time_stamp, app.config)
    logger = log_utils.get_logger('baking-api')
    log_utils.print_imports_versions(logger)

    logger.info('Starting {} server at http://{}:5000/api/v1'.format(app.config['ENV'], app.config['SERVER_NAME']))

    # Igniting DB
    db.init_app(app)

    # Bcrypt
    flask_bcrypt.init_app(app)

    return app
