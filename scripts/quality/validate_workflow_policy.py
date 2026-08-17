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
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Z_][A-Z0-9_]*)\1")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _validate_yaml_sensitive_shell_source(source: str, file: str) -> None:
    lines = source.splitlines()
    for line_no, line in enumerate(lines, 1):
        match = re.match(r"^\s*if:\s*(.+)$", line)
        if match:
            value = match.group(1).strip()
            if value and not value.startswith(("'", '"', "|", ">")) and ": " in value:
                raise ValueError(
                    f"{file}:{line_no} has an unquoted if expression containing ': '; quote the whole YAML scalar"
                )

    for line_index, line in enumerate(lines):
        for match in HEREDOC.finditer(line):
            delimiter = match.group(2)
            opener_indent = _indent_width(line)
            closing_index = None
            for candidate_index in range(line_index + 1, len(lines)):
                if lines[candidate_index].strip() == delimiter:
                    closing_index = candidate_index
                    break
            if closing_index is None:
                raise ValueError(f"{file}:{line_index + 1} has unterminated shell heredoc {delimiter}")
            for candidate_index in range(line_index + 1, closing_index + 1):
                candidate = lines[candidate_index]
                if candidate.strip() and _indent_width(candidate) < opener_indent:
                    raise ValueError(
                        f"{file}:{candidate_index + 1} shell heredoc content escapes its YAML run block indentation"
                    )


def validate_workflow_source(source: str, file: str) -> None:
    _validate_yaml_sensitive_shell_source(source, file)
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


