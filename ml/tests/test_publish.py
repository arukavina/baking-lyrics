"""publish.py tests with a fake S3 client: never touches AWS."""

import hashlib
import json

import pytest

from ml.publish import main, publish_bundle, validate_bundle


class FakeS3:
    def __init__(self, existing: int = 0):
        self.existing = existing
        self.uploads: list[tuple[str, str, dict]] = []
        self.puts: list[dict] = []

    def list_objects_v2(self, **kw):
        return {"KeyCount": self.existing}

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append((bucket, key, ExtraArgs))

    def put_object(self, **kw):
        self.puts.append(kw)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "v1"
    root.mkdir()
    files = {"model.onnx": b"onnx", "vocab.json": b"{}", "artists.json": b"{}", "samples.md": b"# s"}
    for name, data in files.items():
        (root / name).write_bytes(data)
    config = {"format_version": 1, "name": "lyrics-lstm", "version": "v1", "created_at": "2026-11-22T00:00:00Z",
              "training": {"metrics": {"best_val_ppl": 50.0, "test_ppl": 51.0}},
              "files": {n: {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for n, d in files.items()}}
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def test_publish_uploads_files_then_latest(bundle):
    s3 = FakeS3()
    latest = publish_bundle(bundle, client=s3, log=lambda *_: None)
    keys = [k for _, k, _ in s3.uploads]
    assert sorted(keys) == sorted(f"models/lyrics-lstm/v1/{n}" for n in
                                  ["model.onnx", "vocab.json", "artists.json", "samples.md", "config.json"])
    assert {b for b, _, _ in s3.uploads} == {"bakinglyrics"}
    assert s3.puts[0]["Key"] == "models/lyrics-lstm/latest.json"
    body = json.loads(s3.puts[0]["Body"])
    assert body == latest and body["prefix"] == "models/lyrics-lstm/v1/" and body["metrics"]["test_ppl"] == 51.0


def test_publish_refuses_existing_version(bundle):
    with pytest.raises(SystemExit):
        publish_bundle(bundle, client=FakeS3(existing=1), log=lambda *_: None)
    s3 = FakeS3(existing=1)
    publish_bundle(bundle, client=s3, overwrite=True, update_latest=False, log=lambda *_: None)
    assert s3.uploads and not s3.puts


def test_dry_run_makes_no_calls(bundle, capsys):
    assert main([str(bundle), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would upload model.onnx" in out and "latest.json" in out


def test_validate_detects_tampering(bundle):
    (bundle / "vocab.json").write_bytes(b"changed")
    with pytest.raises(ValueError):
        validate_bundle(bundle)
    (bundle / "model.onnx").unlink()
    with pytest.raises(ValueError):
        validate_bundle(bundle)
