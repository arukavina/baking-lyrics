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

# Rate limiting per client, stored in the {BAKING_TABLE_PREFIX}-ratelimit table (see baking/main/ratelimit.py)
RATELIMIT_ENABLED = True
SHARE_RATE_LIMIT = '10 per minute;100 per day'
# One budget shared by the three generation routes (artificial songs with and without seed, artificial titles)
GENERATION_RATE_LIMIT = os.environ.get('GENERATION_RATE_LIMIT') or '5 per minute;50 per day'

# Log
MAIL_FROM_EMAIL = "rukavina.andrei@gmail.com"  # For use in application emails
LOG_DIR = r'logs/'  # Relative paths are resolved against the repository root
LOG_LEVEL = 2

# Lyrics model bundle (see baking/main/v1/models/generator.py and ml/BUNDLE.md)
# MODEL_DIR: local bundle directory (development, tests); when set, S3 is not used
MODEL_DIR = os.environ.get('MODEL_DIR') or None
# Otherwise s3://MODEL_BUCKET/MODEL_PREFIX/<MODEL_VERSION or the version in latest.json>/
MODEL_BUCKET = os.environ.get('MODEL_BUCKET') or 'bakinglyrics'
MODEL_PREFIX = os.environ.get('MODEL_PREFIX') or 'models/lyrics-lstm'
MODEL_VERSION = os.environ.get('MODEL_VERSION') or None
# Download cache (default /tmp/models, the only writable path on Lambda)
MODEL_CACHE_DIR = os.environ.get('MODEL_CACHE_DIR') or None
# true: start loading the model when the app is created instead of on the first generation request
MODEL_PRELOAD = os.environ.get('MODEL_PRELOAD', 'false')
# onnxruntime intra op threads (default 1: Lambda at 2048 MB gets about 1.16 vCPU, see DEFAULT_THREADS)
MODEL_THREADS = os.environ.get('MODEL_THREADS') or None
# Seconds before a failed load is retried
MODEL_RETRY_SECONDS = 300
