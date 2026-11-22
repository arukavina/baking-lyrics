import os
from pathlib import Path

# Repository root: config/default.py -> repo
REPO_ROOT = Path(__file__).resolve().parent.parent


def _database_url():
    url = os.environ.get('DATABASE_URL')
    if url:
        # Heroku style URLs are not accepted by SQLAlchemy >= 1.4
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        return url
    return 'sqlite:///' + (REPO_ROOT / 'baking' / 'resources' / 'flask_bakinglyrics_main.db').as_posix()


# Flask settings
DEBUG = False
FLASK_DEBUG = False
# Read from the environment (or a .env file). create_app falls back to a dev-only key in development/testing.
SECRET_KEY = os.environ.get('SECRET_KEY')

# Flask-RESTX settings
SWAGGER_UI_DOC_EXPANSION = 'list'
RESTX_VALIDATE = True
RESTX_MASK_SWAGGER = False
RESTX_ERROR_404_HELP = False

# SQLAlchemy settings
SQLALCHEMY_DATABASE_URI = _database_url()
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Rate limiting (Flask-Limiter). In memory per process by default; set RATELIMIT_STORAGE_URI
# (for example redis://...) when running several workers.
RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
RATELIMIT_HEADERS_ENABLED = True
SHARE_RATE_LIMIT = '10 per minute;100 per day'

# Log
MAIL_FROM_EMAIL = "rukavina.andrei@gmail.com"  # For use in application emails
LOG_DIR = r'logs/'  # Relative paths are resolved against the repository root
LOG_LEVEL = 2

# Title
TITLE_LSTM_MODEL = r'TitleLSTMModel'

# Title - LSTM
TITLE_LSTM_MODEL_FILE_PATH = 'baking/resources/models/titler_v1'
TITLE_LSTM_TOKENIZER_FILE_PATH = ""
