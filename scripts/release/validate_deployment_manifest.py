#!/usr/bin/env python3
"""Validate a Sea Speed deployment manifest without external dependencies."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
TARGETS = {"vps", "ubuntu-worker", "windows-worker"}
STATES = {"installed", "deployed", "runtime_verified", "rolled_back", "failed"}
CHECK_STATUSES = {"passed", "skipped", "failed"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def valid_version(value: object) -> bool:
    return isinstance(value, str) and (
        bool(SHA_RE.fullmatch(value)) or value == "unmanaged-baseline" or value.startswith("bootstrap-")
    )


def validate(payload: dict[str, object]) -> None:
    required = {
        "schema", "deliveryId", "target", "sourceCommit", "previousVersion",
        "artifactSha256", "installedAt", "checks", "rollbackTarget",
        "runtimeVerified", "state",
    }
    missing = required - payload.keys()
    if missing:
        fail("missing fields: " + ", ".join(sorted(missing)))
    if payload["schema"] != "sea_speed_deployment_manifest_v1":
        fail("unexpected deployment manifest schema")
    if payload["target"] not in TARGETS:
        fail("invalid deployment target")
    if payload["state"] not in STATES:
        fail("invalid deployment state")
    if not valid_version(payload["sourceCommit"]):
        fail("invalid sourceCommit")
    previous = payload["previousVersion"]
    if previous is not None and not valid_version(previous):
        fail("invalid previousVersion")
    rollback = payload["rollbackTarget"]
    if rollback is not None and not valid_version(rollback):
        fail("invalid rollbackTarget")
    artifact = payload["artifactSha256"]
    if artifact is not None and (not isinstance(artifact, str) or not DIGEST_RE.fullmatch(artifact)):
        fail("invalid artifactSha256")
    if not isinstance(payload["runtimeVerified"], bool):
        fail("runtimeVerified must be boolean")
    checks = payload["checks"]
    if not isinstance(checks, list) or not checks:
        fail("checks must be a non-empty list")
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("name"), str):
            fail("invalid check entry")
        if check.get("status") not in CHECK_STATUSES:
            fail(f"invalid status for check {check.get('name')}")
    if payload["runtimeVerified"] and any(check.get("status") == "failed" for check in checks):
        fail("runtimeVerified cannot be true when a check failed")
    if payload["state"] == "runtime_verified" and not payload["runtimeVerified"]:
        fail("runtime_verified state requires runtimeVerified=true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("manifest root must be an object")
    validate(payload)
    print(f"Deployment manifest valid: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
