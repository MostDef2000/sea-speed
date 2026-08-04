#!/usr/bin/env python3
"""Verify that an exact commit has a successful aggregate quality check run."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import SHA40_RE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--required-name", default="quality-integration")
    args = parser.parse_args()
    commit = args.commit.lower()
    if not SHA40_RE.fullmatch(commit):
        raise SystemExit("commit must be a full lowercase 40-character SHA")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    url = f"https://api.github.com/repos/{args.repository}/commits/{commit}/check-runs?per_page=100"
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
        payload = json.load(response)
    matches = [run for run in payload.get("check_runs", []) if run.get("name") == args.required_name]
    if not matches:
        raise SystemExit(f"required quality check not found: {args.required_name}")
    latest = max(matches, key=lambda run: run.get("completed_at") or run.get("started_at") or "")
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise SystemExit(f"quality check is not successful: status={latest.get('status')} conclusion={latest.get('conclusion')}")
    print(f"Quality check verified for {commit}: {args.required_name}=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
