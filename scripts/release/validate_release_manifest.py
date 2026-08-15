#!/usr/bin/env python3
"""Validate Sea Speed release manifests while preserving legacy v1 readability."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
V1_COMPONENTS = {"vps", "windows-worker", "mixed", "governance"}
V2_COMPONENTS = {"vps", "ubuntu-worker", "windows-worker", "mixed", "governance"}
STATES = {"validated", "packaged", "ready_for_deployment"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_artifacts(artifacts: object, root: Path | None) -> None:
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
            if not local.is_file() or local.stat().st_size != size or file_sha256(local) != digest:
                fail(f"artifact does not match manifest: {local}")


def validate_v1(payload: dict[str, object], root: Path | None) -> None:
    required = {"schema", "deliveryId", "component", "issue", "sourceCommit", "baseCommit", "approvedScopeHash", "approvedFiles", "artifacts", "createdAt", "state"}
    missing = required - payload.keys()
    if missing:
        fail("missing v1 fields: " + ", ".join(sorted(missing)))
    if payload["component"] not in V1_COMPONENTS or payload["state"] not in STATES:
        fail("invalid legacy release component or state")
    if not isinstance(payload["issue"], int) or payload["issue"] < 0:
        fail("legacy issue must be a non-negative integer")
    for key in ("sourceCommit", "baseCommit"):
        if not isinstance(payload[key], str) or not SHA_RE.fullmatch(payload[key]):
            fail(f"{key} must be a lowercase full Git SHA")
    files = payload["approvedFiles"]
    if not isinstance(files, list) or not files or files != sorted(set(files)):
        fail("approvedFiles must be a non-empty sorted unique list")
    expected = canonical_hash({"baseCommit": payload["baseCommit"], "sourceCommit": payload["sourceCommit"], "approvedFiles": files})
    if payload["approvedScopeHash"] != expected:
        fail("legacy approvedScopeHash mismatch")
    validate_artifacts(payload["artifacts"], root)


def validate_v2(payload: dict[str, object], root: Path | None) -> None:
    required = {
        "schema", "deliveryId", "component", "canonicalIssue", "pullRequest", "sourceCommit", "baseCommit",
        "outcomeContractHash", "changeContractHash", "authorizationFingerprint", "approvedScopeHash",
        "approvedFiles", "actualFiles", "artifacts", "evidence", "createdAt", "state",
    }
    missing = required - payload.keys()
    if missing:
        fail("missing v2 fields: " + ", ".join(sorted(missing)))
    if payload["component"] not in V2_COMPONENTS or payload["state"] not in STATES:
        fail("invalid release component or state")
    if not isinstance(payload["canonicalIssue"], int) or payload["canonicalIssue"] <= 0:
        fail("canonicalIssue must be positive")
    if not isinstance(payload["pullRequest"], int) or payload["pullRequest"] <= 0:
        fail("pullRequest must be positive")
    for key in ("sourceCommit", "baseCommit"):
        if not isinstance(payload[key], str) or not SHA_RE.fullmatch(payload[key]):
            fail(f"{key} must be a lowercase full Git SHA")
    for key in ("outcomeContractHash", "changeContractHash", "authorizationFingerprint", "approvedScopeHash"):
        if not isinstance(payload[key], str) or not DIGEST_RE.fullmatch(payload[key]):
            fail(f"{key} must be a lowercase SHA-256")
    approved = payload["approvedFiles"]
    actual = payload["actualFiles"]
    if not isinstance(approved, list) or not approved or approved != sorted(set(approved)):
        fail("approvedFiles must be a non-empty sorted unique list")
    if not isinstance(actual, list) or not actual or actual != sorted(set(actual)):
        fail("actualFiles must be a non-empty sorted unique list")
    if actual != approved:
        fail("actualFiles must exactly match the approved Change Contract scope")
    binding = {
        "canonicalIssue": payload["canonicalIssue"],
        "pullRequest": payload["pullRequest"],
        "sourceCommit": payload["sourceCommit"],
        "baseCommit": payload["baseCommit"],
        "outcomeContractHash": payload["outcomeContractHash"],
        "changeContractHash": payload["changeContractHash"],
        "approvedFiles": approved,
    }
    if payload["approvedScopeHash"] != canonical_hash(binding):
        fail("approvedScopeHash does not bind Issue/PR/Outcome/Change Contract and scope")
    validate_artifacts(payload["artifacts"], root)
    if payload["state"] == "ready_for_deployment" and payload["component"] != "governance" and not payload["artifacts"]:
        fail("ready_for_deployment requires exact artifacts")
    evidence = payload["evidence"]
    if not isinstance(evidence, dict) or not evidence:
        fail("v2 evidence bindings are required")
    for key, value in evidence.items():
        if not key.endswith("Sha256") or not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
            fail(f"invalid evidence binding: {key}")


def validate(payload: dict[str, object], root: Path | None = None) -> None:
    schema = payload.get("schema")
    if schema == "sea_speed_release_manifest_v1":
        validate_v1(payload, root)
    elif schema == "sea_speed_release_manifest_v2":
        validate_v2(payload, root)
    else:
        fail("unexpected release manifest schema")


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
