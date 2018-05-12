DEBUG = False
SQLALCHEMY_ECHO = False
BCRYPT_LOG_ROUNDS = 12  # Configuration for the Flask-Bcrypt extension
MAIL_FROM_EMAIL = "rukavina.andrei@gmail.com"  # For use in application emails
LOG_DIR = r'logs/'
LOG_LEVEL = 2

BANDS_PATH = r'./resources/Bands.json'

# Current
CURRENT_MODEL_LYRICS = r'LYRICS_LSTM_MODEL'
CURRENT_MODEL_TITLE = r'TitleLSSTMMModel'

# Lyrics
LYRICS_LSTM_MODEL = r'LyricsLSTMModel'
NGRAMS_LSTM_MODEL = r'NGramsModel'

# Lyrics - LSTM
LYRICS_LSTM_MODEL_FILE_PATH = r'data/models/lstm/text_generator_700_0.2_700_0.2_700_0.2_100_big_model.yaml'
LYRICS_LSTM_WEIGHTS_FILE_PATH = r'data/models/lstm/text_generator_700_0.2_700_0.2_700_0.2_100_big_weights.h5'
LYRICS_LSTM_SEED_FILE_PATH = r'data/martin-fierro.txt'

# Lyrics - NGran
LYRICS_NGRAM_MODEL_FILE_PATH = r'data/models/lstm/text_generator_700_0.2_700_0.2_700_0.2_100_big_model.yaml'

# Title
TITLE_LSTM_MODEL = r'TitleLSSTMMModel'

# Title - LSTM
TITLE_LSTM_MODEL_FILE_PATH = ""
TITLE_LSTM_TOKENIZER_FILE_PATH = ""