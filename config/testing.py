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

TESTING = True
'''
Enable testing mode.
Exceptions are propagated rather than handled by the the app’s error handlers.
Extensions may also change their behavior to facilitate easier testing. You should enable this in your own tests.
Default: False
'''

PROPAGATE_EXCEPTIONS = None
'''
Exceptions are re-raised rather than being handled by the app’s error handlers.
If not set, this is implicitly true if TESTING or DEBUG is enabled.
Default: None
'''

ENV = 'testing'
'''
What environment the app is running in. Flask and extensions may enable behaviors based on the environment, such as
enabling debug mode. The env attribute maps to this config key. This is set by the FLASK_ENV environment variable
and may not behave as expected if set in code.

Do not enable development when deploying in production.
'''

SERVER_NAME_LOG = 'localhost'  # So I don't use SERVER_NAME (reserved)

# Logs
LOG_DIR = r'logs/'
LOG_LEVEL = 2

# AWS
AWS = False
AWS_BUCKET = 'bakinglyrics'

# Models
MODELS_PATH = r'baking/resources/models'
MODEL_NAME_STR = 'lyrics_skth_v0_20_40_300_5000_100'

# DynamoDB: tests run against moto with their own prefix, never against real tables
BAKING_TABLE_PREFIX = 'baking-lyrics-test'

# Seeding
DATA_FILE_PATH = r'baking/resources/lyrics_4_tests.csv'

# Off by default in tests; tests that check limits enable it explicitly
RATELIMIT_ENABLED = False
