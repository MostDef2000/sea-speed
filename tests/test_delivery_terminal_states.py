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
        assert "resume" in text, f"{path} must require automatic resume after the human decision"


def test_progress_only_statuses_are_not_terminal_handoffs() -> None:
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "pr created" in combined or "pr creation" in combined
    assert "ci is running" in combined or "queued/running ci" in combined or "queued/running" in combined
    assert "while a safe authorized next action" in combined or "while an authorized safe next step" in combined
