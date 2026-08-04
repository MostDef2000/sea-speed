#!/usr/bin/env python3
"""Build deterministic release-quality evidence for exact artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import SHA40_RE, load_json, repository_root, sha256_file, write_json_atomic

DEPENDENCY_FILES = (
    "api/requirements.txt",
    "worker/requirements.txt",
    "requirements.txt",
    "pyproject.toml",
    "package-lock.json",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifacts-manifest", required=True)
    parser.add_argument("--output", default="dist/quality-evidence.json")
    args = parser.parse_args()
    source_commit = args.source_commit.lower()
    if not SHA40_RE.fullmatch(source_commit):
        raise SystemExit("source commit must be a full lowercase 40-character SHA")
    root = repository_root()
    artifacts_path = Path(args.artifacts_manifest)
    if not artifacts_path.is_absolute():
        artifacts_path = root / artifacts_path
    artifacts_manifest = load_json(artifacts_path)
    if artifacts_manifest.get("source_commit") != source_commit:
        raise SystemExit("artifact manifest source commit mismatch")

    artifacts = []
    for artifact in artifacts_manifest.get("artifacts", []):
        archive_path = artifacts_path.parent / artifact["filename"]
        if sha256_file(archive_path) != artifact["sha256"]:
            raise SystemExit(f"artifact digest mismatch: {artifact['component']}")
        artifacts.append({
            "component": artifact["component"],
            "filename": artifact["filename"],
            "sha256": artifact["sha256"],
            "size": artifact["size"],
            "files": [entry["path"] for entry in artifact["files"]],
        })

    dependency_inventory = []
    for name in DEPENDENCY_FILES:
        path = root / name
        if path.is_file():
            dependency_inventory.append({"path": name, "sha256": sha256_file(path), "size": path.stat().st_size})

    evidence = {
        "schema": "sea_speed_quality_evidence_v1",
        "source_commit": source_commit,
        "quality_context": "Quality integration gate / quality-integration",
        "state": "ready_for_deployment",
        "artifacts": sorted(artifacts, key=lambda item: item["component"]),
        "contracts": {
            "contract_set": "sea-speed-contracts-v1",
            "active_media_mode": "mvp_v1",
            "target_media_mode": "edge_v2",
        },
        "deployment": {
            "automatic_from_main": False,
            "approval": "production environment",
            "exact_commit_required": True,
        },
        "rollback": {
            "required": True,
            "instructions": "Deploy the previously runtime-verified full commit SHA and validate its deployment manifest before reopening traffic.",
        },
        "sbom": {
            "format": "source-dependency-inventory-v1",
            "dependency_files": dependency_inventory,
        },
        "accepted_risk_register": "data/quality/accepted-risks-v1.json",
        "branch_protection": "not independently verified by this evidence bundle",
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    write_json_atomic(output, evidence)
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
