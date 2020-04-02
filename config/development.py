import os

DEBUG = True
SQLALCHEMY_ECHO = False  # True to see queries
TESTING = True
PROPAGATE_EXCEPTIONS = None
PRESERVE_CONTEXT_ON_EXCEPTION = False  # True

FLASK_ENV = 'development'
ENV = 'development'

SERVER_NAME_LOG = 'localhost'  # So I don't use SERVER_NAME (reserved)

MODELS_PATH = r'baking/resources/models'

MODEL_NAME_STR = 'lyrics_skth_v0_20_40_300_5000_100'

DATA_FILE_PATH = r'baking/resources/lyrics_4_tests.csv'

# SQLAlchemy settings
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join('baking/resources', 'flask_bakinglyrics_main.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
DATA_FILE_PATH = r'baking/resources/songdata.csv'