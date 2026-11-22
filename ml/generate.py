"""Lyrics and title generation from an exported model bundle (numpy + onnxruntime only, no torch).

The API imports this module at serving time:

    from ml.generate import LyricsGenerator

    gen = LyricsGenerator.from_bundle("/tmp/lyrics-lstm/2026.11.0")
    result = gen.generate(artist="bee-gees", seed_text="night fever", number_words=120, seed=7)
    result.lyrics, result.title
    gen.generate_title("Some lyrics\\nover two lines", artist="bee-gees", seed=7)

The decoding loop runs one ONNX step per token with the recurrent state passed explicitly (see ml/BUNDLE.md).
Anything that implements the `Stepper` protocol can drive the loop, which is how training reuses it with torch.

CLI:
    python -m ml.generate <bundle_dir> --artist bee-gees --seed-text "night fever" --words 120 --seed 7
"""

from __future__ import annotations

import argparse
import json
import string
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

import numpy as np

from ml.tokenizer import Tokenizer

BUNDLE_FORMAT_VERSION = 1


@dataclass(frozen=True)
class SamplingConfig:
    temperature: float = 0.9  # <= 0 means greedy
    top_k: int = 50  # 0 disables
    top_p: float = 0.95  # 1.0 disables
    repetition_penalty: float = 1.2  # CTRL style, applied to words seen in the last `repetition_window` tokens
    repetition_window: int = 64
    max_repeat_run: int = 2  # the same word at most this many times in a row ("kill kill kill kill")
    title_temperature: float = 0.7
    max_title_words: int = 8
    title_copy_bonus: float = 1.0  # logit bonus for title words that appear in the lyrics (titles often quote them)
    extra_words: int = 15  # after the budget, words allowed while waiting for a line end


@dataclass
class Generation:
    lyrics: str
    title: str | None
    artist: str | None
    words: int
    token_ids: list[int] = field(default_factory=list)
    title_ids: list[int] = field(default_factory=list)
    seed: int | None = None


