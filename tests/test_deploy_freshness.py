"""Behavioral tests for the tree-aware freshness gate (issue #409).

These tests do not re-implement the freshness logic in Python. They extract the
`Require quality commit is current main tip` step's shell block from
`.github/workflows/deploy-runtime-autonomous.yml` at test time, write it to a
temporary script with `GITHUB_OUTPUT` redirected to a temporary file, and
execute it with bash inside a temporary git fixture repository. The workflow's
own commands (`git merge-base --is-ancestor`, the `:(glob,exclude)specs/*/tasks.md`
diff pathspec, and the sync bot's `:(glob)specs/*/tasks.md` staging pathspec)
are the single source of truth: the sync-bot file-set semantics are exercised
through git itself via the extracted pathspec only, never through a Python
copy of the bot regex.

By default the tests read the working-tree workflow files. For differential
runs (for example proving RED against the pre-fix workflow) the paths can be
overridden with:

- ``SEA_SPEED_DEPLOY_FRESHNESS_WORKFLOW`` — alternate deploy-runtime-autonomous.yml
- ``SEA_SPEED_SYNC_TASKS_WORKFLOW`` — alternate sync-merged-tasks.yml
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = Path(
    os.environ.get("SEA_SPEED_DEPLOY_FRESHNESS_WORKFLOW")
    or (ROOT / ".github/workflows/deploy-runtime-autonomous.yml")
)
SYNC_WORKFLOW = Path(
    os.environ.get("SEA_SPEED_SYNC_TASKS_WORKFLOW")
    or (ROOT / ".github/workflows/sync-merged-tasks.yml")
)
BOT_COMMIT_MESSAGE = "chore(sdd): auto-sync tasks.md completion on merge to main"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "freshness-fixture",
    "GIT_AUTHOR_EMAIL": "freshness-fixture@example.invalid",
    "GIT_COMMITTER_NAME": "freshness-fixture",
    "GIT_COMMITTER_EMAIL": "freshness-fixture@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _run_git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True,
        env={**os.environ, **GIT_ENV},
    )
    return result.stdout.strip()


def _extract_freshness_run_block(source: str) -> str:
    """Slice the freshness step's `run:` block between stable YAML anchors."""
    lines = source.splitlines()
    anchor = next((i for i, line in enumerate(lines) if line.strip() == "id: freshness"), None)
    if anchor is None:
        raise AssertionError("workflow YAML has no freshness step anchor 'id: freshness'")
    run_index = None
    for index in range(anchor, min(anchor + 8, len(lines))):
        if re.match(r"^\s*run:\s*\|\s*$", lines[index]):
            run_index = index
            break
    if run_index is None:
        raise AssertionError("freshness step has no 'run: |' block after 'id: freshness'")
    block: list[str] = []
    for line in lines[run_index + 1:]:
        if re.match(r"^      - name:", line):
            break
        block.append(line)
    while block and not block[-1].strip():
        block.pop()
    if not block:
        raise AssertionError("freshness run block is empty")
    indent = min(len(line) - len(line.lstrip(" ")) for line in block if line.strip())
    return "\n".join(line[indent:] if line.strip() else "" for line in block) + "\n"


def _read_github_output_text(output_file: str) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for line in output_file.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            outputs[key] = value
    return outputs


