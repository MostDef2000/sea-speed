"""Production admission decision regression (issue #580, audit #534 P2-06).

Pins the end-to-end admission decision of
``scripts/release/evaluate_production_policy.py`` — the real ``evaluate()``
and the real ``main()`` — against a REAL temporary Git repository whose
``--no-ff`` merge commit is the exact source identity the evaluator diffs
(``exact_changed_files``, evaluate_production_policy.py:59-70). Only the
``github_json`` transport is mocked, with exact expected API URLs and no
network or credentials; the production policy, change-control policy,
delegation shape and decision integrity all come from the real repository
contracts under ``data/contracts/``.

Production-observed behavior pinned here: a docs/tests-only merged change
is admitted only when the canonical Issue carries the Outcome Contract
(#590 2026-11-01, #582 2026-11-02), and mutable PR runtime metadata can
never override the exact source-derived contours
(evaluate_production_policy.py:107-140).
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "scripts" / "release"
EVALUATOR_PATH = RELEASE_DIR / "evaluate_production_policy.py"
POLICY_MODULE_PATH = RELEASE_DIR / "production_policy.py"
PRODUCTION_POLICY_PATH = ROOT / "data/contracts/production-autonomy-policy-v1.json"
CHANGE_POLICY_PATH = ROOT / "data/contracts/change-control-policy-v1.json"

# Capture the import side-effect state BEFORE loading the evaluator: its
# module-level import inserts scripts/release into sys.path and registers
# production_policy in sys.modules (evaluate_production_policy.py:16-19).
_PRELOAD_SYS_PATH = list(sys.path)
_PRELOAD_HAD_POLICY_MODULE = "production_policy" in sys.modules

spec = importlib.util.spec_from_file_location("evaluate_production_policy", EVALUATOR_PATH)
assert spec and spec.loader
EVALUATOR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVALUATOR)

policy_spec = importlib.util.spec_from_file_location("production_policy_580", POLICY_MODULE_PATH)
assert policy_spec and policy_spec.loader
POLICY_MODULE = importlib.util.module_from_spec(policy_spec)
policy_spec.loader.exec_module(POLICY_MODULE)

REAL_POLICY = json.loads(PRODUCTION_POLICY_PATH.read_text(encoding="utf-8"))
CHANGE_POLICY = json.loads(CHANGE_POLICY_PATH.read_text(encoding="utf-8"))

REPOSITORY = "MostDef2000/sea-speed"
FAKE_TOKEN = "test-token-580"
CANONICAL_ISSUE = 580
PULL_REQUEST = 590
GIT_ENV_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")

DOCS_CHANGED_FILES = [
    "docs/quality/testing-policy.md",
    "tests/test_release_admission_regression.py",
]
DOCS_FIXTURE_FILES = {
    "docs/quality/testing-policy.md": "Testing policy baseline.\n",
    "tests/test_release_admission_regression.py": "Regression pin.\n",
}
API_CHANGED_FILES = ["api/app/main.py"]
API_FIXTURE_FILES = {"api/app/main.py": "API app entry.\n"}


def pr_body(changed_files: list[str], *, production_impact: str, vps_deployment: str,
            ubuntu_update: str, vps_capability: str, ubuntu_capability: str) -> str:
    """A PR body matching the evaluator's exact Change Contract regexes.

    ``- Issue:`` (ISSUE_FIELD_RE, evaluate_production_policy.py:21), the
    ``## Change`` section with ``- Changed files:`` two-space-indented
    backtick paths (DECLARED_PATH_RE, :23) and the ``- Out of scope:``
    boundary (:49-52), plus the five mandatory runtime fields
    (validate_pr_runtime_metadata, :112-115).
    """
    paths = "\n".join(f"  - `{path}`" for path in changed_files)
    return (
        f"- Issue: #{CANONICAL_ISSUE}\n"
        "\n"
        "## Change\n"
        "\n"
        "Merged release change under exact admission evaluation.\n"
        "\n"
        f"- Production impact: {production_impact}\n"
        f"- VPS deployment: {vps_deployment}\n"
        f"- Ubuntu worker/relay update: {ubuntu_update}\n"
        f"- VPS execution capability: {vps_capability}\n"
        f"- Ubuntu worker execution capability: {ubuntu_capability}\n"
        "\n"
        "- Changed files:\n"
        f"{paths}\n"
        "- Out of scope:\n"
        "  - production code changes\n"
    )


DOCS_PR_BODY = pr_body(
    DOCS_CHANGED_FILES,
    production_impact="NONE",
    vps_deployment="NOT REQUIRED",
    ubuntu_update="NOT REQUIRED",
    vps_capability="NOT APPLICABLE",
    ubuntu_capability="NOT APPLICABLE",
)
# The declared changed file is exact (changed-file equality passes) but the
# mutable runtime metadata still claims NONE contours for a VPS-impacting
# source diff — the mismatch validate_pr_runtime_metadata must reject.
API_PR_BODY = pr_body(
    API_CHANGED_FILES,
    production_impact="NONE",
    vps_deployment="NOT REQUIRED",
    ubuntu_update="NOT REQUIRED",
    vps_capability="NOT APPLICABLE",
    ubuntu_capability="NOT APPLICABLE",
)

OUTCOME_CONTRACT_TEXT = (
    "- Docs and tests only; no production code change.\n"
    "- The admission decision is pinned end to end by a regression test."
)
ISSUE_BODY_WITH_CONTRACT = (
    "# Sea Speed canonical task #580\n"
    "\n"
    "## Canonical task\n"
    "Pin the production admission decision for docs/tests-only release changes.\n"
    "\n"
    "## Outcome Contract\n"
    + OUTCOME_CONTRACT_TEXT + "\n"
)
ISSUE_BODY_WITHOUT_CONTRACT = (
    "# Sea Speed canonical task #580\n"
    "\n"
    "## Canonical task\n"
    "Pin the production admission decision for docs/tests-only release changes.\n"
    "\n"
    "## Delivery\n"
    "Merge to main and run the quality gate.\n"
)


def delegation_raw() -> str:
    """Standing delegation fixture shape (tests/test_production_policy.py:15-39)
    bound to the REAL repository production policy hash."""
    return json.dumps({
        "schema": "sea_speed_standing_production_delegation_v1",
        "delegationId": "prod-autonomy-v1",
        "principal": "sea-speed-delivery-orchestrator",
        "repository": REPOSITORY,
        "environment": "production",
        "permissions": ["deploy", "rollback"],
        "mode": "autonomous",
        "policyHash": POLICY_MODULE.policy_hash(REAL_POLICY),
        "enabled": True,
    })


@contextlib.contextmanager
def fixture_cwd(repo: Path):
    """Run inside the fixture repo with GIT_* env vars isolated and restored."""
    old_cwd = os.getcwd()
    saved = {name: os.environ.pop(name, None) for name in GIT_ENV_VARS}
    os.chdir(repo)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextlib.contextmanager
def main_env():
    """Isolate GITHUB_TOKEN and the delegation env var for a real main() run.

    The delegation is always passed via --delegation-json (or absent), so the
    environment-scoped variable is removed to keep the run deterministic
    (evaluate_production_policy.py:237-243).
    """
    saved_token = os.environ.pop("GITHUB_TOKEN", None)
    saved_delegation = os.environ.pop("SEA_SPEED_PRODUCTION_DELEGATION_V1", None)
    os.environ["GITHUB_TOKEN"] = FAKE_TOKEN
    try:
        yield
    finally:
        if saved_token is None:
            os.environ.pop("GITHUB_TOKEN", None)
        else:
            os.environ["GITHUB_TOKEN"] = saved_token
        if saved_delegation is None:
            os.environ.pop("SEA_SPEED_PRODUCTION_DELEGATION_V1", None)
        else:
            os.environ["SEA_SPEED_PRODUCTION_DELEGATION_V1"] = saved_delegation


class ReleaseAdmissionRegressionTests(unittest.TestCase):
    """End-to-end admission decision pins (issue #580, audit #534 P2-06)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(cls._restore_import_side_effects)

    @classmethod
    def _restore_import_side_effects(cls):
        """Restore sys.path/sys.modules to the state before this module loaded."""
        if not _PRELOAD_HAD_POLICY_MODULE:
            sys.modules.pop("production_policy", None)
        if str(RELEASE_DIR) not in _PRELOAD_SYS_PATH:
            sys.path[:] = [entry for entry in sys.path if entry != str(RELEASE_DIR)]

    # -- fixture construction -------------------------------------------------

    def _git(self, repo: Path, *args: str) -> str:
        env = {key: value for key, value in os.environ.items() if key not in GIT_ENV_VARS}
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _build_fixture_repo(self, feature_files: dict[str, str]) -> tuple[Path, Path, str]:
        """A real Git repo: baseline commit -> feature commit -> --no-ff merge.

        Returns (repo, tmp_root, merge_sha); the merge SHA is read from the
        real repo and is the exact identity the evaluator diffs.
        """
        tmp = tempfile.TemporaryDirectory(prefix="sea-speed-admission-580-")
        self.addCleanup(tmp.cleanup)
        tmp_root = Path(tmp.name)
        repo = tmp_root / "repo"
        repo.mkdir()
        self._git(repo, "init", "-b", "main")
        self._git(repo, "config", "user.name", "Sea Speed Admission Test")
        self._git(repo, "config", "user.email", "admission-test@example.invalid")
        self._git(repo, "config", "commit.gpgsign", "false")
        hooks_dir = tmp_root / "hooks-disabled"
        hooks_dir.mkdir()
        self._git(repo, "config", "core.hooksPath", str(hooks_dir))
        (repo / "README.md").write_text("Sea Speed admission fixture baseline.\n", encoding="utf-8")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-m", "baseline")
        self._git(repo, "checkout", "-b", "feature")
        for path, content in feature_files.items():
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-m", "feature change")
        self._git(repo, "checkout", "main")
        self._git(repo, "merge", "--no-ff", "feature", "-m", "Merge feature branch")
        merge_sha = self._git(repo, "rev-parse", "HEAD")
        self.assertRegex(merge_sha, r"^[0-9a-f]{40}$")
        return repo, tmp_root, merge_sha

    # -- transport and invocation helpers --------------------------------------

    def _fake_github_json(self, fixtures: dict[str, object]):
        def fake_github_json(url: str, token: str) -> object:
            self.assertEqual(token, FAKE_TOKEN)
            self.assertIn(url, fixtures, f"unexpected GitHub API URL: {url}")
            return fixtures[url]

        return fake_github_json

    def _api_fixtures(self, merge_sha: str, pr_body_text: str, issue_body: str) -> dict[str, object]:
        return {
            f"https://api.github.com/repos/{REPOSITORY}/commits/{merge_sha}/pulls": [
                {
                    "number": PULL_REQUEST,
                    "merged_at": "2026-11-01T12:00:00Z",
                    "merge_commit_sha": merge_sha,
                    "body": pr_body_text,
                }
            ],
            f"https://api.github.com/repos/{REPOSITORY}/issues/{CANONICAL_ISSUE}": {
                "number": CANONICAL_ISSUE,
                "body": issue_body,
            },
        }

    def _evaluate(self, repo: Path, merge_sha: str, fixtures: dict[str, object],
                  delegation: str | None) -> dict:
        with mock.patch.object(EVALUATOR, "github_json", side_effect=self._fake_github_json(fixtures)), \
                fixture_cwd(repo):
            return EVALUATOR.evaluate(
                repository=REPOSITORY,
                source_commit=merge_sha,
                token=FAKE_TOKEN,
                policy=REAL_POLICY,
                delegation_raw=delegation,
                action="deploy",
                environment="production",
                change_policy=CHANGE_POLICY,
                expected_issue=CANONICAL_ISSUE,
            )

    def _main_argv(self, repo: Path, merge_sha: str, *, delegation: str | None) -> list[str]:
        argv = [
            "evaluate_production_policy.py",
            "--repository", REPOSITORY,
            "--commit", merge_sha,
            "--issue", str(CANONICAL_ISSUE),
            "--action", "deploy",
            "--environment", "production",
            "--policy", str(PRODUCTION_POLICY_PATH),
            "--change-control-policy", str(CHANGE_POLICY_PATH),
            "--evidence-output", str(repo / "evidence.json"),
            "--github-output", str(repo / "github-output.txt"),
            "--require-allow",
        ]
        if delegation is not None:
            argv += ["--delegation-json", delegation]
        return argv

    def _run_main(self, repo: Path, root: Path, merge_sha: str, fixtures: dict[str, object],
                  *, delegation: str | None, capture_name: str) -> tuple[int, str]:
        """Run the real main() with isolated argv/env/CWD; return (exit_code, captured text)."""
        capture_path = root / capture_name
        stream = "stdout" if capture_name == "main-stdout.txt" else "stderr"
        with mock.patch.object(EVALUATOR, "github_json", side_effect=self._fake_github_json(fixtures)), \
                mock.patch.object(sys, "argv", self._main_argv(repo, merge_sha, delegation=delegation)), \
                main_env(), \
                fixture_cwd(repo), \
                capture_path.open("w", encoding="utf-8") as handle:
            old_stream = getattr(sys, stream)
            setattr(sys, stream, handle)
            try:
                exit_code = EVALUATOR.main()
            finally:
                setattr(sys, stream, old_stream)
        return exit_code, capture_path.read_text(encoding="utf-8")

    # -- required cases ---------------------------------------------------------

    def test_missing_outcome_contract_denies(self):
        # Production-observed: #590 (2026-11-01) and #582 (2026-11-02) — a
        # docs/tests-only merged change is denied when the canonical Issue
        # lacks the Outcome Contract heading (outcome_contract,
        # evaluate_production_policy.py:38-42).
        repo, _root, merge_sha = self._build_fixture_repo(DOCS_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, DOCS_PR_BODY, ISSUE_BODY_WITHOUT_CONTRACT)
        with self.assertRaises(EVALUATOR.PolicyError) as ctx:
            self._evaluate(repo, merge_sha, fixtures, delegation=delegation_raw())
        self.assertEqual(str(ctx.exception), "canonical Issue is missing Outcome Contract")

    def test_docs_only_change_admits_with_not_required(self):
        repo, _root, merge_sha = self._build_fixture_repo(DOCS_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, DOCS_PR_BODY, ISSUE_BODY_WITH_CONTRACT)
        decision = self._evaluate(repo, merge_sha, fixtures, delegation=delegation_raw())
        self.assertEqual(decision["decision"], "allow")
        self.assertEqual(decision["reason"], "standing_delegation_and_repository_policy_allow")
        self.assertEqual(
            decision["runtimeContours"],
            {"productionImpact": "NONE", "vps": "NOT REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"},
        )
        self.assertEqual(decision["approvedFiles"], sorted(DOCS_CHANGED_FILES))
        self.assertEqual(decision["sourceCommit"], merge_sha)
        self.assertEqual(decision["canonicalIssue"], CANONICAL_ISSUE)
        self.assertEqual(decision["pullRequest"], PULL_REQUEST)
        self.assertEqual(decision["delegationId"], "prod-autonomy-v1")
        self.assertEqual(decision["principal"], "sea-speed-delivery-orchestrator")
        self.assertEqual(decision["policyHash"], POLICY_MODULE.policy_hash(REAL_POLICY))
        self.assertEqual(
            decision["executionCapabilities"],
            {"vps": "NOT APPLICABLE", "ubuntuWorkerRelay": "NOT APPLICABLE"},
        )
        self.assertEqual(
            decision["outcomeContractHash"],
            hashlib.sha256(OUTCOME_CONTRACT_TEXT.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            decision["changeContractHash"],
            hashlib.sha256(DOCS_PR_BODY.encode("utf-8")).hexdigest(),
        )
        # Decision payload integrity: the decisionId binds the exact payload
        # (production_policy.py:184, 199-206) and the allow decision validates
        # with require_allow (production_policy.py:207-213).
        self.assertEqual(decision["schema"], "sea_speed_production_policy_decision_v1")
        payload = dict(decision)
        expected_id = payload.pop("decisionId")
        self.assertEqual(POLICY_MODULE.canonical_json_sha256(payload), expected_id)
        POLICY_MODULE.validate_decision(decision, require_allow=True)

    def test_declared_not_required_cannot_override_runtime_diff(self):
        # The merge contains api/app/main.py (VPS impact per the real
        # change-control policy) and the PR declares that exact path, so the
        # changed-file equality (evaluate_production_policy.py:167-173)
        # passes; the failure must come from the runtime metadata check
        # (validate_pr_runtime_metadata, :107-140).
        repo, _root, merge_sha = self._build_fixture_repo(API_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, API_PR_BODY, ISSUE_BODY_WITH_CONTRACT)
        with self.assertRaises(EVALUATOR.PolicyError) as ctx:
            self._evaluate(repo, merge_sha, fixtures, delegation=delegation_raw())
        message = str(ctx.exception)
        self.assertTrue(
            message.startswith("mutable PR runtime metadata does not match exact source-derived contours"),
            message,
        )
        self.assertIn(
            "derived={'productionImpact': 'VPS', 'vps': 'REQUIRED', 'ubuntuWorkerRelay': 'NOT REQUIRED'}",
            message,
        )

    def test_main_deny_exit_and_stderr(self):
        repo, root, merge_sha = self._build_fixture_repo(DOCS_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, DOCS_PR_BODY, ISSUE_BODY_WITHOUT_CONTRACT)
        exit_code, stderr_text = self._run_main(
            repo, root, merge_sha, fixtures,
            delegation=delegation_raw(), capture_name="main-stderr.txt",
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR: canonical Issue is missing Outcome Contract", stderr_text)
        # The deny path returns before any output is written
        # (evaluate_production_policy.py:260-262 precedes :264-279).
        self.assertFalse((repo / "evidence.json").exists())
        self.assertFalse((repo / "github-output.txt").exists())

    def test_main_allow_emits_decision(self):
        repo, root, merge_sha = self._build_fixture_repo(DOCS_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, DOCS_PR_BODY, ISSUE_BODY_WITH_CONTRACT)
        exit_code, stdout_text = self._run_main(
            repo, root, merge_sha, fixtures,
            delegation=delegation_raw(), capture_name="main-stdout.txt",
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("Production policy evaluated: decision=allow", stdout_text)
        self.assertIn(f"issue=#{CANONICAL_ISSUE} pr=#{PULL_REQUEST}", stdout_text)
        self.assertIn(f"commit={merge_sha}", stdout_text)
        # The --github-output mechanism (evaluate_production_policy.py:267-279)
        # emits key=value lines; assert against what it really writes.
        fields = dict(
            line.split("=", 1) for line in (repo / "github-output.txt").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(fields["allowed"], "true")
        self.assertEqual(fields["decision"], "allow")
        self.assertEqual(fields["reason"], "standing_delegation_and_repository_policy_allow")
        self.assertEqual(fields["vps_required"], "false")
        self.assertEqual(fields["ubuntu_worker_required"], "false")
        self.assertEqual(fields["canonical_issue"], str(CANONICAL_ISSUE))
        self.assertEqual(fields["pr_number"], str(PULL_REQUEST))
        self.assertEqual(fields["policy_hash"], POLICY_MODULE.policy_hash(REAL_POLICY))
        self.assertRegex(fields["policy_decision_id"], r"^[0-9a-f]{64}$")
        evidence = json.loads((repo / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["decision"], "allow")
        self.assertEqual(evidence["sourceCommit"], merge_sha)

    def test_missing_delegation_with_require_allow_fails(self):
        # Valid metadata and delegation-free environment: the typed deny
        # reason standing_delegation_missing (production_policy.py:137) must
        # surface through --require-allow (evaluate_production_policy.py:258-259)
        # — distinguishing a legitimate deny from authorization success.
        repo, root, merge_sha = self._build_fixture_repo(DOCS_FIXTURE_FILES)
        fixtures = self._api_fixtures(merge_sha, DOCS_PR_BODY, ISSUE_BODY_WITH_CONTRACT)
        exit_code, stderr_text = self._run_main(
            repo, root, merge_sha, fixtures,
            delegation=None, capture_name="main-stderr.txt",
        )
        self.assertEqual(exit_code, 1)
        self.assertIn(
            "ERROR: production policy denied execution: standing_delegation_missing",
            stderr_text,
        )


if __name__ == "__main__":
    unittest.main()
