#!/usr/bin/env python3
"""Validate the canonical Sea Speed contract set and documentation links."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CANONICAL_FILES = (
    "AGENTS.md",
    "README.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/task-intake.md",
    "contracts/branches/project-manager.md",
    "contracts/branches/core-release.md",
    "data/contracts/sea-speed-contracts-v1.schema.json",
    "data/contracts/fixtures-v1.json",
    "data/contracts/contract-policy-v1.json",
    "data/contracts/change-control-policy-v1.json",
    "data/quality/quality-gates-v1.json",
    "data/quality/reliability-budget-v1.json",
    "data/quality/accepted-risks-v1.json",
    "docs/architecture/sea-speed-control-plane.md",
    "docs/quality/testing-policy.md",
    "docs/quality/quality-gate-architecture.md",
    "docs/decision_records/DR-001-two-runtime-delivery-model.md",
    "docs/decision_records/DR-002-task-intake-and-delivery-controls.md",
    "docs/decision_records/DR-003-release-provenance-and-evidence-loop.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
    "docs/evidence/POST_RELEASE_REVIEW.md",
    "schemas/release-manifest.schema.json",
    "schemas/deployment-manifest.schema.json",
    "schemas/telemetry.schema.json",
    "schemas/quality-evidence.schema.json",
    "scripts/release/build_release_manifest.py",
    "scripts/release/validate_release_manifest.py",
    "scripts/release/validate_deployment_manifest.py",
    "scripts/ci/validate_change_contract.py",
    "scripts/ci/validate_telemetry.py",
    "scripts/quality/validate_quality_contracts.py",
    "scripts/quality/validate_workflow_policy.py",
    "scripts/quality/build_exact_artifacts.py",
    "scripts/quality/validate_exact_artifacts.py",
    "scripts/quality/build_quality_evidence.py",
    "scripts/quality/validate_quality_evidence.py",
    "scripts/quality/verify_quality_status.py",
    "scripts/operations/verify_runtime.py",
    ".github/workflows/quality-integration.yml",
    ".github/workflows/deploy-vps.yml",
)

REFERENCE_FILES = (
    "AGENTS.md",
    "README.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/task-intake.md",
    "contracts/branches/project-manager.md",
    "contracts/branches/core-release.md",
    "docs/architecture/sea-speed-control-plane.md",
    "docs/quality/testing-policy.md",
    "docs/quality/quality-gate-architecture.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
    "docs/evidence/POST_RELEASE_REVIEW.md",
)

REPO_PATH_PATTERN = re.compile(
    r"`((?:contracts|data|docs|scripts|deploy|api|frontend|worker|tests|schemas|\.github)/[^`\n]+)`"
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
        if source_name != "README.md" and "Status: Active" not in text and "Status: Accepted" not in text:
            fail(f"active or accepted status marker missing from {source_name}")
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
