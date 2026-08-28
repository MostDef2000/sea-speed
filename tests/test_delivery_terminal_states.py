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

TERMINAL_STATES = ("DONE", "BLOCKED", "HUMAN DECISION REQUIRED")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_active_orchestration_contracts_define_only_three_terminal_interaction_states() -> None:
    for path in CONTRACT_PATHS:
        text = _read(path)
        lowered = text.lower()
        assert "terminal interaction" in lowered, path
        for state in TERMINAL_STATES:
            assert state in text, f"{path} missing {state}"

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
    for path in CONTRACT_PATHS:
        text = _read(path)
        assert "`FAILED`" in text, f"{path} must explicitly classify FAILED"
        assert "not a terminal interaction state" in text, path


def test_blocked_requires_external_blocker_evidence_and_unblock_condition() -> None:
    required_fragments = (
        "external blocker",
        "evidence",
        "unblock condition",
        "next admissible action",
    )
    for path in CONTRACT_PATHS:
        text = _read(path).lower()
        for fragment in required_fragments:
            assert fragment in text, f"{path} missing BLOCKED semantic: {fragment}"


def test_remediable_internal_failures_cannot_be_terminal_blockers() -> None:
    for path in CONTRACT_PATHS:
        text = _read(path).lower()
        assert "remedi" in text, f"{path} must require automatic remediation"
        assert "ci" in text, f"{path} must cover CI continuation"
        assert "not" in text, path


def test_human_decision_required_is_structured_and_resumable() -> None:
    for path in CONTRACT_PATHS:
        text = _read(path).lower()
        assert "human decision required" in text, path
        assert "decision" in text, path
        assert "authorization" in text or "protected input" in text, path
        assert "exact" in text, path

    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "resume" in combined, "contracts must require automatic resume after the human decision"


def test_progress_only_statuses_are_not_terminal_handoffs() -> None:
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "pr created" in combined or "pr creation" in combined
    assert (
        "ci running" in combined
        or "ci is running" in combined
        or "queued/running ci" in combined
        or "queued/running" in combined
        or ("queued" in combined and "in_progress" in combined)
    )
    assert "remains `active`" in combined
    assert "not a reason to return `waiting_external`" in combined or "never represented as `waiting_external`" in combined
    assert "while a safe authorized next action is executable now" in combined


def test_waiting_external_is_nonterminal_and_requires_no_executable_work() -> None:
    for path in CONTRACT_PATHS:
        text = _read(path)
        assert "WAITING_EXTERNAL" in text, path
        assert "nonterminal" in text.lower(), path
        assert "executable now" in text.lower(), path
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    assert "safe authorized action executable now = NO" in runtime
    assert "terminal interaction state = NONE" in runtime


def test_waiting_external_does_not_claim_background_polling() -> None:
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "no background" in combined
    assert "unchanged" in combined
    assert "generation" in combined


def test_known_pending_ci_is_foreground_active_not_waiting_external() -> None:
    combined = "\n".join(_read(path) for path in CONTRACT_PATHS)
    lowered = combined.lower()
    for marker in ("queued", "in_progress", "foreground", "at least 30 seconds"):
        assert marker in lowered
    assert "no observation count or deadline" in lowered
    assert "no checkpoint-generation churn" in lowered
    assert "failure immediately narrows to failed job/log remediation" in lowered


def test_checkpoint_update_is_not_a_terminal_handoff() -> None:
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "checkpoint" in combined
    assert "checkpoint update" in combined or "checkpoint updated" in combined
    assert "not terminal" in combined


def test_context_loss_is_not_a_blocker_or_human_decision() -> None:
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
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

    def test_ci_foreground(self) -> None:
        test_known_pending_ci_is_foreground_active_not_waiting_external()

    def test_checkpoint(self) -> None:
        test_checkpoint_update_is_not_a_terminal_handoff()

    def test_context_loss(self) -> None:
        test_context_loss_is_not_a_blocker_or_human_decision()
