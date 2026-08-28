#!/usr/bin/env python3
"""Idempotently sync SDD tasks.md completion markers to [x] after a green merge to main.

This is the mutating counterpart to the read-only `validate_sdd.py --freshness`
gate. It only flips well-known completion markers (T007/T008, the Definition
of Done CI/merge markers and the Completion gate markers) for spec directories
that were actually changed in the merged commit. It never unchecks a box, never
edits task content or any line that is not a recognized completion marker.

Usage:
  python scripts/ci/sync_tasks_md.py --base B --head H --sha S
  python scripts/ci/sync_tasks_md.py --specs specs/067-foo specs/056-bar
  python scripts/ci/sync_tasks_md.py                 # local: diff HEAD~1..HEAD
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Completion markers that are auto-marked done once a PR is merged green to main.
COMPLETION_RE = re.compile(
    r"^\s*-\s*\[\s*\]\s*("
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

FEATURE_DIR_RE = re.compile(r"^specs/(\d{3,}-[a-z0-9][a-z0-9-]*)/")


def git_changed_spec_dirs(base: str, head: str, root: Path = ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    dirs: set[Path] = set()
    for path in result.stdout.splitlines():
        normalized = path.replace("\\", "/")
        match = FEATURE_DIR_RE.match(normalized)
        if match:
            candidate = root / "specs" / match.group(1)
            if (candidate / "tasks.md").is_file():
                dirs.add(candidate)
    return sorted(dirs)


def sync_tasks_file(tasks: Path, sha: str) -> bool:
    text = tasks.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    out: list[str] = []
    for line in lines:
        match = COMPLETION_RE.match(line)
        if match:
            indent = line[: len(line) - len(line.lstrip())]
            rest = match.group(1).rstrip()
            if "auto-synced on merge" not in rest:
                rest = f"{rest} — auto-synced on merge to main ({sha[:8]})"
            out.append(f"{indent}- [x] {rest}")
            changed = True
        else:
            out.append(line)
    if changed:
        tasks.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-sync SDD tasks.md completion markers.")
    parser.add_argument("--specs", nargs="*", default=(), help="Explicit spec directories to sync.")
    parser.add_argument("--base", help="Base SHA to diff changed spec dirs from.")
    parser.add_argument("--head", help="Head SHA to diff changed spec dirs to.")
    parser.add_argument("--sha", default="HEAD", help="SHA used in the auto-sync note.")
    args = parser.parse_args()

    if args.specs:
        spec_dirs = [Path(s) for s in args.specs]
    elif args.base and args.head:
        spec_dirs = git_changed_spec_dirs(args.base, args.head)
    else:
        spec_dirs = git_changed_spec_dirs("HEAD~1", "HEAD")

    if not spec_dirs:
        print("sync_tasks_md: no changed spec tasks.md found; nothing to do")
        return 0

    total = 0
    for spec_dir in spec_dirs:
        tasks = spec_dir / "tasks.md"
        if not tasks.is_file():
            continue
        if sync_tasks_file(tasks, args.sha):
            total += 1
            print(f"sync_tasks_md: updated {tasks}")

    if total:
        print(f"sync_tasks_md: {total} tasks.md file(s) synced")
    else:
        print("sync_tasks_md: all changed tasks.md already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
