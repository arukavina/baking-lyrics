import json

import pytest

from ml.tokenizer import (
    BOS,
    EOS,
    LINE,
    SPECIALS,
    TITLE,
    VERSE,
    Tokenizer,
    detokenize,
    normalise_text,
    title_from_slug,
    tokenize,
)

SONG = "Oh baby, how you doing?\nI'm goin' down 'cause it's late\n\n\nSecond verse: here we go!"


def test_tokenize_splits_words_punctuation_and_lines():
    assert tokenize(SONG) == [
        "oh", "baby", ",", "how", "you", "doing", "?", LINE,
        "i'm", "goin'", "down", "'cause", "it's", "late", VERSE,
        "second", "verse", ":", "here", "we", "go", "!",
    ]


def test_tokenize_without_lines_drops_structure():
    assert LINE not in tokenize(SONG, lines=False)
    assert VERSE not in tokenize(SONG, lines=False)


def test_typographic_quotes_and_dashes_are_folded():
    text = "don" + chr(0x2019) + "t stop " + chr(0x2014) + " " + chr(0x201C) + "now" + chr(0x201D)
    assert tokenize(text) == ["don't", "stop", "-", "now"]


def test_hyphenated_words_are_split_and_symbols_dropped():
    assert tokenize("la-la-la (yeah) [chorus] #1") == ["la", "la", "la", "yeah", "chorus", "1"]


def test_detokenize_renders_lines_verses_and_capitals():
    assert detokenize(tokenize(SONG)) == "Oh baby, how you doing?\nI'm goin' down 'cause it's late\n\nSecond verse: here we go!"


def test_detokenize_skips_other_specials_and_empty_lines():
    assert detokenize([BOS, "hi", LINE, LINE, VERSE, VERSE, "i", "know", TITLE, EOS]) == "Hi\n\nI know"


def test_normalise_text_keeps_single_blank_line_between_stanzas():
    assert normalise_text("  a   b \r\n\r\n\r\n c\t d \n") == "a b\n\nc d"


def test_build_orders_by_frequency_and_respects_limits():
    tok = Tokenizer.build(["b b b a a c", "b a d"], max_size=len(SPECIALS) + 2, min_freq=2)
    assert tok.itos[: len(SPECIALS)] == list(SPECIALS)
    assert tok.itos[len(SPECIALS):] == ["b", "a"]
    assert tok.encode("c") == [tok.unk_id]


def test_encode_song_layout_and_truncation_keeps_title():
    tok = Tokenizer.build([SONG, "my title"], min_freq=1)
    ids = tok.encode_song(SONG, "my title")
    assert ids[0] == tok.bos_id and ids[-1] == tok.eos_id
    assert list(ids).count(tok.title_id) == 1
    short = tok.encode_song(SONG, "my title", max_len=8)
    assert len(short) == 8
    assert tok.ids_to_tokens(short[-4:]) == [TITLE, "my", "title", EOS]


def test_round_trip_through_json(tmp_path):
    tok = Tokenizer.build([SONG], min_freq=1)
    path = tmp_path / "vocab.json"
    tok.save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format_version"] == 1 and data["specials"] == list(SPECIALS)
    loaded = Tokenizer.load(path)
    assert loaded.itos == tok.itos
    assert loaded.decode(loaded.encode(SONG)) == detokenize(tokenize(SONG))


def test_rejects_bad_vocab():
    with pytest.raises(ValueError):
        Tokenizer(["a", "b"])
    with pytest.raises(ValueError):
        Tokenizer.from_dict({"format_version": 99, "itos": list(SPECIALS)})


def test_count_words_ignores_specials_and_punctuation():
    tok = Tokenizer.build([SONG], min_freq=1)
    assert tok.count_words(tok.encode("oh, baby!")) == 2
    assert tok.count_words(tok.encode("oh, baby!\nhow")) == 3


def test_title_from_slug():
    assert title_from_slug("ego-remix") == "ego remix"


def test_tokenizer_module_does_not_import_torch():
    import ml.tokenizer as mod

    assert "import torch" not in open(mod.__file__, encoding="utf-8").read()
