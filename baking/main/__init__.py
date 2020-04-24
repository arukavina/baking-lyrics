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
from flask_migrate import Migrate

from sqlalchemy.orm.exc import NoResultFound
from config import default

# Own
from baking.main.util import log_utils

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


def create_app(app_config_file=None):

    print('Current wd={}'.format(os.getcwd()))
    app = Flask("baking-lyrics",
                static_folder="baking/static/dist",
                template_folder="baking/static")

    # Configure

    # Load the default configuration
    app.config.from_object('config.default')

    # Load the file specified by the APP_CONFIG_FILE environment variable
    # Variables defined here will override those in the default configuration
    if app_config_file is None:
        if os.getenv('APP_CONFIG_FILE') is not None:
            print('Using config env_var: APP_CONFIG_FILE = {}'.format(os.getenv('APP_CONFIG_FILE')))
            app.config.from_envvar('APP_CONFIG_FILE')
        else:
            raise EnvironmentError('APP_CONFIG_FILE variable is not set')
    else:
        print('Using config file = {}'.format(app_config_file))
        app.config.from_pyfile(app_config_file)

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
                                                                       os.getenv('FLASK_RUN_PORT')))

    logger.info('Using DB: {}'.format(app.config['SQLALCHEMY_DATABASE_URI']))

    # Igniting DB
    db.init_app(app)

    # Other
    from baking.main import v1

    migrate = Migrate(app, db)

    # Bcrypt
    flask_bcrypt.init_app(app)

    app = v1.init_app(app, api)
    app.app_context().push()

    if app.config['ENV'] != 'testing':

        from baking.main.v1.models import machine_learning as ml

        logger.info('Instantiating  AI models')

        model_name_str = app.config['MODEL_NAME_STR']
        model_path = app.config['MODELS_PATH']
        aws = app.config['AWS']

        print('AWS: ' + str(aws))

        # Loading Tokenizer
        tokenizer_filename = os.path.join(model_path, model_name_str + '.tokenizer.pickle')
        embedding_matrix_filename = os.path.join(model_path, model_name_str + '.embmat.npz')
        artist_genre_tokenizer_filename = os.path.join(model_path, model_name_str + '.artist_genre_tokenizer.npz')

        tokenizer = ml.Tokenizer(
            model_name=model_name_str,
            artist_genre_tokenizer_path=artist_genre_tokenizer_filename,
            tokenizer_path=tokenizer_filename,
            embedded_matrix_path=embedding_matrix_filename,
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

    return app
