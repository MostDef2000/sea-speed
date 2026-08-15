#!/usr/bin/env python3
"""Validate a pull request Change Contract against its exact Git diff."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "data/contracts/change-control-policy-v1.json"
FIELD_PATTERN = re.compile(r"^- ([A-Za-z][A-Za-z0-9 /_-]*):\s*(.*?)\s*$", re.MULTILINE)
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
DECLARED_PATH_PATTERN = re.compile(r"^\s{2}- `([^`]+)`\s*$", re.MULTILINE)
PLACEHOLDERS = {
    "", "TBD", "TODO", "TBC", "YES/NO", "NO/YES", "REQUIRED / NOT REQUIRED",
    "OUTCOME APPROVED / LEGACY COMMIT APPROVED",
    "NONE / CONTROL_PLANE / VPS / UBUNTU_WORKER / WINDOWS_WORKER / MIXED",
}
SOURCE_AUTHORIZATIONS = {"OUTCOME APPROVED", "LEGACY COMMIT APPROVED"}
RUNTIME_IMPACTS = {"VPS", "UBUNTU_WORKER", "WINDOWS_WORKER"}


class ContractError(ValueError):
    """Raised when a Change Contract is incomplete or inconsistent."""


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema") != "sea-speed-change-control-policy/v1":
        raise ContractError("unsupported change-control policy schema")
    return policy


def field_values(body: str) -> dict[str, str]:
    return {name: value.strip() for name, value in FIELD_PATTERN.findall(body)}


def section(body: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", body, re.MULTILINE)
    if not match:
        raise ContractError(f"missing PR section: {heading}")
    start = match.end()
    next_heading = re.search(r"^##\s+", body[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end]


def declared_changed_files(body: str) -> set[str]:
    change = section(body, "Change")
    marker = re.search(r"^- Changed files:\s*$", change, re.MULTILINE)
    boundary = re.search(r"^- Out of scope:", change, re.MULTILINE)
    if not marker or not boundary or boundary.start() <= marker.end():
        raise ContractError("Changed files must be an exact backtick list before Out of scope")
    paths = set(DECLARED_PATH_PATTERN.findall(change[marker.end():boundary.start()]))
    if not paths:
        raise ContractError("Changed files list is empty")
    return paths


def classify_file(path: str, policy: dict) -> str:
    for rule in policy["rules"]:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in rule["patterns"]):
            return rule["impact"]
    return "NONE"


def derive_runtime_contours(changed_files: Iterable[str], policy: dict) -> set[str]:
    contours: set[str] = set()
    for path in changed_files:
        impact = classify_file(path, policy)
        if impact == "MIXED":
            contours.update({"UBUNTU_WORKER", "WINDOWS_WORKER"})
        elif impact in RUNTIME_IMPACTS:
            contours.add(impact)
    return contours


def derive_impact(changed_files: Iterable[str], policy: dict) -> str:
    paths = list(changed_files)
    contours = derive_runtime_contours(paths, policy)
    if len(contours) > 1:
        return "MIXED"
    if contours:
        return next(iter(contours))
    if any(classify_file(path, policy) == "CONTROL_PLANE" for path in paths):
        return "CONTROL_PLANE"
    return "NONE"


def require_value(fields: dict[str, str], name: str) -> str:
    value = fields.get(name, "").strip()
    if value.upper() in PLACEHOLDERS or not value:
        raise ContractError(f"missing or placeholder PR field: {name}")
    return value


def validate_authorization(fields: dict[str, str]) -> str:
    authorization = require_value(fields, "Source authorization")
    if authorization not in SOURCE_AUTHORIZATIONS:
        raise ContractError("Source authorization must be OUTCOME APPROVED or LEGACY COMMIT APPROVED")
    if fields.get("Approval recorded after Implementation Scope Check") != "YES":
        raise ContractError("Implementation Scope Check approval must be YES")
    if fields.get("Material scope/protected-boundary change since authorization", "").strip() != "NO":
        raise ContractError("material scope/protected-boundary change requires fresh authorization before PR admission")
    return authorization


def validate_deployment_fields(impact: str, fields: dict[str, str]) -> None:
    allowed = {"REQUIRED", "NOT REQUIRED"}
    values = {
        "VPS": fields.get("VPS deployment", ""),
        "UBUNTU_WORKER": fields.get("Ubuntu worker/relay update", ""),
        "WINDOWS_WORKER": fields.get("Windows worker update", ""),
    }
    if any(value not in allowed for value in values.values()):
        raise ContractError("all deployment contour fields must be REQUIRED or NOT REQUIRED")
    expected = {
        "NONE": set(),
        "CONTROL_PLANE": set(),
        "VPS": {"VPS"},
        "UBUNTU_WORKER": {"UBUNTU_WORKER"},
        "WINDOWS_WORKER": {"WINDOWS_WORKER"},
    }
    declared = {name for name, value in values.items() if value == "REQUIRED"}
    if impact == "MIXED":
        if len(declared) < 2:
            raise ContractError("MIXED impact must mark every applicable runtime contour REQUIRED")
    elif declared != expected[impact]:
        raise ContractError(f"deployment contour declaration {sorted(declared)} does not match {impact}")
    production_envelope = fields.get("Production safety envelope", "")
    if production_envelope not in allowed:
        raise ContractError("Production safety envelope must be REQUIRED or NOT REQUIRED")
    runtime_impact = bool(declared)
    if runtime_impact and production_envelope != "REQUIRED":
        raise ContractError("runtime production impact requires a Production safety envelope")
    if not runtime_impact and production_envelope != "NOT REQUIRED":
        raise ContractError("non-runtime impact must declare Production safety envelope NOT REQUIRED")


def validate_contract(body: str, changed_files: Iterable[str], policy: dict | None = None) -> str:
    policy = policy or load_policy()
    headings = set(HEADING_PATTERN.findall(body))
    missing_sections = [name for name in policy["required_sections"] if name not in headings]
    if missing_sections:
        raise ContractError("missing PR sections: " + ", ".join(missing_sections))
    fields = field_values(body)
    issue = require_value(fields, "Issue")
    if not re.fullmatch(r"#\d+", issue):
        raise ContractError("Issue must be a canonical GitHub issue reference such as #172")
    validate_authorization(fields)
    for name in (
        "Approved scope", "Acceptance criteria", "Intended behavior", "Out of scope",
        "Production-impact rationale", "Security impact", "API/event/state/storage schema impact",
        "Detection/tracking/calibration/speed formula impact", "Backward compatibility", "Rollout order",
        "Release manifest", "Rollback target", "Local checks", "PR checks", "Runtime acceptance plan",
        "Telemetry/evidence plan",
    ):
        require_value(fields, name)
    actual = set(changed_files)
    declared = declared_changed_files(body)
    if declared != actual:
        missing = sorted(actual - declared)
        extra = sorted(declared - actual)
        raise ContractError(f"declared changed files do not match Git diff; missing={missing}; extra={extra}")
    impact = derive_impact(actual, policy)
    declared_impact = fields.get("Production impact", "")
    if declared_impact not in policy["impact_classes"]:
        raise ContractError("Production impact must use a policy impact class")
    if declared_impact != impact:
        raise ContractError(f"declared Production impact {declared_impact} does not match derived {impact}")
    validate_deployment_fields(impact, fields)
    return impact


def git_changed_files(base_sha: str, head_sha: str) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", base_sha, head_sha], cwd=ROOT, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


def event_contract(event_path: Path) -> tuple[str, list[str]]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        raise ContractError("GitHub event does not contain a pull_request")
    return pull_request.get("body") or "", git_changed_files(pull_request["base"]["sha"], pull_request["head"]["sha"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, default=Path(os.environ.get("GITHUB_EVENT_PATH", "")))
    args = parser.parse_args()
    if not str(args.event):
        raise ContractError("--event or GITHUB_EVENT_PATH is required")
    try:
        body, changed_files = event_contract(args.event)
        impact = validate_contract(body, changed_files)
    except (ContractError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Change Contract valid: impact={impact}; changed_files={len(changed_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
