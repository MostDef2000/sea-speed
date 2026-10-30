import importlib.util
import json
import unittest
from pathlib import Path

from tests.support import markdown_docs


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_CONTRACTS = (
    "AGENTS.md",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
    "contracts/branches/project-manager.md",
)

RESUME_ENTRYPOINTS = ACTIVE_CONTRACTS + (
    "contracts/branches/task-intake.md",
    "docs/agents/PM_BOOTSTRAP.md",
    "docs/architecture/sea-speed-control-plane.md",
)

# Machine-readable resumable fields of the Delivery Checkpoint v2 (issue #398
# wave 6): asserted structurally against the doc's embedded JSON example AND
# the schema it conforms to, not as quoted fragments in doc prose.
CHECKPOINT_V2_FIELDS = (
    "generation",
    "approved_scope_identity",
    "authorization_base_main",
    "current_phase",
    "branch",
    "pr",
    "exact_working_head",
    "completed_gates",
    "evidence_cursors",
    "next_admissible_action",
    "session_disposition",
    "external_wait",
    "state_invalidation_reason",
)

MATERIAL_INVALIDATION_REASONS = (
    "MATERIAL_SCOPE_CHANGE",
    "PROTECTED_BOUNDARY_CHANGE",
    "USER_CHANGED_OUTCOME",
    "MATERIAL_MAIN_DIVERGENCE",
    "EVIDENCE_CONTRADICTION",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_truth_classes_are_explicit_and_do_not_replace_main() -> None:
    # SS twins (issue #398 wave 6): the three truth classes must be defined
    # together in ONE co-locating section of every contract resume entrypoint;
    # PM_BOOTSTRAP states the same three classes as bootstrap prose inside its
    # "Canonical bootstrap prompt" section (different phrasing than the
    # contracts' truth-class bullet lists), so its twin binds the concepts to
    # that co-locating section. The runtime truth section must bind
    # Repository/product truth to `main` and Delivery-control truth to the
    # canonical Issue.
    for path in RESUME_ENTRYPOINTS:
        if path == "docs/agents/PM_BOOTSTRAP.md":
            continue
        section = markdown_docs.section_containing(
            _read(path),
            "Repository/product truth",
            "Delivery-control truth",
            "Transient interaction state",
        )
        assert section is not None, path
    bootstrap_section = markdown_docs.section_containing(
        _read("docs/agents/PM_BOOTSTRAP.md"),
        "repository/product",
        "delivery-control truth",
        "transient interaction state",
    )
    assert bootstrap_section is not None
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    truth_section = markdown_docs.section_titled(runtime, "Truth classes")
    assert truth_section is not None
    assert "current `main`" in truth_section[1]
    assert "canonical Issue" in truth_section[1]


def test_initial_admission_remains_adjacent_but_receipt_can_resume_same_scope() -> None:
    # SP keep (issue #398 wave 6): "immediately-following `commit approved`"
    # is the exact adjacency policy wording; no executable validator enforces
    # the phrase, so the literal pin stays.
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    assert "immediately-following `commit approved`" in combined
    # SS twins: every active contract must carry the receipt-continuation
    # semantics (same exact admitted scope, no authority creation, no
    # production authority) together in ONE section.
    for path in ACTIVE_CONTRACTS:
        text = _read(path)
        section = markdown_docs.section_containing(text, "same exact admitted scope", "production authority")
        assert section is not None, path
        lowered = (section[0] + section[1]).lower()
        assert "authorization receipt" in lowered, path
        assert "cannot create" in lowered, path


def test_delivery_checkpoint_v2_has_machine_readable_resumable_fields() -> None:
    # SS twin (issue #398 wave 6): the checkpoint v2 section must embed a
    # JSON example that parses and carries every resumable field as a real
    # JSON key, cross-checked against the machine-readable schema the doc
    # names (properties AND required). The retired raw pins (quoted
    # '"field"' fragments anywhere in the file) are superseded by this
    # parsed-structure twin.
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    section = markdown_docs.section_titled(runtime, "Sea Speed Delivery Checkpoint v2")
    assert section is not None
    json_blocks = [
        block
        for block in markdown_docs.fenced_blocks(section[1])
        if block and block[0].lstrip().startswith("{")
    ]
    assert len(json_blocks) == 1
    example = json.loads("\n".join(json_blocks[0]))
    schema = json.loads(_read("schemas/delivery-checkpoint-v2.schema.json"))
    for field in CHECKPOINT_V2_FIELDS:
        assert field in example, field
        assert field in schema["properties"], field
        assert field in schema["required"], field


def test_persisted_v1_checkpoint_has_executable_upgrade_path() -> None:
    # Executed twin (issue #398 wave 6): the repository validator really
    # parses a persisted v1 checkpoint and upgrades it to a valid v2
    # checkpoint — the upgrade path the contracts promise is executed here,
    # not just named. The retired combined-text pins ("v1 checkpoints remain
    # readable", validator path) are superseded by this executed twin plus
    # the placement twin on the canonical runtime section below.
    module_spec = importlib.util.spec_from_file_location(
        "validate_delivery_checkpoint_under_test",
        ROOT / "scripts/ci/validate_delivery_checkpoint.py",
    )
    assert module_spec is not None
    loader = module_spec.loader
    assert loader is not None
    module = importlib.util.module_from_spec(module_spec)
    loader.exec_module(module)
    upgraded = module.upgrade_v1_checkpoint(
        _v1_checkpoint_text(),
        next_action_kind="merge",
        next_action_executable_now=True,
    )
    assert upgraded["schema"] == "sea_speed_delivery_checkpoint_v2"
    assert upgraded["generation"] == 3
    assert upgraded["completed_gates"] == ["repository", "contracts"]
    assert upgraded["session_disposition"] == "ACTIVE"
    assert upgraded["authorization_receipt"] == "commit approved"
    # SS placement twin: the canonical runtime section must state v1
    # readability together with the executable validator upgrade.
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    section = markdown_docs.section_titled(runtime, "Sea Speed Delivery Checkpoint v2")
    assert section is not None
    assert "remain readable" in section[1]
    assert "scripts/ci/validate_delivery_checkpoint.py" in section[1]


def _v1_checkpoint_text() -> str:
    fields = {
        "Task": "#398",
        "Checkpoint generation": "2",
        "Approved scope identity": "scope-hash-1",
        "Authorization receipt": "commit approved",
        "Authorization base main": "a" * 40,
        "Current phase": "IMPLEMENTING",
        "Branch": "test/398-wave6-governance-docs",
        "PR": "#569",
        "Exact working head": "b" * 40,
        "Completed gates": "repository, contracts",
        "Evidence cursor / Issue": "comment-1",
        "Evidence cursor / PR": "#569",
        "Evidence cursor / CI": "run-1",
        "Evidence cursor / Policy": "NONE",
        "Evidence cursor / Runtime": "NONE",
        "Next admissible action": "merge exact green head",
        "State invalidation reason": "NONE",
        "Terminal interaction state": "NONE",
    }
    return "## Sea Speed Delivery Checkpoint v1\n\n" + "\n".join(
        f"- {key}: {value}" for key, value in fields.items()
    )


def test_known_task_recovery_uses_bounded_resume_probe() -> None:
    # SS twins: each recovery entrypoint must carry the bounded Resume Probe
    # together with the full-recovery restriction in ONE section, and the
    # bootstrap Required behavior must scope the probe to current `main`,
    # the valid checkpoint and the canonical Issue.
    for path in ("AGENTS.md", "contracts/branches/project-manager.md", "docs/agents/PM_BOOTSTRAP.md"):
        section = markdown_docs.section_containing(_read(path), "Resume Probe", "full project recovery")
        assert section is not None, path
    bootstrap = _read("docs/agents/PM_BOOTSTRAP.md")
    section = markdown_docs.section_titled(bootstrap, "Required behavior")
    assert section is not None
    lowered = (section[0] + section[1]).lower()
    for marker in ("valid checkpoint", "current `main`", "canonical issue"):
        assert marker in lowered, marker


def test_context_loss_is_not_authorization_or_phase_invalidation() -> None:
    # SS twins: every active contract must classify context loss together
    # with the DISCUSSION non-invalidation in ONE section (with the
    # does-not negation), and pair the unified receipt vocabulary with the
    # retired legacy receipt in one section.
    for path in ACTIVE_CONTRACTS:
        text = _read(path)
        section = markdown_docs.section_containing(
            text, "context compaction", "session restart", "connector truncation", "discussion"
        )
        assert section is not None, path
        lowered = (section[0] + section[1]).lower()
        assert "does not" in lowered or "do not" in lowered, path
        receipt_section = markdown_docs.section_containing(text, "commit approved", "outcome approved")
        assert receipt_section is not None, path


def test_lifecycle_is_monotonic_with_explicit_material_invalidation() -> None:
    # SS twin: the runtime monotonic-transition section must enumerate the
    # bounded invalidation-reason set as an exact fenced set (adding or
    # dropping a reason fails) and keep the CONTEXT_LOSS ban in the same
    # section.
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    section = markdown_docs.section_titled(runtime, "Monotonic transition rule")
    assert section is not None
    assert "monotonic" in (section[0] + section[1]).lower()
    reason_blocks = [
        block
        for block in markdown_docs.fenced_blocks(section[1])
        if "MATERIAL_SCOPE_CHANGE" in "\n".join(block)
    ]
    assert len(reason_blocks) == 1
    reasons = {line.strip() for line in reason_blocks[0] if line.strip()}
    assert reasons == set(MATERIAL_INVALIDATION_REASONS)
    assert "`CONTEXT_LOSS` is intentionally not a valid reason" in section[1]


def test_connector_reads_are_progressive_and_cursor_bound() -> None:
    # SS twins: the progressive retrieval chain, the equivalent-read ban and
    # the evidence-identity guard must co-occur in ONE connector section of
    # every resume entrypoint, together with the mandatory fresh-read
    # exception. The retired combined-substring pins are superseded.
    for path in ACTIVE_CONTRACTS + ("docs/architecture/sea-speed-control-plane.md",):
        section = markdown_docs.section_containing(
            _read(path),
            "known object -> metadata -> targeted detail -> failure fragment",
            "equivalent",
            "evidence identity",
        )
        assert section is not None, path
        lowered = (section[0] + section[1]).lower()
        assert (
            "fresh read" in lowered or "fresh evidence" in lowered or "freshness" in lowered
        ), path


def test_checkpoint_updates_are_event_driven_not_per_tool_call() -> None:
    # SS twin: each contract that carries the checkpoint-update rule must
    # pair meaningful transitions with the explicit not-after-every-tool-call
    # rule in ONE section. RELEASE_READINESS_GATE.md never carried either
    # marker (the retired pin was combined-text, satisfied by the other five
    # contracts), so its coverage stays on the combined pin below — nothing
    # is weakened: the combined assertion is the retired pin kept verbatim.
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    assert "meaningful" in combined
    assert "not after every tool call" in combined
    for path in ACTIVE_CONTRACTS:
        if path == "contracts/runtime/RELEASE_READINESS_GATE.md":
            continue
        section = markdown_docs.section_containing(_read(path), "not after every tool call", "meaningful")
        assert section is not None, path


def test_synchronous_external_wait_has_bounded_replay_semantics() -> None:
    # SS twins: every resume entrypoint must classify WAITING_EXTERNAL as a
    # nonterminal disposition in one section and carry the bounded replay
    # (unchanged cursor preserves wait and generation, no background work)
    # — with its negation — in one section.
    for path in RESUME_ENTRYPOINTS:
        text = _read(path)
        wait_section = markdown_docs.section_containing(text, "WAITING_EXTERNAL", "nonterminal")
        assert wait_section is not None, path
        replay_section = markdown_docs.section_containing(text, "unchanged", "generation", "background")
        assert replay_section is not None, path
        lowered = (replay_section[0] + replay_section[1]).lower()
        assert any(
            negation in lowered
            for negation in (
                "no background",
                "without background",
                "without promising background",
                "never claim",
                "never promise",
                "never promises",
            )
        ), path
    # SP keeps (issue #398 wave 6): "executable now"/"executable_now" and the
    # one-bounded-observation wording are doc-level vocabulary (task-intake
    # carries the wait rule without the literal), so they stay combined pins.
    combined = "\n".join(_read(path) for path in RESUME_ENTRYPOINTS)
    lowered = combined.lower()
    assert "executable now" in lowered or "executable_now" in combined
    assert "one bounded" in lowered or "once" in lowered


def test_known_pending_ci_stays_active_in_current_invocation() -> None:
    # SS twins: every active contract must carry the CI-foreground rule —
    # queued/in_progress runs remain `ACTIVE` with rate-limited exact-cursor
    # observation — in ONE section, and the persisted pre-amendment
    # compatibility upgrade in one section.
    for path in ACTIVE_CONTRACTS:
        text = _read(path)
        assert markdown_docs.section_containing(
            text, "queued", "in_progress", "remains `active`", "30 seconds", "observation count", "churn"
        ) is not None, path
        assert markdown_docs.section_containing(text, "persisted pre-amendment", "active") is not None, path


def test_resume_model_preserves_terminal_interaction_contract() -> None:
    # SS twins: every active contract must present the three terminal
    # interaction states inside its session-disposition/terminal section;
    # the runtime classifies WAITING_EXTERNAL against the terminal
    # vocabulary in its session-dispositions section; AGENTS classifies
    # progress markers as not terminal in its terminal-contract section.
    for path in ACTIVE_CONTRACTS:
        section = markdown_docs.section_containing(
            _read(path), "DONE", "BLOCKED", "HUMAN DECISION REQUIRED", "terminal interaction"
        )
        assert section is not None, path
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    wait_section = markdown_docs.section_titled(runtime, "Session dispositions and terminal interaction states")
    assert wait_section is not None
    # SP keep (issue #398 wave 6): the exact WAITING_EXTERNAL
    # not-a-lifecycle-phase/not-terminal wording IS the classification
    # policy; no validator enforces it, so the literal stays (placement-
    # pinned to the runtime session-disposition section).
    assert "`WAITING_EXTERNAL` is not a lifecycle phase, terminal interaction state" in wait_section[1]
    agents = _read("AGENTS.md")
    terminal_section = markdown_docs.section_titled(agents, "session disposition")
    assert terminal_section is not None
    assert "PR created" in terminal_section[1] or "PR creation" in terminal_section[1]


class DeliveryResumeContractTests(unittest.TestCase):
    def test_truth_classes(self) -> None:
        test_truth_classes_are_explicit_and_do_not_replace_main()

    def test_initial_admission(self) -> None:
        test_initial_admission_remains_adjacent_but_receipt_can_resume_same_scope()

    def test_checkpoint_v2(self) -> None:
        test_delivery_checkpoint_v2_has_machine_readable_resumable_fields()

    def test_v1_upgrade(self) -> None:
        test_persisted_v1_checkpoint_has_executable_upgrade_path()

    def test_resume_probe(self) -> None:
        test_known_task_recovery_uses_bounded_resume_probe()

    def test_context_loss(self) -> None:
        test_context_loss_is_not_authorization_or_phase_invalidation()

    def test_monotonic(self) -> None:
        test_lifecycle_is_monotonic_with_explicit_material_invalidation()

    def test_reads(self) -> None:
        test_connector_reads_are_progressive_and_cursor_bound()

    def test_checkpoint_events(self) -> None:
        test_checkpoint_updates_are_event_driven_not_per_tool_call()

    def test_wait_replay(self) -> None:
        test_synchronous_external_wait_has_bounded_replay_semantics()

    def test_ci_foreground(self) -> None:
        test_known_pending_ci_stays_active_in_current_invocation()

    def test_terminal(self) -> None:
        test_resume_model_preserves_terminal_interaction_contract()


if __name__ == "__main__":
    unittest.main()
