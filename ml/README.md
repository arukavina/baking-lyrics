# Lyrics model: training guide

The Baking Lyrics generator is a conditional word level LSTM language model (AWD-LSTM family) trained in PyTorch, exported to ONNX and served on AWS Lambda with onnxruntime and numpy only.

This folder holds everything needed to retrain it: data preparation, training, export, a generator for serving and a publishing script.

The bundle format consumed by the API is described in [BUNDLE.md](BUNDLE.md).

## Contents

| Path | Purpose |
|---|---|
| `data.py` | Download (Kaggle) or read a local CSV, clean, filter, split by song, write `songs.parquet`, `catalog.csv`, `artists.json` |
| `tokenizer.py` | Word level tokenizer shared by training and serving (pure Python and numpy, JSON vocab) |
| `model.py` | PyTorch model and the single step decoder that is exported |
| `train.py` | Training CLI: presets, AMP, checkpoints and resume, validation perplexity, early stopping, samples |
| `export.py` | ONNX export, torch vs onnxruntime parity check, bundle writer |
| `generate.py` | Generation from a bundle with onnxruntime (imported by the API) |
| `publish.py` | Upload a bundle to S3 and switch `latest.json` |
| `notebooks/train_lyrics_lstm.ipynb` | Colab and local GPU notebook that drives the steps above |
| `tests/` | CPU tests (seconds), run by `uv run pytest` |

Local data, runs and bundles go to `ml/data/`, `ml/runs/` and `ml/bundles/`, which git ignores.

## The model

Input at each step: a 300 d word embedding, a 64 d artist embedding and a 16 d genre embedding, concatenated.

Three LSTM layers with 1024 units; the last layer has 300 units so the output softmax can share the input embedding matrix (weight tying).

Regularisation as in AWD-LSTM: embedding dropout, locked dropout on inputs, between layers and on outputs, and DropConnect on the recurrent weights (training only, so the exported weights are plain LSTM weights).

Conditioning dropout: 10 percent of training songs see the "unknown artist" id 0, so generation also works for an artist the model does not know.

Each song is one sequence `<bos> lyrics <title> title <eos>`, so the same model writes lyrics and then a title for them.

Vocabulary: the 30,000 most frequent words of the training split (minimum count 3), lowercase, punctuation as separate tokens, `<line>` for a line break and `<verse>` for a blank line.

Optimiser: AdamW with gradient clipping at 1.0, linear warmup then cosine decay, mixed precision on CUDA (bf16 on L4, A100 and RTX 30 or newer, fp16 with loss scaling on T4).

Decoding: temperature, top-k and nucleus sampling, a repetition penalty, at most two identical words in a row, `<unk>` never sampled, a word budget that ends on a line break, and a title sampled after `<title>` with a bonus for words from the lyrics.

About 25 M parameters with the full vocabulary; `model.onnx` is about 100 MB in float32.

## Data

