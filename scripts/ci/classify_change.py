#!/usr/bin/env python3
"""Classify change lane and runtime need from exact Git diff."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ci.validate_change_contract import derive_runtime_contours, load_policy  # noqa: E402

def git_changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]

def changed_files_from_event(event_path: Path) -> list[str]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pr = event.get("pull_request")
    if pr:
        return git_changed_files(pr["base"]["sha"], pr["head"]["sha"])
    # push / workflow_dispatch fallback: compare HEAD^..HEAD
    # For push on main, compare last commit
    try:
        base = subprocess.run(
            ["git", "rev-parse", "HEAD^"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        if base and head:
            return git_changed_files(base, head)
    except subprocess.CalledProcessError:
        pass
    return []

def classify(changed: list[str]) -> tuple[str, bool, str]:
    policy = load_policy()
    contours = derive_runtime_contours(changed, policy)
    if contours:
        lane = "PRODUCTION" if len(contours) > 1 else "STANDARD"
        # Runtime artifacts required for VPS/UBUNTU changes
        runtime_required = True
        impact = "MIXED" if len(contours) > 1 else next(iter(contours))
    else:
        # Use policy impact for CONTROL_PLANE vs NONE
        from scripts.ci.validate_change_contract import derive_impact
        impact = derive_impact(changed, policy)
        if impact in {"VPS", "UBUNTU_WORKER", "MIXED"}:
            runtime_required = True
            lane = "STANDARD"
        elif impact == "CONTROL_PLANE":
            runtime_required = False
            lane = "FAST"
        else:
            runtime_required = False
            lane = "FAST"
    return lane, runtime_required, impact

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, default=Path(os.environ.get("GITHUB_EVENT_PATH", "")) if os.environ.get("GITHUB_EVENT_PATH") else None)
    parser.add_argument("--base", type=str, default=None)
    parser.add_argument("--head", type=str, default=None)
    parser.add_argument("--github-output", type=Path, default=None)
    args = parser.parse_args()

    if args.base and args.head:
        changed = git_changed_files(args.base, args.head)
    elif args.event and args.event.is_file():
        changed = changed_files_from_event(args.event)
    else:
        # local: diff against origin/main or HEAD
        try:
            # try diff against origin/main...HEAD for development
            changed = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                cwd=ROOT, capture_output=True, text=True,
            ).stdout.splitlines()
            if not changed:
                changed = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD"],
                    cwd=ROOT, capture_output=True, text=True,
                ).stdout.splitlines()
        except subprocess.CalledProcessError:
            changed = []

    lane, runtime_required, impact = classify(changed)

    out = args.github_output or (Path(os.environ["GITHUB_OUTPUT"]) if "GITHUB_OUTPUT" in os.environ else None)
    if out:
        with out.open("a", encoding="utf-8") as f:
            f.write(f"lane={lane}\n")
            f.write(f"runtime_required={'true' if runtime_required else 'false'}\n")
            f.write(f"impact={impact}\n")
            f.write(f"changed_files={len(changed)}\n")

    print(f"lane={lane} impact={impact} runtime_required={runtime_required} files={len(changed)}")
    if changed:
        for p in sorted(changed)[:20]:
            print(f"  - {p}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
