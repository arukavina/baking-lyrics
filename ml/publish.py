"""Publish a model bundle to S3 and point `latest.json` at it.

    uv run python -m ml.publish ml/bundles/2026.11.0 --dry-run
    uv run python -m ml.publish ml/bundles/2026.11.0 --profile my-aws-profile

Layout in the bucket (default `bakinglyrics`):
    models/lyrics-lstm/<version>/model.onnx, vocab.json, artists.json, config.json, samples.md
    models/lyrics-lstm/latest.json   -> {"version": ..., "prefix": "models/lyrics-lstm/<version>/", ...}

The bundle files are uploaded first and `latest.json` last, so the API never sees a half uploaded version.
An existing version is never overwritten unless `--overwrite` is given. `--no-latest` uploads without switching.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Iterable
from pathlib import Path

DEFAULT_BUCKET = "bakinglyrics"
DEFAULT_PREFIX = "models/lyrics-lstm"
REQUIRED_FILES = ("model.onnx", "vocab.json", "artists.json", "config.json")
CONTENT_TYPES = {".onnx": "application/octet-stream", ".json": "application/json",
                 ".md": "text/markdown; charset=utf-8"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def validate_bundle(bundle: Path) -> dict:
    """Check required files and the sha256 list in config.json. Returns the config."""
    missing = [f for f in REQUIRED_FILES if not (bundle / f).is_file()]
    if missing:
        raise ValueError(f"{bundle}: missing {missing}")
    config = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
    for name, info in config.get("files", {}).items():
        path = bundle / name
        if not path.is_file():
            raise ValueError(f"{bundle}: config.json lists {name} but it is missing")
        if _sha256(path) != info["sha256"]:
            raise ValueError(f"{bundle}: {name} does not match its sha256 in config.json")
    return config


def build_latest(config: dict, prefix: str) -> dict:
    version = config["version"]
    return {
        "name": config.get("name", "lyrics-lstm"),
        "version": version,
        "prefix": f"{prefix}/{version}/",
        "format_version": config.get("format_version"),
        "created_at": config.get("created_at"),
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": config.get("files", {}),
        "metrics": {k: config.get("training", {}).get("metrics", {}).get(k) for k in ("best_val_ppl", "test_ppl")},
    }


def publish_bundle(bundle: str | Path, bucket: str = DEFAULT_BUCKET, prefix: str = DEFAULT_PREFIX,
                   dry_run: bool = False, update_latest: bool = True, overwrite: bool = False,
                   client=None, log=print) -> dict:
    """Upload `bundle` to s3://bucket/prefix/<version>/ and update prefix/latest.json. Returns latest.json."""
    bundle = Path(bundle)
    prefix = prefix.strip("/")
    config = validate_bundle(bundle)
    version = config["version"]
    target = f"{prefix}/{version}/"
    files = sorted(p for p in bundle.iterdir() if p.is_file())
    latest = build_latest(config, prefix)
    size = sum(p.stat().st_size for p in files)
    log(f"{'[dry run] ' if dry_run else ''}publishing {bundle} ({size / 1e6:.1f} MB) to s3://{bucket}/{target}")
    if dry_run:
        for p in files:
            log(f"  would upload {p.name} -> s3://{bucket}/{target}{p.name}")
        if update_latest:
            log(f"  would write s3://{bucket}/{prefix}/latest.json:\n{json.dumps(latest, indent=1)}")
        return latest
    if client is None:
        import boto3

        client = boto3.client("s3")
    existing = client.list_objects_v2(Bucket=bucket, Prefix=target, MaxKeys=1).get("KeyCount", 0)
    if existing and not overwrite:
        raise SystemExit(f"s3://{bucket}/{target} already exists; pick a new version or pass --overwrite")
    for p in files:
        extra = {"ContentType": CONTENT_TYPES.get(p.suffix, "application/octet-stream"),
                 "Metadata": {"sha256": _sha256(p)}}
        client.upload_file(str(p), bucket, target + p.name, ExtraArgs=extra)
        log(f"  uploaded {p.name}")
    if update_latest:
        client.put_object(Bucket=bucket, Key=f"{prefix}/latest.json", ContentType="application/json",
                          Body=json.dumps(latest, indent=1).encode("utf-8"), CacheControl="no-cache")
        log(f"  latest.json -> {version}")
    return latest


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bundle", help="bundle directory written by ml.export")
    p.add_argument("--bucket", default=DEFAULT_BUCKET)
    p.add_argument("--prefix", default=DEFAULT_PREFIX)
    p.add_argument("--profile", default=None, help="AWS profile (otherwise the default credential chain)")
    p.add_argument("--region", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-latest", action="store_true", help="upload without switching latest.json")
    p.add_argument("--overwrite", action="store_true", help="allow replacing an existing version")
    args = p.parse_args(list(argv) if argv is not None else None)
    client = None
    if not args.dry_run and (args.profile or args.region):
        import boto3

        client = boto3.Session(profile_name=args.profile, region_name=args.region).client("s3")
    publish_bundle(args.bundle, args.bucket, args.prefix, dry_run=args.dry_run, update_latest=not args.no_latest,
                   overwrite=args.overwrite, client=client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