class FreshnessFixture:
    """Git fixture: quality commit A = {specs/001-x/tasks.md, api-file} plus scenario tips.

    Chain: R (root) -> A (quality commit) -> B (bot-only tasks.md tick) -> C (non-bot delta).
    The `quality` branch pins A so the work clone always carries its objects.
    Scenario tips are selected by repointing origin's `main` before the run.
    """

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.origin = base / "origin"
        self.work = base / "work"
        self.origin.mkdir()
        _run_git(self.origin, "init", "--initial-branch=main", ".")
        (self.origin / "specs" / "001-x").mkdir(parents=True)
        (self.origin / "specs" / "001-x" / "tasks.md").write_text("# Tasks 001\n", encoding="utf-8")
        self._commit("R: root")
        self.root_sha = self._rev("HEAD")
        (self.origin / "specs" / "001-x" / "tasks.md").write_text("# Tasks 001\n- [ ] T-1\n", encoding="utf-8")
        (self.origin / "api-file").write_text("api v1\n", encoding="utf-8")
        self._commit("A: quality-approved commit")
        self.quality_sha = self._rev("HEAD")
        # Nested-delta tip branches directly off A: its ONLY delta vs the
        # quality SHA is a new nested specs/001-x/sub/tasks.md file.
        _run_git(self.origin, "checkout", "-q", "-b", "nested")
        (self.origin / "specs" / "001-x" / "sub").mkdir(parents=True)
        (self.origin / "specs" / "001-x" / "sub" / "tasks.md").write_text("# nested tick\n", encoding="utf-8")
        self._commit("D: nested tasks.md delta (not bot-shaped)")
        self.nested_sha = self._rev("HEAD")
        _run_git(self.origin, "checkout", "-q", "main")
        (self.origin / "specs" / "001-x" / "tasks.md").write_text("# Tasks 001\n- [x] T-1\n", encoding="utf-8")
        self._commit(BOT_COMMIT_MESSAGE)
        self.bot_sha = self._rev("HEAD")
        (self.origin / "api-file").write_text("api v2\n", encoding="utf-8")
        self._commit("C: non-bot delta")
        self.nonbot_sha = self._rev("HEAD")
        _run_git(self.origin, "branch", "quality", self.quality_sha)
        subprocess.run(
            ["git", "clone", "--quiet", str(self.origin), str(self.work)], check=True,
            text=True, capture_output=True, env={**os.environ, **GIT_ENV},
        )

    def _rev(self, revision: str) -> str:
        return _run_git(self.origin, "rev-parse", revision)

    def _commit(self, message: str) -> None:
        _run_git(self.origin, "add", "-A")
        _run_git(self.origin, "commit", "-m", message)

    def point_main_at(self, tip: str) -> None:
        _run_git(self.origin, "update-ref", "refs/heads/main", tip)

    def run_freshness(self, deploy_sha: str) -> tuple[subprocess.CompletedProcess[str], str]:
        """Execute the extracted freshness block; return (process, GITHUB_OUTPUT text)."""
        block = _extract_freshness_run_block(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as scratch:
            script = Path(scratch) / "freshness.sh"
            script.write_text(block, encoding="utf-8")
            github_output = Path(scratch) / "github_output.txt"
            github_output.touch()
            result = subprocess.run(
                ["bash", str(script)], cwd=self.work, text=True, capture_output=True,
                env={**os.environ, **GIT_ENV, "DEPLOY_SHA": deploy_sha, "GITHUB_OUTPUT": str(github_output)},
            )
            output_file = github_output.read_text(encoding="utf-8")
        return result, output_file

    def cleanup(self) -> None:
        self._tmp.cleanup()


class FreshnessGateBehaviorTests(unittest.TestCase):
    """Scenario (a) is the #409 race; it must fail against the pre-fix workflow."""

    def setUp(self) -> None:
        self.fixture = FreshnessFixture()
        self.addCleanup(self.fixture.cleanup)

    def _run(self, deploy_sha: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str], str]:
        result, output_file = self.fixture.run_freshness(deploy_sha)
        self.assertEqual(result.returncode, 0, f"freshness step exited non-zero: {result.stderr}")
        outputs = _read_github_output_text(output_file)
        evidence = f"{result.stdout}{result.stderr}"
        return result, outputs, evidence

    def test_tasks_md_only_delta_after_quality_is_fresh_tree_modulo_tasks(self):
        self.fixture.point_main_at(self.fixture.bot_sha)
        _, outputs, evidence = self._run(self.fixture.quality_sha)
        self.assertEqual(outputs.get("fresh"), "true")
        self.assertEqual(outputs.get("fresh_basis"), "tree-modulo-tasks")
        self.assertEqual(outputs.get("current_main"), self.fixture.bot_sha)
        self.assertIn("descends from quality SHA", evidence)
        self.assertIn(self.fixture.quality_sha, evidence)
        self.assertIn("delta confined to specs/*/tasks.md", evidence)

    def test_non_bot_delta_keeps_fresh_false_with_stale_evidence(self):
        self.fixture.point_main_at(self.fixture.nonbot_sha)
        _, outputs, evidence = self._run(self.fixture.quality_sha)
        self.assertEqual(outputs.get("fresh"), "false")
        self.assertEqual(outputs.get("current_main"), self.fixture.nonbot_sha)
        self.assertIn("Ignoring stale successful Quality run", evidence)
        if "fresh_basis" in outputs:
            self.assertEqual(outputs["fresh_basis"], "stale")

    def test_non_descendant_tip_keeps_fresh_false(self):
        self.fixture.point_main_at(self.fixture.root_sha)
        _, outputs, evidence = self._run(self.fixture.quality_sha)
        self.assertEqual(outputs.get("fresh"), "false")
        self.assertIn("Ignoring stale successful Quality run", evidence)
        if "fresh_basis" in outputs:
            self.assertEqual(outputs["fresh_basis"], "stale")

    def test_nested_tasks_md_delta_is_not_bot_shaped(self):
        # Peer-review finding: in git's default fnmatch `*` crosses `/`, so a
        # non-glob `:(exclude)specs/*/tasks.md` would silently treat a nested
        # specs/NNN/sub/tasks.md delta as bot-shaped. The exclusion must use
        # `:(glob,exclude)` so only single-level specs/<feature>/tasks.md
        # deltas mirror the bot's staging pathspec.
        self.fixture.point_main_at(self.fixture.nested_sha)
        _, outputs, evidence = self._run(self.fixture.quality_sha)
        self.assertEqual(outputs.get("fresh"), "false")
        self.assertIn("Ignoring stale successful Quality run", evidence)
        if "fresh_basis" in outputs:
            self.assertEqual(outputs["fresh_basis"], "stale")

    def test_exact_tip_is_fresh(self):
        self.fixture.point_main_at(self.fixture.quality_sha)
        _, outputs, _ = self._run(self.fixture.quality_sha)
        self.assertEqual(outputs.get("fresh"), "true")
        self.assertEqual(outputs.get("current_main"), self.fixture.quality_sha)
        if "fresh_basis" in outputs:
            self.assertEqual(outputs["fresh_basis"], "tip")


