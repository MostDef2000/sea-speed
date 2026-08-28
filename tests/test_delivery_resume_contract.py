import unittest
from pathlib import Path


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


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_truth_classes_are_explicit_and_do_not_replace_main() -> None:
    combined = "\n".join(_read(path) for path in RESUME_ENTRYPOINTS)
    for marker in ("Repository/product truth", "Delivery-control truth", "Transient interaction state"):
        assert marker in combined
    assert "main" in combined
    assert "canonical Issue" in combined


def test_initial_admission_remains_adjacent_but_receipt_can_resume_same_scope() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    assert "immediately-following `OUTCOME APPROVED`" in combined
    assert "authorization receipt" in combined.lower()
    assert "same exact admitted scope" in combined.lower()
    assert "cannot create" in combined.lower() or "never creates" in combined.lower()
    assert "production authority" in combined.lower()


def test_delivery_checkpoint_v2_has_machine_readable_resumable_fields() -> None:
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    assert "Sea Speed Delivery Checkpoint v2" in runtime
    for marker in (
        '"generation"', '"approved_scope_identity"', '"authorization_base_main"',
        '"current_phase"', '"branch"', '"pr"', '"exact_working_head"',
        '"completed_gates"', '"evidence_cursors"', '"next_admissible_action"',
        '"session_disposition"', '"external_wait"', '"state_invalidation_reason"',
    ):
        assert marker in runtime, marker


def test_persisted_v1_checkpoint_has_executable_upgrade_path() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    assert "v1 checkpoints remain readable" in combined
    assert "scripts/ci/validate_delivery_checkpoint.py" in combined


def test_known_task_recovery_uses_bounded_resume_probe() -> None:
    for path in ("AGENTS.md", "contracts/branches/project-manager.md", "docs/agents/PM_BOOTSTRAP.md"):
        text = _read(path)
        assert "Resume Probe" in text, path
        assert "full project recovery" in text.lower(), path
    bootstrap = _read("docs/agents/PM_BOOTSTRAP.md").lower()
    assert "valid checkpoint" in bootstrap
    assert "current `main`" in bootstrap
    assert "canonical issue" in bootstrap


def test_context_loss_is_not_authorization_or_phase_invalidation() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS).lower()
    for marker in ("context compaction", "session restart", "connector truncation"):
        assert marker in combined
    assert "does not" in combined
    assert "discussion" in combined
    assert "outcome approved" in combined


def test_lifecycle_is_monotonic_with_explicit_material_invalidation() -> None:
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    assert "monotonic" in runtime.lower()
    for reason in (
        "MATERIAL_SCOPE_CHANGE",
        "PROTECTED_BOUNDARY_CHANGE",
        "USER_CHANGED_OUTCOME",
        "MATERIAL_MAIN_DIVERGENCE",
        "EVIDENCE_CONTRADICTION",
    ):
        assert reason in runtime
    assert "`CONTEXT_LOSS` is intentionally not a valid reason" in runtime


def test_connector_reads_are_progressive_and_cursor_bound() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS + ("docs/architecture/sea-speed-control-plane.md",))
    assert "known object -> metadata -> targeted detail -> failure fragment" in combined
    lowered = combined.lower()
    assert "equivalent" in lowered
    assert "evidence identity" in lowered
    assert "mandatory" in lowered and "fresh read" in lowered


def test_checkpoint_updates_are_event_driven_not_per_tool_call() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    lowered = combined.lower()
    assert "meaningful" in lowered
    assert "not after every tool call" in lowered


def test_synchronous_external_wait_has_bounded_replay_semantics() -> None:
    combined = "\n".join(_read(path) for path in RESUME_ENTRYPOINTS)
    lowered = combined.lower()
    assert "WAITING_EXTERNAL" in combined
    assert "nonterminal" in lowered
    assert "no background" in lowered
    assert "executable now" in lowered or "executable_now" in combined
    assert "unchanged" in lowered
    assert "generation" in lowered
    assert "one bounded" in lowered or "once" in lowered


def test_known_pending_ci_stays_active_in_current_invocation() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    lowered = combined.lower()
    assert "queued" in lowered and "in_progress" in lowered
    assert "remains `active`" in lowered
    assert "at least 30 seconds" in lowered
    assert "no observation count or deadline" in lowered
    assert "no checkpoint-generation churn" in lowered
    assert "persisted pre-amendment" in lowered
    assert "upgrades to `active`" in lowered or "upgrade the disposition to `active`" in lowered


def test_resume_model_preserves_terminal_interaction_contract() -> None:
    combined = "\n".join(_read(path) for path in ACTIVE_CONTRACTS)
    for state in ("DONE", "BLOCKED", "HUMAN DECISION REQUIRED"):
        assert state in combined
    assert "`WAITING_EXTERNAL` is not a lifecycle phase, terminal interaction state" in combined
    assert "PR created" in combined or "PR creation" in combined


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
