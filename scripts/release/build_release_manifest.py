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
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def validate_sha(value: str, label: str) -> str:
    if value != value.lower() or not SHA_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact lowercase full 40-character Git SHA")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.as_posix(), "sha256": sha256_bytes(data), "sizeBytes": len(data)}


def manifest_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def scope_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def created_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def load_authorization(path: Path, source_commit: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "sea_speed_production_authorization_evidence_v1":
        raise ValueError("unsupported production authorization evidence")
    if payload.get("sourceCommit") != source_commit:
        raise ValueError("authorization evidence sourceCommit mismatch")
    if not isinstance(payload.get("canonicalIssue"), int) or payload["canonicalIssue"] <= 0:
        raise ValueError("authorization evidence must contain canonical Issue")
    if not isinstance(payload.get("pullRequest"), int) or payload["pullRequest"] <= 0:
        raise ValueError("authorization evidence must contain pull request")
    approved = payload.get("approvedFiles")
    if not isinstance(approved, list) or not approved or approved != sorted(set(approved)):
        raise ValueError("authorization evidence approvedFiles must be a sorted non-empty unique list")
    for key in ("outcomeContractHash", "changeContractHash", "authorizationFingerprint"):
        value = payload.get(key)
        if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
            raise ValueError(f"authorization evidence {key} must be SHA-256")
    return payload


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    source_commit = validate_sha(args.source_commit, "source commit")
    base_commit = validate_sha(args.base_commit, "base commit")
    authorization = load_authorization(args.authorization_evidence, source_commit)
    approved_files = list(authorization["approvedFiles"])
    actual_files = sorted(line for line in git("diff", "--name-only", base_commit, source_commit).splitlines() if line)
    if not actual_files:
        raise ValueError("actual Git diff must not be empty")
    if actual_files != approved_files:
        raise ValueError(f"actual Git diff does not match approved scope: approved={approved_files} actual={actual_files}")
    artifacts = [file_digest(Path(item)) for item in args.artifact or []]
    if args.state == "ready_for_deployment" and args.component != "governance" and not artifacts:
        raise ValueError("ready_for_deployment requires at least one exact artifact")
    binding = {
        "canonicalIssue": authorization["canonicalIssue"],
        "pullRequest": authorization["pullRequest"],
        "sourceCommit": source_commit,
        "baseCommit": base_commit,
        "outcomeContractHash": authorization["outcomeContractHash"],
        "changeContractHash": authorization["changeContractHash"],
        "approvedFiles": approved_files,
    }
    approved_scope_hash = scope_hash(binding)
    evidence: dict[str, str] = {
        "productionAuthorizationSha256": manifest_digest(args.authorization_evidence),
    }
    if args.exact_artifacts_manifest:
        evidence["exactArtifactsManifestSha256"] = manifest_digest(args.exact_artifacts_manifest)
    if args.quality_evidence:
        evidence["qualityEvidenceSha256"] = manifest_digest(args.quality_evidence)
    return {
        "schema": "sea_speed_release_manifest_v2",
        "deliveryId": f"{args.component}-{source_commit[:12]}-{approved_scope_hash[:12]}",
        "component": args.component,
        "canonicalIssue": authorization["canonicalIssue"],
        "pullRequest": authorization["pullRequest"],
        "sourceCommit": source_commit,
        "baseCommit": base_commit,
        "outcomeContractHash": authorization["outcomeContractHash"],
        "changeContractHash": authorization["changeContractHash"],
        "authorizationFingerprint": authorization["authorizationFingerprint"],
        "approvedScopeHash": approved_scope_hash,
        "approvedFiles": approved_files,
        "actualFiles": actual_files,
        "artifacts": artifacts,
        "evidence": evidence,
        "createdAt": created_at(),
        "state": args.state,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True, choices=("vps", "ubuntu-worker", "windows-worker", "mixed", "governance"))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--authorization-evidence", required=True, type=Path)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--exact-artifacts-manifest", type=Path)
    parser.add_argument("--quality-evidence", type=Path)
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
