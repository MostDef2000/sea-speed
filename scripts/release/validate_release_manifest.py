#!/usr/bin/env python3
"""Validate a Sea Speed release manifest without external dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
COMPONENTS = {"vps", "windows-worker", "mixed", "governance"}
STATES = {"validated", "packaged", "ready_for_deployment"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def expected_scope_hash(payload: dict[str, object]) -> str:
    source = {
        "baseCommit": payload["baseCommit"],
        "sourceCommit": payload["sourceCommit"],
        "approvedFiles": payload["approvedFiles"],
    }
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(payload: dict[str, object], root: Path | None = None) -> None:
    required = {
        "schema", "deliveryId", "component", "issue", "sourceCommit", "baseCommit",
        "approvedScopeHash", "approvedFiles", "artifacts", "createdAt", "state",
    }
    missing = required - payload.keys()
    if missing:
        fail("missing fields: " + ", ".join(sorted(missing)))
    if payload["schema"] != "sea_speed_release_manifest_v1":
        fail("unexpected release manifest schema")
    if payload["component"] not in COMPONENTS:
        fail("invalid component")
    if payload["state"] not in STATES:
        fail("invalid release state")
    if not isinstance(payload["issue"], int) or payload["issue"] < 0:
        fail("issue must be a non-negative integer")
    for key in ("sourceCommit", "baseCommit"):
        if not isinstance(payload[key], str) or not SHA_RE.fullmatch(payload[key]):
            fail(f"{key} must be a lowercase full Git SHA")
    files = payload["approvedFiles"]
    if not isinstance(files, list) or not files or files != sorted(set(files)):
        fail("approvedFiles must be a non-empty sorted unique list")
    if payload["approvedScopeHash"] != expected_scope_hash(payload):
        fail("approvedScopeHash does not match commit and file scope")
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        fail("artifacts must be a list")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            fail("artifact entry must be an object")
        path = artifact.get("path")
        digest = artifact.get("sha256")
        size = artifact.get("sizeBytes")
        if not isinstance(path, str) or not path:
            fail("artifact path is required")
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            fail(f"invalid artifact digest for {path}")
        if not isinstance(size, int) or size < 0:
            fail(f"invalid artifact size for {path}")
        if root is not None:
            local = root / path
            if not local.is_file():
                fail(f"artifact is missing: {local}")
            if local.stat().st_size != size or file_sha256(local) != digest:
                fail(f"artifact does not match manifest: {local}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("manifest root must be an object")
    validate(payload, args.root)
    print(f"Release manifest valid: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
