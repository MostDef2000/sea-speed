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
        # RF-020 (live, run 40325903845 / PR #563, 2026-10-26): pull_request
        # runs DO fire for a bot-authored auto-sync PR but are PARKED as
        # action_required, and the ruleset's required context evaluates on
        # them — the flow must approve every parked run on the branch via the
        # REST actions-approve endpoint before polling.
        self.assertIn('gh api "repos/${GH_REPO}/actions/runs?branch=${BRANCH}&status=action_required&per_page=30" --jq \'.workflow_runs[].id\'', runs)
        self.assertIn('gh api -X POST "repos/${GH_REPO}/actions/runs/${rid}/approve"', runs)
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
        self.assertIn("*\"no checks reported\"*)", runs)
        # RF-008 (live): parked approval-gated pull_request runs carry HIGHER
        # run_numbers than the dispatched ones — the poll must exclude them
        # or it can never observe success. (The workflow stores the jq filter
        # with shell-escaped quotes, hence the literal backslashes below.)
        self.assertIn('and .conclusion != \\"action_required\\"', runs)
        # Final gate consistent with the ruleset: required contexts green on
        # the head SHA.
        self.assertIn('gh pr checks "${PR_NUMBER}" --required', runs)


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


if __name__ == "__main__":
    unittest.main()
