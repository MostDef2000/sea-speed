import re
import unittest
from pathlib import Path

from tests.support import markdown_docs


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

SESSION_DISPOSITIONS = ("ACTIVE", "WAITING_EXTERNAL", "TERMINAL")

# CI-foreground bundle (issue #398 wave 6): every active contract carries the
# full queued/in_progress foreground-observation rule co-located in ONE
# section (verified for all six contracts; RELEASE_READINESS_GATE.md and
# project-manager.md carry it in "Resume/readiness boundary" / "Mandatory
# flow" without the churn clause, which stays a combined pin below).
CI_FOREGROUND_BUNDLE = (
    "queued",
    "in_progress",
    "remains `active`",
    "at least 30 seconds",
    "no observation count or deadline",
    "failure immediately narrows to failed job/log remediation",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_all_active_orchestration_contracts_define_only_three_terminal_interaction_states() -> None:
    # SS twins (issue #398 wave 6): every active contract must present the
    # three terminal interaction states INSIDE its session-disposition/
    # terminal section (the retired pin accepted them anywhere in the file).
    for path in CONTRACT_PATHS:
        section = markdown_docs.section_titled(_read(path), "session disposition")
        assert section is not None, path
        blob = section[0] + "\n" + section[1]
        assert "terminal interaction" in blob.lower(), path
        for state in TERMINAL_STATES:
            assert state in blob, f"{path} missing {state} in terminal section"

    # SS twin: the runtime terminal-state fenced block enumerates EXACTLY the
    # three states (adding or dropping one fails), and the sibling
    # session-disposition block enumerates exactly the three dispositions.
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    terminal_section = markdown_docs.section_titled(runtime, "session disposition")
    assert terminal_section is not None
    state_blocks = [
        block
        for block in markdown_docs.fenced_blocks(terminal_section[1])
        if "HUMAN DECISION REQUIRED" in block
    ]
    assert len(state_blocks) == 1
    assert [line.strip() for line in state_blocks[0]] == list(TERMINAL_STATES)
    disposition_blocks = [
        block
        for block in markdown_docs.fenced_blocks(terminal_section[1])
        if "WAITING_EXTERNAL" in block
    ]
    assert len(disposition_blocks) == 1
    assert [line.strip() for line in disposition_blocks[0]] == list(SESSION_DISPOSITIONS)

    # SP keeps (issue #398 wave 6): the legacy state vocabularies are banned
    # verbatim; a ban must keep matching the exact retired phrasing so any
    # reintroduction anywhere in the contracts fails.
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
    # SS twin (issue #398 wave 6): the runtime Required status block template
    # must carry the session-disposition and terminal-interaction lines as
    # EXACT list lines inside its single fenced template block (the retired
    # substring pins are superseded by line-exact placement).
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    status_section = markdown_docs.section_titled(runtime, "required status block")
    assert status_section is not None
    template_blocks = [
        block
        for block in markdown_docs.fenced_blocks(status_section[1])
        if any(line.strip() == "- Session disposition: ACTIVE/WAITING_EXTERNAL/TERMINAL" for line in block)
    ]
    assert len(template_blocks) == 1
    lines = {line.strip() for line in template_blocks[0]}
    assert "- Session disposition: ACTIVE/WAITING_EXTERNAL/TERMINAL" in lines
    assert "- Terminal interaction state: NONE/DONE/BLOCKED/HUMAN DECISION REQUIRED" in lines
    # SP keep (issue #398 wave 6): the legacy "Final state" line is banned
    # from the runtime doc verbatim — negative contract, kept as-is.
    assert "Final state: PENDING/COMPLETE/BLOCKED/FAILED" not in runtime


def test_failed_is_an_event_not_a_terminal_interaction_state() -> None:
    # SS twin (issue #398 wave 6): the FAILED classification and its
    # not-a-terminal-interaction-state rule must co-occur in the terminal
    # section of every active contract (the retired pin accepted them
    # anywhere in the file).
    for path in CONTRACT_PATHS:
        section = markdown_docs.section_titled(_read(path), "session disposition")
        assert section is not None, path
        blob = section[0] + section[1]
        assert "`FAILED`" in blob, f"{path} must explicitly classify FAILED"
        assert "not a terminal interaction state" in blob.lower(), path


def test_blocked_requires_external_blocker_evidence_and_unblock_condition() -> None:
    # SS twin (issue #398 wave 6): the full BLOCKED semantic bundle must
    # co-occur in the terminal section of every active contract (the retired
    # pin accepted the fragments scattered anywhere in the file).
    required_fragments = (
        "external blocker",
        "evidence",
        "unblock condition",
        "next admissible action",
    )
    for path in CONTRACT_PATHS:
        section = markdown_docs.section_titled(_read(path), "session disposition")
        assert section is not None, path
        lowered = (section[0] + section[1]).lower()
        for fragment in required_fragments:
            assert fragment in lowered, f"{path} missing BLOCKED semantic: {fragment}"


def _section_with_ci_continuation(text: str) -> tuple[str, str] | None:
    """First section pairing a remediation rule with a word-bounded CI token.

    Peer review F3: the scanner matches literal substrings, so a plain "ci"
    marker is vacuous (it matches "decision"/"specific"). The CI
    continuation co-marker must be the word "CI" (case-insensitive,
    word-bounded) — the real contract phrasings are "in-scope CI
    remediation", "remediate in-scope CI" and the CI-foreground rule.
    """
    for heading, body in markdown_docs.sections(text):
        haystack = f"{heading}\n{body}"
        if "remedi" in haystack.lower() and re.search(r"\bci\b", haystack, re.IGNORECASE):
            return heading, body
    return None


def test_remediable_internal_failures_cannot_be_terminal_blockers() -> None:
    # SS twins (issue #398 wave 6): every active contract must pair its
    # remediation rule with a word-bounded CI token in ONE section (the
    # retired pin accepted "remedi" and the substring "ci" anywhere — its
    # "ci" marker was vacuous, matching "decision"/"specific"; this twin
    # word-bounds it so only a real CI-continuation rule pairs with the
    # remediation rule, and the twin fails if a contract drops that rule).
    # The two contracts that state the rule explicitly ("A remediable
    # in-scope failure is not a blocker.") must carry it in their terminal
    # section; the other four carry the same semantics as automatic in-scope
    # remediation/continuation rules, verified by the co-location twin.
    for path in CONTRACT_PATHS:
        assert _section_with_ci_continuation(_read(path)) is not None, path
    for path in (
        "contracts/runtime/RELEASE_READINESS_GATE.md",
        "contracts/branches/project-manager.md",
    ):
        section = markdown_docs.section_titled(_read(path), "session disposition")
        assert section is not None, path
        assert "A remediable in-scope failure is not a blocker." in section[1], path


def test_human_decision_required_is_structured_and_resumable() -> None:
    # SS twin (issue #398 wave 6): every active contract must classify
    # HUMAN DECISION REQUIRED together with the exact action/reply
    # requirement and the authorization/protected-input vocabulary in ONE
    # section (the retired pin accepted the fragments anywhere in the file).
    for path in CONTRACT_PATHS:
        text = _read(path)
        section = markdown_docs.section_containing(text, "HUMAN DECISION REQUIRED", "exact")
        assert section is not None, path
        lowered = (section[0] + section[1]).lower()
        assert "authorization" in lowered or "protected input" in lowered, path
    # SP keep (issue #398 wave 6): the automatic-resume-after-decision
    # requirement is doc-level vocabulary spread across the contracts; the
    # combined pin stays verbatim.
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "resume" in combined, "contracts must require automatic resume after the human decision"


def test_progress_only_statuses_are_not_terminal_handoffs() -> None:
    # SS twin (issue #398 wave 6): AGENTS.md — the contract that enumerates
    # the progress markers — must co-locate "PR created", "checkpoint
    # updated" and the executable-now continuation rule in its terminal
    # section. The remaining marker vocabulary is combined-text across the
    # contracts (only AGENTS enumerates the full marker list), so those
    # retired combined pins stay verbatim below.
    agents = _read("AGENTS.md")
    terminal_section = markdown_docs.section_titled(agents, "session disposition")
    assert terminal_section is not None
    blob = (terminal_section[0] + terminal_section[1]).lower()
    assert "pr created" in blob or "pr creation" in blob
    assert "checkpoint updated" in blob
    assert "while a safe authorized next action is executable now" in blob
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
    # SS twins (issue #398 wave 6): every active contract must classify
    # WAITING_EXTERNAL as nonterminal in one section and pair it with the
    # executable-now condition in one section (the retired pin accepted the
    # fragments anywhere in the file). The runtime wait-contract literals are
    # placement-pinned to the WAITING_EXTERNAL contract section.
    for path in CONTRACT_PATHS:
        text = _read(path)
        assert markdown_docs.section_containing(text, "WAITING_EXTERNAL", "nonterminal") is not None, path
        assert markdown_docs.section_containing(text, "WAITING_EXTERNAL", "executable now") is not None, path
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    wait_section = markdown_docs.section_titled(runtime, "WAITING_EXTERNAL contract")
    assert wait_section is not None
    assert "safe authorized action executable now = NO" in wait_section[1]
    assert "terminal interaction state = NONE" in wait_section[1]


def test_waiting_external_does_not_claim_background_polling() -> None:
    # SP keep (issue #398 wave 6): the no-background/unchanged/generation
    # vocabulary is combined-text across the contracts; the per-doc placement
    # twins for the bounded replay live in test_delivery_resume_contract.py
    # (same-change coverage ledger), so this file keeps the retired combined
    # pin verbatim as a duplicate-coverage guard.
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "no background" in combined
    assert "unchanged" in combined
    assert "generation" in combined


def test_known_pending_ci_is_foreground_active_not_waiting_external() -> None:
    # SS twin (issue #398 wave 6): every active contract must carry the full
    # CI-foreground bundle — queued/in_progress runs remain `ACTIVE` with
    # rate-limited exact-cursor observation and failure narrowing — in ONE
    # section. "foreground" and the churn clause are not carried by every
    # contract's bundle section, so their retired combined pins stay
    # verbatim below.
    for path in CONTRACT_PATHS:
        assert markdown_docs.section_containing(_read(path), *CI_FOREGROUND_BUNDLE) is not None, path
    combined = "\n".join(_read(path) for path in CONTRACT_PATHS)
    lowered = combined.lower()
    assert "foreground" in lowered
    assert "no checkpoint-generation churn" in lowered


def test_checkpoint_update_is_not_a_terminal_handoff() -> None:
    # SP keep (issue #398 wave 6): the checkpoint-update non-terminal
    # wording is combined-text across the contracts; the placement twins for
    # checkpoint-update events live in test_delivery_resume_contract.py
    # (same-change coverage ledger), so this file keeps the retired combined
    # pin verbatim.
    combined = "\n".join(_read(path).lower() for path in CONTRACT_PATHS)
    assert "checkpoint" in combined
    assert "checkpoint update" in combined or "checkpoint updated" in combined
    assert "not terminal" in combined


def test_context_loss_is_not_a_blocker_or_human_decision() -> None:
    # SP keep (issue #398 wave 6): the context-loss marker vocabulary is
    # combined-text across the contracts; the per-doc context-loss placement
    # twins live in test_delivery_resume_contract.py (same-change coverage
    # ledger), so this file keeps the retired combined pin verbatim.
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


if __name__ == "__main__":
    unittest.main()
