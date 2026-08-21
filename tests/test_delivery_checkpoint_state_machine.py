from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.ci.validate_delivery_checkpoint import (
    CheckpointValidationError,
    decide_session_disposition,
    replay_external_observation,
    upgrade_v1_checkpoint,
    validate_checkpoint,
)

ROOT = Path(__file__).resolve().parents[1]


def checkpoint(*, disposition: str = "ACTIVE") -> dict[str, object]:
    waiting = disposition == "WAITING_EXTERNAL"
    terminal = disposition == "TERMINAL"
    return {
        "schema": "sea_speed_delivery_checkpoint_v2",
        "task": "#248",
        "generation": 3,
        "approved_scope_identity": "synchronous-external-wait-v1",
        "authorization_receipt": "OUTCOME APPROVED",
        "authorization_base_main": "a" * 40,
        "current_phase": "IMPLEMENTING",
        "branch": "agent/synchronous-external-wait",
        "pr": "#249",
        "exact_working_head": "b" * 40,
        "completed_gates": ["SOURCE_AUTHORIZATION_ADMISSION", "PR_CREATED"],
        "evidence_cursors": {
            "issue": "issue:#248@generation-3",
            "pr": "pr:#249@head-b",
            "ci": "run:100@queued",
            "policy": None,
            "runtime": None,
        },
        "next_admissible_action": {
            "kind": "MERGE_EXACT_GREEN_HEAD" if waiting else "RUN_LOCAL_VALIDATION",
            "description": "Merge after exact-head CI succeeds" if waiting else "Run validation",
            "executable_now": not waiting and not terminal,
        },
        "session_disposition": disposition,
        "external_wait": (
            {
                "condition": "Exact-head CI reaches a terminal conclusion",
                "resume_trigger": "A later synchronous invocation observes the exact run",
                "evidence_cursor": "run:100@queued",
            }
            if waiting
            else None
        ),
        "state_invalidation_reason": None,
        "terminal_interaction_state": "DONE" if terminal else None,
    }


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
    def test_schema_declares_cross_field_disposition_rules(self) -> None:
        schema = json.loads((ROOT / "schemas/delivery-checkpoint-v2.schema.json").read_text(encoding="utf-8"))
        dispositions = {
            rule["if"]["properties"]["session_disposition"]["const"]
            for rule in schema["allOf"]
        }
        self.assertEqual(dispositions, {"ACTIVE", "WAITING_EXTERNAL", "TERMINAL"})
        validate_checkpoint(checkpoint(disposition="WAITING_EXTERNAL"))

    def test_pending_ci_without_executable_work_returns_waiting_external(self) -> None:
        self.assertEqual(decide_session_disposition(external_condition_pending=True), ("WAITING_EXTERNAL", None))

    def test_immediately_executable_work_takes_precedence_over_waiting(self) -> None:
        self.assertEqual(
            decide_session_disposition(safe_action_executable_now=True, external_condition_pending=True),
            ("ACTIVE", None),
        )

    def test_terminal_condition_rejects_concurrent_executable_work(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "cannot coexist"):
            decide_session_disposition(external_blocker=True, safe_action_executable_now=True)

    def test_unchanged_external_evidence_preserves_checkpoint_and_generation(self) -> None:
        value = checkpoint(disposition="WAITING_EXTERNAL")
        before = deepcopy(value)
        result = replay_external_observation(value, "run:100@queued")
        self.assertEqual(result, before)
        self.assertEqual(value, before)
        self.assertEqual(result["generation"], 3)

    def test_changed_external_evidence_produces_valid_active_checkpoint(self) -> None:
        value = checkpoint(disposition="WAITING_EXTERNAL")
        result = replay_external_observation(value, "run:100@success")
        validate_checkpoint(result)
        self.assertEqual(result["session_disposition"], "ACTIVE")
        self.assertEqual(result["generation"], 4)
        self.assertEqual(result["evidence_cursors"]["ci"], "run:100@success")
        self.assertIsNone(result["external_wait"])
        self.assertTrue(result["next_admissible_action"]["executable_now"])
        self.assertEqual(value["session_disposition"], "WAITING_EXTERNAL")

    def test_terminal_conditions_remain_distinct_from_external_wait(self) -> None:
        cases = (
            ({"outcome_complete": True}, ("TERMINAL", "DONE")),
            ({"external_blocker": True}, ("TERMINAL", "BLOCKED")),
            ({"human_decision_required": True}, ("TERMINAL", "HUMAN DECISION REQUIRED")),
        )
        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertEqual(decide_session_disposition(**condition), expected)

    def test_waiting_checkpoint_rejects_an_executable_action(self) -> None:
        value = checkpoint(disposition="WAITING_EXTERNAL")
        value["next_admissible_action"]["executable_now"] = True
        with self.assertRaisesRegex(CheckpointValidationError, "cannot coexist"):
            validate_checkpoint(value)

    def test_wait_cursor_must_reference_exactly_one_evidence_cursor(self) -> None:
        value = checkpoint(disposition="WAITING_EXTERNAL")
        value["external_wait"]["evidence_cursor"] = "unknown"
        with self.assertRaisesRegex(CheckpointValidationError, "exactly one"):
            validate_checkpoint(value)

    def test_persisted_v1_checkpoint_upgrades_to_valid_waiting_v2(self) -> None:
        result = upgrade_v1_checkpoint(
            V1_CHECKPOINT,
            next_action_kind="MERGE_EXACT_GREEN_HEAD",
            next_action_executable_now=False,
            external_wait={
                "condition": "Exact-head CI reaches a terminal conclusion",
                "resume_trigger": "A later invocation observes run 90",
                "evidence_cursor": "run:90@queued",
            },
        )
        validate_checkpoint(result)
        self.assertEqual(result["schema"], "sea_speed_delivery_checkpoint_v2")
        self.assertEqual(result["generation"], 8)
        self.assertEqual(result["session_disposition"], "WAITING_EXTERNAL")
        self.assertEqual(result["authorization_receipt"], "OUTCOME APPROVED")

    def test_absence_of_action_wait_or_terminal_condition_fails_closed(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "no executable action"):
            decide_session_disposition()