Use the raw Kaggle file `lyrics.csv` from [gyani95/380000-lyrics-from-metrolyrics](https://www.kaggle.com/datasets/gyani95/380000-lyrics-from-metrolyrics) (version 2, 362,237 rows, columns `index,song,year,artist,genre,lyrics`).

It keeps line breaks and punctuation, so the model learns line and verse structure.

The derived `original_cleaned_lyrics.csv` and `english_cleaned_lyrics.csv` files are also accepted (their extra leading index column is detected), but their lyrics are flattened onto one line without punctuation.

For flattened lyrics `data.py` restores line breaks with a heuristic: a capitalised word (other than "I", "I'm", ...) starts a new line, a run of capitalised words stays together, and nearly all lowercase or all capitals texts stay one line; this recovers most lines but merges lines that began with "I", which is why the raw file is preferred.

The Kaggle "55000+ Song Lyrics" `songdata.csv` (`artist,song,link,text`) can be merged with `--extra-songdata songdata.csv`; its artist names are turned into the same slug scheme, its genre is "Other", it has no year, and songs already in MetroLyrics are removed by the deduplication.

Cleaning rules: drop empty lyrics, "instrumental" and "not available" notes, the Polish "tekst piosenki" placeholders, texts under 30 or over 1,200 words and texts with more than 10 percent non Latin letters; remove `[Chorus]` style annotations and section header lines; normalise whitespace and quotes; keep at most one blank line between stanzas; keep English songs only (fastText `lid.176` lite model through `fast-langdetect`, a stopword heuristic when it is not installed); deduplicate identical lyrics and identical artist and title pairs.

Selection: artists with at least 20 songs, the 900 with most songs (the API catalog seeds at most 900 artists), at most 150 songs per artist (random with a fixed seed), split 90 / 5 / 5 by song within each artist.

`catalog.csv` has the original Kaggle columns and only the songs of the artists the model knows; seed the API catalog from it so the site's artists and the model's artist ids match: `python -m baking.refresh_database --data ml/data/processed/catalog.csv`.

On the full raw file, cleaning keeps 257,025 rows, 233,471 are English and 215,941 remain after deduplication (measured on this repository's copy).

## Retraining on Google Colab

1. Open `ml/notebooks/train_lyrics_lstm.ipynb` in Colab (File > Open notebook > GitHub, repository `arukavina/baking-lyrics`) and choose Runtime > Change runtime type > T4, L4 or A100 GPU.
2. Create a Kaggle API token (kaggle.com > Settings > API > Generate New Token) and add it as a Colab secret named `KAGGLE_API_TOKEN` with notebook access.
3. In the first cell set `PRESET` (`colab-t4` on a T4, `gpu-large` on L4 or A100) and `VERSION` (for example `2026.11.0`).
4. Run all cells; data, checkpoints and the bundle are stored in Google Drive under `MyDrive/baking-lyrics/`.
5. If the session disconnects, run the setup cells and the training cell again: training resumes from `last.pt`.
6. When it finishes, check the test perplexity and the samples, then download `MyDrive/baking-lyrics/bundles/<VERSION>/` and publish it from your machine (below).

## Retraining on a local CUDA machine (Windows PowerShell)

Requirements: an NVIDIA GPU with 8 GB or more, a recent driver, `uv`, and this repository.

```powershell
uv sync --group train
# Replace the CPU torch wheel with a CUDA build (pick the index for your driver at https://pytorch.org/get-started/locally/)
uv pip install --reinstall torch --index-url https://download.pytorch.org/whl/cu132
uv run --no-sync python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Use `uv run --no-sync` from then on, otherwise `uv run` may put the CPU wheel back from the lock file.

```powershell
$env:KAGGLE_API_TOKEN = "<your token>"
uv run --no-sync python -m ml.data --kaggle --out ml\data\processed
# or, with the raw CSV already downloaded:
uv run --no-sync python -m ml.data --csv ml\data\lyrics.csv --out ml\data\processed
Invoke-WebRequest https://nlp.stanford.edu/data/glove.6B.zip -OutFile ml\data\glove.6B.zip
uv run --no-sync python -m ml.train --data ml\data\processed --out ml\runs\local --preset colab-t4 --glove ml\data\glove.6B.zip
uv run --no-sync python -m ml.train --data ml\data\processed --out ml\runs\local --eval-only --split test
uv run --no-sync python -m ml.export --run ml\runs\local --out ml\bundles --version 2026.11.0
uv run --no-sync python -m ml.generate ml\bundles\2026.11.0 --artist bee-gees --seed-text "night fever" --words 120 --seed 7
```

On an 8 GB laptop GPU use `--set batch_size=16` (or `--set max_len=320`); on 16 GB the `colab-t4` preset fits; on 24 GB or more use `gpu-large`.

The same commands work on Linux and macOS with `/` paths; on Apple silicon training runs on `mps` without mixed precision and is much slower than CUDA.

## Publishing

```powershell
uv run --group train python -m ml.publish ml\bundles\2026.11.0 --dry-run
uv run --group train python -m ml.publish ml\bundles\2026.11.0 --profile <your-aws-profile>
```

It uploads to `s3://bakinglyrics/models/lyrics-lstm/<version>/`, then writes `models/lyrics-lstm/latest.json`; it refuses to overwrite an existing version unless `--overwrite` is given, and `--no-latest` uploads without switching.

The IAM user needs `s3:PutObject` and `s3:ListBucket` on `bakinglyrics` under `models/lyrics-lstm/`.

## Expected durations and costs

These are estimates from the model size (about 150 MFLOP per training token) and the dataset size (about 120,000 songs and 35 M tokens per epoch with the default selection); they were not measured on a GPU.

| Hardware | Preset | Per epoch | Full run | Cost |
|---|---|---|---|---|
| Colab T4 (free or Pay As You Go) | `colab-t4` | 20 to 40 min | 12 epochs, 4 to 8 h | free tier (with reconnects) or about 2 USD in compute units |
| Colab L4 | `gpu-large` | 10 to 20 min | 25 epochs or early stop, 3 to 6 h | about 3 to 5 USD in compute units |
| Colab A100 | `gpu-large` | 5 to 10 min | 2 to 4 h | about 5 to 10 USD in compute units |
| Laptop RTX 4070 / 4080 | `colab-t4` | 15 to 30 min | 3 to 6 h | electricity |
| CPU | `smoke` | minutes on a 20 artist subset | pipeline check only | none |

Data preparation takes 2 to 5 minutes and export about 1 minute on any of them.

## Knobs

| Setting | Where | Effect |
|---|---|---|
| `--max-artists`, `--min-songs`, `--max-songs-per-artist` | `ml.data` | Size and balance of the corpus; more songs per artist gives a better language model but longer epochs |
| `--set epochs=N`, `--set patience=N` | `ml.train` | Training length and early stopping |
| `--set max_minutes=N` | `ml.train` | Stop and checkpoint after N minutes (fits a Colab session; rerun to continue) |
| `--set batch_size=N`, `--set max_len=N` | `ml.train` | GPU memory use; logits take `batch_size * max_len * 30000` floats |
| `--set lr=0.001`, `--set warmup_steps=N` | `ml.train` | Learning rate and warmup |
| `--set vocab_size=N`, `--set min_freq=N` | `ml.train` (new run only) | Vocabulary size |
| `--set model.hidden=N`, `model.layers`, `model.emb_dim` | `ml.train` (new run only) | Capacity; `emb_dim` must be 300 to use GloVe 6B 300d |
| `--set model.weight_drop=0.3`, `model.dropout_*` | `ml.train` | Regularisation; raise them if validation perplexity rises while training perplexity falls |
| `--set model.cond_drop=0.1` | `ml.train` | How often the artist is hidden, which trains the generic style |
| `temperature`, `top_k`, `top_p`, `repetition_penalty` | `ml.generate` | Creativity versus coherence at generation time |

Settings can also come from a JSON file: `--config my.json` with `{"epochs": 8, "model": {"hidden": 768}}`.

When resuming, the saved settings are used and only the `--set` values given on that command change them.

## Troubleshooting

`CUDA out of memory`: lower `batch_size` (32 to 16) or `max_len` (400 to 320) with `--set`.

`UnicodeEncodeError` on Windows: run `$env:PYTHONUTF8 = "1"` before the commands (the export already silences the PyTorch exporter's emoji output).

`torch.cuda.is_available()` is False after `uv sync`: reinstall the CUDA wheel as shown above and use `uv run --no-sync`.

Kaggle `401` or `403`: the token is missing or expired; create a new one and set `KAGGLE_API_TOKEN` (or the legacy `KAGGLE_USERNAME` and `KAGGLE_KEY`).

Training perplexity drops but validation rises: overfitting; raise the dropouts or `--max-songs-per-artist`, or rely on early stopping.

Samples repeat lines: raise `repetition_penalty` (1.3) or lower `temperature` and `top_p` at generation time.

The parity check fails in export: make sure `onnxruntime` and `onnxscript` are current; `--exporter torchscript` uses the legacy exporter as a fallback.

`fast-langdetect` downloads nothing: the lite model ships with the package; `--lang-detector heuristic` avoids it entirely.

## History

2018: the first models were Keras notebooks on Colab. `lgen_v45` trained a word level LSTM on one artist at a time (for example Bon Jovi) with 50 word windows, a 5,000 word vocabulary and one-hot targets; its loss plateaued with accuracy stuck at the most frequent word (sigmoid output with categorical cross entropy and RMSprop at learning rate 0.1), and the samples looped on single words ("kill kill kill").

2018: the titlers (`titler_train`, `Word level Entitler V2`) were small encoder-decoders on the 55000+ Song Lyrics data: an LSTM read the first 100 lyric tokens and another LSTM wrote up to 8 title tokens with frozen GloVe 100d embeddings; they kept titles that share a word with the lyrics and overfitted after about 8 epochs.

2019 to 2021: `Text_Generation_Revisisted_v5` moved to a hierarchical skip-thought design: a verse encoder, a verse sequence model with self attention conditioned on artist (32 d) and genre (4 d) embeddings, and a word decoder, with a 5,000 word vocabulary, frozen GloVe 100d, `xseqstart` and `xnewlinefeed` marker tokens, and models pickled with Keras; it needed TensorFlow, keras-self-attention and several model files at serving time.

What we kept: word level modelling, GloVe initialisation, learned artist and genre embeddings, line break tokens, titles that echo the lyrics, at most 8 title words.

What changed: one model for lyrics and titles, a 30,000 word vocabulary with punctuation, all artists in one model, sparse cross entropy instead of one-hot targets, AdamW with warmup and cosine decay, AWD-LSTM regularisation, sampling with top-k, top-p and repetition control instead of plain multinomial sampling, a JSON vocabulary instead of pickles, and ONNX serving without TensorFlow.

The old notebooks are kept outside git in `ml/legacy/` for reference.
