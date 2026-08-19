#!/usr/bin/env python3
"""Evaluate standing production delegation against exact merged Sea Speed release metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from production_policy import PolicyError, decision_payload, parse_delegation, validate_policy, validate_sha40

ISSUE_FIELD_RE = re.compile(r"^- Issue:\s*#(\d+)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z0-9 /_-]*):\s*(.*?)\s*$", re.MULTILINE)
DECLARED_PATH_RE = re.compile(r"^\s{2}- `([^`]+)`\s*$", re.MULTILINE)


def github_json(url: str, token: str) -> object:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sea-speed-production-policy",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def outcome_contract(issue_body: str) -> str:
    match = re.search(r"^#{1,2}\s+Outcome Contract\s*$([\s\S]*?)(?=^#{1,2}\s+|\Z)", issue_body, re.MULTILINE)
    if not match:
        raise PolicyError("canonical Issue is missing Outcome Contract")
    return match.group(1).strip()


def declared_changed_files(pr_body: str) -> list[str]:
    change = re.search(r"^## Change\s*$([\s\S]*?)(?=^## |\Z)", pr_body, re.MULTILINE)
    if not change:
        raise PolicyError("PR is missing Change section")
    marker = re.search(r"^- Changed files:\s*$", change.group(1), re.MULTILINE)
    boundary = re.search(r"^- Out of scope:", change.group(1), re.MULTILINE)
    if not marker or not boundary or boundary.start() <= marker.end():
        raise PolicyError("PR Changed files declaration is invalid")
    paths = sorted(set(DECLARED_PATH_RE.findall(change.group(1)[marker.end():boundary.start()])))
    if not paths:
        raise PolicyError("PR approved file scope is empty")
    return paths


def release_metadata(repository: str, source_commit: str, token: str, expected_issue: int | None) -> dict[str, object]:
    validate_sha40(source_commit)
    pulls = github_json(f"https://api.github.com/repos/{repository}/commits/{source_commit}/pulls", token)
    if not isinstance(pulls, list):
        raise PolicyError("unexpected commit-to-PR response")
    merged = [pr for pr in pulls if pr.get("merged_at") and pr.get("merge_commit_sha") == source_commit]
    if len(merged) != 1:
        raise PolicyError("exact main merge commit must resolve to exactly one merged PR")
    pr = merged[0]
    pr_number = int(pr["number"])
    pr_body = pr.get("body") or ""
    issue_match = ISSUE_FIELD_RE.search(pr_body)
    if not issue_match:
        raise PolicyError("PR Change Contract does not bind a canonical Issue")
    issue_number = int(issue_match.group(1))
    if expected_issue is not None and issue_number != expected_issue:
        raise PolicyError("PR Change Contract canonical Issue does not match requested Issue")
    issue = github_json(f"https://api.github.com/repos/{repository}/issues/{issue_number}", token)
    if not isinstance(issue, dict) or issue.get("pull_request"):
        raise PolicyError("canonical Issue is missing or resolves to a pull request")
    issue_body = issue.get("body") or ""
    outcome_text = outcome_contract(issue_body)
    fields = {name: value.strip() for name, value in FIELD_RE.findall(pr_body)}
    required = (
        "Production impact", "VPS deployment", "Ubuntu worker/relay update",
        "VPS execution capability", "Ubuntu worker execution capability",
    )
    missing = [name for name in required if not fields.get(name)]
    if missing:
        raise PolicyError("PR Change Contract is missing runtime fields: " + ", ".join(missing))
    runtime_contours = {
        "productionImpact": fields["Production impact"],
        "vps": fields["VPS deployment"],
        "ubuntuWorkerRelay": fields["Ubuntu worker/relay update"],
    }
    execution_capabilities = {
        "vps": fields["VPS execution capability"],
        "ubuntuWorkerRelay": fields["Ubuntu worker execution capability"],
    }
    return {
        "canonicalIssue": issue_number,
        "pullRequest": pr_number,
        "sourceCommit": source_commit,
        "outcomeContractHash": hashlib.sha256(outcome_text.encode("utf-8")).hexdigest(),
        "changeContractHash": hashlib.sha256(pr_body.encode("utf-8")).hexdigest(),
        "approvedFiles": declared_changed_files(pr_body),
        "runtimeContours": runtime_contours,
        "executionCapabilities": execution_capabilities,
    }


def evaluate(
    *, repository: str, source_commit: str, token: str, policy: dict[str, object], delegation_raw: str | None,
    action: str, environment: str, expected_issue: int | None = None,
) -> dict[str, object]:
    validate_policy(policy)
    metadata = release_metadata(repository, source_commit, token, expected_issue)
    delegation = parse_delegation(delegation_raw)
    return decision_payload(
        policy=policy,
        delegation=delegation,
        repository=repository,
        environment=environment,
        action=action,
        source_commit=source_commit,
        canonical_issue=int(metadata["canonicalIssue"]),
        pull_request=int(metadata["pullRequest"]),
        outcome_contract_hash=str(metadata["outcomeContractHash"]),
        change_contract_hash=str(metadata["changeContractHash"]),
        approved_files=list(metadata["approvedFiles"]),
        runtime_contours=dict(metadata["runtimeContours"]),
        execution_capabilities=dict(metadata["executionCapabilities"]),
    )


def bool_required(value: object) -> str:
    return "true" if str(value).strip().upper() == "REQUIRED" else "false"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--issue", type=int)
    parser.add_argument("--action", default="deploy")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--policy", type=Path, default=Path("data/contracts/production-autonomy-policy-v1.json"))
    parser.add_argument("--delegation-json")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument("--require-allow", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("ERROR: GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    raw_delegation = args.delegation_json
    if raw_delegation is None:
        raw_delegation = os.environ.get("SEA_SPEED_PRODUCTION_DELEGATION_V1", "")
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        decision = evaluate(
            repository=args.repository,
            source_commit=args.commit,
            token=token,
            policy=policy,
            delegation_raw=raw_delegation,
            action=args.action,
            environment=args.environment,
            expected_issue=args.issue,
        )
        if args.require_allow and decision["decision"] != "allow":
            raise PolicyError(f"production policy denied execution: {decision['reason']}")
    except (PolicyError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output:
        contours = decision["runtimeContours"]
        assert isinstance(contours, dict)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"allowed={'true' if decision['decision'] == 'allow' else 'false'}\n")
            handle.write(f"decision={decision['decision']}\n")
            handle.write(f"reason={decision['reason']}\n")
            handle.write(f"policy_decision_id={decision['decisionId']}\n")
            handle.write(f"policy_hash={decision['policyHash']}\n")
            handle.write(f"canonical_issue={decision['canonicalIssue']}\n")
            handle.write(f"pr_number={decision['pullRequest']}\n")
            handle.write(f"vps_required={bool_required(contours.get('vps'))}\n")
            handle.write(f"ubuntu_worker_required={bool_required(contours.get('ubuntuWorkerRelay'))}\n")
    print(
        "Production policy evaluated: "
        f"decision={decision['decision']} reason={decision['reason']} "
        f"issue=#{decision['canonicalIssue']} pr=#{decision['pullRequest']} commit={decision['sourceCommit']} "
        f"decision_id={decision['decisionId']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
