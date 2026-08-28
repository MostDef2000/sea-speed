import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = ("AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md", "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md", "contracts/runtime/RELEASE_READINESS_GATE.md", "contracts/branches/project-manager.md")
def combined() -> str: return "\n".join((ROOT / p).read_text(encoding="utf-8-sig") for p in PATHS)

class DeliveryTerminalStateTests(unittest.TestCase):
    def test_three_terminal_states(self):
        text = combined()
        for state in ("DONE", "BLOCKED", "HUMAN DECISION REQUIRED"): self.assertIn(state, text)
        for path in PATHS:
            source = (ROOT / path).read_text(encoding="utf-8-sig")
            self.assertIn("`FAILED`", source); self.assertIn("not a terminal interaction state", source)
    def test_blocked_and_human_semantics(self):
        text = combined().lower()
        for marker in ("external blocker", "evidence", "unblock condition", "next admissible action", "human decision required"): self.assertIn(marker, text)
    def test_wait_is_nonterminal(self):
        text = combined().lower()
        for marker in ("waiting_external", "nonterminal", "executable now", "no background", "generation"): self.assertIn(marker, text)
    def test_pending_ci_is_active(self):
        text = combined().lower()
        for marker in ("queued", "in_progress", "remains `active`", "foreground", "at least 30 seconds", "no observation count or deadline", "no checkpoint-generation churn", "failure immediately narrows to failed job/log remediation"): self.assertIn(marker, text)
        self.assertTrue("not a reason to return `waiting_external`" in text or "never represented as `waiting_external`" in text)

if __name__ == "__main__": unittest.main()
