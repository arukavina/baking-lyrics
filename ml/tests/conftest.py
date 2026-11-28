"""Shared fixtures: a tiny prepared dataset and a tiny trained run, built once per test session in a tmp dir."""

import pytest


def _corpus():
    import pandas as pd

    lines = {
        "bee-gees": ["night fever night fever", "we know how to do it", "stayin alive stayin alive",
                     "you should be dancing yeah"],
        "eminem": ["look if you had one shot", "one opportunity to seize", "mom's spaghetti on my sweater",
                   "lose yourself in the music"],
    }
    rows, idx = [], 0
    for artist, pool in lines.items():
        for n in range(12):
            text = "\n".join(pool[(n + i) % len(pool)] for i in range(8))
            rows.append({"index": idx, "song": f"{artist}-song-{n}", "year": 2001, "artist": artist,
                         "genre": "Pop" if artist == "bee-gees" else "Hip-Hop", "lyrics": text + f"\nnumber {n}"})
            idx += 1
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def tiny_data(tmp_path_factory):
    pytest.importorskip("pyarrow")
    from ml.data import PrepConfig, prepare, write_outputs

    out = tmp_path_factory.mktemp("data")
    cfg = PrepConfig(min_songs=5, min_words=5, lang_detector="none", val_frac=0.2, test_frac=0.2)
    df, meta = prepare(_corpus(), cfg, log=lambda *_: None)
    write_outputs(df, meta, out, cfg, source="unit")
    return out


@pytest.fixture(scope="session")
def tiny_run(tmp_path_factory, tiny_data):
    pytest.importorskip("torch")
    from ml.train import build_config, train

    run_dir = tmp_path_factory.mktemp("run")
    cfg = build_config("smoke", None, ["epochs=1", "max_steps_per_epoch=8", "batch_size=4", "min_freq=1",
                                       "sample_words=10", "model.hidden=24", "model.emb_dim=16"])
    train(tiny_data, run_dir, cfg, device_name="cpu", log=lambda *_: None)
    return run_dir, tiny_data
