DEBUG = False
'''
Whether debug mode is enabled. 
When using flask run to start the development server, an interactive debugger will be shown for unhandled exceptions, 
and the server will be reloaded when code changes. The debug attribute maps to this config key. 
This is enabled when ENV is 'development' and is overridden by the FLASK_DEBUG environment variable. 
It may not behave as expected if set in code.
Do not enable debug mode when deploying in production.

Default: True if ENV is 'development', or False otherwise.
'''

TESTING = False
'''
Enable testing mode. 
Exceptions are propagated rather than handled by the the app’s error handlers. 
Extensions may also change their behavior to facilitate easier testing. You should enable this in your own tests.
Default: False
'''

PROPAGATE_EXCEPTIONS = False
'''
Exceptions are re-raised rather than being handled by the app’s error handlers. 
If not set, this is implicitly true if TESTING or DEBUG is enabled.
Default: None
'''

PRESERVE_CONTEXT_ON_EXCEPTION = False
'''
Don’t pop the request context when an exception occurs. 
If not set, this is true if DEBUG is true. 
This allows debuggers to introspect the request data on errors, and should normally not need to be set directly.
Default: None
'''

ENV = 'production'
'''
What environment the app is running in. Flask and extensions may enable behaviors based on the environment, such as 
enabling debug mode. The env attribute maps to this config key. This is set by the FLASK_ENV environment variable 
and may not behave as expected if set in code.

Do not enable development when deploying in production.
'''

SERVER_NAME_LOG = 'ai.bakinglyrics.com'  # So I don't use SERVER_NAME (reserved)

# Logs
LOG_DIR = r'logs/'
LOG_LEVEL = 2

# Models
MODELS_PATH = r'baking/resources/models'
MODEL_NAME_STR = 'lyrics_skth_v0_20_40_300_5000_100'

# SQLAlchemy settings
SQLALCHEMY_ECHO = False
SQLALCHEMY_TRACK_MODIFICATIONS = False
DATA_FILE_PATH = r'baking/resources/lyrics.csv'


# # Log
# LOG_DIR = r'/mnt/vol/logs/'
# LOG_LEVEL = 1
#
# # Lyrics - LSTM
# LYRICS_LSTM_MODEL_FILE_PATH = r'/mnt/vol/resources/models/generator_v1.yaml'
# LYRICS_LSTM_WEIGHTS_FILE_PATH = r'/mnt/vol/resources/models/generator_v1_weights.h5'
#
# # Title - LSTM
# TITLE_LSTM_MODEL_FILE_PATH = '/mnt/vol/resources/models/titler_v1.yaml'
# TITLE_LSTM_TOKENIZER_FILE_PATH = '/mnt/vol/resources/models/titler_v1_tokenizer.pickle'
