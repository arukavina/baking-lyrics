# Baking Lyrics API as an AWS Lambda container image.
#
# The unchanged Flask app runs under gunicorn on port 8080. On Lambda the AWS Lambda Web Adapter
# extension (https://github.com/awslabs/aws-lambda-web-adapter) turns Function URL events into HTTP
# requests to that port. Outside Lambda the extension is inert, so the same image runs locally:
#
#   docker build -t baking-lyrics-backend .
#   docker run --rm -p 8080:8080 -e SECRET_KEY=change-me -e ALLOWED_ORIGINS=http://localhost:3000 baking-lyrics-backend
#   curl http://localhost:8080/api/v1/general/ping

ARG PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12.16-slim-trixie

FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 AS lambda-adapter


FROM ${PYTHON_IMAGE} AS build

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /src

# Install exactly what uv.lock pins for the API plus the `ml` extra (onnxruntime, numpy) into a venv.
# No dev or train group: torch never enters the image.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --extra ml --no-emit-project --format requirements-txt \
        --output-file requirements.lock.txt \
    && uv venv /opt/venv --python /usr/local/bin/python3 \
    && uv pip install --python /opt/venv/bin/python --no-cache --require-hashes -r requirements.lock.txt


FROM ${PYTHON_IMAGE}

COPY --from=lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=build /opt/venv /opt/venv

# The app resolves relative paths (config, resources) against the folder holding baking/ and config/.
WORKDIR /var/task
COPY pyproject.toml ./
COPY config ./config
COPY baking ./baking
# Only the serving modules of the model package (ml/__init__.py, generate.py, tokenizer.py; see .dockerignore).
COPY ml ./ml
# Lambda mounts the image read only, so compile the bytecode now instead of on every cold start.
RUN /opt/venv/bin/python -m compileall -q baking config ml

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_CONFIG_FILE=config/production.py \
    AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/api/v1/general/ping

# Lyrics model bundle: s3://MODEL_BUCKET/MODEL_PREFIX/<version>/, the version named by latest.json unless
# MODEL_VERSION pins one. It is downloaded to /tmp/models on the first generation request (or at start with
# MODEL_PRELOAD=true) and reused by later cold starts of the same environment. MODEL_DIR=/path/to/bundle uses
# a mounted bundle instead of S3. Lambda settings: 2048 MB memory, 30 s timeout, 1024 MB ephemeral storage.
ENV MODEL_BUCKET=bakinglyrics \
    MODEL_PREFIX=models/lyrics-lstm

# Commit reported by GET /api/v1/general/version (there is no .git in the image).
ARG BAKING_COMMIT_SHA=""
ARG BAKING_COMMIT_DATE=""
ENV BAKING_COMMIT_SHA=${BAKING_COMMIT_SHA} \
    BAKING_COMMIT_DATE=${BAKING_COMMIT_DATE}

EXPOSE 8080

# One process with a few threads: Lambda sends one request at a time per execution environment.
# --timeout 0 turns off the gunicorn worker heartbeat check. Lambda freezes the environment between
# invocations, and after a long freeze the arbiter would kill a healthy worker. The request time limit
# is the Lambda function timeout (30 s) instead. The control socket is off because the image file
# system is read only on Lambda.
CMD ["gunicorn", "baking.manage:app", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "0", \
     "--graceful-timeout", "5", \
     "--no-control-socket", \
     "--access-logfile", "-"]
