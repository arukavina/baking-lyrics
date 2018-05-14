# Flask settings
DEBUG = False

# Flask-Restplus settings
RESTPLUS_SWAGGER_UI_DOC_EXPANSION = 'list'
RESTPLUS_VALIDATE = True
RESTPLUS_MASK_SWAGGER = False
RESTPLUS_ERROR_404_HELP = False

# SQLAlchemy settings
SQLALCHEMY_DATABASE_URI = 'sqlite:///db.sqlite'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Log
MAIL_FROM_EMAIL = "rukavina.andrei@gmail.com"  # For use in application emails
LOG_DIR = r'logs/'
LOG_LEVEL = 2

BANDS_PATH = r'./resources/Bands.json'

# Current
CURRENT_MODEL_LYRICS = r'LYRICS_LSTM_MODEL'
CURRENT_MODEL_TITLE = r'TITLE_LSTM_MODEL'

# Lyrics
LYRICS_LSTM_MODEL = r'LyricsLSTMModel'
NGRAMS_LSTM_MODEL = r'NGramsModel'

# Lyrics - LSTM
LYRICS_LSTM_MODEL_FILE_PATH = r'resources/text_generator_dummy.yaml'
LYRICS_LSTM_WEIGHTS_FILE_PATH = r'resources/text_generator_dummy_weights.h5'
LYRICS_LSTM_SEED_FILE_PATH = r'resources/martin-fierro.txt'

# Lyrics - NGran
LYRICS_NGRAM_MODEL_FILE_PATH = r'resources/text_generator_dummy.yaml'

# Title
TITLE_LSTM_MODEL = r'TitleLSTMModel'

# Title - LSTM
TITLE_LSTM_MODEL_FILE_PATH = ""
TITLE_LSTM_TOKENIZER_FILE_PATH = ""