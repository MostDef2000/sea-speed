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
(e) Issue #595: the ACTUAL lookup/reuse/create shell suffix of the
    "Push sync branch and create or reuse the auto-sync PR" step is
    extracted from the committed workflow and executed verbatim by bash
    against a deterministic fake gh that reproduces GitHub's head-filter
    semantics (owner:branch) and the duplicate-create 422. The old
    head=${GH_REPO}:${BRANCH} filter (owner/repo:branch) matches nothing,
    so the open auto-sync PR was never detected and the flow died on the
    duplicate-create 422.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "ci" / "sync_tasks_md.py"
BODY_SCRIPT = ROOT / "scripts" / "ci" / "build_sync_pr_body.py"
CONTRACT_VALIDATOR = ROOT / "scripts" / "ci" / "validate_change_contract.py"

# Synthetic fixture carrying pending completion markers. Deliberately NOT
# read from any live spec file (#477 RF-013): the loop-safety proof must be
# independent of repository state. Reading a real spec file here made every
# successful autonomous flip redden these tests — the flip lands on main,
# the fixture stops matching COMPLETION_RE, and the next sync PR fails CI.
PENDING_TASKS_TEXT = """\
# Tasks — synthetic sync trio

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
"""

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
        self.tasks.write_text(PENDING_TASKS_TEXT, encoding="utf-8")
        self.sync = _load("sync_tasks_md_scratch", SYNC_SCRIPT)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

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
            tasks.write_text(PENDING_TASKS_TEXT, encoding="utf-8")
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
            tasks.write_text(PENDING_TASKS_TEXT, encoding="utf-8")
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
            tasks.write_text(PENDING_TASKS_TEXT, encoding="utf-8")
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
        # Token scope: exactly the writes the flow needs (actions: write is
        # required by gh workflow run — the only way to produce the ruleset's
        # required check runs on a GITHUB_TOKEN-created PR, see RF-006).
        self.assertEqual(
            wf["permissions"],
            {"contents": "write", "pull-requests": "write", "actions": "write"},
        )
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
        # RF-014 (live): the refresh must be REST (gh api PATCH) — `gh pr edit`
        # is GraphQL and demands read:org, which the SYNC_PR_TOKEN classic PAT
        # (public_repo) lacks.
        self.assertIn('gh api -X PATCH "repos/${GH_REPO}/pulls/${number}"', runs)
        self.assertNotIn("gh pr edit", runs)
        # #558 (live, run 40281552508): PR creation must be REST too — the CLI
        # create path is GraphQL-backed and dies with "HTTP 401: Bad
        # credentials" on the same public_repo-only classic PAT. Only the
        # REST POST /repos/${GH_REPO}/pulls form may appear.
        self.assertIn('gh api -X POST "repos/${GH_REPO}/pulls"', runs)
        self.assertNotIn("gh pr create", runs)
        # #558 (live, run on merge 88e54f2): the reuse CHECK must be REST too —
        # the CLI list path is GraphQL-backed and dies on the same classic PAT
        # right after the branch push.
        self.assertIn('gh api "repos/${GH_REPO}/pulls?head=${GH_REPO%%/*}:${BRANCH}&base=main&state=open"', runs)
        self.assertNotIn("gh pr list", runs)
        # RF-006 (live): GITHUB_TOKEN-created PRs emit no pull_request events, so
        # the flow must dispatch the two required-check workflows on the sync
        # branch itself; both dispatched names are pinned (no arbitrary dispatch).
        self.assertIn('gh workflow run pr-validation.yml --ref "${BRANCH}"', runs)
        self.assertIn('gh workflow run quality-integration.yml --ref "${BRANCH}"', runs)
        # #604: the parked-run approval is NARROW — only runs on the expected
        # head/ref/repository with the intended PR association and a fixed
        # workflow allowlist (incl. Security) are approved, revalidated before
        # each POST. The old broad "approve every parked run on the branch"
        # (RF-020) is obsolete. Identity guards: the flow validates the bot
        # author and the expected local head before any approval or merge.
        self.assertIn("github-actions[bot]", runs)
        self.assertIn("rev-parse HEAD", runs)
        # RF-018 (live, run 38576674559): the ref update must be a git push
        # carrying the PAT credential in the URL — a REST ref PATCH/POST
        # cannot upload the locally created commit (422 "Object does not
        # exist"), and a plain `git push` uses the checkout's GITHUB_TOKEN,
        # whose bot actor parks the PR's pull_request runs (RF-015). The
        # PAT-URL push uploads the objects AND keeps the synchronize actor
        # a human collaborator.
        # #558 (live, sync run on merge cc25cbd): the PAT 401s on gh api REST
        # too (Bad credentials) even though the same value authenticates the
        # git push — so the PAT is pinned to the PUSH ONLY (SYNC_PUSH_TOKEN)
        # and every REST call in the step uses the workflow token; bot
        # authorship is safe because the flow dispatches the required-check
        # workflows itself (RF-006).
        self.assertIn('git push --force "https://x-access-token:${SYNC_PUSH_TOKEN}@github.com/${GH_REPO}.git"', runs)
        # #558 (live, sync run on merge cc25cbd): the PAT cannot serve gh api
        # REST (401 Bad credentials) while the same value authenticates the
        # git push — the env block pins SYNC_PUSH_TOKEN (PAT) to the push and
        # GH_TOKEN (workflow token) to every REST call in the step. Twin reads
        # the env wiring from the PARSED step (issue #398 wave 5): the step
        # that carries the PAT-URL push must carry both tokens itself, so a
        # comment or an env block on an unrelated step cannot satisfy the pin.
        push_step = next(
            step
            for step in job["steps"]
            if 'git push --force "https://x-access-token:${SYNC_PUSH_TOKEN}@github.com/${GH_REPO}.git"' in (step.get("run") or "")
        )
        step_env = push_step["env"]
        self.assertEqual(step_env["GH_TOKEN"], "${{ github.token }}")
        self.assertEqual(step_env["SYNC_PUSH_TOKEN"], "${{ secrets.SYNC_PR_TOKEN || github.token }}")
        self.assertIn('"HEAD:refs/heads/${BRANCH}"', runs)
        self.assertNotIn("git/refs/heads/", runs)  # REST ref update cannot transfer objects (RF-018)
        self.assertNotIn("git push origin", runs)  # checkout-credential push = bot actor (RF-015)
        # RF-019 (live, run 38590991898): a transient GitHub 5xx rejected the
        # PAT-URL push ("remote rejected ... Internal Server Error") and killed
        # the whole sync run — the push is retried with bounded backoff (3
        # attempts, 10s-multiples) before the run fails.
        self.assertIn('for attempt in 1 2 3', runs)
        self.assertIn('if git push --force "https://x-access-token:${SYNC_PUSH_TOKEN}@github.com/${GH_REPO}.git" "HEAD:refs/heads/${BRANCH}"; then', runs)
        self.assertIn('exit 1', runs)
        # #604: the poll must NOT select by workflow name + max run_number
        # (the old name-max selection could observe a stale run's conclusion);
        # it polls the exact dispatched run IDs until completed-success.
        self.assertNotIn("max_by(.run_number)", runs)
        # The merge must pin the expected head so a drift between the validated
        # head and the merged head cannot slip through.
        self.assertIn("--match-head-commit", runs)
        # Final gate consistent with the ruleset: required contexts green on
        # the head SHA, read as structured JSON (not a text grep).
        self.assertIn('gh pr checks "${PR_NUMBER}" --required', runs)
        self.assertIn("--json", runs)


# ---------------------------------------------------------------------------
# Issue #595: the auto-sync PR reuse lookup used head=${GH_REPO}:${BRANCH}
# (owner/repo:branch). GitHub's head filter is owner:branch, so the
# malformed filter matched nothing, the open auto-sync PR was never
# detected, and the flow died on the duplicate-create 422. The cases below
# execute the ACTUAL lookup/reuse/create shell suffix extracted from the
# committed workflow (the conditional is NOT reimplemented in Python)
# against a deterministic fake gh that reproduces GitHub's head-filter
# semantics and the duplicate-create 422.
# ---------------------------------------------------------------------------

FAKE_GH_SOURCE = r'''#!/__PYTHON__
"""Deterministic fake gh for the #595 sync-flow regression tests.

Logs every invocation as a JSON argument array to
$FAKE_GH_STATE_DIR/calls.log and serves ONLY the REST operations the sync
PR step may perform:

  GET   repos/FixtureOwner/fixture-repo/pulls?head=...&base=main&state=open
  PATCH repos/FixtureOwner/fixture-repo/pulls/<number>
  POST  repos/FixtureOwner/fixture-repo/pulls

The lookup reproduces GitHub's head-filter semantics: the filter is
"owner:branch"; a malformed owner (e.g. "owner/repo") matches nothing —
exactly the #595 root cause of the old ${GH_REPO}:${BRANCH} query. A POST
while an open PR already exists for the head branch returns the real
GitHub 422 duplicate-create error. Anything else is rejected.
"""
import json
import os
import sys
import urllib.parse

OWNER = "FixtureOwner"
REPO = "fixture-repo"
BRANCH = "chore/tasks-md-auto-sync"
BASE = "main"
PULLS = "repos/%s/%s/pulls" % (OWNER, REPO)


def die(msg, code=64):
    sys.stderr.write("fake-gh: %s\n" % msg)
    sys.exit(code)


def read_state(name):
    path = os.path.join(os.environ["FAKE_GH_STATE_DIR"], name)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def open_prs():
    return [line.strip() for line in read_state("open_prs.txt").splitlines() if line.strip()]


def main():
    if not os.environ.get("FAKE_GH_STATE_DIR"):
        die("FAKE_GH_STATE_DIR is not set")
    args = sys.argv[1:]
    with open(os.path.join(os.environ["FAKE_GH_STATE_DIR"], "calls.log"), "a", encoding="utf-8") as log:
        log.write(json.dumps(args) + "\n")

    if not args or args[0] != "api":
        die("unexpected gh call (only 'gh api' is served): %r" % (args,))

    method = "GET"
    endpoint = None
    fields = []
    jq = None
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in ("-X", "-f", "-F", "--jq"):
            i += 1
            if i >= len(args):
                die("dangling %s" % arg)
            if arg == "-X":
                method = args[i]
            elif arg == "--jq":
                jq = args[i]
            else:
                fields.append(args[i])
        elif arg.startswith("-"):
            die("unexpected flag: %s" % arg)
        elif endpoint is not None:
            die("unexpected positional argument: %s" % arg)
        else:
            endpoint = arg
        i += 1
    if endpoint is None:
        die("no endpoint given")

    path, _, query = endpoint.partition("?")
    params = dict(urllib.parse.parse_qsl(query))
    mode = read_state("mode").strip()

    if path == PULLS and method == "GET":
        if mode == "lookup-401":
            sys.stderr.write("HTTP 401: Bad credentials (fake-gh simulated)\n")
            sys.exit(1)
        if mode == "lookup-network-fail":
            sys.stderr.write(
                "GET https://api.github.com/%s: connection reset by peer (fake-gh simulated)\n" % PULLS
            )
            sys.exit(1)
        if params.get("base") != BASE or params.get("state") != "open":
            die("unexpected lookup query params: %r" % (params,))
        if jq != ".[0].number // empty":
            die("unexpected lookup --jq: %r" % (jq,))
        head = params.get("head", "")
        owner, sep, branch = head.partition(":")
        if not sep:
            owner = OWNER  # a bare branch name means the head is in the base repo
        if owner == OWNER and branch == BRANCH:
            prs = open_prs()
            if prs:
                sys.stdout.write(prs[0] + "\n")
        return

    if path.startswith(PULLS + "/") and method == "PATCH":
        number = path.rsplit("/", 1)[1]
        if number not in open_prs():
            die("PATCH on unknown or closed PR number: %s" % number)
        kv = dict(field.split("=", 1) for field in fields)
        if "title" not in kv or not kv.get("body", "").startswith("@"):
            die("unexpected PATCH fields: %r" % (fields,))
        body_file = kv["body"][1:]
        if not os.path.exists(body_file) or os.path.getsize(body_file) == 0:
            die("PATCH body file missing or empty: %s" % body_file)
        sys.stdout.write("{}\n")
        return

    if path == PULLS and method == "POST":
        kv = dict(field.split("=", 1) for field in fields)
        if kv.get("head") != BRANCH or kv.get("base") != BASE:
            die("unexpected POST fields: %r" % (fields,))
        if "title" not in kv or not kv.get("body", "").startswith("@"):
            die("unexpected POST fields: %r" % (fields,))
        body_file = kv["body"][1:]
        if not os.path.exists(body_file) or os.path.getsize(body_file) == 0:
            die("POST body file missing or empty: %s" % body_file)
        if jq != ".number":
            die("unexpected POST --jq: %r" % (jq,))
        if open_prs():
            sys.stderr.write(
                "HTTP 422: A pull request already exists for %s:%s (fake-gh simulated)\n" % (OWNER, BRANCH)
            )
            sys.exit(1)
        counter = read_state("next_number").strip()
        next_number = int(counter) if counter else 566
        with open(os.path.join(os.environ["FAKE_GH_STATE_DIR"], "next_number"), "w", encoding="utf-8") as handle:
            handle.write(str(next_number + 1))
        with open(os.path.join(os.environ["FAKE_GH_STATE_DIR"], "open_prs.txt"), "a", encoding="utf-8") as handle:
            handle.write(str(next_number) + "\n")
        sys.stdout.write(str(next_number) + "\n")
        return

    die("unexpected gh api call: method=%s endpoint=%s" % (method, endpoint))


main()
'''

