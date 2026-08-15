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
ISSUE_RE = re.compile(r"(?m)^- Issue:\s*#\d+\s*$")

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

# Historical collision created before numeric-prefix uniqueness became policy.
GRANDFATHERED_PREFIX_COLLISIONS = {
    "002": {"002-camera-preview-gallery", "002-sdd-adoption"},
}

SIGNIFICANT_PREFIXES = (
    "api/", "frontend/", "worker/", "deploy/", "schemas/", "scripts/ci/",
    "scripts/operations/", "scripts/quality/", "scripts/release/", ".github/workflows/",
    "contracts/", "data/contracts/", "data/quality/",
)
SIGNIFICANT_EXACT = {"AGENTS.md"}


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


def git_changed_files(base_sha: str, head_sha: str, root: Path = ROOT) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", base_sha, head_sha], cwd=root, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


def event_contract(event_path: Path, root: Path = ROOT) -> tuple[str, list[str]]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        raise SddError("GitHub event does not contain a pull_request")
    return pull_request.get("body") or "", git_changed_files(pull_request["base"]["sha"], pull_request["head"]["sha"], root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path)
    args = parser.parse_args()
    try:
        validate_repository(ROOT)
        if args.event:
            body, changed_files = event_contract(args.event, ROOT)
            validate_pr_link(body, changed_files, ROOT)
    except (SddError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Sea Speed SDD validation passed")
    if args.event:
        print("PR specification linkage valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
