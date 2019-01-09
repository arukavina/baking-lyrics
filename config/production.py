import os

DEBUG = False
SQLALCHEMY_ECHO = False
TESTING = False
PROPAGATE_EXCEPTIONS = None
PRESERVE_CONTEXT_ON_EXCEPTION = None
ENV = 'production'

DATA_FILE_PATH = r'/mnt/vol/resources/lyrics.csv'
LYRICS_LSTM_SEED_FILE_PATH = r'/mnt/vol/resources/lyrics.csv'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join('/mnt/vol/resources', 'bakinglyrics_main.db')

# Log
LOG_DIR = r'/mnt/vol/logs/'
LOG_LEVEL = 1

# Lyrics - LSTM
LYRICS_LSTM_MODEL_FILE_PATH = r'/mnt/vol/resources/models/generator_v1.yaml'
LYRICS_LSTM_WEIGHTS_FILE_PATH = r'/mnt/vol/resources/models/generator_v1_weights.h5'

# Title - LSTM
TITLE_LSTM_MODEL_FILE_PATH = '/mnt/vol/resources/models/titler_v1.yaml'
TITLE_LSTM_TOKENIZER_FILE_PATH = '/mnt/vol/resources/models/titler_v1_tokenizer.pickle'
