from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.ci.validate_delivery_checkpoint import (
    CheckpointValidationError,
    decide_session_disposition,
    replay_external_observation,
    upgrade_v1_checkpoint,
    validate_checkpoint,
)

ROOT = Path(__file__).resolve().parents[1]


def checkpoint(*, disposition: str = "ACTIVE") -> dict[str, Any]:
    waiting = disposition == "WAITING_EXTERNAL"
    terminal = disposition == "TERMINAL"
    return {
        "schema": "sea_speed_delivery_checkpoint_v2", "task": "#248", "generation": 3,
        "approved_scope_identity": "synchronous-external-wait-v1", "authorization_receipt": "OUTCOME APPROVED",
        "authorization_base_main": "a" * 40, "current_phase": "IMPLEMENTING",
        "branch": "agent/synchronous-external-wait", "pr": "#249", "exact_working_head": "b" * 40,
        "completed_gates": ["SOURCE_AUTHORIZATION_ADMISSION", "PR_CREATED"],
        "evidence_cursors": {"issue": "issue:#248@generation-3", "pr": "pr:#249@head-b", "ci": "run:100@queued", "policy": None, "runtime": None},
        "next_admissible_action": {"kind": "MERGE_EXACT_GREEN_HEAD" if waiting else "RUN_LOCAL_VALIDATION", "description": "Merge after exact-head CI succeeds" if waiting else "Run validation", "executable_now": not waiting and not terminal},
        "session_disposition": disposition,
        "external_wait": {"condition": "Exact-head CI reaches a terminal conclusion", "resume_trigger": "A later synchronous invocation observes the exact run", "evidence_cursor": "run:100@queued"} if waiting else None,
        "state_invalidation_reason": None, "terminal_interaction_state": "DONE" if terminal else None,
    }


def non_ci_wait_checkpoint() -> dict[str, Any]:
    value = checkpoint(disposition="WAITING_EXTERNAL")
    value["evidence_cursors"]["ci"] = None
    value["evidence_cursors"]["runtime"] = "runtime:external-transition@pending"
    value["external_wait"]["evidence_cursor"] = "runtime:external-transition@pending"
    return value


V1_CHECKPOINT = """Sea Speed Delivery Checkpoint v1
- Task: #240
- Checkpoint generation: 7
- Approved scope identity: resumable-delivery-v1
- Authorization receipt: OUTCOME APPROVED
- Authorization base main: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Current phase: IMPLEMENTING
- Branch: agent/resumable-delivery-orchestration
- PR: #247
- Exact working head: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- Completed gates: SOURCE_AUTHORIZATION_ADMISSION, PR_CREATED
- Evidence cursor / Issue: issue:#240@generation-7
- Evidence cursor / PR: pr:#247@head-b
- Evidence cursor / CI: run:90@queued
- Evidence cursor / Policy: NONE
- Evidence cursor / Runtime: NONE
- Next admissible action: Merge after exact-head CI succeeds
- State invalidation reason: NONE
- Terminal interaction state: PENDING
"""


class DeliveryCheckpointStateMachineTests(unittest.TestCase):
    def test_schema_and_non_ci_wait(self) -> None:
        schema = json.loads((ROOT / "schemas/delivery-checkpoint-v2.schema.json").read_text())
        self.assertEqual({r["if"]["properties"]["session_disposition"]["const"] for r in schema["allOf"]}, {"ACTIVE", "WAITING_EXTERNAL", "TERMINAL"})
        validate_checkpoint(non_ci_wait_checkpoint())

    def test_new_ci_wait_rejected_but_legacy_readable(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "known CI pending"):
            validate_checkpoint(checkpoint(disposition="WAITING_EXTERNAL"))
        validate_checkpoint(checkpoint(disposition="WAITING_EXTERNAL"), allow_legacy_ci_wait=True)

    def test_disposition_precedence(self) -> None:
        self.assertEqual(decide_session_disposition(external_condition_pending=True), ("WAITING_EXTERNAL", None))
        self.assertEqual(decide_session_disposition(ci_run_pending=True), ("ACTIVE", None))
        self.assertEqual(decide_session_disposition(ci_run_pending=True, external_condition_pending=True), ("ACTIVE", None))
        self.assertEqual(decide_session_disposition(safe_action_executable_now=True, external_condition_pending=True), ("ACTIVE", None))
        with self.assertRaisesRegex(CheckpointValidationError, "cannot coexist"):
            decide_session_disposition(external_blocker=True, ci_run_pending=True)

    def test_non_ci_replay(self) -> None:
        value = non_ci_wait_checkpoint()
        before = deepcopy(value)
        self.assertEqual(replay_external_observation(value, "runtime:external-transition@pending"), before)
        result = replay_external_observation(value, "runtime:external-transition@complete")
        validate_checkpoint(result)
        self.assertEqual((result["session_disposition"], result["generation"]), ("ACTIVE", 4))

    def test_legacy_ci_replay_routes_pending_success_failure(self) -> None:
        cases = (("queued", "OBSERVE_EXACT_CI"), ("success", "MERGE_EXACT_GREEN_HEAD"), ("failure", "INSPECT_FAILED_CI"))
        for state, kind in cases:
            result = replay_external_observation(checkpoint(disposition="WAITING_EXTERNAL"), f"run:100@{state}")
            validate_checkpoint(result)
            self.assertEqual(result["session_disposition"], "ACTIVE")
            self.assertEqual(result["generation"], 4)
            self.assertEqual(result["next_admissible_action"]["kind"], kind)

    def test_wait_invariants_and_v1(self) -> None:
        value = non_ci_wait_checkpoint(); value["next_admissible_action"]["executable_now"] = True
        with self.assertRaises(CheckpointValidationError): validate_checkpoint(value)
        result = upgrade_v1_checkpoint(V1_CHECKPOINT, next_action_kind="MERGE_EXACT_GREEN_HEAD", next_action_executable_now=False, external_wait={"condition": "Exact-head CI reaches terminal", "resume_trigger": "Observe run 90", "evidence_cursor": "run:90@queued"})
        validate_checkpoint(result, allow_legacy_ci_wait=True)
        self.assertEqual(result["generation"], 8)


if __name__ == "__main__":
    unittest.main()
