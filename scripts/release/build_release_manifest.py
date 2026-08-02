#!/usr/bin/env python3
"""Build a non-secret Sea Speed release provenance manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_RE = re.compile(r"#(\d+)")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def validate_sha(value: str, label: str) -> str:
    normalized = value.lower()
    if not SHA_RE.fullmatch(normalized):
        raise ValueError(f"{label} must be a full 40-character Git SHA")
    return normalized


def discover_issue(source_commit: str, explicit_issue: int) -> int:
    if explicit_issue > 0:
        return explicit_issue
    try:
        message = git("log", "-1", "--format=%B", source_commit)
    except Exception:
        return 0
    match = ISSUE_RE.search(message)
    return int(match.group(1)) if match else 0


def scope_hash(base_commit: str, source_commit: str, files: list[str]) -> str:
    payload = {"baseCommit": base_commit, "sourceCommit": source_commit, "approvedFiles": files}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": path.as_posix(), "sha256": digest.hexdigest(), "sizeBytes": path.stat().st_size}


def created_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    source_commit = validate_sha(args.source_commit, "source commit")
    base_commit = validate_sha(args.base_commit, "base commit")
    files = sorted(set(args.file or []))
    if not files:
        files = sorted(line for line in git("diff", "--name-only", base_commit, source_commit).splitlines() if line)
    if not files:
        raise ValueError("approved file set must not be empty")
    artifacts = [file_digest(Path(item)) for item in args.artifact or []]
    approved_scope_hash = scope_hash(base_commit, source_commit, files)
    return {
        "schema": "sea_speed_release_manifest_v1",
        "deliveryId": f"{args.component}-{source_commit[:12]}-{approved_scope_hash[:12]}",
        "component": args.component,
        "issue": discover_issue(source_commit, args.issue),
        "sourceCommit": source_commit,
        "baseCommit": base_commit,
        "approvedScopeHash": approved_scope_hash,
        "approvedFiles": files,
        "artifacts": artifacts,
        "createdAt": created_at(),
        "state": args.state,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True, choices=("vps", "windows-worker", "mixed", "governance"))
    parser.add_argument("--issue", type=int, default=0)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--state", default="validated", choices=("validated", "packaged", "ready_for_deployment"))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Release manifest written: {args.output}")
    print(f"Delivery ID: {manifest['deliveryId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
