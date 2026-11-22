# Lyrics model bundle format (format_version 1)

A bundle is a directory produced by `python -m ml.export` and consumed by `ml.generate.LyricsGenerator.from_bundle`.
Serving needs only `numpy`, `onnxruntime` and the two pure Python modules `ml/tokenizer.py` and `ml/generate.py`.

## Files

| File | Content |
|---|---|
| `model.onnx` | Single step decoder, weights embedded (no external data file), float32 |
| `vocab.json` | Word vocabulary (`ml.tokenizer.Tokenizer`) |
| `artists.json` | Artist and genre ids used for conditioning |
| `config.json` | Model hyperparameters, ONNX interface, tokenizer settings, data hash, metrics, sampling defaults, file hashes |
| `samples.md` | Samples generated from the exported ONNX model for the largest artists |

## S3 layout

```
s3://bakinglyrics/models/lyrics-lstm/<version>/model.onnx
s3://bakinglyrics/models/lyrics-lstm/<version>/vocab.json
s3://bakinglyrics/models/lyrics-lstm/<version>/artists.json
s3://bakinglyrics/models/lyrics-lstm/<version>/config.json
s3://bakinglyrics/models/lyrics-lstm/<version>/samples.md
s3://bakinglyrics/models/lyrics-lstm/latest.json
```

`latest.json` is written last by `python -m ml.publish`:

```json
{
 "name": "lyrics-lstm",
 "version": "2026.11.0",
 "prefix": "models/lyrics-lstm/2026.11.0/",
 "format_version": 1,
 "created_at": "2026-11-22T10:00:00Z",
 "published_at": "2026-11-22T11:00:00Z",
 "files": {"model.onnx": {"bytes": 104857600, "sha256": "..."}, "...": {}},
 "metrics": {"best_val_ppl": 0.0, "test_ppl": 0.0}
}
```

Suggested loading in the API: read `latest.json` (or use a pinned `MODEL_VERSION`), download every file of `prefix` to `/tmp/lyrics-lstm/<version>/` on cold start, check the sha256 values from `files`, then `LyricsGenerator.from_bundle(path)`.
Versions are immutable: `ml.publish` refuses to overwrite an existing version unless `--overwrite` is passed.

## model.onnx interface

One decoding step for a batch (serving uses batch 1; the batch axis is dynamic, 1 to 64).

| Name | Type | Shape | Meaning |
|---|---|---|---|
| input `token` | int64 | `[batch]` | Current token id |
| input `artist` | int64 | `[batch]` | Artist id from `artists.json` (0 = unknown or any artist) |
| input `genre` | int64 | `[batch]` | Genre id from `artists.json` (0 = unknown) |
| input `state` | float32 | `[batch, S]` | Recurrent state, zeros at the start of a sequence |
| output `logits` | float32 | `[batch, V]` | Unnormalised next token scores |
| output `state_out` | float32 | `[batch, S]` | State to feed into the next step |

`S` is `config.json` `onnx.state_size`, `V` is the vocabulary size.
The state is the concatenation `[h_0, c_0, h_1, c_1, h_2, c_2]` of the LSTM layers; offsets are listed in `onnx.state_layout` (callers treat it as opaque).
The graph contains plain MatMul, Sigmoid and Tanh ops (the LSTM cell is written out), exported with the PyTorch dynamo exporter.
Export checks onnxruntime against torch on a random sequence; the max absolute logit difference is stored in `onnx.parity_max_abs_diff` and must be below `onnx.parity_atol` (1e-4).

## vocab.json

```json
{"format_version": 1, "type": "word", "lowercase": true,
 "specials": ["<pad>", "<unk>", "<bos>", "<eos>", "<line>", "<verse>", "<title>"],
 "itos": ["<pad>", "<unk>", "<bos>", "<eos>", "<line>", "<verse>", "<title>", "you", "i", "the", "..."]}
```

