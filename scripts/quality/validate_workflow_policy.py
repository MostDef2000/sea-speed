#!/usr/bin/env python3
"""Validate aggregate-gate and controlled-deployment workflow policy."""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import repository_root

ALLOWED_ACTIONS = {"actions/checkout", "actions/setup-python", "actions/setup-node", "actions/upload-artifact"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_workflow_source(source: str, file: str) -> None:
    if re.search(r"^\s*permissions:\s*write-all\s*$", source, re.MULTILINE):
        raise ValueError(f"{file} must not use write-all permissions")
    if re.search(r"^\s*pull_request_target\s*:", source, re.MULTILINE):
        raise ValueError(f"{file} must not use pull_request_target")
    if re.search(r"(?:curl|wget)[^\n|]*\|\s*(?:ba)?sh\b", source):
        raise ValueError(f"{file} must not pipe downloads into a shell")
    if not re.search(r"^permissions:\s*$", source, re.MULTILINE):
        raise ValueError(f"{file} must declare explicit top-level permissions")

    for match in re.finditer(r"^\s*-?\s*uses:\s*([^\s#]+)", source, re.MULTILINE):
        value = match.group(1)
        if value.startswith("./"):
            continue
        action_match = re.fullmatch(r"([^@\s]+)@([^\s]+)", value)
        if not action_match:
            raise ValueError(f"{file} has invalid action reference: {value}")
        action, revision = action_match.groups()
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"unapproved action {action} in {file}")
        if not FULL_SHA.fullmatch(revision):
            raise ValueError(f"{file} action is not pinned to a full commit SHA: {value}")


def main() -> int:
    root = repository_root()
    quality_path = root / ".github/workflows/quality-integration.yml"
    deploy_path = root / ".github/workflows/deploy-vps.yml"
    quality = quality_path.read_text(encoding="utf-8-sig")
    deploy = deploy_path.read_text(encoding="utf-8-sig")

    for marker in ("name: Quality integration gate", "pull_request:", "push:", "workflow_dispatch:", "contents: read", "static-contract-security:", "property-fuzz-reliability:", "exact-artifact-e2e:", "release-deployment-evidence:", "quality-integration:", "if: always()"):
        if marker not in quality:
            fail(f"quality workflow marker missing: {marker}")
    if re.search(r"^\s+paths(?:-ignore)?:", quality, re.MULTILINE):
        fail("aggregate workflow must not use path filters")
    aggregate_block = quality[quality.index("  quality-integration:"):]
    for dependency in ("static-contract-security", "property-fuzz-reliability", "exact-artifact-e2e", "release-deployment-evidence"):
        if dependency not in aggregate_block:
            fail(f"aggregate job does not depend on {dependency}")

    on_block = deploy.split("permissions:", 1)[0]
    if "workflow_dispatch:" not in on_block:
        fail("VPS deployment must be manually dispatched")
    if re.search(r"^\s{2}(push|pull_request):", on_block, re.MULTILINE):
        fail("VPS production deployment must not run on push or pull request")
    for marker in ("commit_sha:", "required: true", "environment: production", "verify_quality_status.py", "--required-name quality-integration", "Build exact deployment artifacts", "Build and validate quality evidence"):
        if marker not in deploy:
            fail(f"controlled deployment marker missing: {marker}")

    for workflow_path in sorted((root / ".github/workflows").glob("*.y*ml")):
        try:
            validate_workflow_source(workflow_path.read_text(encoding="utf-8-sig"), str(workflow_path.relative_to(root)))
        except ValueError as exc:
            fail(str(exc))

    print("Workflow policy valid: immutable actions, least privilege, aggregate gate, explicit deployment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
