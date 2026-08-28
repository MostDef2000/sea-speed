from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = ("AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md", "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md", "contracts/runtime/RELEASE_READINESS_GATE.md", "contracts/branches/project-manager.md")

class DeliveryContractConvergenceTests(unittest.TestCase):
    def read(self, path: str) -> str: return (ROOT / path).read_text(encoding="utf-8-sig")
    def test_owner_and_authorization(self):
        project = self.read("contracts/branches/project-manager.md")
        self.assertIn("Role: Sea Speed Delivery Orchestrator", project)
        self.assertIn("Source authorization: OUTCOME APPROVED", self.read(".github/pull_request_template.md"))
    def test_resume_convergence(self):
        for path in PATHS:
            text = self.read(path)
            for marker in ("Resume Probe", "Delivery Checkpoint", "Next admissible action", "WAITING_EXTERNAL"): self.assertIn(marker, text, path)
    def test_pending_ci_convergence(self):
        combined = "\n".join(self.read(p) for p in PATHS).lower()
        for path in PATHS:
            text = self.read(path)
            for marker in ("queued", "in_progress", "ACTIVE", "WAITING_EXTERNAL", "Connector/provider capability outage"): self.assertIn(marker, text, path)
            self.assertIn("foreground", text.lower(), path)
        for marker in ("at least 30 seconds", "no observation count or deadline", "no checkpoint-generation churn", "failure immediately narrows to failed job/log remediation"): self.assertIn(marker, combined)

if __name__ == "__main__": unittest.main()