Token id = position in `itos`. The special ids are fixed: pad 0, unk 1, bos 2, eos 3, line 4, verse 5, title 6.
Text is lowercased; words keep inner apostrophes; `, . ! ? ; : - '` are separate tokens; `<line>` is a newline and `<verse>` a blank line.
A training sequence is `<bos> lyrics <title> title <eos>`, so the same model writes a title after the lyrics.

## artists.json

```json
{"format_version": 1, "unknown_artist_id": 0, "unknown_genre_id": 0,
 "genres": {"Country": 1, "Hip-Hop": 2, "Pop": 3, "Rock": 4},
 "artists": {"bee-gees": {"id": 3, "display_name": "Bee Gees", "genre": "Pop", "genre_id": 3, "songs": 150}}}
```

Keys are the Kaggle artist slugs, which are also the `name` of the artists seeded into the API catalog from the same `catalog.csv`.
`display_name` follows the rule of `baking.refresh_database` (`slug.replace("-", " ").title()`).
Unknown artists use id 0: the model was trained with 10 percent of the artist ids replaced by 0, so 0 means "generic style".

## config.json (main keys)

| Key | Content |
|---|---|
| `format_version` | 1; `from_bundle` refuses other values |
| `name`, `version`, `created_at` | Bundle identity |
| `onnx` | `file`, `exporter`, `opset`, `torch_version`, `inputs`, `outputs`, `state_size`, `state_layout`, `parity_max_abs_diff`, `parity_atol` |
| `model` | `ModelConfig` fields (vocab size, embedding sizes, hidden size, layers, dropouts) and `parameters` |
| `tokenizer` | Type, lowercase flag, vocab size, specials, sequence layout |
| `training` | Training config, metrics (`best_val_ppl`, `test_ppl`, epochs, steps, train time, device) |
| `data` | Source file, song, artist and genre counts, splits, `data_sha256` of the prepared data, prep settings |
| `sampling` | Default `SamplingConfig` used by `LyricsGenerator` |
| `files` | `bytes` and `sha256` of every other file in the bundle |

## Python API (ml/generate.py)

```python
from ml.generate import LyricsGenerator, SamplingConfig, Generation

gen = LyricsGenerator.from_bundle(bundle_dir: str | Path, threads: int | None = None)

gen.generate(
    artist: str | None = None,       # slug or display name, case-insensitive; unknown -> generic style
    seed_text: str = "",             # prompt, included at the start of the lyrics
    number_words: int = 150,         # generated words (seed not counted); stops at the next line end
    *, seed: int | None = None,      # same seed + same inputs -> same output
    genre: str | None = None,        # optional genre override (a key of artists.json "genres")
    with_title: bool = True,
    sampling: SamplingConfig | None = None,
    **overrides,                     # any SamplingConfig field, e.g. temperature=0.8
) -> Generation  # .lyrics (str, newlines), .title, .artist (slug or None), .words, .token_ids, .title_ids, .seed

gen.generate_title(lyrics: str, artist: str | None = None, *, seed: int | None = None,
                   genre: str | None = None, max_lyrics_tokens: int = 400, sampling=None, **overrides) -> str

gen.resolve_artist(artist, genre=None) -> tuple[slug | None, artist_id, genre_id]
gen.artist_slugs -> list[str]
```

`SamplingConfig` defaults: temperature 0.9, top_k 50, top_p 0.95, repetition_penalty 1.2 over the last 64 tokens, at most 2 identical words in a row, title temperature 0.7, at most 8 title words, title copy bonus 1.0 (words from the lyrics are favoured in the title), `<unk>` never sampled.
`LyricsGenerator` is not thread safe (it reuses input buffers); use one instance per worker, which is the Lambda model.
Cost: one ONNX run per token, including the prompt; a 150 word song is about 200 to 250 steps. Measured with the full size model (99 MB, 25 M parameters) on a laptop CPU: 0.2 s session load, 7.5 ms per step on one thread, about 1.4 s for 150 words; expect roughly 2x on a 1 vCPU Lambda, so 2 GB memory and a 30 s timeout leave ample room.

## Compatibility

Any change to the ONNX inputs or outputs, the vocab format or the artists format bumps `format_version`, and `ml/generate.py` must accept the new value before such a bundle is published.
