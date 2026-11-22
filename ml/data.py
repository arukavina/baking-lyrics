"""Dataset preparation for the lyrics model.

Input: the Kaggle "380,000 lyrics from MetroLyrics" dataset (gyani95, version 2), columns
`index,song,year,artist,genre,lyrics`, or any local CSV with that schema (an extra leading unnamed index
column, as in the "*_cleaned_lyrics.csv" derivatives, is detected and dropped).

Output directory (default `ml/data/processed`):
- `songs.parquet`: cleaned songs with `split` (train/val/test, by song), `artist_id`, `genre_id`, `title`;
- `catalog.csv`: the same songs in the original Kaggle schema, for `python -m baking.refresh_database --data`;
- `artists.json`: artist slug -> {id, display_name, genre, genre_id, songs} plus the genre ids;
- `prep_meta.json`: the preparation settings, counts and a content hash of the prepared data.

Usage:
    python -m ml.data --kaggle --out ml/data/processed
    python -m ml.data --csv path/to/lyrics.csv --out ml/data/processed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ml.tokenizer import normalise_text, title_from_slug

KAGGLE_HANDLE = "gyani95/380000-lyrics-from-metrolyrics/versions/2"
COLUMNS = ["index", "song", "year", "artist", "genre", "lyrics"]
ARTISTS_FORMAT_VERSION = 1
API_MAX_ARTISTS = 900  # baking.refresh_database keeps the top 900 artists of the catalog

_ANNOTATION_RE = re.compile(r"\[[^\]\n]*\]|<[^>\n]*>|\{[^}\n]*\}")
_SECTION_LINE_RE = re.compile(
    r"^\(?(chorus|verse|bridge|intro|outro|hook|refrain|pre-?chorus|post-?chorus|interlude|repeat)"
    r"(\s*\d+)?\s*(x\s*\d+)?\)?\s*:?\s*$",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"tekst|lyrics (are )?not available|we (do not|don't) have the lyrics|^\W*instrumental\W*$",
    re.IGNORECASE,
)
_I_FORMS = {"I", "I'm", "I'll", "I'd", "I've", "I'ma"}
_EN_STOPWORDS = frozenset(
    "the a an and or but if of to in on at for with from by is are was were be been am i you he she it we they "
    "me my your his her our their this that these those not no do don't i'm it's what when where how all so "
    "just can will would could like love know oh yeah baby got get go come up down out now never ever".split()
)


@dataclass
class PrepConfig:
    max_artists: int = 900
    min_songs: int = 20
    max_songs_per_artist: int = 150
    min_words: int = 30
    max_words: int = 1200
    val_frac: float = 0.05
    test_frac: float = 0.05
    seed: int = 1234
    lang_detector: str = "auto"  # auto | fasttext | heuristic | none
    line_mode: str = "auto"  # auto | newlines | heuristic | none
    artists: list[str] = field(default_factory=list)  # explicit artist slugs (overrides the top-N choice)


# Loading ------------------------------------------------------------------------------------------


def download_kaggle(dest_dir: str | Path | None = None, handle: str = KAGGLE_HANDLE) -> Path:
    """Download the Kaggle dataset with kagglehub and return the path of `lyrics.csv`.

    Credentials (any one): env `KAGGLE_API_TOKEN`, a Colab secret `KAGGLE_API_TOKEN`, `~/.kaggle/access_token`,
    legacy `~/.kaggle/kaggle.json` or legacy env `KAGGLE_USERNAME` + `KAGGLE_KEY`.
    """
    import kagglehub

    kwargs = {"output_dir": str(dest_dir)} if dest_dir else {}
    root = Path(kagglehub.dataset_download(handle, **kwargs))
    candidates = sorted(root.rglob("*.csv")) + sorted(root.rglob("*.zip"))
    if not candidates:
        raise FileNotFoundError(f"no CSV found in {root}")
    return max(candidates, key=lambda p: p.stat().st_size)


def read_lyrics_csv(path: str | Path) -> pd.DataFrame:
    """Read a lyrics CSV (or a zip holding one) and return the 6 Kaggle columns, in order."""
    df = pd.read_csv(path, dtype={"lyrics": "string", "song": "string", "artist": "string", "genre": "string"},
                     keep_default_na=False, na_values=[""], low_memory=False)
    unnamed = [c for c in df.columns if not str(c).strip() or str(c).startswith("Unnamed")]
    df = df.drop(columns=unnamed)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; found {list(df.columns)}")
    return df[COLUMNS].copy()


# Cleaning -----------------------------------------------------------------------------------------


def is_placeholder(text: str) -> bool:
    """Lyrics that are not lyrics: Polish "tekst" placeholders, "instrumental", "not available" notes."""
    if "tekst piosenki" in text[:200].lower():
        return True
    return len(text) < 400 and bool(_PLACEHOLDER_RE.search(text))


def restore_lines(text: str) -> str:
    """Heuristic line breaks for lyrics flattened onto one line.

    In the flattened MetroLyrics derivatives every original line starts with a capital letter while words inside a
    line are mostly lowercase, so a capitalised word (other than "I" forms) starts a new line. Lines keep at least
    two words and a run of capitalised words stays together. Texts that are almost all lowercase or all capitals
    are left as one line. Lines that really started with "I" are merged into the previous line (accepted loss).
    """
    words = text.split()
    if len(words) < 8:
        return text
    caps = [w[:1].isupper() and w not in _I_FORMS for w in words]
    ratio = sum(caps) / len(words)
    if ratio < 0.03 or ratio > 0.6:
        return text
    lines: list[list[str]] = [[]]
    prev_cap = False
    for word, cap in zip(words, caps, strict=True):
        # A run of capitalised words ("New York", "L A") is a name, not a new line each.
        if cap and not prev_cap and len(lines[-1]) >= 2:
            lines.append([])
        lines[-1].append(word)
        prev_cap = cap
    return "\n".join(" ".join(line) for line in lines)


def clean_lyrics(text: object, line_mode: str = "auto", min_words: int = 30, max_words: int = 1200) -> str | None:
    """Return cleaned lyrics, or None when the song should be dropped."""
    if text is None or (isinstance(text, float) and np.isnan(text)) or text is pd.NA:
        return None
    text = normalise_text(str(text))
    if not text or is_placeholder(text):
        return None
    text = _ANNOTATION_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if not _SECTION_LINE_RE.match(ln)]
    text = normalise_text("\n".join(lines))
    if line_mode == "none":
        text = " ".join(text.split())
    elif line_mode == "heuristic" or (line_mode == "auto" and "\n" not in text):
        text = restore_lines(" ".join(text.split()))
    n_words = len(text.split())
    if n_words < min_words or n_words > max_words:
        return None
    letters = [c for c in text if c.isalpha()]
    if not letters or sum(1 for c in letters if not c.isascii()) / len(letters) > 0.1:
        return None
    return text


class LanguageFilter:
    """English detection: fastText lid.176 through fast-langdetect when available, else a stopword heuristic."""

    def __init__(self, mode: str = "auto", min_score: float = 0.5):
        self.mode = mode
        self.min_score = min_score
        self._detector = None
        if mode in ("auto", "fasttext"):
            try:
                from fast_langdetect import LangDetectConfig, LangDetector

                self._detector = LangDetector(LangDetectConfig(model="lite", max_input_length=None))
                self.mode = "fasttext"
            except ImportError:
                if mode == "fasttext":
                    raise
                self.mode = "heuristic"

    @staticmethod
    def _sample(text: str) -> str:
        return " ".join(text.split())[:240]

    def is_english(self, text: str) -> bool:
        if self.mode == "none":
            return True
        sample = self._sample(text)
        if self._detector is not None:
            result = self._detector.detect(sample, k=1)
            top = result[0] if result else {}
            return top.get("lang") == "en" and float(top.get("score", 0.0)) >= self.min_score
        tokens = re.findall(r"[a-z']+", sample.lower())
        return bool(tokens) and sum(t in _EN_STOPWORDS for t in tokens) / len(tokens) >= 0.25


def _dedupe_key(text: str) -> str:
    return hashlib.sha1(re.sub(r"[^a-z0-9]+", "", text.lower()).encode()).hexdigest()


def display_name(slug: str) -> str:
    """Same rule as baking.refresh_database: "beyonce-knowles" -> "Beyonce Knowles"."""
    return str(slug).strip().replace("-", " ").title()


def normalise_genre(genre: object) -> str:
    g = str(genre).strip() if genre is not None and genre is not pd.NA else ""
    return "Other" if g in ("", "nan", "Not Available") else g


def clean_frame(df: pd.DataFrame, cfg: PrepConfig, log=print) -> pd.DataFrame:
    """Apply the cleaning rules, language filter and dedupe. Returns the kept rows with cleaned lyrics."""
    n0 = len(df)
    df = df.dropna(subset=["lyrics", "artist", "song"]).copy()
    df["artist"] = df["artist"].astype(str).str.strip()
    df = df[df["artist"] != ""]
    if cfg.artists:
        df = df[df["artist"].isin(cfg.artists)]
    df["lyrics"] = [clean_lyrics(t, cfg.line_mode, cfg.min_words, cfg.max_words) for t in df["lyrics"]]
    df = df.dropna(subset=["lyrics"])
    n_clean = len(df)
    lang = LanguageFilter(cfg.lang_detector)
    df = df[[lang.is_english(t) for t in df["lyrics"]]]
    n_lang = len(df)
    df["_key"] = [_dedupe_key(t) for t in df["lyrics"]]
    df["_title_key"] = df["artist"] + "|" + df["song"].astype(str).str.lower()
    df = df.drop_duplicates("_key").drop_duplicates("_title_key").drop(columns=["_key", "_title_key"])
    df["genre"] = [normalise_genre(g) for g in df["genre"]]
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    log(f"rows: {n0} read, {n_clean} after cleaning, {n_lang} English ({lang.mode}), {len(df)} after dedupe")
    return df


def select_artists(df: pd.DataFrame, cfg: PrepConfig, log=print) -> pd.DataFrame:
    """Keep artists with >= min_songs songs (top max_artists by count) and cap songs per artist."""
    counts = df.groupby("artist").size()
    counts = counts[counts >= cfg.min_songs]
    order = sorted(counts.index, key=lambda a: (-int(counts[a]), a))[: cfg.max_artists]
    if cfg.max_artists > API_MAX_ARTISTS:
        log(f"warning: max_artists {cfg.max_artists} > {API_MAX_ARTISTS}; the API catalog seeds only the top "
            f"{API_MAX_ARTISTS}, so some model artists would not be selectable on the site")
    rng = np.random.default_rng(cfg.seed)
    parts = []
    for artist in sorted(order):
        songs = df[df["artist"] == artist].sort_values("index")
        if len(songs) > cfg.max_songs_per_artist:
            keep = np.sort(rng.choice(len(songs), cfg.max_songs_per_artist, replace=False))
            songs = songs.iloc[keep]
        parts.append(songs)
    if not parts:
        raise ValueError("no artist left after filtering; lower --min-songs or check the input")
    out = pd.concat(parts, ignore_index=True)
    log(f"artists: {len(order)} kept (>= {cfg.min_songs} songs), {len(out)} songs after capping "
        f"at {cfg.max_songs_per_artist} per artist")
    return out


def split_by_song(df: pd.DataFrame, cfg: PrepConfig) -> pd.Series:
    """Deterministic train/val/test split by song, stratified per artist (every artist keeps training songs)."""
    rng = np.random.default_rng(cfg.seed + 1)
    split = pd.Series("train", index=df.index, dtype="object")
    for artist in sorted(df["artist"].unique()):
        idx = df.index[df["artist"] == artist].to_numpy()
        idx = idx[rng.permutation(len(idx))]
        n_val = int(round(len(idx) * cfg.val_frac))
        n_test = int(round(len(idx) * cfg.test_frac))
        if n_val + n_test >= len(idx):
            n_val = n_test = 0
        split[idx[:n_val]] = "val"
        split[idx[n_val:n_val + n_test]] = "test"
    return split


def build_artists(df: pd.DataFrame) -> dict:
    genres = sorted(df["genre"].unique())
    genre_ids = {g: i + 1 for i, g in enumerate(genres)}
    artists = {}
    for i, (artist, songs) in enumerate(sorted(df.groupby("artist"), key=lambda kv: kv[0])):
        counts = songs["genre"].value_counts()
        preferred = [g for g in counts.index if g != "Other"]
        genre = preferred[0] if preferred else counts.index[0]
        artists[artist] = {"id": i + 1, "display_name": display_name(artist), "genre": genre,
                           "genre_id": genre_ids[genre], "songs": int(len(songs))}
    return {"format_version": ARTISTS_FORMAT_VERSION, "unknown_artist_id": 0, "unknown_genre_id": 0,
            "genres": genre_ids, "artists": artists}


def data_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    for row in df[["index", "artist", "split", "title", "lyrics"]].itertuples(index=False):
        h.update("\x1f".join(str(v) for v in row).encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def prepare(raw: pd.DataFrame, cfg: PrepConfig, log=print) -> tuple[pd.DataFrame, dict]:
    df = clean_frame(raw, cfg, log=log)
    df = select_artists(df, cfg, log=log)
    df["split"] = split_by_song(df, cfg)
    df["title"] = [title_from_slug(s) for s in df["song"]]
    meta = build_artists(df)
    df["artist_id"] = [meta["artists"][a]["id"] for a in df["artist"]]
    df["genre_id"] = [meta["genres"][g] for g in df["genre"]]
    df = df.sort_values(["artist", "index"]).reset_index(drop=True)
    return df, meta


def write_outputs(df: pd.DataFrame, meta: dict, out_dir: str | Path, cfg: PrepConfig, source: str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "songs.parquet", index=False)
    df[COLUMNS].to_csv(out / "catalog.csv", index=False)
    (out / "artists.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    info = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "config": asdict(cfg),
        "songs": int(len(df)),
        "artists": len(meta["artists"]),
        "genres": len(meta["genres"]),
        "splits": {k: int(v) for k, v in df["split"].value_counts().items()},
        "data_sha256": data_hash(df),
    }
    (out / "prep_meta.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="local lyrics CSV (or zip) with the Kaggle schema")
    src.add_argument("--kaggle", action="store_true", help=f"download {KAGGLE_HANDLE} with kagglehub")
    p.add_argument("--download-dir", help="where kagglehub stores the dataset (default: its cache)")
    p.add_argument("--out", default="ml/data/processed")
    d = PrepConfig()
    p.add_argument("--max-artists", type=int, default=d.max_artists)
    p.add_argument("--min-songs", type=int, default=d.min_songs)
    p.add_argument("--max-songs-per-artist", type=int, default=d.max_songs_per_artist)
    p.add_argument("--min-words", type=int, default=d.min_words)
    p.add_argument("--max-words", type=int, default=d.max_words)
    p.add_argument("--val-frac", type=float, default=d.val_frac)
    p.add_argument("--test-frac", type=float, default=d.test_frac)
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--lang-detector", choices=["auto", "fasttext", "heuristic", "none"], default=d.lang_detector)
    p.add_argument("--line-mode", choices=["auto", "newlines", "heuristic", "none"], default=d.line_mode)
    p.add_argument("--artists", default="", help="comma separated artist slugs to keep (overrides top-N)")
    args = p.parse_args(list(argv) if argv is not None else None)

    cfg = PrepConfig(
        max_artists=args.max_artists, min_songs=args.min_songs, max_songs_per_artist=args.max_songs_per_artist,
        min_words=args.min_words, max_words=args.max_words, val_frac=args.val_frac, test_frac=args.test_frac,
        seed=args.seed, lang_detector=args.lang_detector, line_mode=args.line_mode,
        artists=[a.strip() for a in args.artists.split(",") if a.strip()],
    )
    t0 = time.time()
    path = download_kaggle(args.download_dir) if args.kaggle else Path(args.csv)
    print(f"reading {path}")
    raw = read_lyrics_csv(path)
    with_newlines = float(raw["lyrics"].dropna().str.contains("\n", regex=False).mean())
    print(f"{len(raw)} rows; {with_newlines:.1%} of lyrics contain line breaks")
    if with_newlines < 0.01 and cfg.line_mode == "auto":
        print("lyrics look flattened (no line breaks): using the capitalisation heuristic to restore lines; "
              "prefer the raw Kaggle download, which keeps the original line breaks")
    df, meta = prepare(raw, cfg)
    info = write_outputs(df, meta, args.out, cfg, source=str(path.name))
    print(json.dumps({k: info[k] for k in ("songs", "artists", "genres", "splits", "data_sha256")}, indent=1))
    print(f"wrote {args.out} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
