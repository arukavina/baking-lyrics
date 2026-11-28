"""Decoding tests with a fake numpy stepper (no torch, no onnxruntime needed)."""

import numpy as np
import pytest

from ml.generate import MAX_PROMPT_TOKENS, LyricsGenerator, SamplingConfig, process_logits, sample
from ml.tokenizer import Tokenizer

WORDS = "love night baby fire dance heart rain sky road home".split()
ARTISTS = {
    "format_version": 1, "unknown_artist_id": 0, "unknown_genre_id": 0,
    "genres": {"Pop": 1, "Rock": 2},
    "artists": {"bee-gees": {"id": 1, "display_name": "Bee Gees", "genre": "Pop", "genre_id": 1, "songs": 3}},
}


class RandomStepper:
    """Logits depend on (token, artist, state) through a fixed random table; state counts steps."""

    def __init__(self, vocab: int, seed: int = 0):
        self.table = np.random.default_rng(seed).normal(size=(vocab, vocab)).astype(np.float32)
        self.calls: list[tuple[int, int, int]] = []

    def initial_state(self):
        return np.zeros((1, 1), dtype=np.float32)

    def step(self, token_id, artist_id, genre_id, state):
        self.calls.append((token_id, artist_id, genre_id))
        return self.table[token_id] + 0.5 * artist_id, state + 1


@pytest.fixture
def gen():
    tok = Tokenizer.build([" ".join(WORDS) + " , ."], min_freq=1)
    return LyricsGenerator(RandomStepper(len(tok)), tok, ARTISTS, {"sampling": {"temperature": 1.0}})


def test_same_seed_same_output(gen):
    a = gen.generate("bee-gees", "night", 40, seed=7)
    b = gen.generate("bee-gees", "night", 40, seed=7)
    c = gen.generate("bee-gees", "night", 40, seed=8)
    assert a.lyrics == b.lyrics and a.title == b.title
    assert a.lyrics != c.lyrics


def test_word_budget_and_seed_text(gen):
    res = gen.generate("bee-gees", "night fire", 30, seed=1)
    assert 30 <= res.words <= 30 + gen.sampling.extra_words
    assert res.lyrics.lower().startswith("night fire")
    assert res.token_ids[-1] not in (gen.tok.line_id, gen.tok.verse_id)


def test_word_budget_starts_after_a_long_seed(gen):
    seed_text = " ".join(WORDS * 20)  # 200 words, longer than the whole token budget of 5 words
    prompt = gen.tok.encode(seed_text)

    res = gen.generate("bee-gees", seed_text, 5, seed=3)

    assert 5 <= res.words <= 5 + gen.sampling.extra_words
    assert res.token_ids[:len(prompt)] == prompt  # the whole seed is echoed
    assert len(res.token_ids) > len(prompt)


def test_only_the_last_prompt_tokens_are_fed():
    tok = Tokenizer.build([" ".join(WORDS) + " , ."], min_freq=1)
    stepper = RandomStepper(len(tok))
    g = LyricsGenerator(stepper, tok, ARTISTS)
    seed_text = " ".join(WORDS * 10)
    prompt = tok.encode(seed_text)
    assert len(prompt) > MAX_PROMPT_TOKENS == 64

    res = g.generate(None, seed_text, 10, seed=0, with_title=False)

    fed = [token for token, _, _ in stepper.calls[:MAX_PROMPT_TOKENS + 1]]
    assert fed == [tok.bos_id, *prompt[-MAX_PROMPT_TOKENS:]]
    assert len(stepper.calls) >= 1 + MAX_PROMPT_TOKENS + len(res.token_ids) - len(prompt)
    assert res.token_ids[:len(prompt)] == prompt


def test_short_seed_is_fed_whole():
    tok = Tokenizer.build([" ".join(WORDS) + " , ."], min_freq=1)
    stepper = RandomStepper(len(tok))
    g = LyricsGenerator(stepper, tok, ARTISTS)

    g.generate(None, "night fire", 10, seed=0, with_title=False)

    assert [token for token, _, _ in stepper.calls[:3]] == [tok.bos_id, *tok.encode("night fire")]


def test_never_emits_forbidden_tokens(gen):
    t = gen.tok
    for seed in range(5):
        res = gen.generate(None, "", 50, seed=seed)
        assert not {t.unk_id, t.pad_id, t.bos_id, t.eos_id, t.title_id} & set(res.token_ids)
        assert t.unk_id not in res.title_ids and t.line_id not in res.title_ids
        for a, b in zip(res.token_ids, res.token_ids[1:], strict=False):
            assert not (a in (t.line_id, t.verse_id) and b in (t.line_id, t.verse_id))


def test_unk_is_forbidden_even_when_it_dominates():
    tok = Tokenizer.build([" ".join(WORDS)], min_freq=1)
    stepper = RandomStepper(len(tok))
    stepper.table[:, tok.unk_id] = 100.0
    g = LyricsGenerator(stepper, tok, ARTISTS)
    assert tok.unk_id not in g.generate(None, "", 20, seed=0).token_ids


def test_max_repeat_run_blocks_word_loops():
    tok = Tokenizer.build([" ".join(WORDS)], min_freq=1)
    stepper = RandomStepper(len(tok))
    kill = tok.stoi["fire"]
    stepper.table[:, kill] = 50.0
    g = LyricsGenerator(stepper, tok, ARTISTS)
    ids = g.generate(None, "", 30, seed=0, repetition_penalty=1.0).token_ids
    runs = [ids[i:i + 3] for i in range(len(ids) - 2)]
    assert [kill] * 3 not in runs


def test_artist_resolution_and_conditioning(gen):
    assert gen.resolve_artist("Bee Gees") == ("bee-gees", 1, 1)
    assert gen.resolve_artist("BEE-GEES", genre="rock") == ("bee-gees", 1, 2)
    assert gen.resolve_artist("nobody") == (None, 0, 0)
    gen.generate("bee gees", "", 5, seed=0)
    assert {c[1:] for c in gen.stepper.calls} == {(1, 1)}


def test_generate_title_from_lyrics(gen):
    title = gen.generate_title("love in the night\nbaby dance", "bee-gees", seed=3)
    assert title and title == gen.generate_title("love in the night\nbaby dance", "bee-gees", seed=3)
    assert title[0].isupper()


def test_process_logits_top_k_top_p_and_penalty():
    cfg = SamplingConfig(temperature=1.0, top_k=2, top_p=1.0, repetition_penalty=1.0)
    probs = process_logits(np.array([3.0, 2.0, 1.0, 0.0]), [], cfg)
    assert probs[2] == 0 and probs[3] == 0 and probs.sum() == pytest.approx(1)
    cfg = SamplingConfig(temperature=1.0, top_k=0, top_p=0.5, repetition_penalty=1.0)
    assert np.count_nonzero(process_logits(np.array([5.0, 1.0, 1.0]), [], cfg)) == 1
    cfg = SamplingConfig(temperature=1.0, top_k=0, top_p=1.0, repetition_penalty=4.0)
    p = process_logits(np.array([2.0, 2.0]), [0], cfg)
    assert p[0] < p[1]
    greedy = process_logits(np.array([0.0, 9.0, 1.0]), [], SamplingConfig(temperature=0))
    assert sample(greedy, np.random.default_rng(0)) == 1
    masked = process_logits(np.array([9.0, 0.0]), [], SamplingConfig(), forbidden=[0])
    assert masked[0] == 0


def test_generate_module_does_not_import_torch():
    import ml.generate as mod

    assert "import torch" not in open(mod.__file__, encoding="utf-8").read()