FAKE_BIN_SENTINEL = r'''#!/__PYTHON__
import sys
sys.stderr.write("fake-bin sentinel: __NAME__ must not be used by the sync PR suffix\n")
sys.exit(99)
'''


class SyncPrLookupReuseCreateTests(unittest.TestCase):
    """#595: execute the REAL lookup/reuse/create suffix from the workflow.

    The suffix is extracted verbatim from the committed step (lookup
    assignment through the PR_NUMBER export) and run by bash under the
    step's own strict shell options, with a fixed synthetic
    GH_REPO/SOURCE_SHA/BRANCH/PR_BODY_FILE/GITHUB_ENV and an isolated PATH
    whose only executables are the fake gh and fail-on-use git/curl
    sentinels. No network, no credentials, no real git/PR mutation.
    """

    STEP_NAME = "Push sync branch and create or reuse the auto-sync PR"
    GH_REPO = "FixtureOwner/fixture-repo"
    SOURCE_SHA = "deadbeefcafe1234deadbeefcafe1234deadbeef"
    BRANCH = "chore/tasks-md-auto-sync"
    LOOKUP_URL = (
        "repos/FixtureOwner/fixture-repo/pulls"
        "?head=FixtureOwner:chore/tasks-md-auto-sync&base=main&state=open"
    )

    def _load_step_script(self):
        """Parse the committed workflow, locate the real named step uniquely,
        and return the ACTUAL shell suffix — from the lookup assignment
        `number="$(gh api ...` through the exact
        `echo "PR_NUMBER=${number}" >> "${GITHUB_ENV}"` — under the step's
        own strict shell options. The conditional is NOT reimplemented in
        Python; the extracted source is executed verbatim by bash."""
        import yaml

        path = ROOT / ".github" / "workflows" / "sync-merged-tasks.yml"
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        job = wf["jobs"]["sync-merged-tasks"]
        steps = [s for s in job["steps"] if s.get("name") == self.STEP_NAME]
        self.assertEqual(len(steps), 1, "the sync PR step must be unique by name")
        lines = steps[0]["run"].splitlines()
        strict = lines[0].strip()
        self.assertEqual(strict, "set -euo pipefail", "the step must keep its strict shell options")
        starts = [
            i
            for i, line in enumerate(lines)
            if line.strip().startswith('number="$(gh api') and "pulls?head=" in line
        ]
        ends = [
            i
            for i, line in enumerate(lines)
            if line.strip() == 'echo "PR_NUMBER=${number}" >> "${GITHUB_ENV}"'
        ]
        self.assertEqual(len(starts), 1, "the lookup assignment must be unique")
        self.assertEqual(len(ends), 1, "the PR_NUMBER export must be unique")
        self.assertLess(starts[0], ends[0])
        suffix = "\n".join(lines[starts[0]:ends[0] + 1])
        return strict + "\n" + suffix

    def _write_fake_bin(self, tmp):
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH_SOURCE.replace("__PYTHON__", sys.executable), encoding="utf-8")
        gh.chmod(0o755)
        for name in ("git", "curl"):
            sentinel = bin_dir / name
            sentinel.write_text(
                FAKE_BIN_SENTINEL.replace("__PYTHON__", sys.executable).replace("__NAME__", name),
                encoding="utf-8",
            )
            sentinel.chmod(0o755)
        return bin_dir

    def _make_state(self, tmp, mode="ok", open_prs=()):
        state = tmp / "state"
        state.mkdir()
        (state / "mode").write_text(mode + "\n", encoding="utf-8")
        (state / "open_prs.txt").write_text("".join(n + "\n" for n in open_prs), encoding="utf-8")
        return state

    def _run_suffix(self, script, tmp, state):
        env = {
            "PATH": str(tmp / "bin"),
            "GH_REPO": self.GH_REPO,
            "SOURCE_SHA": self.SOURCE_SHA,
            "BRANCH": self.BRANCH,
            "PR_BODY_FILE": str(tmp / "pr-body.md"),
            "GITHUB_ENV": str(tmp / "github_env"),
            "FAKE_GH_STATE_DIR": str(state),
            "LC_ALL": "C",
        }
        return subprocess.run(
            [shutil.which("bash"), "-c", script],
            capture_output=True,
            text=True,
            env=env,
        )

    @staticmethod
    def _calls(state):
        log = state / "calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _github_env(tmp):
        env_file = tmp / "github_env"
        return env_file.read_text(encoding="utf-8") if env_file.exists() else ""

    def _expected_title(self):
        return "chore(sdd): auto-sync tasks.md completion (%s)" % self.SOURCE_SHA[:8]

    def test_existing_open_pr_is_reused_via_patch_never_post(self):
        """Case 1: an open auto-sync PR #566 exists. The suffix must find it
        through the owner-only head filter and PATCH it — no POST — and
        export PR_NUMBER=566."""
        with tempfile.TemporaryDirectory(prefix="595-reuse-") as raw:
            tmp = Path(raw)
            (tmp / "pr-body.md").write_text("## Change\nsynthetic body\n", encoding="utf-8")
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, mode="ok", open_prs=("566",))
            result = self._run_suffix(self._load_step_script(), tmp, state)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self._calls(state)
            self.assertEqual(
                calls[0],
                ["api", self.LOOKUP_URL, "--jq", ".[0].number // empty"],
                "the evaluated lookup URL must use the owner-only head filter",
            )
            self.assertEqual(
                calls[1],
                [
                    "api", "-X", "PATCH", "repos/FixtureOwner/fixture-repo/pulls/566",
                    "-f", "title=" + self._expected_title(),
                    "-F", "body=@" + str(tmp / "pr-body.md"),
                ],
            )
            self.assertEqual(len(calls), 2, "lookup + PATCH only — no POST")
            self.assertIn("PR_NUMBER=566", self._github_env(tmp))

    def test_no_open_pr_creates_exactly_once_and_exports_number(self):
        """Case 2: a successful empty lookup must lead to exactly one POST
        (head branch / base main / title / body) and export the returned
        number."""
        with tempfile.TemporaryDirectory(prefix="595-create-") as raw:
            tmp = Path(raw)
            (tmp / "pr-body.md").write_text("## Change\nsynthetic body\n", encoding="utf-8")
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, mode="ok", open_prs=())
            result = self._run_suffix(self._load_step_script(), tmp, state)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self._calls(state)
            self.assertEqual(
                calls[0],
                ["api", self.LOOKUP_URL, "--jq", ".[0].number // empty"],
                "the evaluated lookup URL must use the owner-only head filter",
            )
            self.assertEqual(
                calls[1],
                [
                    "api", "-X", "POST", "repos/FixtureOwner/fixture-repo/pulls",
                    "-f", "head=chore/tasks-md-auto-sync", "-f", "base=main",
                    "-f", "title=" + self._expected_title(),
                    "-F", "body=@" + str(tmp / "pr-body.md"),
                    "--jq", ".number",
                ],
            )
            self.assertEqual(len(calls), 2, "lookup + one POST — no PATCH")
            self.assertIn("PR_NUMBER=566", self._github_env(tmp))

    def test_lookup_401_fails_closed_without_create_or_export(self):
        """Case 3: a 401 lookup must abort the step (fail-closed, no
        `|| true`) — lookup only, no POST/PATCH, no PR_NUMBER export."""
        with tempfile.TemporaryDirectory(prefix="595-401-") as raw:
            tmp = Path(raw)
            (tmp / "pr-body.md").write_text("## Change\nsynthetic body\n", encoding="utf-8")
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, mode="lookup-401", open_prs=("566",))
            result = self._run_suffix(self._load_step_script(), tmp, state)
            self.assertNotEqual(result.returncode, 0)
            calls = self._calls(state)
            self.assertEqual(len(calls), 1, "the lookup only — no POST/PATCH after a 401")
            self.assertEqual(calls[0][0], "api")
            self.assertIn("repos/FixtureOwner/fixture-repo/pulls?head=", calls[0][1])
            self.assertNotIn("PR_NUMBER=", self._github_env(tmp))

    def test_lookup_network_failure_fails_closed_without_create_or_export(self):
        """Case 4: a network failure on the lookup must abort the step the
        same way as a 401 — lookup only, no POST/PATCH, no export."""
        with tempfile.TemporaryDirectory(prefix="595-netfail-") as raw:
            tmp = Path(raw)
            (tmp / "pr-body.md").write_text("## Change\nsynthetic body\n", encoding="utf-8")
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, mode="lookup-network-fail", open_prs=("566",))
            result = self._run_suffix(self._load_step_script(), tmp, state)
            self.assertNotEqual(result.returncode, 0)
            calls = self._calls(state)
            self.assertEqual(len(calls), 1, "the lookup only — no POST/PATCH after a network failure")
            self.assertEqual(calls[0][0], "api")
            self.assertIn("repos/FixtureOwner/fixture-repo/pulls?head=", calls[0][1])
            self.assertNotIn("PR_NUMBER=", self._github_env(tmp))

    def test_repeated_invocation_reuses_created_pr_never_second_post(self):
        """Case 5: stateful fake — the first run (no open PR) creates the PR
        once; the second run must discover the same open PR and PATCH it,
        never a second POST. The fake reproduces GitHub's head-filter
        semantics, so the old owner/repo:branch filter finds nothing and
        the second run dies on the duplicate-create 422 (the #595 failure)."""
        with tempfile.TemporaryDirectory(prefix="595-repeat-") as raw:
            tmp = Path(raw)
            (tmp / "pr-body.md").write_text("## Change\nsynthetic body\n", encoding="utf-8")
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, mode="ok", open_prs=())
            script = self._load_step_script()
            first = self._run_suffix(script, tmp, state)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("PR_NUMBER=566", self._github_env(tmp))
            self.assertEqual(len(self._calls(state)), 2, "first run: lookup + one POST")
            (tmp / "github_env").write_text("", encoding="utf-8")
            second = self._run_suffix(script, tmp, state)
            self.assertEqual(second.returncode, 0, second.stderr)
            calls = self._calls(state)
            self.assertEqual(len(calls), 4, "second run: lookup + PATCH")
            self.assertEqual(
                calls[2],
                ["api", self.LOOKUP_URL, "--jq", ".[0].number // empty"],
                "the second run's lookup must use the owner-only head filter",
            )
            self.assertEqual(
                calls[3],
                [
                    "api", "-X", "PATCH", "repos/FixtureOwner/fixture-repo/pulls/566",
                    "-f", "title=" + self._expected_title(),
                    "-F", "body=@" + str(tmp / "pr-body.md"),
                ],
            )
            posts = [c for c in calls if len(c) > 2 and c[1] == "-X" and c[2] == "POST"]
            self.assertEqual(len(posts), 1, "the PR is created exactly once across both runs")
            self.assertIn("PR_NUMBER=566", self._github_env(tmp))


