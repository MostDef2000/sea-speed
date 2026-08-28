import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CONTRACTS = ("AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md", "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md", "contracts/runtime/RELEASE_READINESS_GATE.md", "contracts/branches/project-manager.md")
RESUME_ENTRYPOINTS = ACTIVE_CONTRACTS + ("contracts/branches/task-intake.md", "docs/agents/PM_BOOTSTRAP.md", "docs/architecture/sea-speed-control-plane.md")


def _read(path: str) -> str: return (ROOT / path).read_text(encoding="utf-8-sig")

def test_truth_and_authority() -> None:
    combined = "\n".join(_read(p) for p in RESUME_ENTRYPOINTS)
    for marker in ("Repository/product truth", "Delivery-control truth", "Transient interaction state", "Resume Probe", "Delivery Checkpoint v2", "Next admissible action"): assert marker in combined
    assert "same exact admitted scope" in combined.lower()

def test_checkpoint_and_context() -> None:
    runtime = _read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
    for marker in ('"generation"', '"approved_scope_identity"', '"evidence_cursors"', '"session_disposition"', '"external_wait"'): assert marker in runtime
    combined = "\n".join(_read(p) for p in ACTIVE_CONTRACTS).lower()
    for marker in ("context compaction", "session restart", "connector truncation"): assert marker in combined

def test_wait_and_pending_ci() -> None:
    combined = "\n".join(_read(p) for p in ACTIVE_CONTRACTS)
    lowered = combined.lower()
    for marker in ("waiting_external", "nonterminal", "no background", "queued", "in_progress", "remains `active`", "at least 30 seconds", "no observation count or deadline", "no checkpoint-generation churn", "persisted pre-amendment"): assert marker in lowered

def test_terminal_contract() -> None:
    combined = "\n".join(_read(p) for p in ACTIVE_CONTRACTS)
    for state in ("DONE", "BLOCKED", "HUMAN DECISION REQUIRED"): assert state in combined

class DeliveryResumeContractTests(unittest.TestCase):
    def test_truth(self): test_truth_and_authority()
    def test_checkpoint(self): test_checkpoint_and_context()
    def test_ci(self): test_wait_and_pending_ci()
    def test_terminal(self): test_terminal_contract()
