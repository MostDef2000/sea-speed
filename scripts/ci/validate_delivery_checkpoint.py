#!/usr/bin/env python3
"""Validate and replay Sea Speed Delivery Checkpoint state."""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_ID = "sea_speed_delivery_checkpoint_v2"
ACTIVE_PHASES = {
    "DISCUSSION", "READY_FOR_IMPLEMENTATION", "IMPLEMENTING", "SOURCE_INTEGRATED",
    "POLICY_PENDING", "ACTIONS_REQUIRED", "ACTIONS_RUNNING", "ACTIONS_COMPLETED",
    "RUNTIME_ACCEPTANCE",
}
SESSION_DISPOSITIONS = {"ACTIVE", "WAITING_EXTERNAL", "TERMINAL"}
TERMINAL_INTERACTION_STATES = {"DONE", "BLOCKED", "HUMAN DECISION REQUIRED"}
INVALIDATION_REASONS = {
    "MATERIAL_SCOPE_CHANGE", "PROTECTED_BOUNDARY_CHANGE", "USER_CHANGED_OUTCOME",
    "MATERIAL_MAIN_DIVERGENCE", "EVIDENCE_CONTRADICTION",
}
EVIDENCE_CURSOR_KEYS = {"issue", "pr", "ci", "policy", "runtime"}
REQUIRED_KEYS = {
    "schema", "task", "generation", "approved_scope_identity", "authorization_receipt",
    "authorization_base_main", "current_phase", "branch", "pr", "exact_working_head",
    "completed_gates", "evidence_cursors", "next_admissible_action", "session_disposition",
    "external_wait", "state_invalidation_reason", "terminal_interaction_state",
}
V1_FIELDS = {
    "Task", "Checkpoint generation", "Approved scope identity", "Authorization receipt",
    "Authorization base main", "Current phase", "Branch", "PR", "Exact working head",
    "Completed gates", "Evidence cursor / Issue", "Evidence cursor / PR",
    "Evidence cursor / CI", "Evidence cursor / Policy", "Evidence cursor / Runtime",
    "Next admissible action", "State invalidation reason", "Terminal interaction state",
}


class CheckpointValidationError(ValueError):
    """Raised when a checkpoint cannot drive deterministic continuation."""


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointValidationError(f"{field} must be a non-empty string")


def _nullable_v1(value: str) -> str | None:
    return None if value in {"NONE", "PENDING", "NOT APPLICABLE"} else value


def parse_v1_checkpoint(text: str) -> dict[str, str]:
    """Parse a persisted v1 Markdown checkpoint without treating it as new authority."""
    if "Sea Speed Delivery Checkpoint v1" not in text:
        raise CheckpointValidationError("v1 checkpoint heading is missing")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- ") or ": " not in line:
            continue
        key, value = line[2:].split(": ", 1)
        if key in V1_FIELDS:
            fields[key] = value.strip()
    missing = sorted(V1_FIELDS - set(fields))
    if missing:
        raise CheckpointValidationError(f"v1 checkpoint fields are missing: {missing}")
    return fields


