#!/usr/bin/env python3
"""Validate quality evidence against contract, exact artifacts and risk boundaries."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import assert_no_secrets, load_json, repository_root, validate_schema_instance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--artifacts-manifest", required=True)
    args = parser.parse_args()
    root = repository_root()
    evidence_path = Path(args.evidence)
    artifacts_path = Path(args.artifacts_manifest)
    if not evidence_path.is_absolute():
        evidence_path = root / evidence_path
    if not artifacts_path.is_absolute():
        artifacts_path = root / artifacts_path
    evidence = load_json(evidence_path)
    artifacts = load_json(artifacts_path)
    schema = load_json(root / "schemas/quality-evidence.schema.json")
    errors = validate_schema_instance(evidence, schema, schema)
    if errors:
        raise SystemExit("quality evidence schema errors: " + "; ".join(errors))
    if evidence.get("source_commit") != artifacts.get("source_commit"):
        raise SystemExit("quality evidence source commit mismatch")
    exact_by_component = {item["component"]: item for item in artifacts.get("artifacts", [])}
    for item in evidence.get("artifacts", []):
        exact = exact_by_component.get(item["component"])
        if exact is None or exact.get("sha256") != item.get("sha256") or exact.get("size") != item.get("size"):
            raise SystemExit(f"quality evidence artifact mismatch: {item.get('component')}")
        forbidden = [name for name in item.get("files", []) if Path(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".sqlite", ".sqlite3", ".db", ".env"}]
        if forbidden:
            raise SystemExit("runtime media or secrets entered evidence inventory: " + ", ".join(forbidden))
    if evidence.get("deployment", {}).get("automatic_from_main") is not False:
        raise SystemExit("automatic deployment from main is forbidden")
    if evidence.get("contracts", {}).get("target_media_mode") != "edge_v2":
        raise SystemExit("target edge media boundary missing")
    if evidence_path.stat().st_size > load_json(root / "data/quality/reliability-budget-v1.json")["limits"]["maximum_quality_evidence_bytes"]:
        raise SystemExit("quality evidence exceeds reliability budget")
    assert_no_secrets([evidence_path])
    print("Quality evidence valid: exact commit, artifacts, media boundary and controlled deployment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
