import os
from pathlib import Path

# Repository root: config/default.py -> repo
REPO_ROOT = Path(__file__).resolve().parent.parent


def _allowed_origins():
    raw = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000')
    return [origin.strip() for origin in raw.split(',') if origin.strip()]


# Flask settings
DEBUG = False
FLASK_DEBUG = False
# Read from the environment (or a .env file). create_app falls back to a dev-only key in development/testing.
SECRET_KEY = os.environ.get('SECRET_KEY')

# CORS: browser origins allowed to call /api/* (comma-separated ALLOWED_ORIGINS environment variable)
ALLOWED_ORIGINS = _allowed_origins()

# Flask-RESTX settings
SWAGGER_UI_DOC_EXPANSION = 'list'
RESTX_VALIDATE = True
RESTX_MASK_SWAGGER = False
RESTX_ERROR_404_HELP = False

# AWS region of the DynamoDB tables and the S3 bucket (Lambda sets AWS_REGION)
AWS_REGION = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'

# DynamoDB: tables are named {BAKING_TABLE_PREFIX}-catalog, -generated, -shares, -counters and -ratelimit
BAKING_TABLE_PREFIX = os.environ.get('BAKING_TABLE_PREFIX') or 'baking-lyrics'
# Optional endpoint for local development (moto server or DynamoDB Local)
DYNAMODB_ENDPOINT_URL = os.environ.get('DYNAMODB_ENDPOINT_URL') or None
# Seconds the artist list is kept in memory by each process
CATALOG_CACHE_SECONDS = 60

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
