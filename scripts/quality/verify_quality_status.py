#!/usr/bin/env python3
"""Verify that an exact main commit has a successful aggregate quality push run."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import SHA40_RE


def github_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sea-speed-quality-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def verify(repository: str, commit: str, token: str, workflow_file: str = "quality-integration.yml") -> dict:
    if commit != commit.lower() or not SHA40_RE.fullmatch(commit):
        raise ValueError("commit must be an exact lowercase full 40-character SHA")
    query = urllib.parse.urlencode({
        "head_sha": commit,
        "branch": "main",
        "event": "push",
        "status": "completed",
        "per_page": 100,
    })
    url = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow_file}/runs?{query}"
    payload = github_json(url, token)
    matches = [
        run for run in payload.get("workflow_runs", [])
        if run.get("head_sha") == commit
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    ]
    if not matches:
        raise ValueError("no successful quality-integration push run on main exists for the exact SHA")
    return max(matches, key=lambda run: run.get("run_number") or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--workflow-file", default="quality-integration.yml")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    try:
        run = verify(args.repository, args.commit, token, args.workflow_file)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Quality push run verified for {args.commit}: run_id={run.get('id')} run_number={run.get('run_number')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
