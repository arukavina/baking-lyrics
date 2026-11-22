"""Train the conditional lyrics LSTM.

    python -m ml.train --data ml/data/processed --out ml/runs/t4 --preset colab-t4 [--glove glove.6B.zip]
    python -m ml.train --data ml/data/processed --out ml/runs/t4 --preset colab-t4      # resumes from last.pt
    python -m ml.train --data ml/data/processed --out ml/runs/t4 --eval-only --split test

Presets: smoke (tiny, CPU minutes), colab-t4 (16 GB GPU), gpu-large (A100 / L4 / 24 GB+). Any field can be changed
with `--set key=value` (model fields as `model.hidden=768`) or a JSON file passed with `--config`.

The run directory holds: vocab.json, artists.json, train_config.json, last.pt (resume), best.pt (best validation
perplexity), metrics.jsonl (one line per evaluation), samples.md (samples after every epoch) and metrics.json.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import shutil
import sys
import time
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from ml.generate import LyricsGenerator, SamplingConfig
from ml.model import LyricsLSTM, ModelConfig, StepDecoder
from ml.tokenizer import SPECIALS, Tokenizer


@dataclass
class TrainConfig:
    vocab_size: int = 30000
    min_freq: int = 3
    max_len: int = 400  # tokens per song including <bos>, title and <eos>; longer lyrics are truncated
    batch_size: int = 32
    epochs: int = 12
    lr: float = 1e-3
    weight_decay: float = 0.01
    betas: tuple[float, float] = (0.9, 0.99)
    warmup_steps: int = 1000
    min_lr_ratio: float = 0.05
    clip: float = 1.0
    patience: int = 3
    amp: bool = True
    seed: int = 1234
    max_steps_per_epoch: int = 0  # 0 = full epoch
    max_minutes: float = 0  # stop (and checkpoint) after this wall time, 0 = no limit
    save_every_minutes: float = 15  # mid-epoch checkpoint for preemptible sessions
    log_every: int = 100
    eval_max_batches: int = 0  # 0 = whole split
    sample_artists: int = 3
    sample_words: int = 80
    model: dict = field(default_factory=dict)  # ModelConfig overrides


PRESETS: dict[str, dict] = {
    "smoke": dict(vocab_size=4000, min_freq=2, max_len=192, batch_size=16, epochs=2, lr=3e-3, warmup_steps=20,
                  max_steps_per_epoch=60, log_every=20, eval_max_batches=10, sample_words=40, save_every_minutes=0,
                  model=dict(emb_dim=48, artist_dim=8, genre_dim=4, hidden=96, layers=3, weight_drop=0.2)),
    "colab-t4": dict(vocab_size=30000, min_freq=3, max_len=400, batch_size=32, epochs=12, lr=1e-3,
                     warmup_steps=1000, patience=3, max_minutes=0, save_every_minutes=15),
    "gpu-large": dict(vocab_size=30000, min_freq=3, max_len=512, batch_size=64, epochs=25, lr=1e-3,
                      warmup_steps=2000, patience=4, save_every_minutes=20),
}


def build_config(preset: str | None, config_file: str | None, overrides: Iterable[str],
                 base: dict | None = None) -> TrainConfig:
    values: dict = json.loads(json.dumps(base)) if base else {}
    if preset:
        values.update(json.loads(json.dumps(PRESETS[preset])))
    if config_file:
        data = json.loads(Path(config_file).read_text(encoding="utf-8"))
        model = {**values.get("model", {}), **data.pop("model", {})}
        values.update(data)
        values["model"] = model
    names = {f.name: f for f in fields(TrainConfig)}
    model_names = {f.name: f for f in fields(ModelConfig)}
    for item in overrides:
        key, _, raw = item.partition("=")
        key = key.strip()
        target, table = (values.setdefault("model", {}), model_names) if key.startswith("model.") else (values, names)
        key = key.removeprefix("model.")
        if key not in table:
            raise SystemExit(f"unknown setting {item!r}")
        try:
            target[key] = json.loads(raw)
        except json.JSONDecodeError:
            target[key] = raw
    if "betas" in values:
        values["betas"] = tuple(values["betas"])
    return TrainConfig(**values)


# Data -----------------------------------------------------------------------------------------------


@dataclass
class Corpus:
    tokenizer: Tokenizer
    artists: dict
    splits: dict[str, list[tuple[np.ndarray, int, int]]]  # (ids, artist_id, genre_id)


def load_corpus(data_dir: Path, run_dir: Path, cfg: TrainConfig, log=print) -> Corpus:
    songs = pd.read_parquet(data_dir / "songs.parquet")
    artists = json.loads((data_dir / "artists.json").read_text(encoding="utf-8"))
    vocab_path = run_dir / "vocab.json"
    if vocab_path.exists():
        tok = Tokenizer.load(vocab_path)
    else:
        train = songs[songs["split"] == "train"]
        tok = Tokenizer.build(list(train["lyrics"]) + list(train["title"]), cfg.vocab_size, cfg.min_freq)
        tok.save(vocab_path)
    shutil.copyfile(data_dir / "artists.json", run_dir / "artists.json")
    if (data_dir / "prep_meta.json").exists():
        shutil.copyfile(data_dir / "prep_meta.json", run_dir / "prep_meta.json")
    splits: dict[str, list] = {"train": [], "val": [], "test": []}
    n_tokens = n_unk = 0
    for row in songs.itertuples(index=False):
        ids = tok.encode_song(row.lyrics, row.title, max_len=cfg.max_len)
        splits[row.split].append((ids, int(row.artist_id), int(row.genre_id)))
        n_tokens += len(ids)
        n_unk += int((ids == tok.unk_id).sum())
    log(f"vocab {len(tok)}, songs " + ", ".join(f"{k} {len(v)}" for k, v in splits.items())
        + f", tokens {n_tokens:,} (unk {n_unk / max(n_tokens, 1):.2%})")
    return Corpus(tok, artists, splits)


def batches(data: list, batch_size: int, rng: np.random.Generator | None) -> list[list[int]]:
    """Length bucketed batches (indices). Shuffled when rng is given."""
    order = np.arange(len(data))
    if rng is not None:
        order = rng.permutation(len(data))
    chunk = batch_size * 50
    out: list[list[int]] = []
    for start in range(0, len(order), chunk):
        part = sorted(order[start:start + chunk], key=lambda i: len(data[i][0]))
        out += [list(part[i:i + batch_size]) for i in range(0, len(part), batch_size)]
    if rng is not None:
        rng.shuffle(out)
    return out


def collate(data: list, idx: list[int], device) -> tuple[torch.Tensor, ...]:
    seqs = [data[i][0] for i in idx]
    width = max(len(s) for s in seqs)
    arr = np.zeros((len(seqs), width), dtype=np.int64)
    for r, s in enumerate(seqs):
        arr[r, :len(s)] = s
    t = torch.from_numpy(arr).to(device, non_blocking=True)
    artist = torch.tensor([data[i][1] for i in idx], device=device)
    genre = torch.tensor([data[i][2] for i in idx], device=device)
    return t[:, :-1], t[:, 1:], artist, genre


# Helpers ----------------------------------------------------------------------------------------------


def pick_device(name: str = "auto") -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def amp_settings(device: torch.device, enabled: bool) -> tuple[torch.dtype | None, bool]:
    """(autocast dtype, use GradScaler). bf16 where supported (A100/L4/RTX 30+), fp16 + scaler on T4."""
    if not enabled or device.type != "cuda":
        return None, False
    if torch.cuda.is_bf16_supported():
        return torch.bfloat16, False
    return torch.float16, True


def lr_lambda(step: int, warmup: int, total: int, min_ratio: float) -> float:
    if step < warmup:
        return (step + 1) / max(1, warmup)
    progress = min(1.0, (step - warmup) / max(1, total - warmup))
    return min_ratio + (1 - min_ratio) * 0.5 * (1 + math.cos(math.pi * progress))


def load_glove(path: str | Path, tok: Tokenizer, dim: int, log=print) -> tuple[torch.Tensor, torch.Tensor]:
    """Read GloVe vectors (a .txt file or the glove.6B.zip archive) for the vocabulary words."""
    path = Path(path)
    vectors = torch.zeros(len(tok), dim)
    found = torch.zeros(len(tok), dtype=torch.bool)

    def lines() -> Iterator[str]:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                member = next(n for n in zf.namelist() if n.endswith(f".{dim}d.txt"))
                with zf.open(member) as fh:
                    for raw in fh:
                        yield raw.decode("utf-8", errors="ignore")
        else:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                yield from fh

    for line in lines():
        word, _, rest = line.rstrip().partition(" ")
        idx = tok.stoi.get(word)
        if idx is None or idx < len(SPECIALS):
            continue
        vals = rest.split(" ")
        if len(vals) != dim:
            continue
        vectors[idx] = torch.tensor([float(v) for v in vals])
        found[idx] = True
    log(f"GloVe: {int(found.sum())}/{len(tok) - len(SPECIALS)} vocabulary words initialised from {path.name}")
    return vectors, found


class TorchStepper:
    """Stepper for ml.generate backed by the torch model (used for samples during training)."""

    def __init__(self, model: LyricsLSTM, device: torch.device):
        self.step_model = StepDecoder(model)
        self.device = device
        self.state_size = model.cfg.state_size

    def initial_state(self):
        return torch.zeros(1, self.state_size, device=self.device)

    @torch.no_grad()
    def step(self, token_id, artist_id, genre_id, state):
        t = torch.tensor([token_id], device=self.device)
        a = torch.tensor([artist_id], device=self.device)
        g = torch.tensor([genre_id], device=self.device)
        logits, state = self.step_model(t, a, g, state)
        return logits[0].float().cpu().numpy(), state


def write_samples(model, corpus: Corpus, device, cfg: TrainConfig, header: str, path: Path, seed: int = 0) -> str:
    was_training = model.training
    model.eval()
    gen = LyricsGenerator(TorchStepper(model, device), corpus.tokenizer, corpus.artists)
    top = sorted(corpus.artists["artists"].items(), key=lambda kv: -kv[1]["songs"])[: cfg.sample_artists]
    parts = [f"## {header}\n"]
    for i, (slug, info) in enumerate(top):
        res = gen.generate(slug, "", cfg.sample_words, seed=seed + i, sampling=SamplingConfig())
        parts.append(f"### {info['display_name']}: {res.title}\n\n```\n{res.lyrics}\n```\n")
    text = "\n".join(parts)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")
    model.train(was_training)
    return text


@torch.no_grad()
def evaluate(model, data: list, cfg: TrainConfig, device, amp_dtype=None) -> float:
    """Perplexity per token (lyrics, title and <eos>) on `data`."""
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    for n, idx in enumerate(batches(data, cfg.batch_size, None)):
        if cfg.eval_max_batches and n >= cfg.eval_max_batches:
            break
        x, y, a, g = collate(data, idx, device)
        ctx = torch.autocast(device.type, dtype=amp_dtype) if amp_dtype else contextlib.nullcontext()
        with ctx:
            logits, _ = model(x, a, g)
        loss = F.cross_entropy(logits.float().reshape(-1, logits.size(-1)), y.reshape(-1), ignore_index=0,
                               reduction="sum")
        total_loss += float(loss)
        total_tokens += int((y != 0).sum())
    model.train()
    return math.exp(total_loss / max(total_tokens, 1))


# Training ---------------------------------------------------------------------------------------------


def train(data_dir: str | Path, run_dir: str | Path, cfg: TrainConfig, glove: str | None = None,
          device_name: str = "auto", fresh: bool = False, overrides: Iterable[str] = (), log=print) -> dict:
    """Train (or resume) a run. When resuming, the saved config is used and only `overrides` change it."""
    data_dir, run_dir = Path(data_dir), Path(run_dir)
    if fresh and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    resume_path = run_dir / "last.pt"
    ckpt = torch.load(resume_path, map_location="cpu", weights_only=False) if resume_path.exists() else None
    if ckpt is not None:
        cfg = build_config(None, None, overrides, base=ckpt["train_config"])
        log(f"resuming from {resume_path} (epoch {ckpt['epoch']}, step {ckpt['step']})")
    (run_dir / "train_config.json").write_text(json.dumps(asdict(cfg), indent=1), encoding="utf-8")

    torch.manual_seed(cfg.seed)
    device = pick_device(device_name)
    amp_dtype, use_scaler = amp_settings(device, cfg.amp)
    log(f"device {device}" + (f" ({torch.cuda.get_device_name(device)})" if device.type == "cuda" else "")
        + f", amp {amp_dtype}")
    corpus = load_corpus(data_dir, run_dir, cfg, log=log)
    mcfg = ModelConfig(vocab_size=len(corpus.tokenizer), n_artists=max(a["id"] for a in
                       corpus.artists["artists"].values()) + 1, n_genres=len(corpus.artists["genres"]) + 1,
                       **cfg.model)
    model = LyricsLSTM(mcfg)
    if glove and ckpt is None:
        vectors, mask = load_glove(glove, corpus.tokenizer, mcfg.emb_dim, log=log)
        model.load_pretrained_embeddings(vectors, mask)
    model.to(device)
    log(f"model {model.num_parameters() / 1e6:.1f}M parameters, state size {mcfg.state_size}")

    decay = [p for n, p in model.named_parameters() if p.dim() >= 2 and "artist_embed" not in n
             and "genre_embed" not in n]
    no_decay = [p for p in model.parameters() if all(p is not q for q in decay)]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": cfg.weight_decay},
                             {"params": no_decay, "weight_decay": 0.0}], lr=cfg.lr, betas=cfg.betas,
                            fused=device.type == "cuda")
    steps_per_epoch = len(batches(corpus.splits["train"], cfg.batch_size, None))
    if cfg.max_steps_per_epoch:
        steps_per_epoch = min(steps_per_epoch, cfg.max_steps_per_epoch)
    total_steps = steps_per_epoch * cfg.epochs
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: lr_lambda(s, cfg.warmup_steps, total_steps, cfg.min_lr_ratio))
    scaler = torch.amp.GradScaler("cuda", enabled=use_scaler)

    state = {"epoch": 0, "batch_in_epoch": 0, "step": 0, "best_val": float("inf"), "bad_epochs": 0,
             "train_seconds": 0.0}
    if ckpt is not None:
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["optimizer"])
        sched.load_state_dict(ckpt["scheduler"])
        scaler.load_state_dict(ckpt["scaler"])
        state.update({k: ckpt[k] for k in state})
        del ckpt

    def save(path: Path, full: bool) -> None:
        payload = {"model": model.state_dict(), "model_config": mcfg.to_dict(), "train_config": asdict(cfg), **state}
        if full:
            payload |= {"optimizer": opt.state_dict(), "scheduler": sched.state_dict(),
                        "scaler": scaler.state_dict()}
        tmp = path.with_suffix(".tmp")
        torch.save(payload, tmp)
        tmp.replace(path)

    metrics_file = run_dir / "metrics.jsonl"
    samples_file = run_dir / "samples.md"
    t_start = time.time()
    t_saved = time.time()
    seconds_before = state["train_seconds"]
    stopped = "completed"
    model.train()
    while state["epoch"] < cfg.epochs:
        epoch = state["epoch"]
        plan = batches(corpus.splits["train"], cfg.batch_size, np.random.default_rng(cfg.seed + epoch))
        plan = plan[:steps_per_epoch]
        run_loss, run_tokens, t_log = 0.0, 0, time.time()
        for b in range(state["batch_in_epoch"], len(plan)):
            x, y, a, g = collate(corpus.splits["train"], plan[b], device)
            ctx = torch.autocast(device.type, dtype=amp_dtype) if amp_dtype else contextlib.nullcontext()
            with ctx:
                logits, _ = model(x, a, g)
            loss = F.cross_entropy(logits.float().reshape(-1, logits.size(-1)), y.reshape(-1), ignore_index=0)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.clip)
            scaler.step(opt)
            scaler.update()
            sched.step()
            n_tok = int((y != 0).sum())
            run_loss += loss.item() * n_tok
            run_tokens += n_tok
            state["step"] += 1
            state["batch_in_epoch"] = b + 1
            if state["step"] % cfg.log_every == 0:
                dt = time.time() - t_log
                log(f"epoch {epoch + 1} batch {b + 1}/{len(plan)} loss {run_loss / run_tokens:.3f} "
                    f"ppl {math.exp(run_loss / run_tokens):.1f} lr {sched.get_last_lr()[0]:.2e} "
                    f"{run_tokens / max(dt, 1e-9):,.0f} tok/s")
                run_loss, run_tokens, t_log = 0.0, 0, time.time()
            elapsed = time.time() - t_start
            state["train_seconds"] = seconds_before + elapsed
            if cfg.save_every_minutes and time.time() - t_saved > cfg.save_every_minutes * 60:
                save(run_dir / "last.pt", full=True)
                t_saved = time.time()
            if cfg.max_minutes and elapsed > cfg.max_minutes * 60:
                stopped = "time limit"
                break
        if stopped == "time limit":
            save(run_dir / "last.pt", full=True)
            log("time limit reached, checkpoint saved; run the same command again to resume")
            break
        val_ppl = evaluate(model, corpus.splits["val"] or corpus.splits["train"], cfg, device, amp_dtype)
        state["epoch"] += 1
        state["batch_in_epoch"] = 0
        improved = val_ppl < state["best_val"]
        if improved:
            state["best_val"], state["bad_epochs"] = val_ppl, 0
        else:
            state["bad_epochs"] += 1
        record = {"epoch": state["epoch"], "step": state["step"], "val_ppl": round(val_ppl, 3),
                  "lr": sched.get_last_lr()[0], "train_seconds": round(state["train_seconds"], 1)}
        with open(metrics_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        log(f"epoch {state['epoch']}: val ppl {val_ppl:.2f}" + (" (best)" if improved else ""))
        if improved:
            save(run_dir / "best.pt", full=False)
        save(run_dir / "last.pt", full=True)
        t_saved = time.time()
        log(write_samples(model, corpus, device, cfg, f"Epoch {state['epoch']} (val ppl {val_ppl:.1f})",
                          samples_file))
        if state["bad_epochs"] >= cfg.patience:
            stopped = "early stopping"
            log(f"early stopping: no improvement for {cfg.patience} epochs")
            break

    result = {"stopped": stopped, "epochs": state["epoch"], "steps": state["step"],
              "best_val_ppl": state["best_val"], "train_seconds": round(state["train_seconds"], 1),
              "device": str(device), "parameters": model.num_parameters()}
    if stopped != "time limit" and (run_dir / "best.pt").exists():
        best = torch.load(run_dir / "best.pt", map_location=device, weights_only=False)
        model.load_state_dict(best["model"])
        if corpus.splits["test"]:
            result["test_ppl"] = evaluate(model, corpus.splits["test"], cfg, device, amp_dtype)
        (run_dir / "metrics.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    log(json.dumps(result, indent=1))
    return result


def eval_only(data_dir: str | Path, run_dir: str | Path, split: str, device_name: str = "auto") -> float:
    run_dir = Path(run_dir)
    device = pick_device(device_name)
    best = torch.load(run_dir / "best.pt", map_location=device, weights_only=False)
    cfg = build_config(None, None, ["eval_max_batches=0"], base=best["train_config"])
    corpus = load_corpus(Path(data_dir), run_dir, cfg)
    model = LyricsLSTM(ModelConfig(**best["model_config"])).to(device)
    model.load_state_dict(best["model"])
    ppl = evaluate(model, corpus.splits[split], cfg, device, amp_settings(device, cfg.amp)[0])
    print(f"{split} perplexity: {ppl:.2f}")
    return ppl


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # progress shows up live in notebooks and logs
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True, help="directory written by ml.data")
    p.add_argument("--out", required=True, help="run directory (resumed when it holds last.pt)")
    p.add_argument("--preset", choices=sorted(PRESETS), default=None)
    p.add_argument("--config", help="JSON file with TrainConfig fields")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    p.add_argument("--glove", help="glove.6B.zip or glove.6B.300d.txt to initialise the embeddings")
    p.add_argument("--device", default="auto")
    p.add_argument("--fresh", action="store_true", help="delete the run directory first")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--split", default="test", choices=["train", "val", "test"])
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.eval_only:
        eval_only(args.data, args.out, args.split, args.device)
        return 0
    cfg = build_config(args.preset, args.config, args.set)
    train(args.data, args.out, cfg, glove=args.glove, device_name=args.device, fresh=args.fresh, overrides=args.set)
    return 0


if __name__ == "__main__":
    sys.exit(main())
