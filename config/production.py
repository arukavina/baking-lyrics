DEBUG = False
SQLALCHEMY_ECHO = False
TESTING = False
PROPAGATE_EXCEPTIONS = None
PRESERVE_CONTEXT_ON_EXCEPTION = None
ENV = 'production'

DATA_FILE_PATH = r'/mnt/s3/resources/songdata.csv'
LYRICS_LSTM_SEED_FILE_PATH = r'/mnt/s3/resources/songdata.csv'

# Log
LOG_DIR = r'/mnt/s3/logs/'
LOG_LEVEL = 1

# Lyrics - LSTM
LYRICS_LSTM_MODEL_FILE_PATH = r'/mnt/s3/resources/generator_v1.yaml'
LYRICS_LSTM_WEIGHTS_FILE_PATH = r'/mnt/s3/resources/generator_v1_weights.h5'

# Title - LSTM
TITLE_LSTM_MODEL_FILE_PATH = '/mnt/s3/resources/models/titler_v1.yaml'
TITLE_LSTM_TOKENIZER_FILE_PATH = '/mnt/s3/resources/models/titler_v1_tokenizer.pickle'