def checkpoint_v3(*, phase: str = "PR", waiting_on: str | None = "ci", authorized: bool = True) -> dict[str, object]:
    return {
        "schema": "sea_speed_delivery_checkpoint_v3",
        "task": "#248",
        "scope_hash": "sha256:" + "a" * 64,
        "authorized": authorized,
        "lane": "FAST" if phase in {"PLANNING", "IMPLEMENTING"} else "STANDARD",
        "phase": phase,
        "pr": "#249",
        "head": "b" * 40,
        "next": "CHECK_CI" if waiting_on else "MERGE",
        "waiting_on": waiting_on,
    }


class DeliveryCheckpointV3Tests(unittest.TestCase):
    def test_v3_schema_valid(self) -> None:
        validate_checkpoint(checkpoint_v3(phase="PR", waiting_on="ci"))

    def test_v3_blocked_requires_external(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "BLOCKED.*external"):
            validate_checkpoint(checkpoint_v3(phase="BLOCKED", waiting_on="ci"))
        validate_checkpoint(checkpoint_v3(phase="BLOCKED", waiting_on="external"))

    def test_v3_human_requires_human(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "HUMAN.*human"):
            validate_checkpoint(checkpoint_v3(phase="HUMAN_DECISION_REQUIRED", waiting_on="external"))
        validate_checkpoint(checkpoint_v3(phase="HUMAN_DECISION_REQUIRED", waiting_on="human"))

    def test_v3_done_requires_null(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "DONE.*null"):
            validate_checkpoint(checkpoint_v3(phase="DONE", waiting_on="ci"))
        validate_checkpoint(checkpoint_v3(phase="DONE", waiting_on=None))

    def test_v3_authorized_required_for_post_admission(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "authorized.*true"):
            validate_checkpoint(checkpoint_v3(phase="PR", waiting_on="ci", authorized=False))
        validate_checkpoint(checkpoint_v3(phase="PLANNING", waiting_on=None, authorized=False))

    def test_v3_waiting_on_enum(self) -> None:
        with self.assertRaisesRegex(CheckpointValidationError, "waiting_on"):
            validate_checkpoint(checkpoint_v3(phase="PR", waiting_on="invalid"))

    def test_v3_replay_unchanged(self) -> None:
        cp = checkpoint_v3(phase="PR", waiting_on="ci")
        before = deepcopy(cp)
        result = replay_external_observation(cp, "ci")
        self.assertEqual(result, before)

    def test_v3_replay_changed_clears_waiting(self) -> None:
        cp = checkpoint_v3(phase="PR", waiting_on="ci")
        result = replay_external_observation(cp, "success")
        validate_checkpoint(result)
        self.assertIsNone(result["waiting_on"])
        self.assertEqual(result["phase"], "PR")


if __name__ == "__main__":
    unittest.main()