def _extract_sync_staging_command(source: str) -> str:
    matches = re.findall(r"(?m)^\s*(git add\b.*)$", source)
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one git add staging command in sync workflow, got {matches!r}")
    return matches[0].strip()


class SyncBotStagingPathspecTests(unittest.TestCase):
    """The bot's staging pathspec itself must confine the index to tasks.md files.

    The bot file-set semantics anchor on the git pathspec executed here (the
    command extracted from the workflow), not on a Python copy of the bot
    regex, so the two cannot drift.
    """

    def test_staging_command_confines_index_to_feature_tasks_md(self):
        staging = _extract_sync_staging_command(SYNC_WORKFLOW.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch)
            _run_git(repo, "init", "--initial-branch=main", ".")
            (repo / "specs" / "001-x").mkdir(parents=True)
            (repo / "specs" / "001-x" / "tasks.md").write_text("# Tasks 001\n", encoding="utf-8")
            (repo / "specs" / "001-x" / "plan.md").write_text("# Plan 001\n", encoding="utf-8")
            (repo / "api-file").write_text("api v1\n", encoding="utf-8")
            _run_git(repo, "add", "-A")
            _run_git(repo, "commit", "-m", "base")
            # Dirty the tree: bot-shaped ticks plus files outside the bot file set.
            (repo / "specs" / "001-x" / "tasks.md").write_text("# Tasks 001\n- [x] T-1\n", encoding="utf-8")
            (repo / "specs" / "001-x" / "plan.md").write_text("# Plan 001 (edited)\n", encoding="utf-8")
            (repo / "api-file").write_text("api v2\n", encoding="utf-8")
            (repo / "specs" / "002-y").mkdir(parents=True)
            (repo / "specs" / "002-y" / "tasks.md").write_text("# Tasks 002\n- [x] T-2\n", encoding="utf-8")
            (repo / "specs" / "001-x" / "sub").mkdir(parents=True)
            (repo / "specs" / "001-x" / "sub" / "tasks.md").write_text("# nested\n", encoding="utf-8")
            staged = subprocess.run(
                staging, shell=True, cwd=repo, text=True, capture_output=True,
                env={**os.environ, **GIT_ENV},
            )
            self.assertEqual(staged.returncode, 0, staged.stderr)
            index = set(_run_git(repo, "diff", "--cached", "--name-only").splitlines())
            self.assertEqual(index, {"specs/001-x/tasks.md", "specs/002-y/tasks.md"})


if __name__ == "__main__":
    unittest.main()
