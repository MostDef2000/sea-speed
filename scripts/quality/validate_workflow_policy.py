#!/usr/bin/env python3
"""Validate aggregate quality and autonomous controlled-deployment workflow policy."""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from scripts.quality.common import repository_root
except ModuleNotFoundError:
    def repository_root() -> Path:
        return Path(__file__).resolve().parents[2]

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
                raise ValueError(f"{file}:{line_no} has an unquoted if expression containing ': '; quote the whole YAML scalar")
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
                    raise ValueError(f"{file}:{candidate_index + 1} shell heredoc content escapes its YAML run block indentation")


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
    autonomous = (workflows / "deploy-runtime-autonomous.yml").read_text(encoding="utf-8-sig")
    deploy_vps = (workflows / "deploy-vps.yml").read_text(encoding="utf-8-sig")
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

    _require_markers(
        autonomous,
        "deploy-runtime-autonomous.yml",
        (
            "name: Autonomous runtime deployment", "workflow_run:", 'workflows: ["Quality integration gate"]',
            "github.event.workflow_run.conclusion == 'success'", "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'", "environment: production",
            "Require quality commit is current main tip", "refs/remotes/origin/main", "Ignoring stale successful Quality run",
            "steps.freshness.outputs.fresh == 'true'", "Verify public protected production source",
            "verify_source_protection.py", '--require-context "quality-integration"',
            "vars.SEA_SPEED_PRODUCTION_DELEGATION_V1", "evaluate_production_policy.py",
            "uses: ./.github/workflows/deploy-vps.yml", "uses: ./.github/workflows/deploy-ubuntu-worker.yml",
        ),
    )
    if autonomous.index("verify_source_protection.py") > autonomous.index("evaluate_production_policy.py"):
        fail("autonomous router must verify source protection before production policy evaluation")
    for forbidden in ("issue_comment:", "PRODUCTION APPROVED", "Authorization-Fingerprint", "Execution-Intent: EXECUTE", "DEPLOY VPS "):
        if forbidden in autonomous:
            fail(f"autonomous runtime router must not use legacy comment authority: {forbidden}")

    for obsolete in ("deploy-runtime-request.yml", "deploy-vps-request.yml"):
        if (workflows / obsolete).exists():
            fail(f"legacy comment-trigger deployment workflow must be absent: {obsolete}")

    for file, source, contour_marker in (
        ("deploy-vps.yml", deploy_vps, "Require VPS contour in exact Change Contract"),
        ("deploy-ubuntu-worker.yml", deploy_ubuntu, "Require Ubuntu contour in exact Change Contract"),
    ):
        on_block = source.split("permissions:", 1)[0]
        for marker in ("workflow_dispatch:", "workflow_call:"):
            if marker not in on_block:
                fail(f"{file} must support {marker.rstrip(':')}")
        if re.search(r"^\s{2}(push|pull_request|issue_comment):", on_block, re.MULTILINE):
            fail(f"{file} must not run directly from push, pull_request, or issue_comment")
        _require_markers(
            source,
            file,
            (
                "environment: production", "refs/heads/main", "--first-parent", "verify_quality_status.py",
                "Verify public protected production source", "verify_source_protection.py",
                '--require-context "quality-integration"',
                "evaluate_production_policy.py", "--require-allow", "vars.SEA_SPEED_PRODUCTION_DELEGATION_V1",
                "production-policy-decision.json", "Build release provenance v3" if file == "deploy-vps.yml" else "Build exact artifacts and Ubuntu release provenance",
                "--policy-decision-evidence", contour_marker, "build_execution_audit.py",
            ),
        )
        if source.index("verify_source_protection.py") > source.index("evaluate_production_policy.py"):
            fail(f"{file} must verify source protection before production policy evaluation")
        for forbidden in ("verify_production_authorization.py", "PRODUCTION APPROVED", "Authorization-Fingerprint", "Execution-Intent: EXECUTE"):
            if forbidden in source:
                fail(f"{file} must not consume legacy production approval authority: {forbidden}")
        transport_marker = "Configure SSH" if file == "deploy-vps.yml" else "Configure restricted VPS ProxyJump to Ubuntu Worker"
        if source.index("evaluate_production_policy.py") > source.index(transport_marker):
            fail(f"{file} must evaluate production policy before runtime transport")

    _require_markers(
        deploy_ubuntu,
        "deploy-ubuntu-worker.yml",
        (
            "UBUNTU_DEPLOY_SSH_PRIVATE_KEY", "UBUNTU_DEPLOY_SSH_KNOWN_HOSTS", "VPS_SSH_PRIVATE_KEY",
            "VPS_SSH_KNOWN_HOSTS", "ProxyJump sea-speed-vps-jump", "HostName 10.123.239.102",
            "User sea-speed-deploy", "StrictHostKeyChecking yes", "ClearAllForwardings yes",
            "sea-speed-ubuntu-deploy-v1", "Operator actions expected: 0",
            "deploy/worker/ubuntu/deploy-authorized.sh",
        ),
    )
    for forbidden in ("ubuntu-worker-one-command.sh", "Build one-command fallback", "one-command-fallback evidence", "StrictHostKeyChecking=no"):
        if forbidden in deploy_ubuntu:
            fail(f"Ubuntu zero-touch workflow must not retain manual fallback execution: {forbidden}")

    for marker in (
        'SEA_SPEED_REQUIRE_AUTH_BOUNDARY: "1"',
        'SEA_SPEED_AUTHENTIK_UPSTREAM: "http://10.123.239.102:19000"',
        'SEA_SPEED_WORKER_PRIVATE_LISTEN: "10.123.239.101:18080"',
        'SEA_SPEED_WORKER_PRIVATE_PEER: "10.123.239.102"',
        "Deploy exact commit and reconcile Road private M2M boundary", "auth_v1_road_private_m2m",
    ):
        if marker not in deploy_vps:
            fail(f"deploy-vps.yml protected marker missing: {marker}")

    for workflow_path in sorted(workflows.glob("*.y*ml")):
        try:
            validate_workflow_source(workflow_path.read_text(encoding="utf-8-sig"), str(workflow_path.relative_to(root)))
        except ValueError as exc:
            fail(str(exc))

    print("Workflow policy valid: protected public main -> exact quality -> standing policy -> restricted VPS/Ubuntu zero-touch execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
