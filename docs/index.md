# Baking Lyrics model

Baking Lyrics writes song lyrics in the style of an artist from a few words of yours. This site documents the machine learning part: the data, the model, how it is trained and exported, and how the API serves it. The web app lives at [bakinglyrics.com](https://bakinglyrics.com) and the code at [arukavina/baking-lyrics](https://github.com/arukavina/baking-lyrics) (backend and model) and [arukavina/baking-lyrics-web](https://github.com/arukavina/baking-lyrics-web) (frontend).

## What the model does

You pick an artist and type how the song starts. The API asks the model to continue the text word by word in that artist's style, until it has written about the number of words requested, and then to write a title for the result.

The generator is a conditional word level LSTM language model (AWD-LSTM family). Every step sees the previous word plus a learned embedding of the artist and of the genre, so the same network writes like 1,500 different artists. It is a deliberately pre-transformer design, small enough (about 25 M parameters, 99 MB) to run on a CPU inside AWS Lambda.

## From raw lyrics to a generated song

```text
Kaggle lyrics CSVs
   │  ml.data: clean, keep English, pick artists, split by song
   ▼
songs.parquet, artists.json, catalog.csv ──▶ baking.refresh_database
   │                                         (the site's artist catalog)
   │  ml.tokenizer: vocab.json (30k words, <line>, <verse>, <title>)
   │  ml.train: PyTorch on a GPU, perplexity, samples
   ▼
best checkpoint
   │  ml.export: model.onnx (one decoding step), vocab, artists, config
   │  ml.publish: s3://bakinglyrics/models/lyrics-lstm/<version>/
   ▼
API on Lambda: baking.main.v1.models.generator loads the bundle,
ml.generate writes the lyrics and a title (onnxruntime and numpy)
```

The catalog the site shows and the artists the model knows come from the same `catalog.csv`, so an artist picked on the site always has a matching artist embedding.

## Contents

```{toctree}
:maxdepth: 2

training
bundle
serving
reference
```