# ---------------------------------------------------------------------------
# Issue #604: the auto-sync flow's "Trigger and wait for the auto-sync PR
# required checks" step and the "Squash-merge the auto-sync PR" step are
# executed VERBATIM (the committed run blocks, under their own strict shell
# options) against a deterministic fake gh / git / date / sleep. The fake gh
# returns RAW REST JSON (the real /usr/bin/jq applies any --jq filter the
# production shell chooses); the fake date/sleep advance a shared state clock
# so the 1800s/900s deadlines are reached in fake time, not real seconds.
#
# The cases below assert the #604 design contract:
#   * EXPECTED_HEAD_SHA = full `git rev-parse HEAD` of the new local bot
#     commit (not SOURCE_SHA), exported to GITHUB_ENV as SYNC_EXPECTED_HEAD_SHA
#     ONLY after both the dispatch-wait and the required-check-wait pass.
#   * Same-repository bot PR identity guards (open, non-draft,
#     github-actions[bot] author, head.ref = BRANCH, head.sha = expected,
#     head/base repo full_names consistent, base.ref = main).
#   * The three fixed workflows (pr-validation.yml, quality-integration.yml,
#     security.yml) resolved by REST workflow metadata (id/path, not display
#     name); each `gh workflow run` output must carry exactly one canonical
#     https://github.com/${GH_REPO}/actions/runs/<positive-id> URL, then the
#     exact REST run.id/workflow_id/path/event/repo/head_repository/
#     head_branch/head_sha are validated.
#   * Poll the EXACT dispatched run IDs until completed-success (1800s/30s);
#     only recognized pending statuses wait, terminal non-success fails.
#   * Narrow parked-run approval: only runs on the expected head/ref/repo with
#     the intended PR association and a fixed workflow allowlist (incl.
#     Security) are approved, revalidated before each POST, once per
#     (id, run_attempt).
#   * The final required-checks gate reads structured JSON
#     (`gh pr checks --required --json ...`); empty is never green,
#     fail/cancel wins, pending waits.
#   * The merge revalidates the PR identity + expected SHA and uses
#     `gh pr merge --squash --delete-branch --match-head-commit
#     "${SYNC_EXPECTED_HEAD_SHA}"`; a missing export or head drift blocks it.
#
# The current (pre-fix) workflow does NOT meet this contract, so these cases
# are RED until the CODE worker rewrites the two run blocks.
# ---------------------------------------------------------------------------

FAKE_GH_WAIT_SOURCE = r'''#!/__PYTHON__
"""Deterministic fake gh for the #604 wait/merge shell regression tests.

Serves RAW REST JSON for the operations the sync wait/merge steps may perform
(the real jq, symlinked into the isolated bin, applies any --jq filter).
Every invocation is logged as a JSON argv array to $FAKE_GH_STATE_DIR/calls.log.

State files (in $FAKE_GH_STATE_DIR):
  clock          fake epoch seconds (advanced by the fake sleep)
  head_sha       value served by `git rev-parse HEAD`
  pr.json        the auto-sync PR object
  workflows.json the repository's workflow metadata (id/name/path/state)
  runs.json      workflow runs, each with a time-indexed history
  checks.json    the PR's required checks (time-indexed state)
  dispatch.json  per-workflow-path dispatch outcome (conclusion/after/run_number)
  dispatch_mode  url | stderr-url | two-ids | wrong-repo | malformed | absent | nonzero
  next_run_id    counter for dispatched run ids

Served operations:
  GET  repos/FixtureOwner/fixture-repo/actions/runs[?branch=&status=&per_page=]
  GET  repos/FixtureOwner/fixture-repo/actions/runs/<id>
  POST repos/FixtureOwner/fixture-repo/actions/runs/<id>/approve
  GET  repos/FixtureOwner/fixture-repo/actions/workflows[/<id>]
  GET  repos/FixtureOwner/fixture-repo/pulls[?head=&base=&state=]
  GET  repos/FixtureOwner/fixture-repo/pulls/<number>
  PATCH repos/FixtureOwner/fixture-repo/pulls/<number>
  POST repos/FixtureOwner/fixture-repo/pulls
  gh workflow run <name-or-path> --ref <branch>
  gh pr checks <number> --required [--json <fields>]
  gh pr merge <number> --squash --delete-branch [--subject ...] [--match-head-commit <sha>]

Anything else fails loudly (exit 64) so a harness gap is never mistaken for a
workflow decision.
"""
import json
import os
import subprocess
import sys
import urllib.parse

OWNER = "FixtureOwner"
REPO = "fixture-repo"
BASE = "repos/%s/%s" % (OWNER, REPO)
BIN = os.path.dirname(os.path.abspath(__file__))


def die(msg, code=64):
    sys.stderr.write("fake-gh: %s\n" % msg)
    d = os.environ.get("FAKE_GH_STATE_DIR")
    if d:
        with open(os.path.join(d, "fake_rejected.log"), "a", encoding="utf-8") as h:
            h.write(msg + "\n")
    sys.exit(code)


def sd():
    return os.environ["FAKE_GH_STATE_DIR"]


def read(name, default=""):
    p = os.path.join(sd(), name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as h:
        return h.read()


def read_json(name, default):
    raw = read(name, "")
    if not raw.strip():
        return default
    return json.loads(raw)


def append(name, text):
    with open(os.path.join(sd(), name), "a", encoding="utf-8") as h:
        h.write(text)


def now():
    return int(read("clock", "1000000").strip() or 1000000)


def run_state(run, t):
    status, conclusion = run["history"][0][1], run["history"][0][2]
    for at, s, c in run["history"]:
        if at <= t:
            status, conclusion = s, c
        else:
            break
    return status, conclusion


def run_response(run, t):
    status, conclusion = run_state(run, t)
    # lookup_id (fixed URL id) and detail_id (detail-only .id override) are
    # fake-internal; never exposed in the list JSON.
    resp = {k: v for k, v in run.items() if k not in ("history", "available_at", "lookup_id", "detail_id")}
    resp["status"] = status
    resp["conclusion"] = conclusion
    return resp


def all_runs():
    return read_json("runs.json", [])


def emit(body, jq):
    if jq:
        # gh api --jq emits raw scalars (no surrounding quotes on strings).
        p = subprocess.run([os.path.join(BIN, "jq"), "-r", jq],
                           input=body, capture_output=True, text=True)
        sys.stdout.write(p.stdout)
        sys.stderr.write(p.stderr)
        sys.exit(p.returncode)
    sys.stdout.write(body + "\n")


def handle_api(method, endpoint, fields, jq):
    path, _, query = endpoint.partition("?")
    params = dict(urllib.parse.parse_qsl(query))
    t = now()

    if path == BASE + "/actions/runs" and method == "GET":
        out = []
        for r in all_runs():
            # Late visibility: a run is invisible until its (fake-internal)
            # available_at is reached.
            if r.get("available_at", 0) > t:
                continue
            status, conclusion = run_state(r, t)
            if params.get("branch") and r.get("head_branch") != params["branch"]:
                continue
            # GitHub's status= filter matches the status OR the conclusion
            # (a parked run is status=completed, conclusion=action_required,
            # so status=action_required selects it via the conclusion).
            if params.get("status") and status != params["status"] and conclusion != params["status"]:
                continue
            out.append(run_response(r, t))
        emit(json.dumps({"workflow_runs": out, "total_count": len(out)}), jq)
        return

    if path.startswith(BASE + "/actions/runs/") and method == "GET":
        rest = path[len(BASE + "/actions/runs/"):]
        if "/" in rest or not rest.isdigit():
            die("unexpected actions/runs path: %s" % path)
        dmode = read("detail_mode", "ok").strip() or "ok"
        if dmode == "401":
            sys.stderr.write("HTTP 401: Bad credentials (fake-gh simulated)\n")
            sys.exit(1)
        if dmode == "malformed":
            sys.stdout.write("this is not valid json at all\n")
            sys.exit(0)
        for r in all_runs():
            # Look up by the fixed URL id (lookup_id) when present, else the
            # JSON id — so an overridden id is a field mismatch, not a 404.
            if r.get("lookup_id", r["id"]) == int(rest):
                if r.get("available_at", 0) > t:
                    sys.stderr.write("HTTP 404: Not found (fake-gh)\n")
                    sys.exit(1)
                resp = run_response(r, t)
                # A per-run detail_id (fake-internal) overrides the .id in the
                # DETAIL response only (the list still serves the normal id),
                # so a list/detail id mismatch is a real field comparison.
                if "detail_id" in r:
                    resp["id"] = r["detail_id"]
                emit(json.dumps(resp), jq)
                return
        sys.stderr.write("HTTP 404: Not found (fake-gh)\n")
        sys.exit(1)

    if (path.startswith(BASE + "/actions/runs/") and path.endswith("/approve")
            and method == "POST"):
        rid = path[len(BASE + "/actions/runs/"):-len("/approve")]
        if not rid.isdigit():
            die("unexpected approve path: %s" % path)
        amode = read("approve_mode", "ok").strip() or "ok"
        if amode == "403":
            # The attempt is already recorded in calls.log (logged before
            # dispatch); a 403 is a served response, not an unknown call.
            sys.stderr.write("HTTP 403: Forbidden (fake-gh simulated)\n")
            sys.exit(1)
        append("approved.log", json.dumps({"id": int(rid), "clock": t}) + "\n")
        emit(json.dumps({}), jq)
        return

    if path == BASE + "/actions/workflows" and method == "GET":
        # The same fault applies to the LIST branch as to the detail branch:
        # a compliant resolver may resolve workflow metadata by list only, so
        # the fault must not depend on a particular resolver layout.
        wmode = read("workflows_detail_mode", "ok").strip() or "ok"
        if wmode == "401":
            sys.stderr.write("HTTP 401: Bad credentials (fake-gh simulated)\n")
            sys.exit(1)
        if wmode == "malformed":
            sys.stdout.write("not json\n")
            sys.exit(0)
        wfs = read_json("workflows.json", [])
        emit(json.dumps({"workflows": wfs, "total_count": len(wfs)}), jq)
        return

    if path.startswith(BASE + "/actions/workflows/") and method == "GET":
        rest = path[len(BASE + "/actions/workflows/"):]
        wmode = read("workflows_detail_mode", "ok").strip() or "ok"
        if wmode == "401":
            sys.stderr.write("HTTP 401: Bad credentials (fake-gh simulated)\n")
            sys.exit(1)
        if wmode == "malformed":
            sys.stdout.write("not json\n")
            sys.exit(0)
        for w in read_json("workflows.json", []):
            # REST accepts a numeric workflow id OR the workflow file path
            # (full .github/workflows/<name>.yml or a bare <name>.yml).
            if rest.isdigit() and w["id"] == int(rest):
                emit(json.dumps(w), jq)
                return
            p = w.get("path", "")
            if p == rest or p.endswith("/" + rest) or w.get("name") == rest:
                emit(json.dumps(w), jq)
                return
        sys.stderr.write("HTTP 404: Not found (fake-gh)\n")
        sys.exit(1)

    if path == BASE + "/pulls" and method == "GET":
        pr = read_json("pr.json", {})
        head = params.get("head", "")
        owner, sep, branch = head.partition(":")
        if sep and (owner != OWNER or branch != pr.get("head", {}).get("ref")):
            emit(json.dumps([]), jq)
            return
        emit(json.dumps([pr]), jq)
        return

    if path.startswith(BASE + "/pulls/") and method == "GET":
        rest = path[len(BASE + "/pulls/"):]
        if not rest.isdigit():
            die("unexpected pulls path: %s" % path)
        pr = read_json("pr.json", {})
        if pr.get("number") != int(rest):
            sys.stderr.write("HTTP 404: Not found (fake-gh)\n")
            sys.exit(1)
        emit(json.dumps(pr), jq)
        return

    if path.startswith(BASE + "/pulls/") and method == "PATCH":
        emit(json.dumps({}), jq)
        return

    if path == BASE + "/pulls" and method == "POST":
        emit(json.dumps(read_json("pr.json", {})), jq)
        return

    die("unexpected gh api call: method=%s path=%s" % (method, path))


def handle_workflow_run(args):
    target = None
    ref = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--ref":
            i += 1
            if i >= len(args):
                die("dangling --ref")
            ref = args[i]
        elif a.startswith("-"):
            die("unexpected workflow run flag: %s" % a)
        else:
            target = a
        i += 1
    if target is None or ref is None:
        die("workflow run requires a target and --ref")
    wf = None
    for w in read_json("workflows.json", []):
        # The CLI target is a bare filename (e.g. pr-validation.yml); the
        # workflow metadata path is the full .github/workflows/<name>.yml.
        # Match on the full path, the bare basename, or the display name.
        p = w.get("path", "")
        if p == target or p.endswith("/" + target) or w.get("name") == target:
            wf = w
            break
    if wf is None:
        sys.stderr.write("HTTP 404: workflow not found: %s (fake-gh)\n" % target)
        sys.exit(1)
    mode = read("dispatch_mode", "url").strip() or "url"
    t = now()
    if mode == "nonzero":
        sys.stderr.write("HTTP 500: Internal Server Error (fake-gh dispatch)\n")
        sys.exit(1)
    spec = read_json("dispatch.json", {}).get(wf["path"], {})
    next_id = int(read("next_run_id", "100").strip() or 100)
    after = spec.get("after", 90)
    conclusion = spec.get("conclusion", "success")
    head_sha = read("head_sha", "").strip()
    new_run = {
        "id": next_id,
        "name": wf["name"],
        "path": wf["path"],
        "event": "workflow_dispatch",
        "workflow_id": wf["id"],
        "run_number": spec.get("run_number", next_id),
        "run_attempt": 1,
        "head_sha": head_sha,
        "head_branch": ref,
        "head_repository": {"id": 11, "full_name": "%s/%s" % (OWNER, REPO)},
        "repository": {"id": 11, "full_name": "%s/%s" % (OWNER, REPO)},
        "pull_requests": [],
        "history": [
            [t, "queued", None],
            [t + 30, "in_progress", None],
            [t + after, "completed", conclusion],
        ],
    }
    # Per-workflow-path raw-JSON overrides (test-controlled fault fixtures):
    # merged verbatim into the generated run so a single metadata field can
    # be corrupted without touching the normal dispatch path.
    for k, v in read_json("dispatch_overrides.json", {}).get(wf["path"], {}).items():
        new_run[k] = v
    # The URL lookup id is fixed to the dispatched id (next_id) and is
    # independent of the (possibly overridden) JSON id field, so an id
    # mismatch is a real field comparison (run.id != url id), not a 404.
    # Excluded from the response (see run_response).
    new_run["lookup_id"] = next_id
    runs = all_runs()
    runs.append(new_run)
    with open(os.path.join(sd(), "runs.json"), "w", encoding="utf-8") as h:
        json.dump(runs, h)
    with open(os.path.join(sd(), "next_run_id"), "w", encoding="utf-8") as h:
        h.write(str(next_id + 1))
    append("dispatches.log",
           json.dumps({"target": target, "ref": ref, "run_id": next_id, "clock": t}) + "\n")
    url = "https://github.com/%s/%s/actions/runs/%d" % (OWNER, REPO, next_id)
    if mode == "url":
        sys.stdout.write(url + "\n")
    elif mode == "stderr-url":
        sys.stderr.write(url + "\n")
    elif mode == "two-ids":
        sys.stdout.write(url + "\n")
        sys.stdout.write("https://github.com/%s/%s/actions/runs/%d\n" % (OWNER, REPO, next_id + 999))
    elif mode == "wrong-repo":
        sys.stdout.write("https://github.com/OtherOwner/other-repo/actions/runs/%d\n" % next_id)
    elif mode == "malformed":
        sys.stdout.write("not a url at all\n")
    elif mode == "numeric-suffix":
        # A valid URL with a non-delimited alphanumeric suffix: the numeric
        # prefix is extractable but the URL is not canonical.
        sys.stdout.write(url + "garbage\n")
    elif mode == "absent":
        pass
    else:
        die("unknown dispatch_mode: %s" % mode)


# The only --json fields the fake serves; anything else is a harness gap.
KNOWN_CHECK_FIELDS = ("bucket", "name", "state", "event", "workflow", "link")


def _approved_ids():
    ids = set()
    for line in read("approved.log", "").splitlines():
        if line.strip():
            ids.add(json.loads(line)["id"])
    return ids


def _check_bucket(state):
    # gh pr checks --json bucket: pass/fail/pending/skipping/cancel, derived
    # from the (uppercase) state — never a check name.
    if state in ("IN_PROGRESS", "QUEUED", "PENDING"):
        return "pending"
    if state == "SUCCESS":
        return "pass"
    if state in ("FAILURE", "TIMED_OUT"):
        return "fail"
    if state in ("SKIPPED", "NEUTRAL"):
        return "skipping"
    if state == "CANCELLED":
        return "cancel"
    return "pending"


def handle_pr_checks(args):
    pr = None
    json_fields = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--required":
            pass
        elif a == "--json":
            i += 1
            if i >= len(args):
                die("dangling --json")
            json_fields = args[i]
        elif a.startswith("-"):
            die("unexpected pr checks flag: %s" % a)
        else:
            pr = a
        i += 1
    if pr is None:
        die("pr checks requires a PR number")
    t = now()
    append("checks_calls.log", json.dumps({"clock": t, "args": args}) + "\n")
    # Fault fixtures only: override the checks query's raw output / exit code.
    # Normal cases derive the valid bucket from the (uppercase) states below.
    cfault = read("checks_fault", "ok").strip() or "ok"
    if cfault == "401":
        sys.stderr.write("HTTP 401: Bad credentials (fake-gh simulated)\n")
        sys.exit(1)
    if cfault == "rc-error":
        sys.stderr.write("fake-gh: unknown CLI error (simulated)\n")
        sys.exit(137)
    if cfault == "malformed":
        sys.stdout.write("this is not valid json\n")
        override = read("checks_exit_override", "").strip()
        sys.exit(int(override) if override else 0)
    checks = read_json("checks.json", [])
    out = []
    any_pending = False
    any_fail = False
    for c in checks:
        state = c["state"].upper()
        if t >= c.get("done_at", 0):
            # A check may gate its final_state on specific approvals (a small
            # fixture condition on approved IDs): it only turns SUCCESS after
            # every required approve POST has landed, not on time alone.
            require = c.get("require_approved", [])
            if all(rid in _approved_ids() for rid in require):
                state = c.get("final_state", c["state"]).upper()
        if state in ("IN_PROGRESS", "QUEUED", "PENDING"):
            any_pending = True
        if state in ("FAILURE", "CANCELLED", "TIMED_OUT"):
            any_fail = True
        out.append({
            "bucket": _check_bucket(state),
            "name": c.get("name", ""),
            "state": state,
            "event": c.get("event", ""),
            "workflow": c.get("workflow", ""),
            "link": c.get("link", ""),
        })
    if json_fields:
        fields = [f.strip() for f in json_fields.split(",") if f.strip()]
        for f in fields:
            if f not in KNOWN_CHECK_FIELDS:
                die("unknown pr checks JSON field: %s" % f)
        proj = [{f: item.get(f, "") for f in fields} for item in out]
        sys.stdout.write(json.dumps(proj) + "\n")
        if cfault == "rc-valid-json":
            # Valid structured JSON (all-pass) but an unknown CLI rc: the
            # workflow must fail closed promptly, not mask it as a pending
            # wait to the 900s deadline.
            sys.exit(137)
    else:
        if not out:
            sys.stderr.write("no checks reported\n")
            override = read("checks_exit_override", "").strip()
            sys.exit(int(override) if override else 8)
        for item in out:
            sys.stdout.write("%s %s\n" % (item["name"], item["state"]))
    if not out:
        override = read("checks_exit_override", "").strip()
        sys.exit(int(override) if override else 8)
    if any_fail:
        sys.exit(1)
    if any_pending:
        sys.exit(8)
    sys.exit(0)


def handle_pr_merge(args):
    append("merges.log", json.dumps({"args": args, "clock": now()}) + "\n")
    sys.stdout.write("Merged PR (fake-gh)\n")
    sys.exit(0)


def main():
    if not os.environ.get("FAKE_GH_STATE_DIR"):
        die("FAKE_GH_STATE_DIR is not set")
    args = sys.argv[1:]
    append("calls.log", json.dumps(args) + "\n")
    if not args:
        die("no args")
    cmd = args[0]
    if cmd == "api":
        method = "GET"
        endpoint = None
        fields = []
        jq = None
        i = 1
        while i < len(args):
            a = args[i]
            if a in ("-X", "-f", "-F", "--jq"):
                i += 1
                if i >= len(args):
                    die("dangling %s" % a)
                if a == "-X":
                    method = args[i]
                elif a == "--jq":
                    jq = args[i]
                else:
                    fields.append(args[i])
            elif a.startswith("-"):
                die("unexpected api flag: %s" % a)
            elif endpoint is not None:
                die("unexpected positional: %s" % a)
            else:
                endpoint = a
            i += 1
        if endpoint is None:
            die("no endpoint")
        handle_api(method, endpoint, fields, jq)
    elif cmd == "workflow":
        if len(args) >= 2 and args[1] == "run":
            handle_workflow_run(args[2:])
        else:
            die("unexpected workflow subcommand: %r" % (args[1:],))
    elif cmd == "pr":
        if len(args) >= 2 and args[1] == "checks":
            handle_pr_checks(args[2:])
        elif len(args) >= 2 and args[1] == "merge":
            handle_pr_merge(args[2:])
        else:
            die("unexpected pr subcommand: %r" % (args[1:],))
    else:
        die("unexpected gh command: %s" % cmd)


main()
'''

