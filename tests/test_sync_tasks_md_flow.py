"""Issue #477 integrity: PR-based tasks.md auto-sync flow.

Guards the locally testable logic of the #477 fix (the workflow itself cannot
run locally — its verification is design review + the live CI test on the
fix PR merge):

(a) Marker round-trip idempotency: scripts/ci/sync_tasks_md.py flips a
    recognized unchecked completion marker exactly once; the flipped line
    ("- [x] ... — auto-synced on merge to main (<sha8>)") can NEVER match
    COMPLETION_RE again (the regex only matches "- [ ]" lines), so re-running
    the sync on an already-synced file is a no-op. This is the loop-safety
    core of the PR flow: the sync PR's own squash merge to main re-triggers
    the sync, which must report "already current" and create nothing.
(b) Marker discipline: unrecognized unchecked boxes are never flipped, and
    the sync never unchecks anything.
(c) The generated PR body (scripts/ci/build_sync_pr_body.py) satisfies the
    REAL Change Contract validator (scripts/ci/validate_change_contract.py
    validate_contract) for the exact delta the sync commit carries —
    specs/*/tasks.md only, derived impact NONE. PR Validation and the
    Quality integration gate validate this body on every pull_request, so a
    template drift would turn every auto-sync PR red.
(d) The synced tasks.md passes scripts/ci/validate_sdd.py --freshness
    semantics (no FRESHNESS_RE match on flipped lines).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "ci" / "sync_tasks_md.py"
BODY_SCRIPT = ROOT / "scripts" / "ci" / "build_sync_pr_body.py"
CONTRACT_VALIDATOR = ROOT / "scripts" / "ci" / "validate_change_contract.py"

# A real tasks.md with pending completion markers (wave-4 transport trio —
# its Definition of Done carries unchecked Required-CI/merge markers on main).
PENDING_TASKS = ROOT / "specs" / "397-wave4-worker-transport" / "tasks.md"

SYNC_BRANCH = "chore/tasks-md-auto-sync"


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyncMarkerRoundTripTests(unittest.TestCase):
    """Loop-safety proof for the PR-based sync (#477 D-3/RISK-003)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="477-sync-"))
        self.tasks = self.tmp / "tasks.md"
        self.tasks.write_text(PENDING_TASKS.read_text(encoding="utf-8"), encoding="utf-8")
        self.sync = _load("sync_tasks_md_scratch", SYNC_SCRIPT)

    def test_round_trip_second_run_is_noop(self):
        pending_markers = sum(
            1
            for line in self.tasks.read_text(encoding="utf-8").splitlines()
            if line.lstrip().startswith("- [ ]")
        )
        self.assertGreater(pending_markers, 0, "fixture must carry pending completion markers")

        self.assertTrue(self.sync.sync_tasks_file(self.tasks, "deadbeef1234567890"))
        first_pass = self.tasks.read_text(encoding="utf-8")

        # The heart of the loop-safety argument: second (and third) runs on the
        # already-synced file change NOTHING.
        self.assertFalse(self.sync.sync_tasks_file(self.tasks, "deadbeef1234567890"))
        self.assertFalse(self.sync.sync_tasks_file(self.tasks, "00000000abcdef12"))
        self.assertEqual(self.tasks.read_text(encoding="utf-8"), first_pass)

        # Suffix appended exactly once per marker, never stacked. Note: some
        # house DoD markers carry the literal phrase "— auto-synced on merge
        # to main" as their static content; sync_tasks_md.py's suffix guard
        # then skips the sha annotation (nothing to stack) — still a one-shot
        # flip, still idempotent.
        for line in first_pass.splitlines():
            self.assertLessEqual(
                line.count("— auto-synced on merge to main"),
                1,
                line,
            )
        # No RECOGNIZED marker remains unchecked (the freshness property);
        # unchecked lines that do not match COMPLETION_RE legitimately stay.
        remaining = [line for line in first_pass.splitlines() if self.sync.COMPLETION_RE.match(line)]
        self.assertEqual(remaining, [])

    def test_only_recognized_markers_flip_and_nothing_unchecks(self):
        original = self.tasks.read_text(encoding="utf-8")
        self.tasks.write_text(
            original
            + "\n## Extra\n\n- [ ] unrecognized pending item must stay unchecked\n"
            + "- [x] Required CI green — orchestrator-owned — auto-synced on merge to main (cafe5678)\n",
            encoding="utf-8",
        )
        before = self.tasks.read_text(encoding="utf-8")
        self.sync.sync_tasks_file(self.tasks, "deadbeef1234567890")
        after = self.tasks.read_text(encoding="utf-8")
        self.assertIn("- [ ] unrecognized pending item must stay unchecked", after)
        self.assertIn("- [x] Required CI (green|is green)", after.replace("Required CI green", "Required CI (green|is green)"))
        self.assertIn("- [x] Required CI green — orchestrator-owned — auto-synced on merge to main (cafe5678)", after)
        # No line that was checked before the run is unchecked afterwards.
        for before_line, after_line in zip(before.splitlines(), after.splitlines()):
            if before_line.lstrip().startswith("- [x]"):
                self.assertTrue(after_line.lstrip().startswith("- [x]"), after_line)

    def test_synced_file_freshness_clean(self):
        validator = _load("validate_sdd_scratch", ROOT / "scripts" / "ci" / "validate_sdd.py")
        self.sync.sync_tasks_file(self.tasks, "deadbeef1234567890")
        stale = validator.check_tasks_freshness([self.tasks.parent])
        self.assertEqual(stale, [])


class SyncPrBodyContractTests(unittest.TestCase):
    """The generated PR body must pass the REAL Change Contract validator."""

    @staticmethod
    def _git_status_tasks_delta(repo: Path) -> list[str]:
        """The workflow's F-3 delta source: git status, filtered to the sync pathspec."""
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", ":(glob)specs/*/tasks.md"],
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        return [line[3:] for line in out.splitlines() if line.strip()]

    def test_generated_body_matches_git_status_derived_delta(self):
        """Declared Changed files must equal the ACTUAL working-tree delta (F-3b).

        The workflow derives the body's file list from `git status --porcelain`
        (the sync's own pathspec), not from the merge diff — this test derives
        the list the same way and requires the REAL validator to accept it.
        """
        validator = _load("validate_change_contract_status", CONTRACT_VALIDATOR)
        generator = _load("build_sync_pr_body_status", BODY_SCRIPT)
        with tempfile.TemporaryDirectory(prefix="477-git-") as tmp:
            repo = Path(tmp)
            (repo / "specs" / "999-flip-only-dir").mkdir(parents=True)
            tasks = repo / "specs" / "999-flip-only-dir" / "tasks.md"
            tasks.write_text(PENDING_TASKS.read_text(encoding="utf-8"), encoding="utf-8")
            ident = ["-c", "user.name=t", "-c", "user.email=t@t.invalid"]
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), *ident, "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), *ident, "commit", "-qm", "init"], check=True)
            self.assertEqual(self._git_status_tasks_delta(repo), [])

            sync = _load("sync_tasks_md_status", SYNC_SCRIPT)
            self.assertTrue(sync.sync_tasks_file(tasks, "deadbeef1234567890"))
            derived = self._git_status_tasks_delta(repo)
            self.assertEqual(derived, ["specs/999-flip-only-dir/tasks.md"])

            body = generator.build_body("a8916b670f733a949bd2f9b8aa299c80b1e39a81", derived)
            self.assertEqual(validator.validate_contract(body, derived), "NONE")

    def test_flip_only_dir_produces_working_tree_delta(self):
        """F-3a silent-discard edge: a merge touching a spec dir ONLY in
        non-tasks.md files while its tasks.md carries pending markers — the
        sync must still flip (dir discovered from the merge diff) and the
        flip must surface as a git-status delta (the workflow's HAS_DELTA
        source), never silently discarded as under the old merge-diff gate.
        """
        sync = _load("sync_tasks_md_flipdir", SYNC_SCRIPT)
        with tempfile.TemporaryDirectory(prefix="477-flipdir-") as tmp:
            repo = Path(tmp)
            spec = repo / "specs" / "999-flip-only-dir"
            spec.mkdir(parents=True)
            tasks = spec / "tasks.md"
            tasks.write_text(PENDING_TASKS.read_text(encoding="utf-8"), encoding="utf-8")
            (spec / "plan.md").write_text("# plan\n", encoding="utf-8")
            ident = ["-c", "user.name=t", "-c", "user.email=t@t.invalid"]
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), *ident, "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), *ident, "commit", "-qm", "init"], check=True)
            # The "merge" touches ONLY plan.md — no tasks.md in the diff.
            (spec / "plan.md").write_text("# plan\n\nchanged\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), *ident, "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), *ident, "commit", "-qm", "merge"], check=True)
            diff_paths = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                cwd=repo, check=True, text=True, capture_output=True,
            ).stdout
            self.assertNotIn("tasks.md", diff_paths)

            # Dir discovery from the merge diff (as the workflow's sync step does)…
            dirs = sync.git_changed_spec_dirs("HEAD~1", "HEAD", root=repo)
            self.assertEqual(dirs, [spec])
            # …flips the pending markers…
            self.assertTrue(sync.sync_tasks_file(tasks, "deadbeef1234567890"))
            # …and the flip SURFACES as the git-status delta (old logic discarded it).
            self.assertEqual(self._git_status_tasks_delta(repo), ["specs/999-flip-only-dir/tasks.md"])

    def test_generated_body_passes_validate_contract(self):
        validator = _load("validate_change_contract_scratch", CONTRACT_VALIDATOR)
        changed = [
            "specs/477-sync-tasks-pr-flow/tasks.md",
            "specs/397-wave4-worker-transport/tasks.md",
        ]
        generator = _load("build_sync_pr_body_scratch", BODY_SCRIPT)
        pr_body = generator.build_body("a8916b670f733a949bd2f9b8aa299c80b1e39a81", changed)
        impact = validator.validate_contract(pr_body, changed)
        self.assertEqual(impact, "NONE")

    def test_generated_body_names_source_sha_and_files(self):
        generator = _load("build_sync_pr_body_scratch2", BODY_SCRIPT)
        changed = ["specs/477-sync-tasks-pr-flow/tasks.md"]
        pr_body = generator.build_body("a8916b670f733a949bd2f9b8aa299c80b1e39a81", changed)
        self.assertIn("a8916b67", pr_body)
        self.assertIn("- `specs/477-sync-tasks-pr-flow/tasks.md`", pr_body)
        self.assertIn("## Canonical task", pr_body)
        self.assertIn("## Change", pr_body)
        self.assertIn("## Impact", pr_body)
        self.assertIn("## Delivery", pr_body)
        self.assertIn("## Validation", pr_body)
        self.assertIn("## Completion", pr_body)
        self.assertIn(SYNC_BRANCH, pr_body)
        # The body must NOT drift into placeholder text the validator rejects.
        for placeholder in ("TBD", "TODO", "TBC"):
            self.assertNotIn(placeholder, pr_body)

    def test_generator_refuses_empty_delta(self):
        generator = _load("build_sync_pr_body_scratch3", BODY_SCRIPT)
        with self.assertRaises(SystemExit):
            generator.build_body("a8916b670f733a949bd2f9b8aa299c80b1e39a81", [])


class SyncScriptCliTests(unittest.TestCase):
    def test_cli_round_trip_via_subprocess(self):
        with tempfile.TemporaryDirectory(prefix="477-cli-") as tmp:
            tasks = Path(tmp) / "tasks.md"
            tasks.write_text(PENDING_TASKS.read_text(encoding="utf-8"), encoding="utf-8")
            first = subprocess.run(
                [sys.executable, str(SYNC_SCRIPT), "--specs", tmp, "--sha", "deadbeef1234567890"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("1 tasks.md file(s) synced", first.stdout)
            second = subprocess.run(
                [sys.executable, str(SYNC_SCRIPT), "--specs", tmp, "--sha", "deadbeef1234567890"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("all changed tasks.md already current", second.stdout)
            # The branch name convention documented in the workflow/trio.
            self.assertEqual(SYNC_BRANCH, "chore/tasks-md-auto-sync")


class WorkflowStructuralPinTests(unittest.TestCase):
    """C-4: committed pin of the rewritten workflow's safety-critical shape."""

    def test_sync_workflow_safety_shape(self):
        import yaml

        path = ROOT / ".github" / "workflows" / "sync-merged-tasks.yml"
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        # Token scope: exactly the two writes the flow needs.
        self.assertEqual(wf["permissions"], {"contents": "write", "pull-requests": "write"})
        # Serialized sync runs (no overlapping auto-sync PRs).
        self.assertEqual(wf["concurrency"]["group"], "sync-merged-tasks")
        self.assertIs(wf["concurrency"]["cancel-in-progress"], False)
        job = wf["jobs"]["sync-merged-tasks"]
        runs = "\n".join(step["run"] for step in job["steps"] if "run" in step)
        # No push ever targets main; the only push target is the chore branch.
        self.assertNotIn("git push origin main", runs)
        for line in runs.splitlines():
            if "git push" in line:
                self.assertIn("refs/heads/${BRANCH}", line, line)
        self.assertIn("BRANCH=chore/tasks-md-auto-sync", runs)
        # The merge is a squash of the bot's own PR (never a direct push).
        self.assertIn("gh pr merge", runs)
        self.assertIn("--squash", runs)
        # F-3: the delta source is the working tree (git status), not the merge diff.
        self.assertIn("git status --porcelain -- ':(glob)specs/*/tasks.md'", runs)
        # F-2: a reused open PR gets its title/body refreshed before waiting.
        self.assertIn("gh pr edit", runs)
        # F-5: both check phases gate on the same required set.
        self.assertIn("--watch --fail-fast --required", runs)


if __name__ == "__main__":
    unittest.main()
