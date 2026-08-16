#!/usr/bin/env python3
"""Parse a three-line production authorization carrying explicit execution intent."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "data/contracts/production-authorization-policy-v1.json"
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
FP_RE = re.compile(r"^[0-9a-f]{64}$")


class RuntimeExecutionRequestError(ValueError):
    pass


def load_authorized_actors(policy_path: Path = POLICY_PATH) -> set[str]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema") != "sea-speed-production-authorization-policy/v1":
        raise RuntimeExecutionRequestError("unsupported production authorization policy")
    actors = {str(actor).strip() for actor in policy.get("authorizedActors") or [] if str(actor).strip()}
    if not actors:
        raise RuntimeExecutionRequestError("production authorization policy has no authorized actors")
    return actors


def parse_event(event: dict[str, object], policy_path: Path = POLICY_PATH) -> dict[str, object]:
    if event.get("action") != "created":
        raise RuntimeExecutionRequestError("runtime execution requests are accepted only from newly created comments")

    issue = event.get("issue")
    comment = event.get("comment")
    sender = event.get("sender")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(sender, dict):
        raise RuntimeExecutionRequestError("issue_comment event is missing issue, comment, or sender data")
    if issue.get("pull_request") is not None:
        raise RuntimeExecutionRequestError("runtime execution requests must be posted on a canonical Issue, not a pull request")
    if str(issue.get("state") or "").lower() != "open":
        raise RuntimeExecutionRequestError("runtime execution requests require an open canonical Issue")

    try:
        issue_number = int(issue["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeExecutionRequestError("canonical Issue number is missing or invalid") from exc
    if issue_number <= 0:
        raise RuntimeExecutionRequestError("canonical Issue number must be positive")

    actor = str(sender.get("login") or "").strip()
    comment_user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
    comment_actor = str(comment_user.get("login") or "").strip()
    if not actor or not comment_actor or actor != comment_actor:
        raise RuntimeExecutionRequestError("comment actor identity is missing or inconsistent")
    if actor not in load_authorized_actors(policy_path):
        raise RuntimeExecutionRequestError(f"actor {actor!r} is not authorized for production execution")

    body = str(comment.get("body") or "")
    if body != body.strip() or "\r" in body:
        raise RuntimeExecutionRequestError("runtime execution request must be exactly three trimmed lines")
    lines = body.split("\n")
    if len(lines) != 3 or any(line != line.strip() or not line for line in lines):
        raise RuntimeExecutionRequestError("runtime execution request must be exactly three non-empty trimmed lines")

    prefix = "PRODUCTION APPROVED "
    if not lines[0].startswith(prefix):
        raise RuntimeExecutionRequestError("first line must be 'PRODUCTION APPROVED <lowercase-40-char-sha>'")
    commit_sha = lines[0][len(prefix):]
    if not SHA40_RE.fullmatch(commit_sha):
        raise RuntimeExecutionRequestError("production commit must be a lowercase 40-character SHA")

    fp_prefix = "Authorization-Fingerprint: "
    if not lines[1].startswith(fp_prefix):
        raise RuntimeExecutionRequestError("second line must be 'Authorization-Fingerprint: <sha256>'")
    fingerprint = lines[1][len(fp_prefix):]
    if not FP_RE.fullmatch(fingerprint):
        raise RuntimeExecutionRequestError("authorization fingerprint must be a lowercase SHA-256")

    if lines[2] != "Execution-Intent: EXECUTE":
        raise RuntimeExecutionRequestError("third line must be exactly 'Execution-Intent: EXECUTE'")

    return {
        "schema": "sea_speed_runtime_execution_request_v1",
        "canonicalIssue": issue_number,
        "commitSha": commit_sha,
        "authorizationFingerprint": fingerprint,
        "executionIntent": "EXECUTE",
        "requestedBy": actor,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()

    try:
        event = json.loads(args.event.read_text(encoding="utf-8"))
        request = parse_event(event)
    except (RuntimeExecutionRequestError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"commit_sha={request['commitSha']}\n")
            handle.write(f"canonical_issue={request['canonicalIssue']}\n")
            handle.write(f"authorization_fingerprint={request['authorizationFingerprint']}\n")

    print(
        "Runtime execution request accepted: "
        f"issue=#{request['canonicalIssue']} commit={request['commitSha']} actor={request['requestedBy']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