FAKE_GIT_SOURCE = r'''#!/__PYTHON__
import os, sys
args = sys.argv[1:]
d = os.environ.get("FAKE_GH_STATE_DIR")
if not d:
    sys.stderr.write("fake-git: FAKE_GH_STATE_DIR not set\n"); sys.exit(64)
if args == ["rev-parse", "HEAD"]:
    with open(os.path.join(d, "head_sha"), encoding="utf-8") as h:
        sys.stdout.write(h.read().strip() + "\n")
    sys.exit(0)
sys.stderr.write("fake-git: unsupported: %r\n" % (args,)); sys.exit(64)
'''

FAKE_DATE_SOURCE = r'''#!/__PYTHON__
import os, sys
args = sys.argv[1:]
d = os.environ.get("FAKE_GH_STATE_DIR")
if not d:
    sys.stderr.write("fake-date: FAKE_GH_STATE_DIR not set\n"); sys.exit(64)
if args == ["+%s"]:
    with open(os.path.join(d, "clock"), encoding="utf-8") as h:
        sys.stdout.write(h.read().strip() + "\n")
    sys.exit(0)
sys.stderr.write("fake-date: unsupported: %r\n" % (args,)); sys.exit(64)
'''

FAKE_SLEEP_SOURCE = r'''#!/__PYTHON__
import json, os, sys
args = sys.argv[1:]
d = os.environ.get("FAKE_GH_STATE_DIR")
if not d:
    sys.stderr.write("fake-sleep: FAKE_GH_STATE_DIR not set\n"); sys.exit(64)
if len(args) == 1 and args[0].lstrip("-").isdigit():
    with open(os.path.join(d, "clock"), encoding="utf-8") as h:
        c = int(h.read().strip())
    c += int(args[0])
    with open(os.path.join(d, "clock"), "w", encoding="utf-8") as h:
        h.write(str(c))
    with open(os.path.join(d, "sleeps.log"), "a", encoding="utf-8") as h:
        h.write(json.dumps({"interval": int(args[0]), "clock": c}) + "\n")
    sys.exit(0)
sys.stderr.write("fake-sleep: unsupported: %r\n" % (args,)); sys.exit(64)
'''
class SyncWaitMergeShellTests(unittest.TestCase):
    """#604: execute the REAL wait + merge run blocks verbatim against a
    deterministic fake gh / git / date / sleep and assert the #604 design
    contract. The current (pre-fix) workflow does not meet the contract, so
    these cases are RED until the CODE worker rewrites the two run blocks.
    """

    WAIT_STEP = "Trigger and wait for the auto-sync PR required checks"
    MERGE_STEP = "Squash-merge the auto-sync PR"
    GH_REPO = "FixtureOwner/fixture-repo"
    BRANCH = "chore/tasks-md-auto-sync"
    SOURCE_SHA = "deadbeefcafe1234deadbeefcafe1234deadbeef"
    # A distinct valid 40-hex base SHA (different from SOURCE_SHA) proves the
    # flow allows a cached base (the PR's base.sha need not equal SOURCE_SHA).
    BASE_SHA = "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1"
    EXPECTED_HEAD = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
    STALE_HEAD = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"
    PR_NUMBER = "566"
    # Full workflow file paths (REST metadata), not bare filenames.
    WORKFLOWS = [
        {"id": 1, "name": "PR Validation", "path": ".github/workflows/pr-validation.yml", "state": "active"},
        {"id": 2, "name": "Quality integration gate", "path": ".github/workflows/quality-integration.yml", "state": "active"},
        {"id": 3, "name": "Security", "path": ".github/workflows/security.yml", "state": "active"},
    ]

    # ------------------------------------------------------------------
    # Harness helpers
    # ------------------------------------------------------------------

    def _load_step(self, name):
        import yaml
        path = ROOT / ".github" / "workflows" / "sync-merged-tasks.yml"
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        job = wf["jobs"]["sync-merged-tasks"]
        steps = [s for s in job["steps"] if s.get("name") == name]
        self.assertEqual(len(steps), 1, "step %r must be unique by name" % name)
        run = steps[0]["run"]
        # The step must keep its strict shell options (set -euo pipefail).
        first = run.splitlines()[0].strip()
        self.assertEqual(first, "set -euo pipefail",
                         "step %r must start with strict shell options" % name)
        return run

    def _write_fake_bin(self, tmp):
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, src in [("gh", FAKE_GH_WAIT_SOURCE), ("git", FAKE_GIT_SOURCE),
                          ("date", FAKE_DATE_SOURCE), ("sleep", FAKE_SLEEP_SOURCE)]:
            p = bin_dir / name
            p.write_text(src.replace("__PYTHON__", sys.executable), encoding="utf-8")
            p.chmod(0o755)
        (bin_dir / "jq").symlink_to("/usr/bin/jq")
        for name in ("curl", "wget"):
            p = bin_dir / name
            p.write_text(
                "#!" + sys.executable + "\nimport sys\n"
                "sys.stderr.write('sentinel " + name + " used\\n')\nsys.exit(99)\n",
                encoding="utf-8",
            )
            p.chmod(0o755)
        return bin_dir

    def _repo(self):
        # Full REST repository object (as served by GET /pulls/<number> for
        # head.repo / base.repo): id/name/full_name/url.
        return {"id": 11, "name": "fixture-repo", "full_name": self.GH_REPO,
                "url": "https://api.github.com/repos/%s" % self.GH_REPO}

    def _assoc_repo(self):
        # Minimal REST association repo (id/name/url; full_name is NOT
        # required in a workflow-run pull_requests association).
        return {"id": 11, "name": "fixture-repo",
                "url": "https://api.github.com/repos/%s" % self.GH_REPO}

    def _valid_pr(self):
        return {
            "number": 566, "state": "open", "draft": False,
            "user": {"login": "github-actions[bot]"},
            "head": {"ref": self.BRANCH, "sha": self.EXPECTED_HEAD,
                     "repo": self._repo()},
            "base": {"ref": "main", "sha": self.BASE_SHA,
                     "repo": self._repo()},
        }

    def _green_checks(self, done_at=1000090):
        # Uppercase states; the fake derives the bucket (pass/fail/pending/
        # skipping/cancel) from the state — never a check-name-valued bucket.
        return [
            {"name": "PR Validation", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "pr-validation.yml",
             "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
             "done_at": done_at, "final_state": "SUCCESS"},
            {"name": "Quality integration gate", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "quality-integration.yml",
             "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
             "done_at": done_at, "final_state": "SUCCESS"},
            {"name": "Security", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "security.yml",
             "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
             "done_at": done_at, "final_state": "SUCCESS"},
        ]

    def _parked_run(self, run_id, name, path, workflow_id, run_number,
                    head_sha, available_at, head_repo=None, pr_number=566,
                    pull_requests=None):
        # A parked (approval-gated) pull_request run: status=completed,
        # conclusion=action_required. Carries the full REST run metadata
        # (run_attempt, pull_requests array with minimal PR association,
        # top-level repository/head_repository with full_name+id) plus the
        # fake-internal available_at (late visibility, excluded from JSON).
        if head_repo is None:
            head_repo = {"id": 11, "full_name": self.GH_REPO}
        if pull_requests is None:
            pull_requests = [{
                "number": pr_number,
                "head": {"ref": self.BRANCH, "sha": head_sha,
                         "repo": self._assoc_repo()},
                "base": {"ref": "main", "sha": self.BASE_SHA,
                         "repo": self._assoc_repo()},
            }]
        return {
            "id": run_id, "name": name, "path": path,
            "event": "pull_request", "workflow_id": workflow_id,
            "run_number": run_number, "run_attempt": 1,
            "head_sha": head_sha, "head_branch": self.BRANCH,
            "head_repository": head_repo,
            "repository": {"id": 11, "full_name": self.GH_REPO},
            "pull_requests": pull_requests,
            "available_at": available_at,
            "history": [[available_at, "completed", "action_required"]],
        }

    def _base_scenario(self):
        return {
            "pr": self._valid_pr(),
            "workflows": self.WORKFLOWS,
            "runs": [],
            "checks": self._green_checks(),
            "dispatch": {
                ".github/workflows/pr-validation.yml": {"conclusion": "success", "after": 90, "run_number": 10},
                ".github/workflows/quality-integration.yml": {"conclusion": "success", "after": 90, "run_number": 11},
                ".github/workflows/security.yml": {"conclusion": "success", "after": 90, "run_number": 12},
            },
            "dispatch_mode": "url",
        }

    def _make_state(self, tmp, scenario):
        state = tmp / "state"
        state.mkdir()
        (state / "clock").write_text("1000000\n", encoding="utf-8")
        (state / "head_sha").write_text(self.EXPECTED_HEAD + "\n", encoding="utf-8")
        (state / "dispatch_mode").write_text(scenario.get("dispatch_mode", "url") + "\n", encoding="utf-8")
        (state / "next_run_id").write_text("100\n", encoding="utf-8")
        (state / "workflows.json").write_text(json.dumps(scenario["workflows"]), encoding="utf-8")
        (state / "pr.json").write_text(json.dumps(scenario["pr"]), encoding="utf-8")
        (state / "runs.json").write_text(json.dumps(scenario.get("runs", [])), encoding="utf-8")
        (state / "checks.json").write_text(json.dumps(scenario.get("checks", [])), encoding="utf-8")
        (state / "dispatch.json").write_text(json.dumps(scenario.get("dispatch", {})), encoding="utf-8")
        (state / "dispatch_overrides.json").write_text(
            json.dumps(scenario.get("dispatch_overrides", {})), encoding="utf-8")
        (state / "detail_mode").write_text(scenario.get("detail_mode", "ok") + "\n", encoding="utf-8")
        (state / "workflows_detail_mode").write_text(
            scenario.get("workflows_detail_mode", "ok") + "\n", encoding="utf-8")
        (state / "approve_mode").write_text(scenario.get("approve_mode", "ok") + "\n", encoding="utf-8")
        (state / "checks_fault").write_text(scenario.get("checks_fault", "ok") + "\n", encoding="utf-8")
        if "checks_exit_override" in scenario:
            (state / "checks_exit_override").write_text(
                str(scenario["checks_exit_override"]) + "\n", encoding="utf-8")
        return state

    def _run_step(self, script, tmp, state, extra_env):
        env = {
            "PATH": str(tmp / "bin"),
            "GH_TOKEN": "fake-workflow-token",
            "GH_REPO": self.GH_REPO,
            "BRANCH": self.BRANCH,
            "SOURCE_SHA": self.SOURCE_SHA,
            "PR_NUMBER": self.PR_NUMBER,
            "GITHUB_ENV": str(tmp / "github_env"),
            "FAKE_GH_STATE_DIR": str(state),
            "LC_ALL": "C",
        }
        env.update(extra_env)
        return subprocess.run([shutil.which("bash"), "-c", script],
                              capture_output=True, text=True, env=env)

    def _run_wait(self, tmp, state, extra_env=None):
        return self._run_step(self._load_step(self.WAIT_STEP), tmp, state, extra_env or {})

    def _run_merge(self, tmp, state, extra_env=None):
        return self._run_step(self._load_step(self.MERGE_STEP), tmp, state, extra_env or {})

    @staticmethod
    def _read_log(state, name):
        p = state / name
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _calls(self, state):
        return self._read_log(state, "calls.log")

    def _approved(self, state):
        return self._read_log(state, "approved.log")

    def _dispatches(self, state):
        return self._read_log(state, "dispatches.log")

    def _merges(self, state):
        return self._read_log(state, "merges.log")

    def _github_env(self, tmp):
        f = tmp / "github_env"
        if not f.exists():
            return {}
        out = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                out[k] = v
        return out

    def _run_detail_ids(self, calls):
        import re
        ids = set()
        for c in calls:
            if c[0] == "api" and len(c) >= 2:
                m = re.match(r"repos/[^/]+/[^/]+/actions/runs/(\d+)$", c[1])
                if m:
                    ids.add(int(m.group(1)))
        return ids

    def _dispatch_run_ids(self, state):
        return {d["run_id"] for d in self._dispatches(state)}

    # ------------------------------------------------------------------
    # Scenario 1: happy wait/merge pins expected head and exact run polls
    # ------------------------------------------------------------------

    def test_happy_wait_merge_pins_expected_head_and_exact_polls(self):
        with tempfile.TemporaryDirectory(prefix="604-happy-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, self._base_scenario())
            r = self._run_wait(tmp, state)
            self.assertEqual(r.returncode, 0, r.stderr)
            env = self._github_env(tmp)
            # EXPECTED_HEAD_SHA (full git rev-parse HEAD, not SOURCE_SHA) is
            # exported to GITHUB_ENV only after both gates pass.
            self.assertEqual(env.get("SYNC_EXPECTED_HEAD_SHA"), self.EXPECTED_HEAD,
                             "SYNC_EXPECTED_HEAD_SHA must be exported after both gates")
            # The fake clock must have advanced by at least 90s (the dispatch
            # completion) before the export.
            final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
            self.assertGreaterEqual(final_clock, 1000000 + 90,
                                    "the fake clock must reach t+90 before the export (got %d)" % final_clock)
            # Exactly TWO workflows are dispatched (by path, not display name);
            # Security is in the approval allowlist but is NOT dispatched.
            targets = sorted(d["target"] for d in self._dispatches(state))
            self.assertEqual(targets,
                             ["pr-validation.yml", "quality-integration.yml"],
                             "exactly two workflows must be dispatched by path (Security is "
                             "approval-allowlisted, not dispatched)")
            # The workflow resolves the workflow metadata by REST
            # (GET /actions/workflows), not by display name.
            wait_calls = self._calls(state)
            self.assertTrue(any(c[0] == "api" and "/actions/workflows" in c[1] for c in wait_calls),
                            "the workflow must resolve the workflow metadata by REST")
            # The poll targets the EXACT dispatched run IDs (run-detail GETs):
            # BOTH dispatched IDs must be polled, not just an intersection.
            dispatched = self._dispatch_run_ids(state)
            polled = self._run_detail_ids(wait_calls)
            self.assertTrue(dispatched, "dispatches must create runs")
            self.assertTrue(dispatched <= polled,
                            "the poll must GET both exact dispatched run IDs (got polled=%s dispatched=%s)"
                            % (polled, dispatched))
            # The merge revalidates the PR and pins the expected head.
            r2 = self._run_merge(tmp, state, env)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            merges = self._merges(state)
            self.assertEqual(len(merges), 1, "exactly one merge call")
            args = merges[0]["args"]
            self.assertIn("--match-head-commit", args, "merge must pin the expected head")
            self.assertIn(self.EXPECTED_HEAD, args, "merge must use the expected head SHA")
            # The merge revalidated the PR identity (GET pulls/566).
            merge_calls = self._calls(state)
            self.assertTrue(any(c[0] == "api" and c[1].endswith("/pulls/566") for c in merge_calls),
                            "the merge must revalidate the PR identity")

    # ------------------------------------------------------------------
    # Scenario 2: stale history cannot cause fail/early-green
    # ------------------------------------------------------------------

    def test_stale_history_cannot_cause_early_green_or_fail(self):
        scenario = self._base_scenario()
        # Stale runs from a previous head, with HIGHER run_numbers than the
        # current dispatches. One stale success, one stale cancelled.
        scenario["runs"] = [
            {"id": 900, "name": "PR Validation",
             "path": ".github/workflows/pr-validation.yml",
             "event": "workflow_dispatch", "workflow_id": 1, "run_number": 90,
             "run_attempt": 1,
             "head_sha": self.STALE_HEAD, "head_branch": self.BRANCH,
             "head_repository": {"id": 11, "full_name": self.GH_REPO},
             "repository": {"id": 11, "full_name": self.GH_REPO},
             "pull_requests": [],
             "history": [[1000000, "completed", "success"]]},
            {"id": 901, "name": "Quality integration gate",
             "path": ".github/workflows/quality-integration.yml",
             "event": "workflow_dispatch", "workflow_id": 2, "run_number": 91,
             "run_attempt": 1,
             "head_sha": self.STALE_HEAD, "head_branch": self.BRANCH,
             "head_repository": {"id": 11, "full_name": self.GH_REPO},
             "repository": {"id": 11, "full_name": self.GH_REPO},
             "pull_requests": [],
             "history": [[1000000, "completed", "cancelled"]]},
        ]
        with tempfile.TemporaryDirectory(prefix="604-stale-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, scenario)
            r = self._run_wait(tmp, state)
            # The wait must poll the EXACT dispatched run IDs (not the stale
            # runs by name + max run_number). A name-based poll would observe
            # the stale success (early green) or the stale cancelled (fail).
            dispatched = self._dispatch_run_ids(state)
            polled = self._run_detail_ids(self._calls(state))
            self.assertTrue(dispatched, "dispatches must create runs")
            self.assertTrue(polled & dispatched,
                            "the poll must target the exact dispatched run IDs, not the stale "
                            "history by name (got polled=%s dispatched=%s)" % (polled, dispatched))
            # The wait must not go green early (due to the stale success) nor
            # fail (due to the stale cancelled) while the exact current
            # dispatch is still pending.
            self.assertEqual(r.returncode, 0,
                             "the wait must succeed on the exact current dispatch, not the stale "
                             "history (rc=%d stderr=%s)" % (r.returncode, r.stderr))

    # ------------------------------------------------------------------
    # Scenario 3: dispatch URL validation
    # ------------------------------------------------------------------

    def test_dispatch_url_validation(self):
        # Each sub-case: a dispatch output that must be rejected (non-zero,
        # no merge, no SYNC_EXPECTED_HEAD_SHA export) or accepted (stderr-url).
        cases = [
            ("absent", False),
            ("two-ids", False),
            ("wrong-repo", False),
            ("malformed", False),
            ("nonzero", False),
            ("numeric-suffix", False),
            ("stderr-url", True),
        ]
        for mode, should_succeed in cases:
            with self.subTest(dispatch_mode=mode):
                scenario = self._base_scenario()
                scenario["dispatch_mode"] = mode
                with tempfile.TemporaryDirectory(prefix="604-url-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    if should_succeed:
                        self.assertEqual(r.returncode, 0,
                                         "a canonical URL on stderr must be accepted (stderr=%s)" % r.stderr)
                        self.assertEqual(env.get("SYNC_EXPECTED_HEAD_SHA"), self.EXPECTED_HEAD)
                    else:
                        self.assertNotEqual(r.returncode, 0,
                                            "dispatch mode %r must fail closed (rc=%d)" % (mode, r.returncode))
                        self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                         "no SYNC_EXPECTED_HEAD_SHA export on a rejected dispatch")
                        self.assertEqual(self._merges(state), [], "no merge on a rejected dispatch")

    # ------------------------------------------------------------------
    # Scenario 4: invalid PR -> no approval / no merge
    # ------------------------------------------------------------------

    def test_invalid_pr_no_approval_no_merge(self):
        def mutate(pr, key):
            pr = json.loads(json.dumps(pr))
            if key == "closed":
                pr["state"] = "closed"
            elif key == "draft":
                pr["draft"] = True
            elif key == "author":
                pr["user"]["login"] = "some-human"
            elif key == "head-sha":
                pr["head"]["sha"] = self.STALE_HEAD
            elif key == "head-repo":
                # A fork: every repo association field differs from the base.
                pr["head"]["repo"] = {"id": 999, "name": "fork-repo",
                                      "full_name": "ForkOwner/fork-repo",
                                      "url": "https://api.github.com/repos/ForkOwner/fork-repo"}
            elif key == "base-ref":
                pr["base"]["ref"] = "develop"
            elif key == "base-repo":
                # The base repo differs from the expected (must match the head repo).
                pr["base"]["repo"] = {"id": 999, "name": "other-repo",
                                      "full_name": "OtherOwner/other-repo",
                                      "url": "https://api.github.com/repos/OtherOwner/other-repo"}
            elif key == "head-ref":
                pr["head"]["ref"] = "other-branch"
            return pr

        for key in ("closed", "draft", "author", "head-sha", "head-repo", "base-ref",
                    "base-repo", "head-ref"):
            with self.subTest(pr_invalid=key):
                scenario = self._base_scenario()
                scenario["pr"] = mutate(self._valid_pr(), key)
                with tempfile.TemporaryDirectory(prefix="604-pr-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    self.assertNotEqual(r.returncode, 0,
                                        "invalid PR (%s) must fail closed (rc=%d)" % (key, r.returncode))
                    self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                     "no SYNC_EXPECTED_HEAD_SHA export on an invalid PR")
                    self.assertEqual(self._approved(state), [],
                                     "no approval on an invalid PR (%s)" % key)
                    self.assertEqual(self._merges(state), [],
                                     "no merge on an invalid PR (%s)" % key)

    # ------------------------------------------------------------------
    # Scenario 5: late approval + security workflow + narrow approve
    # ------------------------------------------------------------------

    def test_late_approval_security_and_narrow_approve(self):
        scenario = self._base_scenario()
        # Two eligible parked runs (expected head, intended PR #566, allowlisted
        # workflow) that appear in two phases via late visibility (available_at):
        #   - PR Validation at t+30 (first phase)
        #   - Security at t+120 (second phase, after the dispatches done at t+90)
        # Five ineligible candidates (fork / wrong PR / unknown workflow / null
        # association / stale head) are present from the start but must NEVER be
        # approved. Security is approval-eligible but NOT a third dispatch.
        scenario["runs"] = [
            self._parked_run(960, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 20,
                             self.EXPECTED_HEAD, available_at=1000030),
            self._parked_run(961, "Security",
                             ".github/workflows/security.yml", 3, 21,
                             self.EXPECTED_HEAD, available_at=1000120),
            # Ineligible: fork (head repo differs from the base repo).
            self._parked_run(970, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 22,
                             self.EXPECTED_HEAD, available_at=1000000,
                             head_repo={"id": 999, "full_name": "ForkOwner/fork-repo"}),
            # Ineligible: wrong PR (a different PR number).
            self._parked_run(971, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 23,
                             self.EXPECTED_HEAD, available_at=1000000,
                             pr_number=999),
            # Ineligible: unknown workflow (not in the approval allowlist).
            self._parked_run(972, "Unknown",
                             ".github/workflows/unknown.yml", 99, 24,
                             self.EXPECTED_HEAD, available_at=1000000),
            # Ineligible: null association (no pull_requests).
            self._parked_run(973, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 25,
                             self.EXPECTED_HEAD, available_at=1000000,
                             pull_requests=[]),
            # Ineligible: stale head.
            self._parked_run(974, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 26,
                             self.STALE_HEAD, available_at=1000000),
        ]
        # The required checks can only become SUCCESS after BOTH eligible
        # approvals (960 and 961) have landed — a fixture condition on the
        # approved IDs, not time alone.
        scenario["checks"] = [
            {"name": "PR Validation", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "pr-validation.yml",
             "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
             "done_at": 1000200, "final_state": "SUCCESS",
             "require_approved": [960, 961]},
            {"name": "Quality integration gate", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "quality-integration.yml",
             "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
             "done_at": 1000200, "final_state": "SUCCESS",
             "require_approved": [960, 961]},
            {"name": "Security", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "security.yml",
             "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
             "done_at": 1000200, "final_state": "SUCCESS",
             "require_approved": [960, 961]},
        ]
        with tempfile.TemporaryDirectory(prefix="604-approve-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, scenario)
            r = self._run_wait(tmp, state)
            self.assertEqual(r.returncode, 0, r.stderr)
            approved = self._approved(state)
            approved_ids = [a["id"] for a in approved]
            # The eligible PR Validation run (960) is approved exactly once,
            # at the correct clock interval (t+30), despite its stale detail.
            self.assertEqual(approved_ids.count(960), 1,
                             "the eligible PR Validation run must be approved exactly once (got %s)" % approved_ids)
            # The eligible Security run (961) is approved exactly once,
            # at the correct clock interval (t+120), despite its stale detail.
            self.assertEqual(approved_ids.count(961), 1,
                             "the eligible Security run must be approved exactly once (got %s)" % approved_ids)
            # The approval clock intervals are correct (one POST each).
            for a in approved:
                if a["id"] == 960:
                    self.assertEqual(a["clock"], 1000030,
                                     "the PR Validation approval must land at t+30 (got %d)" % a["clock"])
                elif a["id"] == 961:
                    self.assertEqual(a["clock"], 1000120,
                                     "the Security approval must land at t+120 (got %d)" % a["clock"])
            # The ineligible candidates are NEVER approved.
            for ineligible in (970, 971, 972, 973, 974):
                self.assertNotIn(ineligible, approved_ids,
                                 "the ineligible run %d must NOT be approved (got %s)" % (ineligible, approved_ids))
            # At least one valid candidate from the same page is approved.
            self.assertTrue(960 in approved_ids or 961 in approved_ids,
                            "at least one valid candidate must be approved (got %s)" % approved_ids)
            # Security is approval-eligible but NOT dispatched: exactly two
            # workflows are dispatched (PR Validation + Quality integration).
            dispatched = self._dispatch_run_ids(state)
            self.assertEqual(len(dispatched), 2,
                             "exactly two workflows must be dispatched (Security is not dispatched)")

    # ------------------------------------------------------------------
    # Scenario 6: current exact dispatch failure -> non-zero, no merge
    # ------------------------------------------------------------------

    def test_dispatch_failure_no_merge(self):
        for conclusion in ("failure", "cancelled", "timed_out"):
            with self.subTest(conclusion=conclusion):
                scenario = self._base_scenario()
                for wf in scenario["dispatch"]:
                    scenario["dispatch"][wf]["conclusion"] = conclusion
                with tempfile.TemporaryDirectory(prefix="604-fail-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    self.assertNotEqual(r.returncode, 0,
                                        "a %s dispatch must fail closed (rc=%d)" % (conclusion, r.returncode))
                    self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                     "no SYNC_EXPECTED_HEAD_SHA export on a failed dispatch")
                    self.assertEqual(self._merges(state), [],
                                     "no merge on a failed dispatch (%s)" % conclusion)

    # ------------------------------------------------------------------
    # Scenario 7: required-checks gate (structured JSON)
    # ------------------------------------------------------------------

    def test_required_checks_gate(self):
        # 7a: checks pending then pass -> the wait succeeds (later pass).
        with self.subTest(case="pending-then-pass"):
            scenario = self._base_scenario()
            scenario["checks"] = self._green_checks(done_at=1000300)
            with tempfile.TemporaryDirectory(prefix="604-gate-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                self.assertEqual(r.returncode, 0,
                                 "pending-then-pass checks must eventually go green (stderr=%s)" % r.stderr)
        # 7c: checks fail -> the wait fails.
        with self.subTest(case="fail"):
            scenario = self._base_scenario()
            scenario["checks"] = [
                {"bucket": "PR Validation", "name": "PR Validation", "state": "in_progress",
                 "event": "pull_request", "workflow": "pr-validation.yml",
                 "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
                 "done_at": 1000090, "final_state": "failure"},
                {"bucket": "Quality integration gate", "name": "Quality integration gate",
                 "state": "in_progress", "event": "pull_request", "workflow": "quality-integration.yml",
                 "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
                 "done_at": 1000090, "final_state": "pass"},
                {"bucket": "Security", "name": "Security", "state": "in_progress",
                 "event": "pull_request", "workflow": "security.yml",
                 "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
                 "done_at": 1000090, "final_state": "pass"},
            ]
            with tempfile.TemporaryDirectory(prefix="604-gate-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                self.assertNotEqual(r.returncode, 0,
                                    "a failed required check must fail the wait (rc=%d)" % r.returncode)
                self.assertEqual(self._merges(state), [], "no merge on a failed required check")

    # ------------------------------------------------------------------
    # Scenario 8: fake-clock timeouts (1800s dispatch + 900s checks)
    # ------------------------------------------------------------------

    def test_fake_clock_timeouts_no_merge(self):
        scenario = self._base_scenario()
        # The dispatch never completes within 1800s of fake time.
        for wf in scenario["dispatch"]:
            scenario["dispatch"][wf]["after"] = 999999
        # The checks never go green within 900s of fake time.
        scenario["checks"] = self._green_checks(done_at=999999999)
        with tempfile.TemporaryDirectory(prefix="604-timeout-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, scenario)
            r = self._run_wait(tmp, state)
            self.assertNotEqual(r.returncode, 0,
                                "a timeout must fail the wait (rc=%d)" % r.returncode)
            self.assertEqual(self._merges(state), [], "no merge on a timeout")
            # The fake clock advanced in 30s steps (not real-time waits).
            final_clock = int((state / "clock").read_text().strip())
            self.assertGreater(final_clock, 1000000, "the fake clock must advance")
            # The dispatch-wait deadline is 1800s; the clock must have advanced
            # by at least 1800s (the dispatch-wait timeout) before failing.
            self.assertGreaterEqual(final_clock - 1000000, 1800,
                                    "the dispatch-wait must run to its 1800s fake deadline")

    # ------------------------------------------------------------------
    # Scenario 9: merge head changed / missing export
    # ------------------------------------------------------------------

    def test_merge_head_changed_and_missing_export(self):
        # 9b: a valid merge includes --match-head-commit with the expected head,
        # and the merge's PR revalidation GET is isolated (after the wait's GET).
        with self.subTest(case="valid-merge"):
            scenario = self._base_scenario()
            with tempfile.TemporaryDirectory(prefix="604-merge-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                self.assertEqual(r.returncode, 0, r.stderr)
                env = self._github_env(tmp)
                self.assertEqual(env.get("SYNC_EXPECTED_HEAD_SHA"), self.EXPECTED_HEAD)
                # Offset: the wait step's PR revalidation GETs.
                wait_pr_gets = sum(
                    1 for c in self._calls(state)
                    if c[0] == "api" and c[1].endswith("/pulls/566"))
                r2 = self._run_merge(tmp, state, env)
                self.assertEqual(r2.returncode, 0, r2.stderr)
                merges = self._merges(state)
                self.assertEqual(len(merges), 1)
                self.assertIn("--match-head-commit", merges[0]["args"])
                self.assertIn(self.EXPECTED_HEAD, merges[0]["args"])
                # The merge's PR revalidation GET is isolated (after the offset),
                # so the wait's GET cannot satisfy the merge identity check.
                merge_pr_gets = sum(
                    1 for c in self._calls(state)
                    if c[0] == "api" and c[1].endswith("/pulls/566"))
                self.assertGreater(merge_pr_gets, wait_pr_gets,
                                   "the merge must revalidate the PR with its own GET (after the wait's GET)")
        # 9d: a real head drift AFTER a successful wait (before the merge) must
        # block the merge (non-zero, no merge call).
        with self.subTest(case="head-drift-after-wait"):
            scenario = self._base_scenario()
            with tempfile.TemporaryDirectory(prefix="604-merge-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                self.assertEqual(r.returncode, 0, r.stderr)
                # Simulate a head drift: the PR's head.sha changes after the wait.
                pr = json.loads((state / "pr.json").read_text(encoding="utf-8"))
                pr["head"]["sha"] = self.STALE_HEAD
                (state / "pr.json").write_text(json.dumps(pr), encoding="utf-8")
                # Run the merge with the expected head exported (simulating the
                # wait step's export), so the only failure is the head drift.
                r2 = self._run_merge(tmp, state, {"SYNC_EXPECTED_HEAD_SHA": self.EXPECTED_HEAD})
                self.assertNotEqual(r2.returncode, 0,
                                    "a head drift after the wait must block the merge (rc=%d)" % r2.returncode)
                self.assertEqual(self._merges(state), [],
                                 "no merge call when the head drifts after the wait")
        # 9c: a missing SYNC_EXPECTED_HEAD_SHA blocks the merge.
        with self.subTest(case="missing-export"):
            scenario = self._base_scenario()
            with tempfile.TemporaryDirectory(prefix="604-merge-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                # Simulate the wait step NOT exporting SYNC_EXPECTED_HEAD_SHA.
                r2 = self._run_merge(tmp, state, {})
                self.assertNotEqual(r2.returncode, 0,
                                    "a missing SYNC_EXPECTED_HEAD_SHA must block the merge (rc=%d)" % r2.returncode)
                self.assertEqual(self._merges(state), [],
                                 "no merge call when SYNC_EXPECTED_HEAD_SHA is missing")

    # ------------------------------------------------------------------
    # Scenario 10: exact dispatch-metadata mismatch (item 1)
    # ------------------------------------------------------------------

    def test_dispatch_metadata_mismatch_fails_closed(self):
        """#604 item 1: corrupting any exact dispatch-metadata field must fail
        the wait closed (non-zero, no export, no merge). The rejection must
        come from the workflow's own validation of the REST run detail (the
        detail GET is observed), not from a fake rejection (harness gap)."""
        fields = {
            "id": {"id": 99999},
            "workflow_id": {"workflow_id": 999},
            "path": {"path": ".github/workflows/other.yml"},
            "event": {"event": "pull_request"},
            "head_sha": {"head_sha": self.STALE_HEAD},
            "head_branch": {"head_branch": "other-branch"},
            "repository": {"repository": {"id": 999, "full_name": "OtherOwner/other-repo"}},
            "head_repository": {"head_repository": {"id": 999, "full_name": "OtherOwner/other-repo"}},
        }
        for field, override in fields.items():
            with self.subTest(field=field):
                scenario = self._base_scenario()
                scenario["dispatch_overrides"] = {
                    ".github/workflows/pr-validation.yml": dict(override),
                    ".github/workflows/quality-integration.yml": dict(override),
                }
                with tempfile.TemporaryDirectory(prefix="604-meta-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    self.assertNotEqual(r.returncode, 0,
                                        "a %s metadata mismatch must fail closed (rc=%d)" % (field, r.returncode))
                    self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                     "no SYNC_EXPECTED_HEAD_SHA export on a %s mismatch" % field)
                    self.assertEqual(self._merges(state), [],
                                     "no merge on a %s mismatch" % field)
                    # The detail GET for a dispatched run ID must be observed
                    # (the workflow fetched the run detail to validate it).
                    dispatched = self._dispatch_run_ids(state)
                    polled = self._run_detail_ids(self._calls(state))
                    self.assertTrue(dispatched, "dispatches must create runs")
                    self.assertTrue(polled & dispatched,
                                    "the detail GET for a dispatched run ID must be observed "
                                    "(got polled=%s dispatched=%s)" % (polled, dispatched))
                    # The failure must come from the workflow's own validation,
                    # not a fake rejection (harness gap).
                    rejected = self._read_log(state, "fake_rejected.log")
                    self.assertEqual(rejected, [],
                                     "the fake must not reject any call on a %s mismatch (got %s)" % (field, rejected))

    # ------------------------------------------------------------------
    # Scenario 11: run-detail / workflow-metadata GET faults (item 1)
    # ------------------------------------------------------------------

    def test_run_detail_malformed_json_and_401(self):
        """#604 item 1: a malformed-JSON or 401 run-detail GET must fail the
        wait closed (non-zero, no export, no merge), with the detail GET
        observed and no fake rejection."""
        for mode in ("malformed", "401"):
            with self.subTest(detail_mode=mode):
                scenario = self._base_scenario()
                scenario["detail_mode"] = mode
                with tempfile.TemporaryDirectory(prefix="604-detail-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    self.assertNotEqual(r.returncode, 0,
                                        "a %s run-detail GET must fail closed (rc=%d)" % (mode, r.returncode))
                    self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                     "no SYNC_EXPECTED_HEAD_SHA export on a %s run-detail GET" % mode)
                    self.assertEqual(self._merges(state), [],
                                     "no merge on a %s run-detail GET" % mode)
                    dispatched = self._dispatch_run_ids(state)
                    polled = self._run_detail_ids(self._calls(state))
                    self.assertTrue(dispatched, "dispatches must create runs")
                    self.assertTrue(polled & dispatched,
                                    "the detail GET must be observed (got polled=%s dispatched=%s)" % (polled, dispatched))
                    rejected = self._read_log(state, "fake_rejected.log")
                    self.assertEqual(rejected, [],
                                     "the fake must not reject any call on a %s run-detail GET (got %s)" % (mode, rejected))

    def test_workflow_metadata_malformed_and_401(self):
        """#604 item 1 (optional): a malformed-JSON or 401 workflow-metadata
        GET must fail the wait closed (non-zero, no export, no merge)."""
        for mode in ("malformed", "401"):
            with self.subTest(workflows_detail_mode=mode):
                scenario = self._base_scenario()
                scenario["workflows_detail_mode"] = mode
                with tempfile.TemporaryDirectory(prefix="604-wfmeta-") as raw:
                    tmp = Path(raw)
                    self._write_fake_bin(tmp)
                    state = self._make_state(tmp, scenario)
                    r = self._run_wait(tmp, state)
                    env = self._github_env(tmp)
                    self.assertNotEqual(r.returncode, 0,
                                        "a %s workflow-metadata GET must fail closed (rc=%d)" % (mode, r.returncode))
                    self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                     "no SYNC_EXPECTED_HEAD_SHA export on a %s workflow-metadata GET" % mode)
                    self.assertEqual(self._merges(state), [],
                                     "no merge on a %s workflow-metadata GET" % mode)

    # ------------------------------------------------------------------
    # Scenario 12: approval POST 403 (item 2)
    # ------------------------------------------------------------------

    def test_approval_403_fails_closed(self):
        """#604 item 2: a 403 on the approve POST must fail the wait closed
        (non-zero, no export, no merge). The valid current parked candidate
        must cause the actual POST (the attempt is recorded before the 403),
        and no unrelated (ineligible) candidate may be approved."""
        scenario = self._base_scenario()
        # One eligible parked run (expected head, intended PR #566, allowlisted
        # workflow) that becomes visible at t+30, and two ineligible candidates
        # (fork / wrong PR) visible from the start. The required checks are
        # gated on the eligible approval, so the workflow must approve 960 to
        # unblock them (and fails on the 403).
        scenario["runs"] = [
            self._parked_run(960, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 20,
                             self.EXPECTED_HEAD, available_at=1000030),
            self._parked_run(970, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 22,
                             self.EXPECTED_HEAD, available_at=1000000,
                             head_repo={"id": 999, "full_name": "ForkOwner/fork-repo"}),
            self._parked_run(971, "PR Validation",
                             ".github/workflows/pr-validation.yml", 1, 23,
                             self.EXPECTED_HEAD, available_at=1000000,
                             pr_number=999),
        ]
        scenario["checks"] = [
            {"name": "PR Validation", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "pr-validation.yml",
             "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
            {"name": "Quality integration gate", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "quality-integration.yml",
             "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
            {"name": "Security", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "security.yml",
             "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
        ]
        scenario["approve_mode"] = "403"
        with tempfile.TemporaryDirectory(prefix="604-403-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, scenario)
            r = self._run_wait(tmp, state)
            env = self._github_env(tmp)
            self.assertNotEqual(r.returncode, 0,
                                "a 403 approve POST must fail closed (rc=%d)" % r.returncode)
            self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                             "no SYNC_EXPECTED_HEAD_SHA export on a 403 approve POST")
            self.assertEqual(self._merges(state), [],
                             "no merge on a 403 approve POST")
            # The failure must be prompt (not masked as a pending wait to the
            # 900s deadline).
            final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
            self.assertLess(final_clock - 1000000, 900,
                            "a 403 approve POST must fail promptly, not wait the 900s deadline (clock advanced %d)" % (final_clock - 1000000))
            # The valid current parked candidate (960) must cause the actual
            # POST (the attempt is recorded before the 403).
            import re
            calls = self._calls(state)
            posted_ids = set()
            for c in calls:
                if c[0] == "api" and len(c) >= 4 and c[1] == "-X" and c[2] == "POST":
                    m = re.search(r"actions/runs/(\d+)/approve$", c[3])
                    if m:
                        posted_ids.add(int(m.group(1)))
            self.assertIn(960, posted_ids,
                          "the valid parked candidate (960) must be the POST target (got %s)" % posted_ids)
            # No unrelated (ineligible) candidate may be approved.
            for ineligible in (970, 971):
                self.assertNotIn(ineligible, posted_ids,
                                 "the ineligible run %d must NOT be approved (got %s)" % (ineligible, posted_ids))
            # The fake must not reject any call (the approve POST is a known call).
            rejected = self._read_log(state, "fake_rejected.log")
            self.assertEqual(rejected, [],
                             "the fake must not reject any call on a 403 approve POST (got %s)" % rejected)

    # ------------------------------------------------------------------
    # Scenario 12b: candidate detail id mismatch (review gap B)
    # ------------------------------------------------------------------

    def test_candidate_detail_id_mismatch_no_post(self):
        """#604 review gap B: a valid parked candidate whose DETAIL GET
        returns a different .id (999) than the list (960) must NOT be
        approved. The current code's pr_eligible only typechecks .id (a
        positive number) and would POST 960 — assert no mutation (RED).
        The candidate DETAIL GET must be observed before asserting no post."""
        scenario = self._base_scenario()
        # A valid parked candidate (expected head, intended PR #566,
        # allowlisted workflow) visible at t+30. The list serves the correct
        # id 960; only the DETAIL GET returns .id=999 (detail_id) with all
        # the same workflow/head/PR metadata.
        run_960 = self._parked_run(960, "PR Validation",
                                   ".github/workflows/pr-validation.yml", 1, 20,
                                   self.EXPECTED_HEAD, available_at=1000030)
        run_960["detail_id"] = 999
        scenario["runs"] = [run_960]
        # The required checks are gated on the eligible approval, so the
        # workflow must approve 960 to unblock them (and must NOT, because
        # the detail id mismatches the list id).
        scenario["checks"] = [
            {"name": "PR Validation", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "pr-validation.yml",
             "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
            {"name": "Quality integration gate", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "quality-integration.yml",
             "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
            {"name": "Security", "state": "IN_PROGRESS",
             "event": "pull_request", "workflow": "security.yml",
             "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
             "done_at": 999999999, "final_state": "SUCCESS",
             "require_approved": [960]},
        ]
        with tempfile.TemporaryDirectory(prefix="604-detailid-") as raw:
            tmp = Path(raw)
            self._write_fake_bin(tmp)
            state = self._make_state(tmp, scenario)
            r = self._run_wait(tmp, state)
            env = self._github_env(tmp)
            # The candidate DETAIL GET must be observed (the workflow fetched
            # the detail for 960 to validate it) — asserted BEFORE no-post.
            calls = self._calls(state)
            detail_gets = self._run_detail_ids(calls)
            self.assertIn(960, detail_gets,
                          "the candidate DETAIL GET for 960 must be observed (got %s)" % detail_gets)
            # No approve POST for 960 (the detail id mismatches the list id).
            import re
            posted_ids = set()
            for c in calls:
                if c[0] == "api" and len(c) >= 4 and c[1] == "-X" and c[2] == "POST":
                    m = re.search(r"actions/runs/(\d+)/approve$", c[3])
                    if m:
                        posted_ids.add(int(m.group(1)))
            self.assertNotIn(960, posted_ids,
                             "no approve POST for 960 when the detail id mismatches the list id (got %s)" % posted_ids)
            # Fail closed (nonzero, no export).
            self.assertNotEqual(r.returncode, 0,
                                "a detail id mismatch must fail the wait closed (rc=%d)" % r.returncode)
            self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                             "no SYNC_EXPECTED_HEAD_SHA export on a detail id mismatch")
            # The fake must not reject any call (the detail GET is a known call).
            rejected = self._read_log(state, "fake_rejected.log")
            self.assertEqual(rejected, [],
                             "the fake must not reject any call on a detail id mismatch (got %s)" % rejected)

    # ------------------------------------------------------------------
    # Scenario 13: required-phase faults (item 3)
    # ------------------------------------------------------------------

    def test_required_checks_faults(self):
        """#604 item 3: required-phase faults must fail the wait closed
        (non-zero, no export, no merge), with the checks query reached and
        no fake rejection. The failure must be prompt (not masked as a
        pending wait to the 900s deadline)."""
        # 3a: fail or cancel with another pending -> fail promptly.
        with self.subTest(case="fail-with-pending"):
            scenario = self._base_scenario()
            scenario["checks"] = [
                {"name": "PR Validation", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "pr-validation.yml",
                 "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
                 "done_at": 1000090, "final_state": "FAILURE"},
                {"name": "Quality integration gate", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "quality-integration.yml",
                 "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
                 "done_at": 999999999, "final_state": "SUCCESS"},
                {"name": "Security", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "security.yml",
                 "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
                 "done_at": 999999999, "final_state": "SUCCESS"},
            ]
            with tempfile.TemporaryDirectory(prefix="604-fault-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "a failed required check (with another pending) must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on a failed required check")
                self.assertEqual(self._merges(state), [],
                                 "no merge on a failed required check")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                self.assertLess(final_clock - 1000000, 900,
                                "a failed required check must fail promptly, not wait the 900s deadline (clock advanced %d)" % (final_clock - 1000000))
        # 3b: malformed JSON -> non-zero promptly, not masked.
        with self.subTest(case="malformed-json"):
            scenario = self._base_scenario()
            scenario["checks_fault"] = "malformed"
            with tempfile.TemporaryDirectory(prefix="604-fault-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "a malformed-JSON checks query must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on a malformed-JSON checks query")
                self.assertEqual(self._merges(state), [],
                                 "no merge on a malformed-JSON checks query")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                self.assertLess(final_clock - 1000000, 900,
                                "a malformed-JSON checks query must fail promptly (clock advanced %d)" % (final_clock - 1000000))
        # 3c: API 401 -> non-zero promptly.
        with self.subTest(case="api-401"):
            scenario = self._base_scenario()
            scenario["checks_fault"] = "401"
            with tempfile.TemporaryDirectory(prefix="604-fault-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "a 401 checks query must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on a 401 checks query")
                self.assertEqual(self._merges(state), [],
                                 "no merge on a 401 checks query")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                self.assertLess(final_clock - 1000000, 900,
                                "a 401 checks query must fail promptly (clock advanced %d)" % (final_clock - 1000000))
        # 3d: unknown CLI rc error -> non-zero promptly.
        with self.subTest(case="rc-error"):
            scenario = self._base_scenario()
            scenario["checks_fault"] = "rc-error"
            with tempfile.TemporaryDirectory(prefix="604-fault-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "an unknown-CLI-rc checks query must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on an unknown-CLI-rc checks query")
                self.assertEqual(self._merges(state), [],
                                 "no merge on an unknown-CLI-rc checks query")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                self.assertLess(final_clock - 1000000, 900,
                                "an unknown-CLI-rc checks query must fail promptly (clock advanced %d)" % (final_clock - 1000000))
        # 3e: unknown CLI rc with VALID all-pass JSON -> non-zero promptly,
        # not masked as a pending wait (the fault is the rc, not garbage JSON).
        with self.subTest(case="rc-valid-json"):
            scenario = self._base_scenario()
            scenario["checks"] = self._green_checks()
            scenario["checks_fault"] = "rc-valid-json"
            with tempfile.TemporaryDirectory(prefix="604-fault-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "an unknown-CLI-rc checks query with valid all-pass JSON must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on an unknown-CLI-rc checks query with valid all-pass JSON")
                self.assertEqual(self._merges(state), [],
                                 "no merge on an unknown-CLI-rc checks query with valid all-pass JSON")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                self.assertLess(final_clock - 1000000, 900,
                                "an unknown-CLI-rc checks query with valid all-pass JSON must fail promptly, not wait the 900s deadline (clock advanced %d)" % (final_clock - 1000000))

    # ------------------------------------------------------------------
    # Scenario 14: required-gate 900s deadline from phase start (item 4)
    # ------------------------------------------------------------------

    def test_required_gate_900s_deadline_from_phase_start(self):
        """#604 item 4: the required-checks gate must run 900s from the start
        of the required phase (separate from the 1800s dispatch deadline).
        Dispatch success after 90s + forever-pending required checks must
        advance 900s from the start of the required phase, with all sleeps
        30s. The current code fails required-pending early (intentionally
        RED: the clock assertion will fail)."""
        # 4a: checks pending forever -> 900s deadline.
        with self.subTest(case="pending-forever"):
            scenario = self._base_scenario()
            scenario["checks"] = [
                {"name": "PR Validation", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "pr-validation.yml",
                 "link": "https://github.com/%s/actions/runs/101" % self.GH_REPO,
                 "done_at": 999999999, "final_state": "SUCCESS"},
                {"name": "Quality integration gate", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "quality-integration.yml",
                 "link": "https://github.com/%s/actions/runs/102" % self.GH_REPO,
                 "done_at": 999999999, "final_state": "SUCCESS"},
                {"name": "Security", "state": "IN_PROGRESS",
                 "event": "pull_request", "workflow": "security.yml",
                 "link": "https://github.com/%s/actions/runs/103" % self.GH_REPO,
                 "done_at": 999999999, "final_state": "SUCCESS"},
            ]
            with tempfile.TemporaryDirectory(prefix="604-gate900-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "forever-pending required checks must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on forever-pending required checks")
                self.assertEqual(self._merges(state), [],
                                 "no merge on forever-pending required checks")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                first_clock = checks_calls[0]["clock"]
                last_clock = checks_calls[-1]["clock"]
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                # The gate must run to its 900s timeout from the start of the
                # required phase: the final fake clock (when the loop exits and
                # the step fails) is first+900. The last query lands in
                # [first+870, first+900] — a `<deadline` loop queries at
                # first+870 then sleeps to first+900; a query-then-check loop
                # queries at first+900 and fails without the trailing sleep.
                self.assertEqual(final_clock - first_clock, 900,
                                 "the gate must time out 900s from the start of the required phase "
                                 "(first=%d final=%d)" % (first_clock, final_clock))
                self.assertGreaterEqual(last_clock, first_clock + 870,
                                        "the last checks query must land in the final 30s of the gate "
                                        "(first=%d last=%d)" % (first_clock, last_clock))
                self.assertLessEqual(last_clock, first_clock + 900,
                                     "the last checks query must not exceed the 900s gate deadline "
                                     "(first=%d last=%d)" % (first_clock, last_clock))
                sleeps = self._read_log(state, "sleeps.log")
                self.assertTrue(sleeps, "the fake clock must advance via sleep")
                for s in sleeps:
                    self.assertEqual(s["interval"], 30,
                                     "all sleeps must be 30s (got %d)" % s["interval"])
        # 4b: empty checks with rc 0 -> 900s deadline (empty is never green).
        with self.subTest(case="empty-rc0"):
            scenario = self._base_scenario()
            scenario["checks"] = []
            scenario["checks_exit_override"] = 0
            with tempfile.TemporaryDirectory(prefix="604-gate900-") as raw:
                tmp = Path(raw)
                self._write_fake_bin(tmp)
                state = self._make_state(tmp, scenario)
                r = self._run_wait(tmp, state)
                env = self._github_env(tmp)
                self.assertNotEqual(r.returncode, 0,
                                    "empty checks with rc 0 must fail the wait (rc=%d)" % r.returncode)
                self.assertNotIn("SYNC_EXPECTED_HEAD_SHA", env,
                                 "no SYNC_EXPECTED_HEAD_SHA export on empty checks with rc 0")
                self.assertEqual(self._merges(state), [],
                                 "no merge on empty checks with rc 0")
                checks_calls = self._read_log(state, "checks_calls.log")
                self.assertTrue(checks_calls, "the checks query must be reached")
                first_clock = checks_calls[0]["clock"]
                last_clock = checks_calls[-1]["clock"]
                final_clock = int((state / "clock").read_text(encoding="utf-8").strip())
                # The gate must run to its 900s timeout from the start of the
                # required phase: the final fake clock (when the loop exits and
                # the step fails) is first+900. The last query lands in
                # [first+870, first+900] — a `<deadline` loop queries at
                # first+870 then sleeps to first+900; a query-then-check loop
                # queries at first+900 and fails without the trailing sleep.
                self.assertEqual(final_clock - first_clock, 900,
                                 "the gate must time out 900s from the start of the required phase "
                                 "(first=%d final=%d)" % (first_clock, final_clock))
                self.assertGreaterEqual(last_clock, first_clock + 870,
                                        "the last checks query must land in the final 30s of the gate "
                                        "(first=%d last=%d)" % (first_clock, last_clock))
                self.assertLessEqual(last_clock, first_clock + 900,
                                     "the last checks query must not exceed the 900s gate deadline "
                                     "(first=%d last=%d)" % (first_clock, last_clock))
                sleeps = self._read_log(state, "sleeps.log")
                self.assertTrue(sleeps, "the fake clock must advance via sleep")
                for s in sleeps:
                    self.assertEqual(s["interval"], 30,
                                     "all sleeps must be 30s (got %d)" % s["interval"])


if __name__ == "__main__":
    unittest.main()
