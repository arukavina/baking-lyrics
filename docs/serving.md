# Serving in the API

The generation endpoints of the API (`/api/v1/artificial_songs/generate/...` and `/api/v1/artificial_titles/generate/...`) run on AWS Lambda. The container installs the `ml` extra only (onnxruntime and numpy, no torch) and copies the two serving modules, `ml.tokenizer` and `ml.generate`.

```{eval-rst}
.. automodule:: baking.main.v1.models.generator
   :no-members:
   :no-index:
```

## Configuration

| Variable | Meaning |
|---|---|
| `MODEL_BUCKET` | S3 bucket of the bundles (production: `bakinglyrics`) |
| `MODEL_PREFIX` | key prefix of the bundles (production: `models/lyrics-lstm`) |
| `MODEL_VERSION` | pin a bundle version instead of following `latest.json` (also used to roll back) |
| `MODEL_DIR` | a local bundle directory, for development and tests; S3 is not used |
| `MODEL_PRELOAD` | `true` loads the model in the background at cold start instead of on the first generation |
| `MODEL_THREADS` | onnxruntime intra op threads (default 1) |

Without a model the generation endpoints answer 503 and the frontend shows that the generator is offline; everything else in the API keeps working.
