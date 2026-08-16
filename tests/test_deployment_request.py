from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "scripts/release/parse_deployment_request.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


def load_parser():
    spec = importlib.util.spec_from_file_location("sea_speed_deployment_request", PARSER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load deployment request parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_parser()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = Path(self.temp.name) / "policy.json"
        self.policy.write_text(
            json.dumps(
                {
                    "schema": "sea-speed-production-authorization-policy/v1",
                    "authorizedActors": ["MostDef2000"],
                }
            ),
            encoding="utf-8",
        )

    def event(self, body: str = f"DEPLOY VPS {SHA}") -> dict[str, object]:
        return {
            "action": "created",
            "issue": {"number": 178, "state": "open"},
            "comment": {"body": body, "user": {"login": "MostDef2000"}},
            "sender": {"login": "MostDef2000"},
        }

    def test_accepts_exact_authorized_open_issue_request(self) -> None:
        request = self.module.parse_event(self.event(), self.policy)
        self.assertEqual(request["canonicalIssue"], 178)
        self.assertEqual(request["commitSha"], SHA)
        self.assertEqual(request["requestedBy"], "MostDef2000")

    def test_rejects_unauthorized_actor(self) -> None:
        event = self.event()
        event["sender"] = {"login": "intruder"}
        event["comment"] = {"body": f"DEPLOY VPS {SHA}", "user": {"login": "intruder"}}
        with self.assertRaises(self.module.DeploymentRequestError):
            self.module.parse_event(event, self.policy)

    def test_rejects_pull_request_comment(self) -> None:
        event = self.event()
        event["issue"] = {"number": 178, "state": "open", "pull_request": {"url": "https://example.invalid/pr"}}
        with self.assertRaises(self.module.DeploymentRequestError):
            self.module.parse_event(event, self.policy)

    def test_rejects_closed_issue(self) -> None:
        event = self.event()
        event["issue"] = {"number": 178, "state": "closed"}
        with self.assertRaises(self.module.DeploymentRequestError):
            self.module.parse_event(event, self.policy)

    def test_rejects_uppercase_or_short_sha(self) -> None:
        for body in (
            f"DEPLOY VPS {SHA.upper()}",
            "DEPLOY VPS 01234567",
        ):
            with self.subTest(body=body):
                with self.assertRaises(self.module.DeploymentRequestError):
                    self.module.parse_event(self.event(body), self.policy)

    def test_rejects_extra_text_or_lines(self) -> None:
        for body in (
            f"DEPLOY VPS {SHA}\nplease",
            f" DEPLOY VPS {SHA}",
            f"DEPLOY VPS {SHA} ",
            f"please DEPLOY VPS {SHA}",
        ):
            with self.subTest(body=body):
                with self.assertRaises(self.module.DeploymentRequestError):
                    self.module.parse_event(self.event(body), self.policy)

    def test_rejects_non_created_or_actor_mismatch(self) -> None:
        event = self.event()
        event["action"] = "edited"
        with self.assertRaises(self.module.DeploymentRequestError):
            self.module.parse_event(event, self.policy)

        event = self.event()
        event["sender"] = {"login": "MostDef2000"}
        event["comment"] = {"body": f"DEPLOY VPS {SHA}", "user": {"login": "different"}}
        with self.assertRaises(self.module.DeploymentRequestError):
            self.module.parse_event(event, self.policy)


if __name__ == "__main__":
    unittest.main()
