#!/usr/bin/env python3
"""Build a typed non-secret execution audit record from policy and deployment evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from production_policy import PolicyError, validate_decision


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-decision", required=True, type=Path)
    parser.add_argument("--deployment-manifest", required=True, type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        decision = json.loads(args.policy_decision.read_text(encoding="utf-8"))
        validate_decision(decision, require_allow=True)
        deployment = json.loads(args.deployment_manifest.read_text(encoding="utf-8"))
        if deployment.get("sourceCommit") != decision.get("sourceCommit"):
            raise PolicyError("deployment manifest sourceCommit does not match policy decision")
        if deployment.get("state") != "runtime_verified" or deployment.get("runtimeVerified") is not True:
            raise PolicyError("deployment manifest is not runtime_verified")
    except (OSError, json.JSONDecodeError, PolicyError) as exc:
        raise SystemExit(f"ERROR: {exc}")

    audit = {
        "schema": "sea_speed_production_execution_audit_v1",
        "decisionId": decision["decisionId"],
        "delegationId": decision["delegationId"],
        "policyVersion": decision["policyVersion"],
        "policyHash": decision["policyHash"],
        "action": decision["action"],
        "repository": decision["repository"],
        "environment": decision["environment"],
        "canonicalIssue": decision["canonicalIssue"],
        "pullRequest": decision["pullRequest"],
        "sourceCommit": decision["sourceCommit"],
        "target": deployment.get("target"),
        "result": "runtime_verified",
        "policyDecisionSha256": sha256_file(args.policy_decision),
        "deploymentManifestSha256": sha256_file(args.deployment_manifest),
        "recordedAt": datetime.now(timezone.utc).isoformat(),
    }
    if args.release_manifest:
        audit["releaseManifestSha256"] = sha256_file(args.release_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Execution audit written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