def upgrade_v1_checkpoint(
    text: str,
    *,
    next_action_kind: str,
    next_action_executable_now: bool,
    external_wait: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Upgrade persisted same-scope v1 evidence at a meaningful state transition."""
    fields = parse_v1_checkpoint(text)
    terminal = _nullable_v1(fields["Terminal interaction state"])
    if terminal is not None:
        disposition = "TERMINAL"
    elif external_wait is not None:
        disposition = "WAITING_EXTERNAL"
    else:
        disposition = "ACTIVE"
    gates = [gate.strip() for gate in fields["Completed gates"].split(",") if gate.strip()]
    checkpoint = {
        "schema": SCHEMA_ID,
        "task": fields["Task"],
        "generation": int(fields["Checkpoint generation"]) + 1,
        "approved_scope_identity": fields["Approved scope identity"],
        "authorization_receipt": fields["Authorization receipt"],
        "authorization_base_main": fields["Authorization base main"],
        "current_phase": fields["Current phase"],
        "branch": _nullable_v1(fields["Branch"]),
        "pr": _nullable_v1(fields["PR"]),
        "exact_working_head": _nullable_v1(fields["Exact working head"]),
        "completed_gates": gates,
        "evidence_cursors": {
            "issue": _nullable_v1(fields["Evidence cursor / Issue"]),
            "pr": _nullable_v1(fields["Evidence cursor / PR"]),
            "ci": _nullable_v1(fields["Evidence cursor / CI"]),
            "policy": _nullable_v1(fields["Evidence cursor / Policy"]),
            "runtime": _nullable_v1(fields["Evidence cursor / Runtime"]),
        },
        "next_admissible_action": {
            "kind": next_action_kind,
            "description": fields["Next admissible action"],
            "executable_now": next_action_executable_now,
        },
        "session_disposition": disposition,
        "external_wait": external_wait,
        "state_invalidation_reason": _nullable_v1(fields["State invalidation reason"]),
        "terminal_interaction_state": terminal,
    }
    validate_checkpoint(checkpoint)
    return checkpoint


def validate_checkpoint(checkpoint: dict[str, Any]) -> None:
    """Validate structural and cross-field v2 checkpoint invariants."""
    if set(checkpoint) != REQUIRED_KEYS:
        missing = sorted(REQUIRED_KEYS - set(checkpoint))
        extra = sorted(set(checkpoint) - REQUIRED_KEYS)
        raise CheckpointValidationError(f"checkpoint keys mismatch: missing={missing}, extra={extra}")
    if checkpoint["schema"] != SCHEMA_ID:
        raise CheckpointValidationError(f"schema must be {SCHEMA_ID}")
    if not isinstance(checkpoint["task"], str) or not re.fullmatch(r"#[1-9][0-9]*", checkpoint["task"]):
        raise CheckpointValidationError("task must be a canonical #<issue> reference")
    generation = checkpoint["generation"]
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise CheckpointValidationError("generation must be a positive integer")
    _require_non_empty_string(checkpoint["approved_scope_identity"], "approved_scope_identity")
    if checkpoint["authorization_receipt"] != "OUTCOME APPROVED":
        raise CheckpointValidationError("authorization_receipt must be OUTCOME APPROVED")
    base = checkpoint["authorization_base_main"]
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40}", base):
        raise CheckpointValidationError("authorization_base_main must be a lowercase 40-character SHA")
    if checkpoint["current_phase"] not in ACTIVE_PHASES:
        raise CheckpointValidationError("current_phase is not an active lifecycle phase")
    for field in ("branch", "pr", "exact_working_head"):
        if checkpoint[field] is not None and not isinstance(checkpoint[field], str):
            raise CheckpointValidationError(f"{field} must be a string or null")
    if checkpoint["pr"] is not None and not re.fullmatch(r"#[1-9][0-9]*", checkpoint["pr"]):
        raise CheckpointValidationError("pr must be null or a #<number> reference")
    head = checkpoint["exact_working_head"]
    if head is not None and not re.fullmatch(r"[0-9a-f]{40}", head):
        raise CheckpointValidationError("exact_working_head must be null or a lowercase 40-character SHA")
    gates = checkpoint["completed_gates"]
    if not isinstance(gates, list) or any(not isinstance(gate, str) or not gate.strip() for gate in gates):
        raise CheckpointValidationError("completed_gates must contain non-empty strings")
    if len(gates) != len(set(gates)):
        raise CheckpointValidationError("completed_gates must be unique")
    cursors = checkpoint["evidence_cursors"]
    if not isinstance(cursors, dict) or set(cursors) != EVIDENCE_CURSOR_KEYS:
        raise CheckpointValidationError("evidence_cursors must contain the five canonical cursor keys")
    if any(value is not None and not isinstance(value, str) for value in cursors.values()):
        raise CheckpointValidationError("evidence cursor values must be strings or null")
    action = checkpoint["next_admissible_action"]
    if not isinstance(action, dict) or set(action) != {"kind", "description", "executable_now"}:
        raise CheckpointValidationError("next_admissible_action has invalid fields")
    _require_non_empty_string(action["kind"], "next_admissible_action.kind")
    _require_non_empty_string(action["description"], "next_admissible_action.description")
    if not isinstance(action["executable_now"], bool):
        raise CheckpointValidationError("next_admissible_action.executable_now must be boolean")
    disposition = checkpoint["session_disposition"]
    if disposition not in SESSION_DISPOSITIONS:
        raise CheckpointValidationError("session_disposition is invalid")
    invalidation = checkpoint["state_invalidation_reason"]
    if invalidation is not None and invalidation not in INVALIDATION_REASONS:
        raise CheckpointValidationError("state_invalidation_reason is invalid")
    terminal = checkpoint["terminal_interaction_state"]
    if terminal is not None and terminal not in TERMINAL_INTERACTION_STATES:
        raise CheckpointValidationError("terminal_interaction_state is invalid")
    wait = checkpoint["external_wait"]
    if disposition == "ACTIVE":
        if not action["executable_now"] or wait is not None or terminal is not None:
            raise CheckpointValidationError("ACTIVE requires executable work and no wait or terminal state")
    elif disposition == "WAITING_EXTERNAL":
        if action["executable_now"] or terminal is not None:
            raise CheckpointValidationError("WAITING_EXTERNAL cannot coexist with executable work or a terminal state")
        if not isinstance(wait, dict) or set(wait) != {"condition", "resume_trigger", "evidence_cursor"}:
            raise CheckpointValidationError("WAITING_EXTERNAL requires a complete external_wait predicate")
        for field in ("condition", "resume_trigger", "evidence_cursor"):
            _require_non_empty_string(wait[field], f"external_wait.{field}")
        if list(cursors.values()).count(wait["evidence_cursor"]) != 1:
            raise CheckpointValidationError("external_wait.evidence_cursor must identify exactly one evidence cursor")
    elif action["executable_now"] or wait is not None or terminal is None:
        raise CheckpointValidationError("TERMINAL requires one terminal state and no executable work or external wait")


def decide_session_disposition(
    *, outcome_complete: bool = False, external_blocker: bool = False,
    human_decision_required: bool = False, safe_action_executable_now: bool = False,
    external_condition_pending: bool = False,
) -> tuple[str, str | None]:
    """Return the only admissible disposition for the current synchronous invocation."""
    terminal_flags = sum((outcome_complete, external_blocker, human_decision_required))
    if terminal_flags > 1:
        raise CheckpointValidationError("terminal conditions are mutually exclusive")
    if terminal_flags and safe_action_executable_now:
        raise CheckpointValidationError("a terminal condition cannot coexist with executable work")
    if outcome_complete:
        return "TERMINAL", "DONE"
    if external_blocker:
        return "TERMINAL", "BLOCKED"
    if human_decision_required:
        return "TERMINAL", "HUMAN DECISION REQUIRED"
    if safe_action_executable_now:
        return "ACTIVE", None
    if external_condition_pending:
        return "WAITING_EXTERNAL", None
    raise CheckpointValidationError("no executable action, external wait, or terminal condition was supplied")


def replay_external_observation(checkpoint: dict[str, Any], observed_cursor: str) -> dict[str, Any]:
    """Apply one bounded resume observation and return the resulting valid checkpoint."""
    validate_checkpoint(checkpoint)
    if checkpoint["session_disposition"] != "WAITING_EXTERNAL":
        raise CheckpointValidationError("external observation requires WAITING_EXTERNAL")
    _require_non_empty_string(observed_cursor, "observed_cursor")
    result = deepcopy(checkpoint)
    wait_cursor = checkpoint["external_wait"]["evidence_cursor"]
    if observed_cursor == wait_cursor:
        return result
    cursor_key = next(key for key, value in result["evidence_cursors"].items() if value == wait_cursor)
    result["generation"] += 1
    result["evidence_cursors"][cursor_key] = observed_cursor
    result["session_disposition"] = "ACTIVE"
    result["external_wait"] = None
    result["next_admissible_action"]["executable_now"] = True
    validate_checkpoint(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="Path to a Delivery Checkpoint v2 JSON document")
    args = parser.parse_args()
    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    validate_checkpoint(checkpoint)
    print("Sea Speed Delivery Checkpoint v2 is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
