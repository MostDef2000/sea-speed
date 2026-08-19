#!/usr/bin/env python3
"""Pure standing-delegation policy primitives for Sea Speed production execution."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
POLICY_SCHEMA = "sea-speed-production-autonomy-policy/v1"
DELEGATION_SCHEMA = "sea_speed_standing_production_delegation_v1"
DECISION_SCHEMA = "sea_speed_production_policy_decision_v1"
ALLOWED_DECISIONS = {"allow", "deny"}


class PolicyError(ValueError):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_sha40(value: str, label: str = "source commit") -> str:
    if value != value.lower() or not SHA40_RE.fullmatch(value):
        raise PolicyError(f"{label} must be an exact lowercase full 40-character Git SHA")
    return value


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema") != POLICY_SCHEMA:
        raise PolicyError("unsupported production autonomy policy schema")
    version = policy.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PolicyError("production autonomy policy version is required")
    for key in ("allowedRepositories", "allowedEnvironments", "allowedActions"):
        value = policy.get(key)
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
            raise PolicyError(f"{key} must be a non-empty string list")
        if value != sorted(set(value)):
            raise PolicyError(f"{key} must be sorted and unique")
    if policy.get("requiredDelegationMode") != "autonomous":
        raise PolicyError("requiredDelegationMode must be autonomous")
    principal = policy.get("requiredPrincipal")
    if not isinstance(principal, str) or not principal:
        raise PolicyError("requiredPrincipal is required")
    return policy


def policy_hash(policy: dict[str, Any]) -> str:
    return canonical_json_sha256(validate_policy(policy))


def parse_delegation(raw: str | None) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PolicyError("trusted standing delegation is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PolicyError("trusted standing delegation must be a JSON object")
    return value


def validate_delegation(delegation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if delegation.get("schema") != DELEGATION_SCHEMA:
        raise PolicyError("unsupported standing production delegation schema")
    for key in ("delegationId", "principal", "repository", "environment", "mode", "policyHash"):
        value = delegation.get(key)
        if not isinstance(value, str) or not value:
            raise PolicyError(f"standing delegation {key} is required")
    if delegation.get("enabled") is not True:
        raise PolicyError("standing delegation is not enabled")
    permissions = delegation.get("permissions")
    if not isinstance(permissions, list) or not permissions or any(not isinstance(item, str) or not item for item in permissions):
        raise PolicyError("standing delegation permissions must be a non-empty string list")
    if permissions != sorted(set(permissions)):
        raise PolicyError("standing delegation permissions must be sorted and unique")
    expected_hash = policy_hash(policy)
    if delegation["policyHash"] != expected_hash:
        raise PolicyError("standing delegation policyHash does not match repository policy")
    if delegation["principal"] != policy["requiredPrincipal"]:
        raise PolicyError("standing delegation principal is not admitted by repository policy")
    if delegation["mode"] != policy["requiredDelegationMode"]:
        raise PolicyError("standing delegation mode is not admitted by repository policy")
    return delegation


def effective_permissions(delegation: dict[str, Any], policy: dict[str, Any]) -> set[str]:
    validate_delegation(delegation, policy)
    return set(delegation["permissions"]) & set(policy["allowedActions"])


def decision_payload(
    *,
    policy: dict[str, Any],
    delegation: dict[str, Any] | None,
    repository: str,
    environment: str,
    action: str,
    source_commit: str,
    canonical_issue: int,
    pull_request: int,
    outcome_contract_hash: str,
    change_contract_hash: str,
    approved_files: list[str],
    runtime_contours: dict[str, str],
    execution_capabilities: dict[str, str],
) -> dict[str, Any]:
    validate_sha40(source_commit)
    validate_policy(policy)
    if not isinstance(canonical_issue, int) or canonical_issue <= 0:
        raise PolicyError("canonical Issue must be positive")
    if not isinstance(pull_request, int) or pull_request <= 0:
        raise PolicyError("pull request must be positive")
    for label, value in (("outcomeContractHash", outcome_contract_hash), ("changeContractHash", change_contract_hash)):
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise PolicyError(f"{label} must be SHA-256")
    if approved_files != sorted(set(approved_files)) or not approved_files:
        raise PolicyError("approvedFiles must be a sorted non-empty unique list")

    decision = "deny"
    reason = "standing_delegation_missing"
    delegation_id = None
    principal = None
    if delegation is not None:
        try:
            validate_delegation(delegation, policy)
        except PolicyError as exc:
            reason = f"standing_delegation_invalid:{exc}"
        else:
            delegation_id = delegation["delegationId"]
            principal = delegation["principal"]
            if repository not in policy["allowedRepositories"]:
                reason = "repository_not_allowed_by_policy"
            elif environment not in policy["allowedEnvironments"]:
                reason = "environment_not_allowed_by_policy"
            elif delegation["repository"] != repository:
                reason = "delegation_repository_mismatch"
            elif delegation["environment"] != environment:
                reason = "delegation_environment_mismatch"
            elif action not in effective_permissions(delegation, policy):
                reason = "action_not_delegated"
            elif action not in {"deploy", "rollback"}:
                reason = "unsupported_action"
            else:
                decision = "allow"
                reason = "standing_delegation_and_repository_policy_allow"

    payload: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "decision": decision,
        "reason": reason,
        "repository": repository,
        "environment": environment,
        "action": action,
        "sourceCommit": source_commit,
        "canonicalIssue": canonical_issue,
        "pullRequest": pull_request,
        "outcomeContractHash": outcome_contract_hash,
        "changeContractHash": change_contract_hash,
        "approvedFiles": approved_files,
        "runtimeContours": runtime_contours,
        "executionCapabilities": execution_capabilities,
        "delegationId": delegation_id,
        "principal": principal,
        "policyVersion": policy["version"],
        "policyHash": policy_hash(policy),
    }
    payload["decisionId"] = canonical_json_sha256(payload)
    return payload


def validate_decision(decision: dict[str, Any], *, require_allow: bool = False) -> dict[str, Any]:
    if decision.get("schema") != DECISION_SCHEMA:
        raise PolicyError("unsupported production policy decision schema")
    if decision.get("decision") not in ALLOWED_DECISIONS:
        raise PolicyError("invalid production policy decision")
    source_commit = decision.get("sourceCommit")
    if not isinstance(source_commit, str):
        raise PolicyError("decision sourceCommit is required")
    validate_sha40(source_commit, "decision source commit")
    for key in ("policyHash", "decisionId", "outcomeContractHash", "changeContractHash"):
        value = decision.get(key)
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise PolicyError(f"decision {key} must be SHA-256")
    without_id = dict(decision)
    actual_id = without_id.pop("decisionId")
    if canonical_json_sha256(without_id) != actual_id:
        raise PolicyError("decisionId does not bind the decision payload")
    if require_allow and decision["decision"] != "allow":
        raise PolicyError(f"production policy denied execution: {decision.get('reason')}")
    if decision["decision"] == "allow":
        if not isinstance(decision.get("delegationId"), str) or not decision["delegationId"]:
            raise PolicyError("allow decision requires delegationId")
        if not isinstance(decision.get("principal"), str) or not decision["principal"]:
            raise PolicyError("allow decision requires principal")
    return decision
