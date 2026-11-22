"""Export a trained run to a serving bundle (see ml/BUNDLE.md).

    python -m ml.export --run ml/runs/t4 --out ml/bundles --version 2026.11.0

Writes `<out>/<version>/` with model.onnx (single step decoder, explicit state), vocab.json, artists.json,
config.json and samples.md, after checking that onnxruntime reproduces the torch logits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import warnings
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from ml.generate import BUNDLE_FORMAT_VERSION, LyricsGenerator, SamplingConfig
from ml.model import LyricsLSTM, ModelConfig, StepDecoder
from ml.tokenizer import SPECIALS, Tokenizer

PARITY_ATOL = 1e-4  # max |torch - onnxruntime| on logits, float32 on CPU (observed ~1e-6)
INPUT_NAMES = ["token", "artist", "genre", "state"]
OUTPUT_NAMES = ["logits", "state_out"]


def load_model(run_dir: Path, checkpoint: str = "best.pt") -> tuple[LyricsLSTM, dict]:
    ckpt = torch.load(run_dir / checkpoint, map_location="cpu", weights_only=False)
    model = LyricsLSTM(ModelConfig(**ckpt["model_config"]))
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, ckpt


def export_onnx(model: LyricsLSTM, path: Path, exporter: str = "dynamo", opset: int | None = None) -> str:
    """Export StepDecoder(model) to `path` as a single file. Returns the exporter actually used."""
    step = StepDecoder(model).eval()
    s = model.cfg.state_size
    args = (torch.zeros(1, dtype=torch.long), torch.zeros(1, dtype=torch.long), torch.zeros(1, dtype=torch.long),
            torch.zeros(1, s))
    if exporter == "dynamo":
        batch = torch.export.Dim("batch", min=1, max=64)
        dynamic_shapes = {"token": {0: batch}, "artist": {0: batch}, "genre": {0: batch}, "state": {0: batch}}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            program = torch.onnx.export(step, args, input_names=INPUT_NAMES, output_names=OUTPUT_NAMES,
                                        dynamic_shapes=dynamic_shapes, opset_version=opset, dynamo=True,
                                        external_data=False, verbose=False)
        program.optimize()
        program.save(str(path), external_data=False)
    else:
        axes = {n: {0: "batch"} for n in INPUT_NAMES + OUTPUT_NAMES}
        torch.onnx.export(step, args, str(path), input_names=INPUT_NAMES, output_names=OUTPUT_NAMES,
                          dynamic_axes=axes, opset_version=opset or 17, dynamo=False)
    return exporter


def parity_check(model: LyricsLSTM, onnx_path: Path, steps: int = 24, seed: int = 0) -> float:
    """Run the same random token sequence through torch (full sequence forward) and onnxruntime (step by step).

    Returns the max absolute logit difference over all steps.
    """
    import onnxruntime as ort

    rng = np.random.default_rng(seed)
    cfg = model.cfg
    tokens = rng.integers(len(SPECIALS), cfg.vocab_size, size=(2, steps))
    artist = np.array([1 % cfg.n_artists, 0])
    genre = np.array([1 % cfg.n_genres, 0])
    with torch.no_grad():
        ref, _ = model(torch.from_numpy(tokens), torch.from_numpy(artist), torch.from_numpy(genre))
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    state = np.zeros((2, cfg.state_size), dtype=np.float32)
    worst = 0.0
    for t in range(steps):
        logits, state = sess.run(OUTPUT_NAMES, {"token": tokens[:, t].astype(np.int64),
                                                "artist": artist.astype(np.int64),
                                                "genre": genre.astype(np.int64), "state": state})
        worst = max(worst, float(np.abs(logits - ref[:, t].numpy()).max()))
    return worst


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_samples(bundle: Path, artists: dict, n_artists: int = 4, words: int = 120) -> str:
    gen = LyricsGenerator.from_bundle(bundle)
    top = sorted(artists["artists"].items(), key=lambda kv: -kv[1]["songs"])[:n_artists]
    parts = [f"# Samples: lyrics-lstm {bundle.name}\n",
             f"Sampling: {json.dumps(asdict(gen.sampling))}\n"]
    for i, (slug, info) in enumerate(top):
        res = gen.generate(slug, "", words, seed=100 + i)
        parts.append(f"## {info['display_name']} ({info['genre']}): {res.title}\n\nseed {100 + i}, "
                     f"{res.words} words\n\n```\n{res.lyrics}\n```\n")
    res = gen.generate(None, "tonight", words, seed=99)
    parts.append(f"## Unknown artist, seed text \"tonight\": {res.title}\n\n```\n{res.lyrics}\n```\n")
    text = "\n".join(parts)
    (bundle / "samples.md").write_text(text, encoding="utf-8")
    return text


def export_bundle(run_dir: str | Path, out_dir: str | Path, version: str | None = None,
                  checkpoint: str = "best.pt", exporter: str = "dynamo", opset: int | None = None,
                  atol: float = PARITY_ATOL, samples: bool = True, log=print) -> Path:
    run_dir = Path(run_dir)
    version = version or time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    bundle = Path(out_dir) / version
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    model, ckpt = load_model(run_dir, checkpoint)
    tok = Tokenizer.load(run_dir / "vocab.json")
    if len(tok) != model.cfg.vocab_size:
        raise ValueError("vocab.json does not match the checkpoint")
    t0 = time.time()
    used = export_onnx(model, bundle / "model.onnx", exporter, opset)
    import onnx

    proto = onnx.load(str(bundle / "model.onnx"))
    onnx.checker.check_model(proto)
    opset_used = next(o.version for o in proto.opset_import if o.domain in ("", "ai.onnx"))
    del proto
    diff = parity_check(model, bundle / "model.onnx")
    log(f"exported with the {used} exporter (opset {opset_used}) in {time.time() - t0:.1f}s; "
        f"parity max |diff| {diff:.2e} (atol {atol:.0e})")
    if not diff <= atol:
        raise RuntimeError(f"ONNX parity check failed: max |diff| {diff} > {atol}")
    shutil.copyfile(run_dir / "vocab.json", bundle / "vocab.json")
    shutil.copyfile(run_dir / "artists.json", bundle / "artists.json")
    artists = json.loads((bundle / "artists.json").read_text(encoding="utf-8"))
    metrics = {}
    if (run_dir / "metrics.json").exists():
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    prep = {}
    if (run_dir / "prep_meta.json").exists():
        prep = json.loads((run_dir / "prep_meta.json").read_text(encoding="utf-8"))
    cfg = model.cfg
    layout, offset = [], 0
    for i, (_, h) in enumerate(cfg.layer_sizes()):
        layout.append({"layer": i, "h": [offset, offset + h], "c": [offset + h, offset + 2 * h]})
        offset += 2 * h
    config = {
        "format_version": BUNDLE_FORMAT_VERSION,
        "name": "lyrics-lstm",
        "version": version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "onnx": {
            "file": "model.onnx", "exporter": used, "opset": opset_used, "torch_version": torch.__version__,
            "inputs": {"token": "int64 [batch]", "artist": "int64 [batch]", "genre": "int64 [batch]",
                       "state": f"float32 [batch, {cfg.state_size}]"},
            "outputs": {"logits": f"float32 [batch, {cfg.vocab_size}]",
                        "state_out": f"float32 [batch, {cfg.state_size}]"},
            "state_size": cfg.state_size, "state_layout": layout,
            "parity_max_abs_diff": diff, "parity_atol": atol,
        },
        "model": {"architecture": "conditional word level AWD-LSTM, tied softmax", **cfg.to_dict(),
                  "parameters": model.num_parameters()},
        "tokenizer": {"file": "vocab.json", "type": "word", "lowercase": tok.lowercase, "vocab_size": len(tok),
                      "specials": list(SPECIALS), "sequence": "<bos> lyrics <title> title <eos>",
                      "line_tokens": {"<line>": "newline", "<verse>": "blank line"}},
        "training": {"checkpoint": checkpoint, "config": ckpt["train_config"], "metrics": metrics,
                     "epochs": ckpt.get("epoch"), "steps": ckpt.get("step"), "best_val_ppl": ckpt.get("best_val")},
        "data": {k: prep.get(k) for k in ("source", "songs", "artists", "genres", "splits", "data_sha256",
                                          "created_at", "config")},
        "sampling": asdict(SamplingConfig()),
    }
    (bundle / "config.json").write_text(json.dumps(config, indent=1), encoding="utf-8")
    if samples:
        write_samples(bundle, artists)
    config["files"] = {p.name: {"bytes": p.stat().st_size, "sha256": _sha256(p)}
                       for p in sorted(bundle.iterdir()) if p.name != "config.json"}
    (bundle / "config.json").write_text(json.dumps(config, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in bundle.iterdir())
    log(f"bundle {bundle} ({size / 1e6:.1f} MB)")
    return bundle


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, help="training run directory")
    p.add_argument("--out", default="ml/bundles", help="parent directory for the bundle")
    p.add_argument("--version", default=None, help="bundle version (default: UTC timestamp)")
    p.add_argument("--checkpoint", default="best.pt")
    p.add_argument("--exporter", choices=["dynamo", "torchscript"], default="dynamo")
    p.add_argument("--opset", type=int, default=None, help="default: the exporter's recommended opset")
    p.add_argument("--atol", type=float, default=PARITY_ATOL)
    p.add_argument("--no-samples", action="store_true")
    args = p.parse_args(list(argv) if argv is not None else None)
    export_bundle(args.run, args.out, args.version, args.checkpoint, args.exporter, args.opset, args.atol,
                  samples=not args.no_samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
