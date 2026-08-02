#!/usr/bin/env python3
"""Validate the canonical Sea Speed contract set and documentation links."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CANONICAL_FILES = (
    "README.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/task-intake.md",
    "contracts/branches/project-manager.md",
    "contracts/branches/core-release.md",
    "docs/architecture/sea-speed-control-plane.md",
    "docs/decision_records/DR-001-two-runtime-delivery-model.md",
    "docs/decision_records/DR-002-task-intake-and-delivery-controls.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
    "schemas/release-manifest.schema.json",
    "schemas/deployment-manifest.schema.json",
    "scripts/release/build_release_manifest.py",
    "scripts/release/validate_release_manifest.py",
    "scripts/release/validate_deployment_manifest.py",
)

REFERENCE_FILES = (
    "README.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/task-intake.md",
    "contracts/branches/project-manager.md",
    "contracts/branches/core-release.md",
    "docs/architecture/sea-speed-control-plane.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
)

REPO_PATH_PATTERN = re.compile(
    r"`((?:contracts|docs|scripts|deploy|api|frontend|worker|tests|schemas|\.github)/[^`\n]+)`"
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    missing = [path for path in CANONICAL_FILES if not (ROOT / path).is_file()]
    if missing:
        fail("canonical files are missing: " + ", ".join(sorted(missing)))

    broken: list[str] = []
    for source_name in REFERENCE_FILES:
        source = ROOT / source_name
        text = source.read_text(encoding="utf-8-sig")
        if "Status: Active" not in text and source_name != "README.md":
            fail(f"active status marker missing from {source_name}")

        for match in REPO_PATH_PATTERN.finditer(text):
            target = match.group(1)
            if "*" in target or "<" in target or target.endswith("/**"):
                continue
            if not (ROOT / target).exists():
                broken.append(f"{source_name} -> {target}")

    if broken:
        fail("broken repository references: " + "; ".join(sorted(set(broken))))

    print("Sea Speed contract validation passed")
    print(f"Canonical files checked: {len(CANONICAL_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
