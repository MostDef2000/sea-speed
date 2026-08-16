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
    request_path = root / ".github/workflows/deploy-vps-request.yml"
    quality = quality_path.read_text(encoding="utf-8-sig")
    deploy = deploy_path.read_text(encoding="utf-8-sig")
    request = request_path.read_text(encoding="utf-8-sig")

    for marker in (
        "name: Quality integration gate", "pull_request:", "push:", "workflow_dispatch:", "contents: read",
        "static-contract-security:", "property-fuzz-reliability:", "exact-artifact-e2e:",
        "release-deployment-evidence:", "quality-integration:", "if: always()", "validate_sdd.py --event",
    ):
        if marker not in quality:
            fail(f"quality workflow marker missing: {marker}")
    if re.search(r"^\s+paths(?:-ignore)?:", quality, re.MULTILINE):
        fail("aggregate workflow must not use path filters")
    aggregate_block = quality[quality.index("  quality-integration:"):]
    for dependency in ("static-contract-security", "property-fuzz-reliability", "exact-artifact-e2e", "release-deployment-evidence"):
        if dependency not in aggregate_block:
            fail(f"aggregate job does not depend on {dependency}")

    on_block = deploy.split("permissions:", 1)[0]
    for marker in ("workflow_dispatch:", "workflow_call:"):
        if marker not in on_block:
            fail(f"VPS deployment must support {marker.rstrip(':')}")
    if re.search(r"^\s{2}(push|pull_request|issue_comment):", on_block, re.MULTILINE):
        fail("VPS deployment implementation must not run directly from push, pull_request, or issue_comment")
    for marker in (
        "commit_sha:", "canonical_issue:", "environment: production", "issues: read", "pull-requests: read",
        "refs/heads/main", "--first-parent", "verify_quality_status.py", "--workflow-file quality-integration.yml",
        "verify_production_authorization.py", "production-authorization.json", "Build exact deployment artifacts",
        "Build and validate quality evidence", "Build release provenance v2",
    ):
        if marker not in deploy:
            fail(f"controlled deployment marker missing: {marker}")
    if "${INPUT_COMMIT,,}" in deploy:
        fail("deployment workflow must reject uppercase SHA rather than normalize it")
    if deploy.index("verify_production_authorization.py") > deploy.index("Configure SSH"):
        fail("production authorization must be verified before SSH configuration")
    if deploy.index("verify_quality_status.py") > deploy.index("Configure SSH"):
        fail("quality evidence must be verified before SSH configuration")

    request_on_block = request.split("permissions:", 1)[0]
    if "issue_comment:" not in request_on_block or "types: [created]" not in request_on_block:
        fail("VPS deployment request workflow must trigger only from created issue_comment events")
    if re.search(r"^\s{2}(push|pull_request|workflow_dispatch):", request_on_block, re.MULTILINE):
        fail("VPS deployment request workflow must not run from push, pull_request, or workflow_dispatch")
    for marker in (
        "startsWith(github.event.comment.body, 'DEPLOY VPS ')",
        "!github.event.issue.pull_request",
        "scripts/release/parse_deployment_request.py",
        "uses: ./.github/workflows/deploy-vps.yml",
        "secrets: inherit",
        "canonical_issue:",
        "commit_sha:",
    ):
        if marker not in request:
            fail(f"VPS deployment request marker missing: {marker}")
    for forbidden in ("environment: production", "Configure SSH", "VPS_SSH_PRIVATE_KEY", "VPS_HOST", "ssh -i"):
        if forbidden in request:
            fail(f"VPS request workflow must delegate protected execution; forbidden marker: {forbidden}")

    for workflow_path in sorted((root / ".github/workflows").glob("*.y*ml")):
        try:
            validate_workflow_source(workflow_path.read_text(encoding="utf-8-sig"), str(workflow_path.relative_to(root)))
        except ValueError as exc:
            fail(str(exc))
    print(
        "Workflow policy valid: immutable actions, aggregate SDD gate, reusable exact-main deployment, "
        "Connector-addressable Issue request, durable authorization"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
