from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release/parse_runtime_execution_request.py"
VERIFY_MODULE_PATH = ROOT / "scripts/release/verify_production_authorization.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


module = load_module("parse_runtime_execution_request", MODULE_PATH)
verifier = load_module("verify_production_authorization_execution_intent", VERIFY_MODULE_PATH)

SHA = "a" * 40
FP = "b" * 64
AUTH_LINE = f"PRODUCTION APPROVED {SHA}"
FP_LINE = f"Authorization-Fingerprint: {FP}"


def policy_file(directory: Path, actors: list[str] | None = None) -> Path:
    path = directory / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "sea-speed-production-authorization-policy/v1",
                "authorizedActors": actors or ["MostDef2000"],
            }
        ),
        encoding="utf-8",
    )
    return path


def event(body: str, *, actor: str = "MostDef2000", state: str = "open", action: str = "created", pr: bool = False) -> dict:
    issue: dict[str, object] = {"number": 178, "state": state}
    if pr:
        issue["pull_request"] = {"url": "https://example.invalid/pr"}
    return {
        "action": action,
        "issue": issue,
        "comment": {"body": body, "user": {"login": actor}},
        "sender": {"login": actor},
    }


def request_body() -> str:
    return f"{AUTH_LINE}\n{FP_LINE}\nExecution-Intent: EXECUTE"


class RuntimeExecutionRequestTests(unittest.TestCase):
    def test_exact_three_line_request_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = module.parse_event(event(request_body()), policy_file(Path(temp_dir)))
        self.assertEqual(parsed["canonicalIssue"], 178)
        self.assertEqual(parsed["commitSha"], SHA)
        self.assertEqual(parsed["authorizationFingerprint"], FP)
        self.assertEqual(parsed["executionIntent"], "EXECUTE")

    def test_authorize_only_comment_is_not_execution(self) -> None:
        body = f"{AUTH_LINE}\n{FP_LINE}"
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(module.RuntimeExecutionRequestError, "three"):
                module.parse_event(event(body), policy_file(Path(temp_dir)))

    def test_malformed_intent_fingerprint_or_sha_fail_closed(self) -> None:
        cases = {
            "intent": request_body().replace("EXECUTE", "YES"),
            "fingerprint": request_body().replace(FP, "B" * 64),
            "sha": request_body().replace(SHA, "A" * 40),
            "extra": request_body() + "\nEXTRA",
            "whitespace": " " + request_body(),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = policy_file(Path(temp_dir))
            for name, body in cases.items():
                with self.subTest(name=name):
                    with self.assertRaises(module.RuntimeExecutionRequestError):
                        module.parse_event(event(body), policy)

    def test_event_and_actor_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = policy_file(Path(temp_dir))
            bad_events = (
                event(request_body(), action="edited"),
                event(request_body(), state="closed"),
                event(request_body(), pr=True),
                event(request_body(), actor="intruder"),
            )
            for item in bad_events:
                with self.assertRaises(module.RuntimeExecutionRequestError):
                    module.parse_event(item, policy)

    def test_sender_and_comment_actor_must_match(self) -> None:
        item = event(request_body())
        item["sender"] = {"login": "MostDef2000"}
        item["comment"] = {"body": request_body(), "user": {"login": "other"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(module.RuntimeExecutionRequestError, "inconsistent"):
                module.parse_event(item, policy_file(Path(temp_dir)))

    def test_authorization_verifier_keeps_two_line_approval_authorize_only(self) -> None:
        authorized, execute = verifier._authorization_comment_state(
            f"{AUTH_LINE}\n{FP_LINE}", AUTH_LINE, FP_LINE
        )
        self.assertTrue(authorized)
        self.assertFalse(execute)

    def test_authorization_verifier_detects_only_exact_third_line_execution_intent(self) -> None:
        authorized, execute = verifier._authorization_comment_state(request_body(), AUTH_LINE, FP_LINE)
        self.assertTrue(authorized)
        self.assertTrue(execute)

        authorized_extra, execute_extra = verifier._authorization_comment_state(
            request_body() + "\nEXTRA", AUTH_LINE, FP_LINE
        )
        self.assertTrue(authorized_extra)
        self.assertFalse(execute_extra)

    def test_authorization_verifier_rejects_wrong_fingerprint_line(self) -> None:
        authorized, execute = verifier._authorization_comment_state(
            f"{AUTH_LINE}\nAuthorization-Fingerprint: {'c' * 64}\nExecution-Intent: EXECUTE",
            AUTH_LINE,
            FP_LINE,
        )
        self.assertFalse(authorized)
        self.assertFalse(execute)


if __name__ == "__main__":
    unittest.main()
