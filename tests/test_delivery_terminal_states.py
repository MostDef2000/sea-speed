import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATHS = (
    "AGENTS.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/project-manager.md",
)

CANONICAL = "contracts/DELIVERY_CANONICAL.md"

TERMINAL_STATES = ("DONE", "BLOCKED", "HUMAN DECISION REQUIRED")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_active_orchestration_contracts_define_only_three_terminal_interaction_states() -> None:
    canonical = _read(CANONICAL)
    for state in TERMINAL_STATES:
        assert state in canonical, f"canonical missing {state}"
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path

    combined = "\n".join(_read(path) for path in CONTRACT_PATHS)
    forbidden_legacy_contracts = (
        "Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`",
        "Valid terminal task states are only `COMPLETE`, `BLOCKED`, and `FAILED`",
        "terminal states: `COMPLETE`, `BLOCKED`, `FAILED` only",
        "terminate only COMPLETE/BLOCKED/FAILED",
        "Final state: PENDING/COMPLETE/BLOCKED/FAILED",
    )
    for legacy in forbidden_legacy_contracts:
        assert legacy not in combined


def test_task_runtime_status_block_separates_session_and_terminal_states() -> None:
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    assert "Session disposition: ACTIVE/WAITING_EXTERNAL/TERMINAL" in runtime
    assert "Terminal interaction state: NONE/DONE/BLOCKED/HUMAN DECISION REQUIRED" in runtime
    assert "Final state: PENDING/COMPLETE/BLOCKED/FAILED" not in runtime


def test_failed_is_an_event_not_a_terminal_interaction_state() -> None:
    canonical = _read(CANONICAL)
    assert "`FAILED`" in canonical
    assert "not a terminal interaction state" in canonical
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path


def test_blocked_requires_external_blocker_evidence_and_unblock_condition() -> None:
    canonical = _read(CANONICAL).lower()
    for fragment in ("external blocker", "evidence", "unblock condition", "next admissible action"):
        assert fragment in canonical, fragment
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path


def test_remediable_internal_failures_cannot_be_terminal_blockers() -> None:
    canonical = _read(CANONICAL).lower()
    assert "remedi" in canonical
    assert "ci" in canonical
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path


def test_human_decision_required_is_structured_and_resumable() -> None:
    canonical = _read(CANONICAL).lower()
    assert "human decision required" in canonical
    assert "authorization" in canonical or "protected input" in canonical
    assert "resume" in canonical
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path


def test_progress_only_statuses_are_not_terminal_handoffs() -> None:
    combined = "\n".join(_read(path).lower() for path in (CANONICAL,) + CONTRACT_PATHS)
    assert "pr created" in combined or "pr creation" in combined
    assert "ci running" in combined or "ci is running" in combined or "queued/running ci" in combined or "queued/running" in combined
    assert "while a safe authorized next action is executable now" in combined


def test_waiting_external_is_nonterminal_and_requires_no_executable_work() -> None:
    canonical = _read(CANONICAL)
    assert "WAITING_EXTERNAL" in canonical
    assert "nonterminal" in canonical.lower()
    assert "executable now" in canonical.lower()
    for path in CONTRACT_PATHS:
        assert "DELIVERY_CANONICAL" in _read(path), path
    runtime = _read(CANONICAL)
    assert "safe authorized action executable now = NO" in runtime
    assert "terminal interaction state = NONE" in runtime


def test_waiting_external_does_not_claim_background_polling() -> None:
    combined = "\n".join(_read(path).lower() for path in (CANONICAL,) + CONTRACT_PATHS)
    assert "no background" in combined
    assert "unchanged" in combined
    assert "generation" in combined


def test_checkpoint_update_is_not_a_terminal_handoff() -> None:
    combined = "\n".join(_read(path).lower() for path in (CANONICAL,) + CONTRACT_PATHS)
    assert "checkpoint" in combined
    assert "checkpoint update" in combined or "checkpoint updated" in combined
    assert "not terminal" in combined


def test_context_loss_is_not_a_blocker_or_human_decision() -> None:
    combined = "\n".join(_read(path).lower() for path in (CANONICAL,) + CONTRACT_PATHS)
    for marker in ("context compaction", "session restart", "connector truncation"):
        assert marker in combined
    assert "does not" in combined
    assert "next admissible action" in combined


class DeliveryTerminalStateTests(unittest.TestCase):
    def test_three_states(self) -> None:
        test_all_active_orchestration_contracts_define_only_three_terminal_interaction_states()

    def test_status_block(self) -> None:
        test_task_runtime_status_block_separates_session_and_terminal_states()

    def test_failed(self) -> None:
        test_failed_is_an_event_not_a_terminal_interaction_state()

    def test_blocked(self) -> None:
        test_blocked_requires_external_blocker_evidence_and_unblock_condition()

    def test_remediation(self) -> None:
        test_remediable_internal_failures_cannot_be_terminal_blockers()

    def test_human(self) -> None:
        test_human_decision_required_is_structured_and_resumable()

    def test_progress(self) -> None:
        test_progress_only_statuses_are_not_terminal_handoffs()

    def test_wait(self) -> None:
        test_waiting_external_is_nonterminal_and_requires_no_executable_work()

    def test_no_background(self) -> None:
        test_waiting_external_does_not_claim_background_polling()

    def test_checkpoint(self) -> None:
        test_checkpoint_update_is_not_a_terminal_handoff()

    def test_context_loss(self) -> None:
        test_context_loss_is_not_a_blocker_or_human_decision()
