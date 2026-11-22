"""Model and training loop tests (CPU, seconds). Skipped when torch is not installed (API CI)."""

import json

import pytest

torch = pytest.importorskip("torch")

from ml.model import LyricsLSTM, ModelConfig, StepDecoder, flatten_state  # noqa: E402

TINY = dict(vocab_size=40, n_artists=3, n_genres=2, emb_dim=8, artist_dim=4, genre_dim=2, hidden=16, layers=3)


def _no_dropout(cfg: ModelConfig) -> ModelConfig:
    for name in ("dropout_emb", "dropout_in", "dropout_hid", "dropout_out", "weight_drop", "cond_drop"):
        setattr(cfg, name, 0.0)
    return cfg


def test_shapes_and_state_size():
    cfg = ModelConfig(**TINY)
    model = LyricsLSTM(cfg)
    logits, state = model(torch.randint(0, 40, (2, 5)), torch.tensor([1, 2]), torch.tensor([0, 1]))
    assert logits.shape == (2, 5, 40)
    assert [h.shape[-1] for h, _ in state] == [16, 16, 8]
    assert cfg.state_size == 2 * (16 + 16 + 8)
    assert model.decoder.weight is model.embed.weight


def test_weight_drop_only_in_training():
    torch.manual_seed(0)
    cfg = _no_dropout(ModelConfig(**TINY))
    cfg.weight_drop = 0.5
    model = LyricsLSTM(cfg)
    x, a, g = torch.randint(0, 40, (2, 6)), torch.tensor([1, 1]), torch.tensor([1, 1])
    model.train()
    assert not torch.allclose(model(x, a, g)[0], model(x, a, g)[0])
    model.eval()
    assert torch.allclose(model(x, a, g)[0], model(x, a, g)[0])
    model.train()
    model(x, a, g)[0].sum().backward()
    assert model.rnns[0].weight_hh_l0.grad.abs().sum() > 0


def test_step_decoder_matches_sequence_forward():
    torch.manual_seed(1)
    model = LyricsLSTM(ModelConfig(**TINY)).eval()
    x, a, g = torch.randint(0, 40, (3, 7)), torch.tensor([0, 1, 2]), torch.tensor([1, 0, 1])
    with torch.no_grad():
        full, state = model(x, a, g)
        step = StepDecoder(model)
        s = torch.zeros(3, model.cfg.state_size)
        for t in range(7):
            logits, s = step(x[:, t], a, g, s)
            assert torch.allclose(logits, full[:, t], atol=1e-5)
    assert torch.allclose(s, flatten_state(state), atol=1e-5)


def test_tiny_model_overfits_one_batch():
    torch.manual_seed(0)
    # Untied so the tiny 16-d softmax is not the bottleneck; the tied path is covered by the training run test.
    model = LyricsLSTM(_no_dropout(ModelConfig(**{**TINY, "emb_dim": 16, "hidden": 32, "tie_weights": False})))
    seq = torch.randint(7, 40, (4, 12))
    a, g = torch.tensor([1, 2, 1, 2]), torch.tensor([1, 1, 0, 0])
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2, weight_decay=0.0)
    first = None
    for _ in range(250):
        logits, _ = model(seq[:, :-1], a, g)
        loss = torch.nn.functional.cross_entropy(logits.reshape(-1, 40), seq[:, 1:].reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        first = first if first is not None else loss.item()
    assert first > 3.0 and loss.item() < 0.2


def test_lr_schedule_warmup_and_cosine():
    from ml.train import lr_lambda

    assert lr_lambda(0, 10, 100, 0.1) == pytest.approx(0.1)
    assert lr_lambda(9, 10, 100, 0.1) == pytest.approx(1.0)
    assert lr_lambda(100, 10, 100, 0.1) == pytest.approx(0.1)
    assert 0.1 < lr_lambda(55, 10, 100, 0.1) < 1.0


def test_build_config_presets_and_overrides(tmp_path):
    from ml.train import build_config

    cfg = build_config("smoke", None, ["epochs=5", "model.hidden=32", "lr=0.01"])
    assert cfg.epochs == 5 and cfg.model["hidden"] == 32 and cfg.model["emb_dim"] == 48 and cfg.lr == 0.01
    with pytest.raises(SystemExit):
        build_config(None, None, ["nope=1"])
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"batch_size": 7, "model": {"layers": 2}}), encoding="utf-8")
    cfg = build_config("smoke", str(path), [])
    assert cfg.batch_size == 7 and cfg.model["layers"] == 2 and cfg.model["hidden"] == 96


def test_train_resume_and_eval(tiny_run):
    from ml.train import build_config, train

    run_dir, data_dir = tiny_run
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["epochs"] == 1 and metrics["test_ppl"] > 1
    for name in ("vocab.json", "artists.json", "last.pt", "best.pt", "samples.md", "metrics.jsonl"):
        assert (run_dir / name).exists()
    resumed = train(data_dir, run_dir, build_config("smoke", None, []), overrides=["epochs=2"], log=lambda *_: None)
    assert resumed["epochs"] == 2
    assert len((run_dir / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()) == 2


def test_load_glove_from_txt_and_zip(tmp_path):
    import zipfile

    from ml.tokenizer import Tokenizer
    from ml.train import load_glove

    tok = Tokenizer.build(["love night baby"], min_freq=1)
    text = "love 0.1 0.2 0.3\nnight 1 2 3\nunrelated 9 9 9\nbroken 1 2\n"
    (tmp_path / "glove.6B.3d.txt").write_text(text, encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "glove.6B.zip", "w") as zf:
        zf.writestr("glove.6B.3d.txt", text)
    for path in (tmp_path / "glove.6B.3d.txt", tmp_path / "glove.6B.zip"):
        vectors, found = load_glove(path, tok, 3, log=lambda *_: None)
        assert int(found.sum()) == 2 and not found[tok.stoi["baby"]]
        assert torch.allclose(vectors[tok.stoi["night"]], torch.tensor([1.0, 2.0, 3.0]))
    model = LyricsLSTM(ModelConfig(**{**TINY, "vocab_size": len(tok), "emb_dim": 3, "hidden": 4}))
    model.load_pretrained_embeddings(vectors, found)
    assert torch.allclose(model.embed.weight[tok.stoi["love"]], torch.tensor([0.1, 0.2, 0.3]))