def _require_markers(source: str, file: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        if marker not in source:
            fail(f"{file} marker missing: {marker}")


def main() -> int:
    root = repository_root()
    workflows = root / ".github/workflows"
    quality = (workflows / "quality-integration.yml").read_text(encoding="utf-8-sig")
    deploy_vps = (workflows / "deploy-vps.yml").read_text(encoding="utf-8-sig")
    vps_request = (workflows / "deploy-vps-request.yml").read_text(encoding="utf-8-sig")
    runtime_request = (workflows / "deploy-runtime-request.yml").read_text(encoding="utf-8-sig")
    deploy_ubuntu = (workflows / "deploy-ubuntu-worker.yml").read_text(encoding="utf-8-sig")

    _require_markers(
        quality,
        "quality-integration.yml",
        (
            "name: Quality integration gate", "pull_request:", "push:", "workflow_dispatch:", "contents: read",
            "static-contract-security:", "property-fuzz-reliability:", "exact-artifact-e2e:",
            "release-deployment-evidence:", "quality-integration:", "if: always()", "validate_sdd.py --event",
        ),
    )
    if re.search(r"^\s+paths(?:-ignore)?:", quality, re.MULTILINE):
        fail("aggregate workflow must not use path filters")
    aggregate_block = quality[quality.index("  quality-integration:"):]
    for dependency in ("static-contract-security", "property-fuzz-reliability", "exact-artifact-e2e", "release-deployment-evidence"):
        if dependency not in aggregate_block:
            fail(f"aggregate job does not depend on {dependency}")

    vps_on = deploy_vps.split("permissions:", 1)[0]
    for marker in ("workflow_dispatch:", "workflow_call:"):
        if marker not in vps_on:
            fail(f"VPS deployment must support {marker.rstrip(':')}")
    if re.search(r"^\s{2}(push|pull_request|issue_comment):", vps_on, re.MULTILINE):
        fail("VPS deployment implementation must not run directly from push, pull_request, or issue_comment")
    _require_markers(
        deploy_vps,
        "deploy-vps.yml",
        (
            "commit_sha:", "canonical_issue:", "environment: production", "issues: read", "pull-requests: read",
            "refs/heads/main", "--first-parent", "verify_quality_status.py", "--workflow-file quality-integration.yml",
            "verify_production_authorization.py", "production-authorization.json", "Build exact deployment artifacts",
            "Build and validate quality evidence", "Build release provenance v2",
            "SEA_SPEED_REQUIRE_AUTH_BOUNDARY: \"1\"",
            "SEA_SPEED_AUTHENTIK_UPSTREAM: \"http://10.123.239.102:19000\"",
            "SEA_SPEED_WORKER_PRIVATE_LISTEN: \"10.123.239.101:18080\"",
            "SEA_SPEED_WORKER_PRIVATE_PEER: \"10.123.239.102\"",
            "bash -n deploy/vps/sea-speed-auth-cutover.sh",
            "Deploy exact commit and reconcile Road private M2M boundary",
            "auth_v1_road_private_m2m",
            "VPS Road private M2M deployment evidence valid",
        ),
    )
    if "${INPUT_COMMIT,,}" in deploy_vps:
        fail("deployment workflow must reject uppercase SHA rather than normalize it")
    if deploy_vps.index("verify_production_authorization.py") > deploy_vps.index("Configure SSH"):
        fail("production authorization must be verified before VPS SSH configuration")
    if deploy_vps.index("verify_quality_status.py") > deploy_vps.index("Configure SSH"):
        fail("quality evidence must be verified before VPS SSH configuration")
    if deploy_vps.index("Build exact deployment artifacts") > deploy_vps.index("Configure SSH"):
        fail("exact VPS artifact must be validated before runtime SSH")
    if deploy_vps.index("Deploy exact commit and reconcile Road private M2M boundary") < deploy_vps.index("Configure SSH"):
        fail("VPS boundary reconcile must execute only after protected SSH setup")

    legacy_request_on = vps_request.split("permissions:", 1)[0]
    if "issue_comment:" not in legacy_request_on or "types: [created]" not in legacy_request_on:
        fail("VPS deployment request workflow must trigger only from created issue_comment events")
    _require_markers(
        vps_request,
        "deploy-vps-request.yml",
        (
            "startsWith(github.event.comment.body, 'DEPLOY VPS ')", "!github.event.issue.pull_request",
            "scripts/release/parse_deployment_request.py", "uses: ./.github/workflows/deploy-vps.yml",
            "secrets: inherit", "canonical_issue:", "commit_sha:",
        ),
    )
    for forbidden in ("environment: production", "Configure SSH", "VPS_SSH_PRIVATE_KEY", "VPS_HOST", "ssh -i"):
        if forbidden in vps_request:
            fail(f"VPS request workflow must delegate protected execution; forbidden marker: {forbidden}")

    runtime_on = runtime_request.split("permissions:", 1)[0]
    if "issue_comment:" not in runtime_on or "types: [created]" not in runtime_on:
        fail("runtime execution request must trigger only from created issue_comment events")
    if re.search(r"^\s{2}(push|pull_request|workflow_dispatch):", runtime_on, re.MULTILINE):
        fail("runtime execution request must not run from push, pull_request, or workflow_dispatch")
    _require_markers(
        runtime_request,
        "deploy-runtime-request.yml",
        (
            "startsWith(github.event.comment.body, 'PRODUCTION APPROVED ')",
            "Execution-Intent: EXECUTE", "github.event.issue.pull_request == null",
            "parse_runtime_execution_request.py", "verify_production_authorization.py",
            "--require-execution-intent", "uses: ./.github/workflows/deploy-vps.yml",
            "uses: ./.github/workflows/deploy-ubuntu-worker.yml", "windows-worker-fallback:", "secrets: inherit",
        ),
    )
    for forbidden in ("environment: production", "Configure SSH", "SSH_PRIVATE_KEY", "ssh -i"):
        if forbidden in runtime_request:
            fail(f"runtime request workflow must only parse/verify/route; forbidden marker: {forbidden}")

    ubuntu_on = deploy_ubuntu.split("permissions:", 1)[0]
    for marker in ("workflow_dispatch:", "workflow_call:"):
        if marker not in ubuntu_on:
            fail(f"Ubuntu deployment must support {marker.rstrip(':')}")
    if re.search(r"^\s{2}(push|pull_request|issue_comment):", ubuntu_on, re.MULTILINE):
        fail("Ubuntu deployment implementation must not run directly from push, pull_request, or issue_comment")
    _require_markers(
        deploy_ubuntu,
        "deploy-ubuntu-worker.yml",
        (
            "environment: production", "refs/heads/main", "--first-parent", "verify_quality_status.py",
            "--workflow-file quality-integration.yml", "verify_production_authorization.py",
            "build_exact_artifacts.py", "sea-speed-ubuntu-worker-", "Build one-command fallback",
            "deploy/worker/ubuntu/deploy-authorized.sh", "UBUNTU_DEPLOY_SSH_PRIVATE_KEY",
            "sea-speed-ubuntu-deploy-v1", "deployment-manifest-ubuntu-worker.json",
            "one-command-fallback", "exit 42",
        ),
    )
    if deploy_ubuntu.index("verify_production_authorization.py") > deploy_ubuntu.index("Resolve zero-touch execution capability"):
        fail("Ubuntu authorization must be verified before transport capability resolution")
    if deploy_ubuntu.index("verify_quality_status.py") > deploy_ubuntu.index("Resolve zero-touch execution capability"):
        fail("Ubuntu quality must be verified before transport capability resolution")

    for workflow_path in sorted(workflows.glob("*.y*ml")):
        try:
            validate_workflow_source(workflow_path.read_text(encoding="utf-8-sig"), str(workflow_path.relative_to(root)))
        except ValueError as exc:
            fail(str(exc))
    print(
        "Workflow policy valid: immutable actions, aggregate SDD gate, exact VPS Auth v1 boundary transaction, "
        "two-intent Connector request routing, durable authorization and bounded fallback"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