class Stepper(Protocol):
    """One decoding step: feed `token_id`, get next-token logits (float32 [vocab]) and the new state."""

    def initial_state(self) -> np.ndarray: ...

    def step(self, token_id: int, artist_id: int, genre_id: int, state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ...


class OnnxStepper:
    """Runs `model.onnx` with onnxruntime on CPU. Inputs/outputs are described in ml/BUNDLE.md."""

    def __init__(self, model_path: str | Path, state_size: int, threads: int | None = None):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
            opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self.state_size = int(state_size)
        self._token = np.zeros((1,), dtype=np.int64)
        self._artist = np.zeros((1,), dtype=np.int64)
        self._genre = np.zeros((1,), dtype=np.int64)

    def initial_state(self) -> np.ndarray:
        return np.zeros((1, self.state_size), dtype=np.float32)

    def step(self, token_id: int, artist_id: int, genre_id: int, state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self._token[0] = token_id
        self._artist[0] = artist_id
        self._genre[0] = genre_id
        logits, new_state = self.session.run(
            ["logits", "state_out"],
            {"token": self._token, "artist": self._artist, "genre": self._genre, "state": state},
        )
        return logits[0], new_state


# Sampling ---------------------------------------------------------------------------------------------


def process_logits(
    logits: np.ndarray,
    history: Sequence[int],
    cfg: SamplingConfig,
    forbidden: Iterable[int] = (),
    exempt: frozenset[int] = frozenset(),
    temperature: float | None = None,
) -> np.ndarray:
    """Turn raw logits into a probability vector (float64) after penalties, masking, temperature, top-k, top-p."""
    x = np.asarray(logits, dtype=np.float64).copy()
    forbidden = list(forbidden)
    if forbidden:
        x[forbidden] = -np.inf
    if cfg.repetition_penalty != 1.0 and history:
        recent = {int(t) for t in history[-cfg.repetition_window:]} - exempt
        if recent:
            ids = np.fromiter(recent, dtype=np.int64)
            vals = x[ids]
            x[ids] = np.where(vals > 0, vals / cfg.repetition_penalty, vals * cfg.repetition_penalty)
    temp = cfg.temperature if temperature is None else temperature
    if temp <= 0:
        probs = np.zeros_like(x)
        probs[int(np.argmax(x))] = 1.0
        return probs
    x = x / temp
    if cfg.top_k and 0 < cfg.top_k < x.size:
        kth = np.partition(x, -cfg.top_k)[-cfg.top_k]
        x[x < kth] = -np.inf
    x -= np.max(x)
    probs = np.exp(x)
    probs /= probs.sum()
    if 0 < cfg.top_p < 1.0:
        order = np.argsort(-probs, kind="stable")
        cum = np.cumsum(probs[order])
        cut = int(np.searchsorted(cum, cfg.top_p)) + 1
        keep = np.zeros_like(probs, dtype=bool)
        keep[order[:cut]] = True
        probs = np.where(keep, probs, 0.0)
        probs /= probs.sum()
    return probs


def sample(probs: np.ndarray, rng: np.random.Generator) -> int:
    cum = np.cumsum(probs)
    return int(min(np.searchsorted(cum, rng.random() * cum[-1], side="right"), probs.size - 1))


# Generator ------------------------------------------------------------------------------------------


class LyricsGenerator:
    def __init__(self, stepper: Stepper, tokenizer: Tokenizer, artists: dict, config: dict | None = None):
        self.stepper = stepper
        self.tok = tokenizer
        self.artists_meta = artists
        self.config = config or {}
        self.sampling = SamplingConfig(**{k: v for k, v in self.config.get("sampling", {}).items()
                                          if k in SamplingConfig.__dataclass_fields__})
        self._by_name: dict[str, str] = {}
        for slug, info in artists.get("artists", {}).items():
            self._by_name[slug.lower()] = slug
            self._by_name[str(info.get("display_name", slug)).lower()] = slug
        t = tokenizer
        self._lyrics_forbidden = [t.pad_id, t.unk_id, t.bos_id, t.eos_id, t.title_id]
        self._title_forbidden = [t.pad_id, t.unk_id, t.bos_id, t.title_id, t.line_id, t.verse_id]
        self._exempt = frozenset(t.special_ids | t.punct_ids)

    # Loading ----------------------------------------------------------------------------------------

    @classmethod
    def from_bundle(cls, bundle_dir: str | Path, threads: int | None = None) -> LyricsGenerator:
        root = Path(bundle_dir)
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        if config.get("format_version") != BUNDLE_FORMAT_VERSION:
            raise ValueError(f"unsupported bundle format {config.get('format_version')!r}")
        tokenizer = Tokenizer.load(root / "vocab.json")
        artists = json.loads((root / "artists.json").read_text(encoding="utf-8"))
        stepper = OnnxStepper(root / "model.onnx", config["onnx"]["state_size"], threads=threads)
        return cls(stepper, tokenizer, artists, config)

    # Artists ----------------------------------------------------------------------------------------

    @property
    def artist_slugs(self) -> list[str]:
        return list(self.artists_meta.get("artists", {}))

    def resolve_artist(self, artist: str | None, genre: str | None = None) -> tuple[str | None, int, int]:
        """Map an artist slug or display name (case-insensitive) to (slug, artist_id, genre_id).

        Unknown or empty artists use the "unknown" ids (0), which the model was trained with as a generic style.
        `genre` (a genre name from artists.json) overrides the artist's genre.
        """
        meta = self.artists_meta
        slug = self._by_name.get(str(artist).strip().lower()) if artist else None
        if slug is None and artist:
            slug = self._by_name.get(str(artist).strip().lower().replace(" ", "-"))
        artist_id = meta["artists"][slug]["id"] if slug else meta.get("unknown_artist_id", 0)
        genre_id = meta["artists"][slug]["genre_id"] if slug else meta.get("unknown_genre_id", 0)
        if genre:
            genres = {k.lower(): v for k, v in meta.get("genres", {}).items()}
            genre_id = genres.get(genre.strip().lower(), genre_id)
        return slug, int(artist_id), int(genre_id)

    # Decoding ---------------------------------------------------------------------------------------

    def _feed(self, ids: Sequence[int], artist_id: int, genre_id: int, state: np.ndarray):
        logits = None
        for i in ids:
            logits, state = self.stepper.step(int(i), artist_id, genre_id, state)
        return logits, state

    def _title(self, state, lyric_ids, artist_id, genre_id, rng, cfg: SamplingConfig) -> list[int]:
        t = self.tok
        logits, state = self.stepper.step(t.title_id, artist_id, genre_id, state)
        copy_ids = np.fromiter({int(i) for i in lyric_ids} - self._exempt, dtype=np.int64)
        out: list[int] = []
        while len(out) < cfg.max_title_words:
            forbidden = list(self._title_forbidden)
            if not out:
                forbidden += [t.eos_id, *t.punct_ids]
            if cfg.title_copy_bonus and copy_ids.size:
                logits = np.array(logits, dtype=np.float32)
                logits[copy_ids] += cfg.title_copy_bonus
            probs = process_logits(logits, out, cfg, forbidden, self._exempt, temperature=cfg.title_temperature)
            nxt = sample(probs, rng)
            if nxt == t.eos_id:
                break
            out.append(nxt)
            logits, state = self.stepper.step(nxt, artist_id, genre_id, state)
        return out

    def render_title(self, ids: Sequence[int]) -> str:
        return string.capwords(self.tok.decode(ids, capitalise=False)).strip(" ,.;:-'")

    def generate(
        self,
        artist: str | None = None,
        seed_text: str = "",
        number_words: int = 150,
        *,
        seed: int | None = None,
        genre: str | None = None,
        with_title: bool = True,
        sampling: SamplingConfig | None = None,
        **overrides,
    ) -> Generation:
        """Generate lyrics (and a title) in the style of `artist`, continuing `seed_text`.

        `number_words` counts generated words (the seed text is not counted); generation stops at the first line
        end after the budget, or `extra_words` later at the latest. `overrides` are SamplingConfig fields.
        """
        cfg = replace(sampling or self.sampling, **overrides)
        rng = np.random.default_rng(seed)
        t = self.tok
        slug, artist_id, genre_id = self.resolve_artist(artist, genre)
        prompt = t.encode(seed_text) if seed_text else []
        logits, state = self._feed([t.bos_id, *prompt], artist_id, genre_id, self.stepper.initial_state())
        out: list[int] = list(prompt)
        words = 0
        boundary = {t.line_id, t.verse_id}
        hard_cap = number_words + cfg.extra_words
        max_tokens = 4 * hard_cap + 64
        while len(out) < max_tokens:
            forbidden = list(self._lyrics_forbidden)
            if not out or out[-1] in boundary:
                forbidden += [t.line_id, t.verse_id]
            run = out[-cfg.max_repeat_run:] if cfg.max_repeat_run else []
            if run and len(run) == cfg.max_repeat_run and len(set(run)) == 1 and run[0] not in self._exempt:
                forbidden.append(run[0])
            probs = process_logits(logits, out, cfg, forbidden, self._exempt)
            nxt = sample(probs, rng)
            if nxt in boundary and words >= number_words:
                break
            out.append(nxt)
            logits, state = self.stepper.step(nxt, artist_id, genre_id, state)
            if nxt not in self._exempt:
                words += 1
                if words >= hard_cap:
                    break
        while out and out[-1] in boundary:
            out.pop()
        title_ids = self._title(state, out, artist_id, genre_id, rng, cfg) if with_title else []
        title = self.render_title(title_ids) if with_title else None
        if with_title and not title:
            title = string.capwords(" ".join(t.decode(out).split()[:4]))
        return Generation(lyrics=t.decode(out), title=title, artist=slug, words=words, token_ids=out,
                          title_ids=title_ids, seed=seed)

    def generate_title(
        self,
        lyrics: str,
        artist: str | None = None,
        *,
        seed: int | None = None,
        genre: str | None = None,
        max_lyrics_tokens: int = 400,
        sampling: SamplingConfig | None = None,
        **overrides,
    ) -> str:
        """Generate a title for existing lyrics: feed `<bos> lyrics` then `<title>` and sample until `<eos>`.

        Words that occur in the lyrics get `title_copy_bonus` (the 2018 titler notebooks found most titles quote
        the lyrics).
        """
        cfg = replace(sampling or self.sampling, **overrides)
        rng = np.random.default_rng(seed)
        t = self.tok
        _, artist_id, genre_id = self.resolve_artist(artist, genre)
        ids = t.encode(lyrics)[:max_lyrics_tokens]
        _, state = self._feed([t.bos_id, *ids], artist_id, genre_id, self.stepper.initial_state())
        title = self.render_title(self._title(state, ids, artist_id, genre_id, rng, cfg))
        return title or string.capwords(" ".join(t.decode(ids).split()[:4]))


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate lyrics from a model bundle")
    p.add_argument("bundle")
    p.add_argument("--artist", default=None)
    p.add_argument("--genre", default=None)
    p.add_argument("--seed-text", default="")
    p.add_argument("--words", type=int, default=120)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--top-p", type=float, default=None)
    p.add_argument("--repetition-penalty", type=float, default=None)
    p.add_argument("--list-artists", action="store_true")
    args = p.parse_args(list(argv) if argv is not None else None)

    gen = LyricsGenerator.from_bundle(args.bundle)
    if args.list_artists:
        print("\n".join(gen.artist_slugs))
        return 0
    overrides = {k: v for k, v in {"temperature": args.temperature, "top_k": args.top_k, "top_p": args.top_p,
                                    "repetition_penalty": args.repetition_penalty}.items() if v is not None}
    for i in range(args.count):
        seed = None if args.seed is None else args.seed + i
        res = gen.generate(args.artist, args.seed_text, args.words, seed=seed, genre=args.genre, **overrides)
        print(f"# {res.title}  ({res.artist or 'any artist'}, {res.words} words, seed {seed})\n")
        print(res.lyrics + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["Generation", "LyricsGenerator", "OnnxStepper", "SamplingConfig", "Stepper", "process_logits", "sample"]
