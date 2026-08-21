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
    "data/contracts/production-authorization-policy-v1.json",
    "data/quality/quality-gates-v1.json",
    "data/quality/reliability-budget-v1.json",
    "data/quality/accepted-risks-v1.json",
    "docs/architecture/sea-speed-control-plane.md",
    "docs/quality/testing-policy.md",
    "docs/quality/quality-gate-architecture.md",
    "docs/decision_records/DR-001-two-runtime-delivery-model.md",
    "docs/decision_records/DR-002-task-intake-and-delivery-controls.md",
    "docs/decision_records/DR-003-release-provenance-and-evidence-loop.md",
    "docs/decision_records/DR-004-delivery-orchestrator-convergence.md",
    "docs/decision_records/DR-005-standing-production-delegation.md",
    "docs/decision_records/DR-006-resumable-delivery-orchestration.md",
    "docs/decision_records/DR-007-synchronous-external-wait.md",
    "docs/agents/PM_BOOTSTRAP.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
    "docs/evidence/POST_RELEASE_REVIEW.md",
    "schemas/release-manifest.schema.json",
    "schemas/deployment-manifest.schema.json",
    "schemas/telemetry.schema.json",
    "schemas/quality-evidence.schema.json",
    "schemas/delivery-checkpoint-v2.schema.json",
    "scripts/release/build_release_manifest.py",
    "scripts/release/validate_release_manifest.py",
    "scripts/release/validate_deployment_manifest.py",
    "scripts/release/verify_production_authorization.py",
    "scripts/ci/validate_change_contract.py",
    "scripts/ci/validate_telemetry.py",
    "scripts/ci/validate_sdd.py",
    "scripts/ci/validate_delivery_checkpoint.py",
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
    "specs/012-delivery-control-hardening/spec.md",
    "specs/013-delivery-orchestrator-convergence/spec.md",
    "specs/013-delivery-orchestrator-convergence/plan.md",
    "specs/013-delivery-orchestrator-convergence/tasks.md",
    "specs/031-resumable-delivery-orchestration/spec.md",
    "specs/031-resumable-delivery-orchestration/plan.md",
    "specs/031-resumable-delivery-orchestration/tasks.md",
    "specs/032-synchronous-external-wait/spec.md",
    "specs/032-synchronous-external-wait/plan.md",
    "specs/032-synchronous-external-wait/tasks.md",
    "tests/test_delivery_resume_contract.py",
    "tests/test_delivery_checkpoint_state_machine.py",
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
    "docs/agents/PM_BOOTSTRAP.md",
    "docs/operations/PRODUCTION_BASELINE.md",
    "docs/operations/RELEASE_PROVENANCE.md",
    "docs/evidence/POST_RELEASE_REVIEW.md",
)

RESUME_CONTRACT_FILES = (
    "AGENTS.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/task-intake.md",
    "contracts/branches/project-manager.md",
    "docs/agents/PM_BOOTSTRAP.md",
    "docs/architecture/sea-speed-control-plane.md",
)

RESUME_MARKERS = (
    "Resume Probe",
    "Delivery Checkpoint v2",
    "Next admissible action",
    "same exact admitted scope",
    "WAITING_EXTERNAL",
)

REPO_PATH_PATTERN = re.compile(r"`((?:contracts|data|docs|scripts|deploy|api|frontend|worker|tests|schemas|specs|\.github)/[^`\n]+)`")


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

    for source_name in RESUME_CONTRACT_FILES:
        text = (ROOT / source_name).read_text(encoding="utf-8-sig")
        missing_markers = [marker for marker in RESUME_MARKERS if marker.lower() not in text.lower()]
        if missing_markers:
            fail(f"resumable delivery markers missing from {source_name}: {', '.join(missing_markers)}")

    runtime = (ROOT / "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md").read_text(encoding="utf-8-sig")
    for reason in (
        "MATERIAL_SCOPE_CHANGE",
        "PROTECTED_BOUNDARY_CHANGE",
        "USER_CHANGED_OUTCOME",
        "MATERIAL_MAIN_DIVERGENCE",
        "EVIDENCE_CONTRADICTION",
    ):
        if reason not in runtime:
            fail(f"task runtime missing resumable invalidation reason: {reason}")
    if "`CONTEXT_LOSS` is intentionally not a valid reason" not in runtime:
        fail("task runtime must explicitly deny context loss as a lifecycle invalidation reason")
    for marker in (
        "ACTIVE", "WAITING_EXTERNAL", "TERMINAL", "schemas/delivery-checkpoint-v2.schema.json",
        "scripts/ci/validate_delivery_checkpoint.py", "executable_now", "resume_trigger", "evidence_cursor",
    ):
        if marker not in runtime:
            fail(f"task runtime missing synchronous wait marker: {marker}")

    print("Sea Speed contract validation passed")
    print(f"Canonical files checked: {len(CANONICAL_FILES)}")
    print(f"Resumable delivery entrypoints checked: {len(RESUME_CONTRACT_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
