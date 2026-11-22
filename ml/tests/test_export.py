"""ONNX export, parity and bundle generation tests (CPU). Skipped without torch / onnx / onnxruntime."""

import json

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("onnx")
pytest.importorskip("onnxscript")
pytest.importorskip("onnxruntime")


@pytest.fixture(scope="module")
def bundle(tiny_run, tmp_path_factory):
    from ml.export import export_bundle

    run_dir, _ = tiny_run
    return export_bundle(run_dir, tmp_path_factory.mktemp("bundles"), version="test-1", log=lambda *_: None)


def test_bundle_layout_and_config(bundle):
    names = {p.name for p in bundle.iterdir()}
    assert names == {"model.onnx", "vocab.json", "artists.json", "config.json", "samples.md"}
    cfg = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
    assert cfg["format_version"] == 1 and cfg["name"] == "lyrics-lstm" and cfg["version"] == "test-1"
    assert cfg["onnx"]["parity_max_abs_diff"] <= cfg["onnx"]["parity_atol"]
    assert cfg["onnx"]["state_size"] == cfg["model"]["hidden"] * 4 + cfg["model"]["emb_dim"] * 2
    assert cfg["data"]["data_sha256"] and cfg["training"]["metrics"]["test_ppl"] > 1
    assert set(cfg["files"]) == names - {"config.json"}
    assert cfg["onnx"]["opset"] >= 17


def test_onnx_matches_torch_step_by_step(tiny_run, bundle):
    import onnxruntime as ort
    import torch

    from ml.export import load_model
    from ml.model import StepDecoder

    model, _ = load_model(tiny_run[0])
    step = StepDecoder(model)
    sess = ort.InferenceSession(str(bundle / "model.onnx"), providers=["CPUExecutionProvider"])
    state_t = torch.zeros(1, model.cfg.state_size)
    state_o = np.zeros((1, model.cfg.state_size), dtype=np.float32)
    for tok in [2, 9, 10, 4, 11, 12]:
        with torch.no_grad():
            ref, state_t = step(torch.tensor([tok]), torch.tensor([1]), torch.tensor([1]), state_t)
        out, state_o = sess.run(None, {"token": np.array([tok], dtype=np.int64), "artist": np.array([1]),
                                       "genre": np.array([1]), "state": state_o})
        np.testing.assert_allclose(out, ref.numpy(), atol=1e-4)
        np.testing.assert_allclose(state_o, state_t.numpy(), atol=1e-4)


def test_generator_from_bundle_is_deterministic(bundle):
    from ml.generate import LyricsGenerator

    gen = LyricsGenerator.from_bundle(bundle, threads=1)
    assert set(gen.artist_slugs) == {"bee-gees", "eminem"}
    a = gen.generate("Bee Gees", "night fever", 20, seed=5)
    b = gen.generate("bee-gees", "night fever", 20, seed=5)
    assert a.lyrics == b.lyrics and a.title == b.title and a.artist == "bee-gees"
    assert a.lyrics.lower().startswith("night fever") and a.words >= 20
    assert gen.tok.unk_id not in a.token_ids
    title = gen.generate_title("stayin alive\nstayin alive", "bee-gees", seed=1)
    assert title == gen.generate_title("stayin alive\nstayin alive", "bee-gees", seed=1)
    assert gen.generate(None, "", 10, seed=0).artist is None


def test_generate_cli(bundle, capsys):
    from ml.generate import main

    assert main([str(bundle), "--artist", "eminem", "--words", "12", "--seed", "3"]) == 0
    assert "eminem" in capsys.readouterr().out
