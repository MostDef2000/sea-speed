#!/usr/bin/env python3
"""Validate Sea Speed Spec-Driven Development artifacts and PR linkage."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR_RE = re.compile(r"^(\d{3,})-[a-z0-9][a-z0-9-]*$")
SPEC_LINK_RE = re.compile(r"(?m)^- Specification:\s*`?(specs/[0-9]{3,}-[a-z0-9][a-z0-9-]*/spec\.md)`?\s*$")
ISSUE_RE = re.compile(r"(?m)^- Issue:\s*#(\d+)\s*$")
RISK_DECLARATION_RE = re.compile(r"(?m)^- Risk profile:\s*(REQUIRED|NOT REQUIRED)\s*$")
AC_RE = re.compile(r"(?m)^- (AC-\d+):\s*.+$")
PR_FIELD_RE = re.compile(r"(?m)^- ([A-Za-z][A-Za-z0-9 /_-]*):\s*(.*?)\s*$")

BASELINE_FILES = (
    ".specify/memory/constitution.md",
    ".specify/templates/overrides/spec-template.md",
    ".specify/templates/overrides/plan-template.md",
    ".specify/templates/overrides/tasks-template.md",
    "specs/README.md",
)
REQUIRED_FEATURE_FILES = ("spec.md", "plan.md", "tasks.md")
SPEC_MARKERS = ("## Product outcome", "## User scenarios", "## Requirements", "## Acceptance criteria", "## Runtime feedback")
PLAN_MARKERS = ("## Architecture", "## Decisions", "## Affected contours", "## Validation", "## Runtime feedback")
TASK_MARKERS = ("## Delivery tasks", "## Completion gate")
QUALITY_SPEC_MARKERS = ("## NFR assessment",)
QUALITY_PLAN_MARKERS = ("## Risk profile", "## Test design", "## Correct-course check")
QUALITY_TASK_MARKERS = ("## Requirements traceability", "## Definition of Done")

GRANDFATHERED_PREFIX_COLLISIONS = {
    "002": {"002-camera-preview-gallery", "002-sdd-adoption"},
}

SIGNIFICANT_PREFIXES = (
    "api/", "frontend/", "worker/", "deploy/", "schemas/", "scripts/ci/",
    "scripts/operations/", "scripts/quality/", "scripts/release/", ".github/workflows/",
    "contracts/", "data/contracts/", "data/quality/",
)
SIGNIFICANT_EXACT = {"AGENTS.md"}

RISK_CATEGORIES = {"TECH", "SEC", "PERF", "DATA", "BUS", "OPS"}
RISK_STATUSES = {"OPEN", "MITIGATED", "ACCEPTED", "CLOSED"}
NFR_STATUSES = {"PASS", "CONCERNS", "FAIL", "NOT APPLICABLE"}
TEST_LEVELS = {"unit", "integration", "end-to-end", "runtime-manual"}
TEST_PRIORITIES = {"P0", "P1", "P2", "P3"}
TRACE_COVERAGE = {"COVERED", "RUNTIME-MANUAL"}
CORRECT_COURSE_TRIGGERS = {"NONE", "PRODUCTION_LEARNING", "ARCHITECTURE_PIVOT", "MATERIAL_SCOPE_CHANGE"}
UNKNOWN_TARGETS = {"UNKNOWN", "TBD", "TODO", "UNDEFINED", "NOT DEFINED"}
TRANSACTION_STAGES = {
    "ADMISSION", "PRE-MUTATION", "MUTATION", "VERIFICATION",
    "STATE-COMMIT", "HOUSEKEEPING", "EVIDENCE", "ROLLBACK",
}
TRANSACTION_MUTATION = {"YES", "NO", "POSSIBLE"}
TRANSACTION_FAILURE = {"FATAL", "BEST-EFFORT", "CONDITIONAL"}
RUNTIME_DEPLOYMENT_FIELDS = ("VPS deployment", "Ubuntu worker/relay update", "Windows worker update")
DOD_MARKERS = (
    "Issue/spec/plan/tasks current",
    "Exact changed-file scope verified",
    "Required tests and evidence complete",
    "Required CI green",
    "Exact-green-head merge complete",
    "Deployment state resolved",
    "Runtime acceptance resolved",
    "Deferred work recorded",
    "Risks resolved or explicitly accepted",
    "Waivers resolved or current",
)


class SddError(ValueError):
    pass


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SddError(f"SDD text is not valid UTF-8: {path}") from exc


def _require_markers(path: Path, markers: Iterable[str]) -> None:
    text = _read(path)
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise SddError(f"{path} missing required SDD sections: {', '.join(missing)}")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        raise SddError(f"missing SDD section: {heading}")
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _records(section_text: str, prefix: str) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for raw in section_text.splitlines():
        line = raw.strip()
        if not line.startswith(f"- {prefix}"):
            continue
        parts = [part.strip() for part in line[2:].split(" | ")]
        record_id = parts[0]
        fields: dict[str, str] = {}
        for part in parts[1:]:
            if ":" not in part:
                raise SddError(f"malformed quality record field: {part}")
            name, value = part.split(":", 1)
            fields[name.strip()] = value.strip()
        rows.append((record_id, fields))
    return rows


def _bullet_values(section_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in section_text.splitlines():
        match = re.match(r"^- ([A-Za-z][A-Za-z0-9 /-]+):\s*(.+?)\s*$", raw.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _require_record_fields(record_id: str, fields: dict[str, str], required: Iterable[str]) -> None:
    missing = [name for name in required if not fields.get(name, "").strip()]
    if missing:
        raise SddError(f"{record_id} missing fields: {', '.join(missing)}")


def validate_feature_dir(feature_dir: Path) -> None:
    if not FEATURE_DIR_RE.fullmatch(feature_dir.name):
        raise SddError(f"invalid feature directory name: {feature_dir.name}")
    missing = [name for name in REQUIRED_FEATURE_FILES if not (feature_dir / name).is_file()]
    if missing:
        raise SddError(f"{feature_dir.name} missing required artifacts: {', '.join(missing)}")
    spec = feature_dir / "spec.md"
    plan = feature_dir / "plan.md"
    tasks = feature_dir / "tasks.md"
    _require_markers(spec, SPEC_MARKERS)
    _require_markers(plan, PLAN_MARKERS)
    _require_markers(tasks, TASK_MARKERS)
    if not ISSUE_RE.search(_read(spec)):
        raise SddError(f"{spec} must contain a canonical '- Issue: #N' line")
    expected_spec_path = f"specs/{feature_dir.name}/spec.md"
    for artifact in (plan, tasks):
        if expected_spec_path not in _read(artifact):
            raise SddError(f"{artifact} must reference {expected_spec_path}")


def validate_prefix_uniqueness(feature_dirs: Iterable[Path]) -> None:
    by_prefix: dict[str, set[str]] = defaultdict(set)
    for feature_dir in feature_dirs:
        match = FEATURE_DIR_RE.fullmatch(feature_dir.name)
        if match:
            by_prefix[match.group(1)].add(feature_dir.name)
    for prefix, names in sorted(by_prefix.items()):
        if len(names) < 2:
            continue
        if names == GRANDFATHERED_PREFIX_COLLISIONS.get(prefix, set()):
            continue
        raise SddError(f"duplicate SDD numeric prefix {prefix}: {', '.join(sorted(names))}")


def validate_repository(root: Path = ROOT) -> None:
    missing_baseline = [path for path in BASELINE_FILES if not (root / path).is_file()]
    if missing_baseline:
        raise SddError("SDD baseline files missing: " + ", ".join(missing_baseline))
    specs_root = root / "specs"
    feature_dirs = sorted(path for path in specs_root.iterdir() if path.is_dir())
    if not feature_dirs:
        raise SddError("at least one feature specification directory is required")
    validate_prefix_uniqueness(feature_dirs)
    for feature_dir in feature_dirs:
        validate_feature_dir(feature_dir)


def _validate_nfr(spec_path: Path) -> None:
    text = _read(spec_path)
    _require_markers(spec_path, QUALITY_SPEC_MARKERS)
    rows = _records(_section(text, "NFR assessment"), "NFR-")
    if not rows:
        raise SddError(f"{spec_path} must contain at least one NFR record")
    for record_id, fields in rows:
        _require_record_fields(record_id, fields, ("Area", "Target", "Validation", "Evidence", "Status"))
        status = fields["Status"].upper()
        if status not in NFR_STATUSES:
            raise SddError(f"{record_id} has invalid NFR status: {fields['Status']}")
        if status == "PASS" and fields["Target"].strip().upper() in UNKNOWN_TARGETS:
            raise SddError(f"{record_id} cannot be PASS with an unknown target")


def _validate_risk_and_test_design(plan_path: Path, declared_risk: str) -> str:
    text = _read(plan_path)
    _require_markers(plan_path, QUALITY_PLAN_MARKERS)
    risk_section = _section(text, "Risk profile")
    plan_decl = re.search(r"(?m)^- Risk profile:\s*(REQUIRED|NOT REQUIRED)\s*$", risk_section)
    if not plan_decl:
        raise SddError(f"{plan_path} must declare Risk profile REQUIRED or NOT REQUIRED")
    if plan_decl.group(1) != declared_risk:
        raise SddError(f"{plan_path} Risk profile declaration does not match PR Change Contract")
    risk_rows = _records(risk_section, "RISK-")
    if declared_risk == "NOT REQUIRED" and risk_rows:
        raise SddError(f"{plan_path} declares Risk profile NOT REQUIRED but contains risk rows")
    if declared_risk == "REQUIRED" and not risk_rows:
        raise SddError(f"{plan_path} requires at least one complete risk row")
    for record_id, fields in risk_rows:
        required = ("Category", "Probability", "Impact", "Score", "Mitigation", "Validation", "Residual risk", "Owner", "Status")
        _require_record_fields(record_id, fields, required)
        if fields["Category"].upper() not in RISK_CATEGORIES:
            raise SddError(f"{record_id} has invalid risk category: {fields['Category']}")
        try:
            probability = int(fields["Probability"])
            impact = int(fields["Impact"])
            score = int(fields["Score"])
        except ValueError as exc:
            raise SddError(f"{record_id} probability, impact and score must be integers") from exc
        if probability not in range(1, 6) or impact not in range(1, 6):
            raise SddError(f"{record_id} probability and impact must be 1-5")
        if score != probability * impact:
            raise SddError(f"{record_id} score must equal probability * impact")
        if fields["Status"].upper() not in RISK_STATUSES:
            raise SddError(f"{record_id} has invalid risk status: {fields['Status']}")

    test_rows = _records(_section(text, "Test design"), "TEST-")
    if not test_rows:
        raise SddError(f"{plan_path} must contain at least one test-design record")
    for record_id, fields in test_rows:
        _require_record_fields(record_id, fields, ("Covers", "Level", "Priority", "Evidence"))
        if fields["Level"] not in TEST_LEVELS:
            raise SddError(f"{record_id} has invalid test level: {fields['Level']}")
        if fields["Priority"].upper() not in TEST_PRIORITIES:
            raise SddError(f"{record_id} has invalid test priority: {fields['Priority']}")

    course = _section(text, "Correct-course check")
    values = _bullet_values(course)
    required_course = ("Trigger", "Issue impact", "Specification impact", "Plan impact", "Tasks impact", "Authorization impact", "Follow-up")
    missing = [name for name in required_course if not values.get(name)]
    if missing:
        raise SddError(f"{plan_path} correct-course check missing: {', '.join(missing)}")
    trigger = values["Trigger"].upper()
    if trigger not in CORRECT_COURSE_TRIGGERS:
        raise SddError(f"{plan_path} has invalid correct-course trigger: {values['Trigger']}")
    if trigger != "NONE":
        impacts = [values[name].strip().upper() for name in required_course[1:-1]]
        if all(value == "NONE" for value in impacts) or values["Follow-up"].strip().upper() == "NONE":
            raise SddError(f"{plan_path} non-NONE correct-course trigger requires impact and follow-up")
    return trigger


def _pr_fields(pr_body: str) -> dict[str, str]:
    return {name: value.strip() for name, value in PR_FIELD_RE.findall(pr_body or "")}


def requires_deployment_transaction_audit(changed_files: Iterable[str], pr_body: str, trigger: str) -> bool:
    if trigger == "PRODUCTION_LEARNING":
        return True
    for path in changed_files:
        normalized = path.replace("\\", "/")
        if normalized.startswith("deploy/") or normalized.startswith("scripts/release/"):
            return True
        if normalized.startswith(".github/workflows/deploy") and normalized.endswith((".yml", ".yaml")):
            return True
    fields = _pr_fields(pr_body)
    return any(fields.get(name, "").upper() == "REQUIRED" for name in RUNTIME_DEPLOYMENT_FIELDS)


def _validate_deployment_transaction_audit(plan_path: Path, trigger: str) -> None:
    text = _read(plan_path)
    audit = _section(text, "Deployment transaction audit")
    rows = _records(audit, "TX-")
    if not rows:
        raise SddError(f"{plan_path} requires deployment transaction audit records")
    stages: set[str] = set()
    for record_id, fields in rows:
        required = ("Stage", "Mutation", "Failure disposition", "State after failure", "Retry", "Rollback", "Evidence")
        _require_record_fields(record_id, fields, required)
        stage = fields["Stage"].upper()
        if stage not in TRANSACTION_STAGES:
            raise SddError(f"{record_id} has invalid transaction stage: {fields['Stage']}")
        if stage in stages:
            raise SddError(f"duplicate deployment transaction stage: {stage}")
        stages.add(stage)
        if fields["Mutation"].upper() not in TRANSACTION_MUTATION:
            raise SddError(f"{record_id} has invalid Mutation value: {fields['Mutation']}")
        if fields["Failure disposition"].upper() not in TRANSACTION_FAILURE:
            raise SddError(f"{record_id} has invalid Failure disposition: {fields['Failure disposition']}")
        for name in ("State after failure", "Retry", "Rollback", "Evidence"):
            if fields[name].strip().upper() in UNKNOWN_TARGETS:
                raise SddError(f"{record_id} cannot use unknown {name}: {fields[name]}")
    if stages != TRANSACTION_STAGES:
        raise SddError(
            "deployment transaction audit stage mismatch; "
            f"missing={sorted(TRANSACTION_STAGES - stages)}; extra={sorted(stages - TRANSACTION_STAGES)}"
        )

    if trigger == "PRODUCTION_LEARNING":
        values = _bullet_values(audit)
        if values.get("Adjacent-stage review", "").upper() != "COMPLETE":
            raise SddError(f"{plan_path} production learning requires '- Adjacent-stage review: COMPLETE'")
        for name in ("Production-learning root cause", "Production-learning adjacent-stage findings"):
            value = values.get(name, "").strip()
            if not value or value.upper() in UNKNOWN_TARGETS | {"NONE", "NOT APPLICABLE"}:
                raise SddError(f"{plan_path} production learning requires concrete {name}")


def _validate_traceability_and_dod(spec_path: Path, tasks_path: Path) -> None:
    text = _read(tasks_path)
    _require_markers(tasks_path, QUALITY_TASK_MARKERS)
    acceptance_ids = set(AC_RE.findall(_read(spec_path)))
    if not acceptance_ids:
        raise SddError(f"{spec_path} must contain at least one AC-NNN acceptance criterion")
    rows = _records(_section(text, "Requirements traceability"), "AC-")
    if not rows:
        raise SddError(f"{tasks_path} must contain requirements traceability rows")
    mapped: set[str] = set()
    for record_id, fields in rows:
        if record_id in mapped:
            raise SddError(f"duplicate traceability row: {record_id}")
        mapped.add(record_id)
        _require_record_fields(record_id, fields, ("Task", "Evidence", "Coverage"))
        coverage = fields["Coverage"].upper()
        if coverage not in TRACE_COVERAGE:
            raise SddError(f"{record_id} has invalid traceability coverage: {fields['Coverage']}")
        if coverage == "RUNTIME-MANUAL" and not fields.get("Reason", "").strip():
            raise SddError(f"{record_id} runtime-manual coverage requires Reason")
    missing = acceptance_ids - mapped
    extra = mapped - acceptance_ids
    if missing or extra:
        raise SddError(f"traceability mismatch; missing={sorted(missing)}; extra={sorted(extra)}")
    dod = _section(text, "Definition of Done")
    missing_dod = [marker for marker in DOD_MARKERS if marker not in dod]
    if missing_dod:
        raise SddError(f"{tasks_path} Definition of Done missing: {', '.join(missing_dod)}")


def validate_feature_quality(feature_dir: Path, pr_body: str, changed_files: Iterable[str] = ()) -> None:
    match = RISK_DECLARATION_RE.search(pr_body or "")
    if not match:
        raise SddError("significant PR must declare '- Risk profile: REQUIRED|NOT REQUIRED'")
    declared_risk = match.group(1)
    spec = feature_dir / "spec.md"
    plan = feature_dir / "plan.md"
    tasks = feature_dir / "tasks.md"
    _validate_nfr(spec)
    trigger = _validate_risk_and_test_design(plan, declared_risk)
    if requires_deployment_transaction_audit(changed_files, pr_body, trigger):
        _validate_deployment_transaction_audit(plan, trigger)
    _validate_traceability_and_dod(spec, tasks)


def requires_spec(changed_files: Iterable[str]) -> bool:
    for path in changed_files:
        normalized = path.replace("\\", "/")
        if normalized in SIGNIFICANT_EXACT or any(normalized.startswith(prefix) for prefix in SIGNIFICANT_PREFIXES):
            return True
    return False


def linked_spec(body: str) -> str | None:
    match = SPEC_LINK_RE.search(body or "")
    return match.group(1) if match else None


def validate_pr_link(body: str, changed_files: Iterable[str], root: Path = ROOT) -> None:
    changed = list(changed_files)
    if not requires_spec(changed):
        return
    spec_path = linked_spec(body)
    if not spec_path:
        raise SddError("significant PR must declare '- Specification: specs/<feature>/spec.md'")
    target = root / spec_path
    if not target.is_file():
        raise SddError(f"linked specification does not exist: {spec_path}")
    validate_feature_dir(target.parent)
    validate_feature_quality(target.parent, body, changed)


def git_changed_files(base_sha: str, head_sha: str, root: Path = ROOT) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", base_sha, head_sha], cwd=root, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


# Completion markers that must be [x] once a PR is merged green to main.
FRESHNESS_RE = re.compile(
    r"^\s*-\s*\[\s*\]\s*(?:"
    r"T007\b.*|"
    r"T008\b.*|"
    r"Required CI (green|is green).*|"
    r"Exact-green-head merge (complete|evidence is recorded.*).*|"
    r"Exact-main source and Quality evidence is recorded.*|"
    r"Required local and GitHub CI evidence is green.*|"
    r"Post-restart.*evidence is recorded.*|"
    r"Runtime acceptance resolved: post-restart control-plane verification pending.*"
    r")$"
)


def changed_spec_dirs(base_sha: str, head_sha: str, root: Path = ROOT) -> list[Path]:
    dirs: set[Path] = set()
    for path in git_changed_files(base_sha, head_sha, root):
        match = FEATURE_DIR_RE.match(path.replace("\\", "/"))
        if match:
            candidate = root / "specs" / match.group(1)
            if (candidate / "tasks.md").is_file():
                dirs.add(candidate)
    return sorted(dirs)


def check_tasks_freshness(dirs: Iterable[Path]) -> list[str]:
    stale: list[str] = []
    for spec_dir in dirs:
        tasks = spec_dir / "tasks.md"
        for index, line in enumerate(tasks.read_text(encoding="utf-8").splitlines(), 1):
            if FRESHNESS_RE.match(line):
                stale.append(f"{tasks}:{index}: {line.strip()}")
    return stale


def event_contract(event_path: Path, root: Path = ROOT) -> tuple[str, list[str]]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        raise SddError("GitHub event does not contain a pull_request")
    return pull_request.get("body") or "", git_changed_files(pull_request["base"]["sha"], pull_request["head"]["sha"], root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path)
    parser.add_argument("--freshness", action="store_true", help="Fail if changed specs still have unchecked completion markers after merge.")
    parser.add_argument("--base", help="Base SHA for --freshness spec discovery.")
    parser.add_argument("--head", help="Head SHA for --freshness spec discovery.")
    args = parser.parse_args()
    try:
        validate_repository(ROOT)
        if args.event:
            body, changed_files = event_contract(args.event, ROOT)
            validate_pr_link(body, changed_files, ROOT)
        if args.freshness:
            if not (args.base and args.head):
                raise SddError("--freshness requires --base and --head")
            stale = check_tasks_freshness(changed_spec_dirs(args.base, args.head, ROOT))
            if stale:
                for entry in stale:
                    print(f"STALE: {entry}", file=sys.stderr)
                raise SddError(f"{len(stale)} stale tasks.md completion marker(s) after merge")
    except (SddError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Sea Speed SDD validation passed")
    if args.event:
        print("PR specification linkage and delivery quality layer valid")
    if args.freshness:
        print("tasks.md freshness check passed (no stale completion markers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
