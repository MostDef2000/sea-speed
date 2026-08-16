#!/usr/bin/env python3
"""Parse a Connector-addressable VPS deployment request from an Issue comment event."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "data/contracts/production-authorization-policy-v1.json"
REQUEST_RE = re.compile(r"^DEPLOY VPS ([0-9a-f]{40})$")


class DeploymentRequestError(ValueError):
    pass


def load_authorized_actors(policy_path: Path = POLICY_PATH) -> set[str]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema") != "sea-speed-production-authorization-policy/v1":
        raise DeploymentRequestError("unsupported production authorization policy")
    actors = {str(actor).strip() for actor in policy.get("authorizedActors") or [] if str(actor).strip()}
    if not actors:
        raise DeploymentRequestError("production authorization policy has no authorized actors")
    return actors


def parse_event(event: dict[str, object], policy_path: Path = POLICY_PATH) -> dict[str, object]:
    if event.get("action") != "created":
        raise DeploymentRequestError("deployment requests are accepted only from newly created comments")

    issue = event.get("issue")
    comment = event.get("comment")
    sender = event.get("sender")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(sender, dict):
        raise DeploymentRequestError("issue_comment event is missing issue, comment, or sender data")
    if issue.get("pull_request") is not None:
        raise DeploymentRequestError("deployment requests must be posted on a canonical Issue, not a pull request")
    if str(issue.get("state") or "").lower() != "open":
        raise DeploymentRequestError("deployment requests require an open canonical Issue")

    try:
        issue_number = int(issue["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DeploymentRequestError("canonical Issue number is missing or invalid") from exc
    if issue_number <= 0:
        raise DeploymentRequestError("canonical Issue number must be positive")

    actor = str(sender.get("login") or "").strip()
    comment_actor = ((comment.get("user") or {}) if isinstance(comment.get("user"), dict) else {}).get("login")
    comment_actor = str(comment_actor or "").strip()
    if not actor or not comment_actor or actor != comment_actor:
        raise DeploymentRequestError("comment actor identity is missing or inconsistent")
    if actor not in load_authorized_actors(policy_path):
        raise DeploymentRequestError(f"actor {actor!r} is not authorized to request production deployment")

    body = str(comment.get("body") or "")
    if body != body.strip() or "\n" in body or "\r" in body:
        raise DeploymentRequestError("deployment request must be exactly one trimmed line")
    match = REQUEST_RE.fullmatch(body)
    if not match:
        raise DeploymentRequestError("deployment request must be exactly 'DEPLOY VPS <lowercase-40-char-sha>'")

    return {
        "schema": "sea_speed_deployment_request_v1",
        "canonicalIssue": issue_number,
        "commitSha": match.group(1),
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
    except (DeploymentRequestError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"commit_sha={request['commitSha']}\n")
            handle.write(f"canonical_issue={request['canonicalIssue']}\n")

    print(
        "Deployment request accepted: "
        f"issue=#{request['canonicalIssue']} commit={request['commitSha']} actor={request['requestedBy']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
