![bakinglyrics.com][logo]

[logo]: img/logo.png "Baking Lyrics logo" 

This is an open source, side project created from the bottom of the world. (Bottom to be read as arse). Here is a map.
But is for everyone. Our humble contribution to those who make our lives wonderful freeing us from our own thoughts (for just a few minutes)

We wish you the best so play as much as you want, release your creativity, innovate,  copy & paste.

Best regards,

The Baking-Lyrics **coding** band.

[www.bakinglyrics.com](https://www.bakinglyrics.com)

[![Documentation Status](https://readthedocs.org/projects/baking-lyrics/badge/?version=latest)](https://baking-lyrics.readthedocs.io/en/latest/?badge=latest)

___

# Intro

Baking-Lyrics works based on a group of Machine and Deep learning models that generates music lyrics and titles automatically.
Currently available in English (soon Spanish as well).

Baking Lyrics was developed by a team of music; machine learning and software development enthusiasts all the way from Buenos Aires, Argentina. Our country is well know for its rock scene so we were tempted on using a 100% rock corpus but our metal loving friends convinced us of accepting other genres. 

## Baking Lyrics: An automatic lyrics generator

Be a rock star using machine learning to generate lyrics!
Baking lyrics is an automatic generator of lyrics based on a natural language model that is trained using the largest database of lyrics online.
The vast corpus contains all the lyrics of the most popular bands and singers of our time. This corpus was used to train a language model that reproduces the style of each band or singer. If you ever wanted to reproduce the talent of your favorite songwriter, now is the time!

# How-to

## Prerequisites

- Clone the repo.
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.12 for you if needed).
  - Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Install dependencies

- Run `uv sync --extra ml` from the repo root to create `.venv` with the API, the model runtime (onnxruntime and numpy) and the dev tools.
- Without `--extra ml` the API still runs, but the generation endpoints answer 503.
- To train or export a model, add the training tools (PyTorch and friends): `uv sync --extra ml --group train`. The API image never installs them.

## Models and data

- Request the `lyrics.csv` dataset and a model bundle from [Andrei Rukavina](mailto:rukavina.andrei@gmail.com), or train your own with [ml/README.md](ml/README.md).
- Put `lyrics.csv` under `baking/resources/` and point `MODEL_DIR` at the bundle folder (see [Model](#model)).
- No dataset yet? Seed with the small sample instead: pass `--data baking/resources/lyrics_4_tests.csv` to the seed command.
- Any CSV with the Kaggle lyrics columns (`song`, `year`, `artist`, `genre`, `lyrics`) works, for example the `catalog.csv` produced by the ML pipeline.

## Environment variables

- `APP_CONFIG_FILE` (required): path to the config file, for example `config/development.py`.
- `SECRET_KEY`: required with `config/production.py`; development and testing fall back to a dev only key.
- `BAKING_TABLE_PREFIX` (optional): DynamoDB table name prefix, `baking-lyrics` by default. Use your own, such as `baking-lyrics-dev`, for development against real AWS.
- `AWS_REGION` or `AWS_DEFAULT_REGION` (optional): region of the tables and the S3 bucket, `us-east-1` by default. Lambda sets `AWS_REGION` itself.
- `DYNAMODB_ENDPOINT_URL` (optional): DynamoDB endpoint for local development, such as a moto server (`http://localhost:5000`) or DynamoDB Local.
- `ALLOWED_ORIGINS` (optional): comma separated browser origins allowed to call `/api/*` (CORS), `http://localhost:3000` by default.
- `BAKING_COMMIT_SHA` and `BAKING_COMMIT_DATE` (optional): commit sha and ISO 8601 commit date reported by `GET /api/v1/general/version`; when both are unset they are read from git, and they are `null` if git is unavailable.
- `GENERATION_RATE_LIMIT` (optional): per client limit of the generation routes, `5 per minute;50 per day` by default (see [Run](#run)).
- `MODEL_DIR`, `MODEL_BUCKET`, `MODEL_PREFIX`, `MODEL_VERSION`, `MODEL_PRELOAD` (optional): where the lyrics model comes from, see [Model](#model).
- AWS credentials: the usual boto3 sources (`AWS_PROFILE`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, SSO). With a moto server any non empty fake values work.

These can also go in a `.env` file at the repo root (it is gitignored).

Windows PowerShell:

```powershell
$env:APP_CONFIG_FILE = 'config/development.py'
$env:SECRET_KEY = 'change-me'                      # optional
$env:BAKING_TABLE_PREFIX = 'baking-lyrics-dev'     # optional
$env:DYNAMODB_ENDPOINT_URL = 'http://localhost:5000'  # optional, moto server
$env:MODEL_DIR = 'ml/bundles/2026.11.0'            # optional, local model bundle
```

macOS/Linux:

```bash
export APP_CONFIG_FILE=config/development.py
export SECRET_KEY=change-me                       # optional
export BAKING_TABLE_PREFIX=baking-lyrics-dev      # optional
export DYNAMODB_ENDPOINT_URL=http://localhost:5000  # optional, moto server
export MODEL_DIR=ml/bundles/2026.11.0             # optional, local model bundle
```

## Data (DynamoDB)

The API stores everything in five on-demand DynamoDB tables named after `BAKING_TABLE_PREFIX`:

- `<prefix>-catalog`: genres, artists and songs.
- `<prefix>-generated`: generated songs and titles.
- `<prefix>-shares`: one item per share of a generated song.
- `<prefix>-counters`: id sequences and the totals behind `GET /api/v1/general/stats`.
- `<prefix>-ratelimit`: per client share and generation rate limit windows, removed by DynamoDB TTL on `ttl`.

Keys, indexes and TTL are defined in one place, `baking/main/repository/schema.py`.

Pick one of these for local development:

- A local moto server, no AWS account needed: `uvx --from "moto[server]" moto_server -p 5000`, then set `DYNAMODB_ENDPOINT_URL=http://localhost:5000` and fake AWS credentials. Its data lives in memory and is lost when it stops.
- Real AWS tables with your own prefix, such as `BAKING_TABLE_PREFIX=baking-lyrics-dev`, and your AWS credentials.

Create the tables (idempotent: existing tables are kept, TTL is enabled where needed):

- `uv run python -m baking.create_tables --wait`
- Options: `--prefix`, `--region` and `--endpoint-url` override the environment variables.

Seed the catalog:

- `uv run python -m baking.refresh_database --data baking/resources/lyrics.csv`
- It keeps the 900 artists with the most songs and at most 10 songs each, skipping empty, too short, instrumental and placeholder lyrics.
- The 16 artists with the most songs in the dataset are flagged as cover artists, the ones `GET /api/v1/artists/random/<n>` picks from (`--cover-artists` changes the number).
- Ids follow the dataset order, so running it again with the same data keeps every id; records no longer in the data are deleted, generated songs and shares are kept.
- `--artificial 30` also creates 30 demo generated songs (model `Dummy`).

## Run

- Start the API: `uv run flask --app baking.manage run --port 9090`
- Open the Swagger UI at http://localhost:9090/api/v1/
- Shares are limited to 10 per minute and 100 per day per client (`SHARE_RATE_LIMIT`), counted in the ratelimit table so the limit holds across processes; the client is the source IP of the Function URL request, else the left-most `X-Forwarded-For` address.
- Generations are limited the same way to 5 per minute and 50 per day per client (`GENERATION_RATE_LIMIT`), one budget shared by the two song generation routes and the title generation route. Only valid requests count (an unknown artist or song is rejected first), and a client over the limit gets `429` with `{"message": "Too many generations from this address, try again later."}`.
- Both limits are off in the testing config (`RATELIMIT_ENABLED = False`).
- The catalog is read only through the API: genres, artists and songs change only by seeding.
- The list endpoints `GET /api/v1/artists/`, `/songs/`, `/artificial_songs/` and `/artificial_titles/` are paginated with the query parameters `page` (from 1) and `per_page` (2, 10, 20, 30, 40 or 50, 10 by default) and answer `{"items": [...], "page", "pages", "per_page", "total"}`; a page past the end has no items.
- Artists and songs are listed by id, generated songs and titles most recent first. A page reads only what it shows (a Query with `Limit`, or an id range of the `by_entity` index newest first for generated songs and titles), so no list ever returns or reads a whole table.

## Test and lint

- Tests: `uv run pytest` (no environment variables or AWS account needed: tests run against DynamoDB and S3 mocked by moto)
- The model tests that train and export a tiny model on the fly run only when the `train` group is installed; the others use a fake generator.
- Lint: `uv run ruff check .`

# Model

Lyrics and titles come from one conditional word level LSTM language model, trained in PyTorch and served with onnxruntime.

- Words: a 30,000 word lowercase vocabulary with punctuation, line and verse break tokens, and 300 d embeddings initialised from GloVe.
- Style: learned artist and genre embeddings are fed at every step, so the chosen artist steers the style and the seed text is the prompt.
- Network: three LSTM layers (AWD-LSTM regularisation, tied input and output embeddings), about 25 M parameters, a 100 MB ONNX file.
- Titles: the model was trained on `lyrics <title> title`, so after writing the lyrics it writes their title.
- Decoding: temperature, top-k and top-p sampling with a repetition penalty, stopping at the first line end after `number_words` words.

Training, evaluation and retraining are described in [ml/README.md](ml/README.md); the bundle format is in [ml/BUNDLE.md](ml/BUNDLE.md).

## Serving

- The API loads the model on the first generation request, so starting the API and the health check stay fast; `MODEL_PRELOAD=true` starts loading in the background when the app starts instead.
- With `MODEL_DIR` set, the bundle is read from that folder.
- Otherwise it is read from `s3://<MODEL_BUCKET>/<MODEL_PREFIX>/<version>/`, where the version is `MODEL_VERSION` when set, else the one named by `<MODEL_PREFIX>/latest.json`.
- Downloaded files go to `/tmp/models/<version>/` (`MODEL_CACHE_DIR` changes it), are checked against the sha256 values in `config.json`, and are reused by later starts of the same Lambda environment.
- A new version is picked up by new Lambda environments; publish it with `python -m ml.publish` and redeploy (or update any setting) to roll every environment over.
- If the model cannot be loaded, the API keeps running: generation endpoints answer 503 and the error is logged; the load is retried after 5 minutes.
- The generator is not thread safe, so each process keeps one model and runs one generation at a time; Lambda sends one request at a time to an environment anyway.
- Generated songs store `lyrics-lstm/<version>` as their `model`.
- The no seed song endpoint writes in the artist's style without a prompt; artists the model was not trained on get its generic style.

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_DIR` | unset | Local bundle folder; when set, S3 is not used |
| `MODEL_BUCKET` | `bakinglyrics` (unset in development and tests) | S3 bucket of the bundles |
| `MODEL_PREFIX` | `models/lyrics-lstm` | S3 prefix holding `latest.json` and one folder per version |
| `MODEL_VERSION` | unset | Pins a version instead of `latest.json` |
| `MODEL_PRELOAD` | `false` | Load at start in the background instead of on the first generation request |
| `MODEL_CACHE_DIR` | `/tmp/models` | Download folder |
| `MODEL_THREADS` | CPU count, at most 4 | onnxruntime threads per generation |

## History

2018: Keras notebooks on Colab, a word level LSTM per artist, separate encoder-decoder titlers and trigram models per band.

2019 to 2021: a hierarchical skip-thought model (verse encoder, verse sequence model with self attention conditioned on artist and genre, word decoder) served with TensorFlow and a separate LSTM titler; both were retired in 2026 for the single PyTorch and ONNX model above. The details are in the history section of [ml/README.md](ml/README.md#history).

# AWS deployment

## Architecture

- The frontend calls the API directly (with CORS) at the Lambda Function URL (auth type `NONE`).
- The function `baking-lyrics-backend` (`us-east-1`) runs the container image built from the [Dockerfile](Dockerfile) on x86_64.
- Inside the image the [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) extension forwards each request to gunicorn on port 8080, which serves the unchanged Flask app.
- Data lives in the DynamoDB tables `baking-lyrics-*` (on demand capacity).
- Model bundles and the lyrics dataset live in the S3 bucket `bakinglyrics` (bundles under `models/lyrics-lstm/`).
- Images are stored in the ECR repository `baking-lyrics-backend`, which keeps the last 10 images.

## Deploy workflow

- [ci.yml](.github/workflows/ci.yml) runs lint and tests on every pull request.
- [deploy.yml](.github/workflows/deploy.yml) runs on every push to `master` (and manually with "Run workflow"): it runs CI, builds the image for `linux/amd64`, pushes it to ECR tagged with the commit sha and `latest`, updates the Lambda function code, waits for the update and smoke tests the API.
- The smoke test calls `GET /api/v1/general/ping` and checks that `GET /api/v1/general/version` reports the deployed commit.
- The deploy job runs in the GitHub environment `production` and assumes an AWS role through GitHub OIDC, so no AWS keys are stored in GitHub.

The `production` environment needs these secrets:

| Secret | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN of the IAM role the workflow assumes (`baking-lyrics-github-deploy`) |
| `AWS_REGION` | `us-east-1` |
| `ECR_REPOSITORY` | `baking-lyrics-backend` |
| `LAMBDA_FUNCTION_NAME` | `baking-lyrics-backend` |
| `API_BASE_URL` | the Function URL, for example `https://<url-id>.lambda-url.us-east-1.on.aws` (no trailing slash) |

## Lambda configuration

These environment variables are set on the function:

- `APP_CONFIG_FILE`: `config/production.py` (also the image default).
- `SECRET_KEY`: a long random value, required by the production config.
- `ALLOWED_ORIGINS`: comma separated origins allowed by CORS, for example `https://bakinglyrics.com,https://www.bakinglyrics.com,https://baking-lyrics-web.vercel.app`.
- `BAKING_TABLE_PREFIX`: prefix of the DynamoDB tables, `baking-lyrics`.
- `MODEL_BUCKET` and `MODEL_PREFIX` default to `bakinglyrics` and `models/lyrics-lstm` in the image; set `MODEL_VERSION` only to pin or roll back a model version.

`BAKING_COMMIT_SHA` and `BAKING_COMMIT_DATE` are not set on the function: the workflow bakes them into the image as build arguments, so `GET /api/v1/general/version` reports the deployed commit.

The function uses 2048 MB of memory (about 1.2 vCPU, so the 100 MB model generates a 150 word song in about 2 to 3 seconds), a 30 second timeout and 1024 MB of ephemeral storage (`/tmp` holds the downloaded model); its execution role grants DynamoDB access to `baking-lyrics-*`, read access to `s3://bakinglyrics` and CloudWatch Logs.

## Run the container locally

Build and run the same image the workflow deploys (Docker, or `nerdctl` with Rancher Desktop):

```bash
docker build -t baking-lyrics-backend --build-arg BAKING_COMMIT_SHA=$(git rev-parse HEAD) --build-arg BAKING_COMMIT_DATE=$(git log -1 --format=%cI) .
docker run --rm -p 8080:8080 -e SECRET_KEY=change-me baking-lyrics-backend
curl http://localhost:8080/api/v1/general/ping
```

- Outside Lambda the adapter extension stays idle and gunicorn answers directly on port 8080.
- Pass the data settings the API needs with `-e` (for example `-e BAKING_TABLE_PREFIX=baking-lyrics-dev -e AWS_REGION=us-east-1` plus AWS credentials).
- To use a local model bundle instead of S3, mount it and set `MODEL_DIR`: `-v /path/to/bundle:/bundle:ro -e MODEL_DIR=/bundle`.
- Logs go to stdout; on AWS they are in the CloudWatch log group `/aws/lambda/baking-lyrics-backend`.
