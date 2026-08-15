#!/usr/bin/env python3
"""Fail-closed verification of canonical Issue/PR production authorization."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "data/contracts/production-authorization-policy-v1.json"
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_FIELD_RE = re.compile(r"^- Issue:\s*#(\d+)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z0-9 /_-]*):\s*(.*?)\s*$", re.MULTILINE)


def github_json(url: str, token: str) -> object:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sea-speed-production-authorization",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def outcome_contract(issue_body: str) -> str:
    match = re.search(r"^## Outcome Contract\s*$([\s\S]*?)(?=^## |\Z)", issue_body, re.MULTILINE)
    if not match:
        raise ValueError("canonical Issue is missing Outcome Contract")
    return match.group(1).strip()


def authorization_payload(issue_number: int, pr_number: int, source_commit: str, issue_body: str, pr_body: str) -> dict[str, object]:
    fields = {name: value.strip() for name, value in FIELD_RE.findall(pr_body)}
    payload: dict[str, object] = {
        "canonicalIssue": issue_number,
        "pullRequest": pr_number,
        "sourceCommit": source_commit,
        "outcomeContract": outcome_contract(issue_body),
        "runtimeContours": {
            "productionImpact": fields.get("Production impact", ""),
            "vps": fields.get("VPS deployment", ""),
            "ubuntuWorkerRelay": fields.get("Ubuntu worker/relay update", ""),
            "windowsWorker": fields.get("Windows worker update", ""),
        },
        "securityImpact": fields.get("Security impact", ""),
        "deploymentTarget": fields.get("Production-impact rationale", ""),
        "rollbackTarget": fields.get("Rollback target", ""),
    }
    if any(value == "" for value in (payload["securityImpact"], payload["deploymentTarget"], payload["rollbackTarget"])):
        raise ValueError("PR Change Contract is missing authorization-bound fields")
    return payload


def authorization_fingerprint(issue_number: int, pr_number: int, source_commit: str, issue_body: str, pr_body: str) -> str:
    return canonical_json_sha256(authorization_payload(issue_number, pr_number, source_commit, issue_body, pr_body))


def verify(repository: str, source_commit: str, issue_number: int, token: str) -> tuple[int, str, str]:
    if source_commit != source_commit.lower() or not SHA40_RE.fullmatch(source_commit):
        raise ValueError("source commit must be an exact lowercase full SHA")
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema") != "sea-speed-production-authorization-policy/v1":
        raise ValueError("unsupported production authorization policy")
    pulls = github_json(f"https://api.github.com/repos/{repository}/commits/{source_commit}/pulls", token)
    if not isinstance(pulls, list):
        raise ValueError("unexpected commit-to-PR response")
    merged = [pr for pr in pulls if pr.get("merged_at") and pr.get("merge_commit_sha") == source_commit]
    if len(merged) != 1:
        raise ValueError("exact main merge commit must resolve to exactly one merged PR")
    pr = merged[0]
    pr_number = int(pr["number"])
    pr_body = pr.get("body") or ""
    issue_match = ISSUE_FIELD_RE.search(pr_body)
    if not issue_match or int(issue_match.group(1)) != issue_number:
        raise ValueError("PR Change Contract does not bind the requested canonical Issue")
    issue = github_json(f"https://api.github.com/repos/{repository}/issues/{issue_number}", token)
    if not isinstance(issue, dict) or issue.get("pull_request"):
        raise ValueError("canonical Issue is missing or resolves to a pull request")
    issue_body = issue.get("body") or ""
    outcome_hash = hashlib.sha256(outcome_contract(issue_body).encode("utf-8")).hexdigest()
    fingerprint = authorization_fingerprint(issue_number, pr_number, source_commit, issue_body, pr_body)
    comments = github_json(f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments?per_page=100", token)
    if not isinstance(comments, list):
        raise ValueError("unexpected Issue comments response")
    prefix = policy.get("approvalPrefix", "PRODUCTION APPROVED")
    approved_actors = set(policy.get("authorizedActors") or [])
    exact_first_line = f"{prefix} {source_commit}"
    fp_line = f"Authorization-Fingerprint: {fingerprint}"
    matches = []
    for comment in comments:
        actor = ((comment.get("user") or {}).get("login") or "").strip()
        body = (comment.get("body") or "").strip()
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if actor in approved_actors and lines and lines[0] == exact_first_line and fp_line in lines[1:]:
            matches.append(comment)
    if not matches:
        raise ValueError(
            "durable production authorization not found; required exact lines: "
            f"{exact_first_line!r} and {fp_line!r} from an authorized actor"
        )
    return pr_number, fingerprint, outcome_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("ERROR: GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    try:
        pr, fingerprint, outcome_hash = verify(args.repository, args.commit, args.issue, token)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"pr_number={pr}\n")
            handle.write(f"authorization_fingerprint={fingerprint}\n")
            handle.write(f"outcome_contract_hash={outcome_hash}\n")
    print(f"Production authorization verified: issue=#{args.issue} pr=#{pr} commit={args.commit} fingerprint={fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
