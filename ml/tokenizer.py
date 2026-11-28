"""Word level tokenizer shared by training and serving.

Pure Python plus numpy: no torch, no pickles. The vocabulary is stored as JSON (`vocab.json`).

Text model:
- lowercase, unicode NFKC, curly quotes folded to ASCII;
- words keep inner apostrophes ("don't", "i'm") and a few common elisions ("'cause", "goin'");
- the punctuation marks , . ! ? ; : - and ' become their own tokens, every other symbol is dropped;
- a line break becomes `<line>`, a blank line (stanza break) becomes `<verse>`.

A training sequence for one song is `<bos> lyrics <title> title <eos>`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np

PAD = "<pad>"
UNK = "<unk>"
BOS = "<bos>"
EOS = "<eos>"
LINE = "<line>"
VERSE = "<verse>"
TITLE = "<title>"
SPECIALS: tuple[str, ...] = (PAD, UNK, BOS, EOS, LINE, VERSE, TITLE)

PUNCTUATION = frozenset(",.!?;:-'")
_NO_SPACE_BEFORE = frozenset(",.!?;:")

# Typographic quotes, dashes and ellipsis folded to ASCII (code points, so the source stays ASCII).
_QUOTES = str.maketrans(
    {chr(cp): "'" for cp in (0x2018, 0x2019, 0x201B, 0x2032, 0x60, 0xB4)}
    | {chr(cp): '"' for cp in (0x201C, 0x201D)}
    | {chr(cp): "-" for cp in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015)}
    | {chr(0x2026): "..."}
)

_TOKEN_RE = re.compile(
    r"'(?:cause|cuz|cos|em|til|till|bout|round|n)(?![a-z0-9])"  # leading elisions
    r"|[a-z0-9]+(?:'[a-z0-9]+)*(?:(?<=in)'(?![a-z0-9]))?"  # words, contractions, g-dropping ("goin'")
    r"|[,.!?;:'\-]"  # kept punctuation
)
_DASHES_RE = re.compile(r"-{2,}")
_HYPHEN_RE = re.compile(r"(?<=[^\W_])-(?=[^\W_])")
_SPACES_RE = re.compile(r"[ \t\f\v]+")

# Words rendered with a capital first letter when decoding.
_ALWAYS_CAPITALISED = {"i", "i'm", "i'll", "i'd", "i've"}

VOCAB_FORMAT_VERSION = 1


def normalise_text(text: str) -> str:
    """Unicode and whitespace normalisation that keeps line structure (used by data prep and the tokenizer)."""
    text = unicodedata.normalize("NFKC", str(text)).translate(_QUOTES)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    blank = False
    for line in lines:
        if line:
            if blank and out:
                out.append("")
            out.append(line)
            blank = False
        else:
            blank = True
    return "\n".join(out)


def tokenize_line(line: str) -> list[str]:
    """Split one line of text into word and punctuation tokens."""
    line = _HYPHEN_RE.sub(" ", line.lower())  # "well-known" -> "well known", "la-la" -> "la la"
    line = _DASHES_RE.sub(" - ", line)
    return _TOKEN_RE.findall(line)


def tokenize(text: str, lines: bool = True) -> list[str]:
    """Split text into tokens, with `<line>` and `<verse>` between lines and stanzas when `lines` is True."""
    text = normalise_text(text)
    tokens: list[str] = []
    pending: str | None = None
    for raw in text.split("\n"):
        if not raw:
            pending = VERSE
            continue
        words = tokenize_line(raw)
        if not words:
            continue
        if tokens:
            if lines:
                tokens.append(pending or LINE)
        tokens.extend(words)
        pending = None
    return tokens


def detokenize(tokens: Iterable[str], capitalise: bool = True) -> str:
    """Render tokens back to text: `<line>` is a newline, `<verse>` a blank line, other specials are dropped."""
    lines: list[list[str] | None] = [[]]
    for tok in tokens:
        if tok == LINE:
            lines.append([])
        elif tok == VERSE:
            lines.extend([None, []])
        elif tok in SPECIALS:
            continue
        else:
            lines[-1].append(tok)  # type: ignore[union-attr]
    out: list[str] = []
    for words in lines:
        if words is None:
            if out and out[-1] != "":
                out.append("")
            continue
        text = _join_words(words)
        if not text:
            continue
        out.append(text[0].upper() + text[1:] if capitalise else text)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def _join_words(words: Sequence[str]) -> str:
    parts: list[str] = []
    for word in words:
        shown = word.capitalize() if word in _ALWAYS_CAPITALISED else word
        if parts and (word in _NO_SPACE_BEFORE or word == "'"):
            parts[-1] += shown
        else:
            parts.append(shown)
    return " ".join(parts)


def title_from_slug(slug: str) -> str:
    """Kaggle song names are slugs ("ego-remix"); turn them into plain title text ("ego remix")."""
    return re.sub(r"[-_]+", " ", str(slug)).strip()


class Tokenizer:
    """Word level vocabulary with JSON persistence."""

    def __init__(self, itos: Sequence[str], lowercase: bool = True):
        itos = list(itos)
        if tuple(itos[: len(SPECIALS)]) != SPECIALS:
            raise ValueError(f"vocabulary must start with the special tokens {SPECIALS}")
        if len(set(itos)) != len(itos):
            raise ValueError("vocabulary contains duplicates")
        self.itos: list[str] = itos
        self.stoi: dict[str, int] = {tok: i for i, tok in enumerate(itos)}
        self.lowercase = lowercase
        self.pad_id = self.stoi[PAD]
        self.unk_id = self.stoi[UNK]
        self.bos_id = self.stoi[BOS]
        self.eos_id = self.stoi[EOS]
        self.line_id = self.stoi[LINE]
        self.verse_id = self.stoi[VERSE]
        self.title_id = self.stoi[TITLE]
        self.special_ids = frozenset(range(len(SPECIALS)))
        self.punct_ids = frozenset(self.stoi[p] for p in PUNCTUATION if p in self.stoi)

    def __len__(self) -> int:
        return len(self.itos)

    # Building -----------------------------------------------------------------------------------

    @classmethod
    def build(cls, texts: Iterable[str], max_size: int = 30000, min_freq: int = 3) -> Tokenizer:
        """Build a vocabulary from texts (already tokenizable strings). `max_size` includes the specials."""
        counts: Counter[str] = Counter()
        for text in texts:
            counts.update(tok for tok in tokenize(text, lines=False))
        return cls.from_counts(counts, max_size=max_size, min_freq=min_freq)

    @classmethod
    def from_counts(cls, counts: Counter[str], max_size: int = 30000, min_freq: int = 3) -> Tokenizer:
        words = [w for w, c in counts.items() if c >= min_freq and w not in SPECIALS]
        words.sort(key=lambda w: (-counts[w], w))
        budget = max(0, max_size - len(SPECIALS))
        return cls(list(SPECIALS) + words[:budget])

    # Encoding -----------------------------------------------------------------------------------

    def tokens_to_ids(self, tokens: Iterable[str]) -> list[int]:
        unk = self.unk_id
        return [self.stoi.get(tok, unk) for tok in tokens]

    def ids_to_tokens(self, ids: Iterable[int]) -> list[str]:
        return [self.itos[int(i)] for i in ids]

    def encode(self, text: str, lines: bool = True) -> list[int]:
        return self.tokens_to_ids(tokenize(text, lines=lines))

    def decode(self, ids: Iterable[int], capitalise: bool = True) -> str:
        return detokenize(self.ids_to_tokens(ids), capitalise=capitalise)

    def encode_song(self, lyrics: str, title: str | None = None, max_len: int | None = None) -> np.ndarray:
        """`<bos> lyrics [<title> title] <eos>` as int32. Long lyrics are truncated, the title is always kept."""
        body = self.encode(lyrics)
        tail: list[int] = []
        if title is not None:
            tail = [self.title_id] + self.encode(title, lines=False)[:16]
        tail.append(self.eos_id)
        if max_len is not None:
            room = max_len - 1 - len(tail)
            if room < 1:
                raise ValueError("max_len too small for the title")
            body = body[:room]
        return np.asarray([self.bos_id] + body + tail, dtype=np.int32)

    def count_words(self, ids: Iterable[int]) -> int:
        """Number of real words (not specials, not punctuation) in ids."""
        skip = self.special_ids | self.punct_ids
        return sum(1 for i in ids if int(i) not in skip)

    # Persistence --------------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "format_version": VOCAB_FORMAT_VERSION,
            "type": "word",
            "lowercase": self.lowercase,
            "specials": list(SPECIALS),
            "itos": self.itos,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> Tokenizer:
        if data.get("format_version") != VOCAB_FORMAT_VERSION:
            raise ValueError(f"unsupported vocab format {data.get('format_version')!r}")
        return cls(data["itos"], lowercase=data.get("lowercase", True))

    @classmethod
    def load(cls, path: str | Path) -> Tokenizer:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
