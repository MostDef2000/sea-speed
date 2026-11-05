# Spec: #604 — Sync flow: exact-head/run wait, safe late approval, head-pinned merge

- Issue: #604
- Spec: specs/604-sync-check-wait/spec.md
- Plan: specs/604-sync-check-wait/plan.md
- Tasks: specs/604-sync-check-wait/tasks.md
- Base: 62323eea (origin/main content baseline; local HEAD f7d485f is
  content-identical to it on the workflow path; the working-tree workflow
  baseline blob 993abd7 additionally carried the already-merged #595
  one-line owner fix as an uncommitted change that must not be reset).
- Authorization: the #604 whole-issue scope — five paths — admitted by the
  delivery orchestrator (canonical receipt: issue #604 comment
  6626966726; RED/freeze checkpoint: comment 6628705454): (1) the wait step
  and adjacent merge step of `.github/workflows/sync-merged-tasks.yml`
  (incl. their env blocks), (2) the test module
  `tests/test_sync_tasks_md_flow.py` (test specialist, RED phase; frozen at
  git blob 6db6b1d4710c487d9add9c73456e327a2d52b488 — the initial RED
  freeze d7307eec1e9ec96ae8e1d7f0ce8d893e3d45b822 plus the security-review
  gap cases added by the test specialist), and (3-5) this SDD trio. The
  code phase edits only the two workflow run blocks and keeps the test
  module byte-identical.

## Product outcome

The tasks.md auto-sync flow's wait step approved EVERY parked workflow run
on the sync branch and polled check results by workflow display name plus
max `run_number`. Both selections are history-based: a stale run from a
previous head could green-light (or fail) the current sync, and any parked
run on the branch was approved regardless of which PR, head or workflow it
belonged to. The merge then ran without pinning the head it had validated,
so a drift between validation and merge could merge a different commit.

After this change the wait step pins `EXPECTED_HEAD_SHA` to the NEW local
bot commit (`git rev-parse HEAD`, never `SOURCE_SHA`), validates the
auto-sync PR's identity against it, resolves the three fixed workflow
identities from REST metadata, dispatches only the two required workflows
accepting each dispatch only with exactly one canonical run URL, polls the
EXACT dispatched run IDs until completed-success, sweeps approval-eligible
parked `pull_request` runs on every tick of both wait phases under a fixed
workflow id+path / head / repository / PR-association allowlist (each
candidate re-fetched before its approve POST, once per run id+attempt),
runs the structured required-checks gate for its own 900s budget, exports
`SYNC_EXPECTED_HEAD_SHA` only after both gates, and the merge step
revalidates the PR independently and pins the head with
`--match-head-commit`. Everything else — token split, push retry, PR
create/reuse, permissions, concurrency — is unchanged.

## User scenarios

- SC-1: the sync PR's parked pull_request runs appear late (approval
  parking) — only runs on the expected head/ref/repository with the
  intended PR association and an allowlisted workflow are approved, each
  exactly once; fork/other-PR/stale-head/null-association/unknown-workflow
  runs are never approved even when other checks are wide green.
- SC-2: a stale run from a previous sync head exists with a higher run
  number — the exact-ID poll ignores it: no early green, no false failure.
- SC-3: a dispatch returns no URL, two URLs, a wrong-repo URL, a
  non-canonical suffixed URL (…/runs/<id>garbage) or garbage — the step
  fails closed (`SYNC_DISPATCH_URL_INVALID`) with no merge.
- SC-4: the PR head drifts after a green wait — the merge step's
  independent revalidation plus `--match-head-commit` block the merge; no
  merge call is made.
- SC-5: a required check fails or the gates time out — the step fails
  closed before any export/merge; a 403 on an approve POST fails promptly
  instead of masquerading as a pending wait.

## Requirements

- R-1: the step "Trigger and wait for the auto-sync PR required checks"
  keeps its name and `set -euo pipefail`, derives `EXPECTED_HEAD_SHA` from
  `git rev-parse HEAD` (validated 40-hex), and REST-validates the PR
  (`repos/${GH_REPO}/pulls/${PR_NUMBER}`): open, non-draft,
  `github-actions[bot]` author, `head.ref == BRANCH`, `head.sha ==
  EXPECTED_HEAD_SHA`, head/base repo same id and `full_name == GH_REPO`,
  `base.ref == main`. The cached `base.sha` is deliberately NOT compared
  with `SOURCE_SHA`. No token or permissions change.
- R-2: the three fixed workflow identities (pr-validation.yml,
  quality-integration.yml, security.yml) are resolved from REST metadata
  (`repos/${GH_REPO}/actions/workflows`) by full path; only the first two
  are dispatched via the pinned literals
  `gh workflow run pr-validation.yml --ref "${BRANCH}"` and the
  quality-integration equivalent. Each dispatch's combined stdout+stderr
  must contain exactly one canonical
  `https://github.com/${GH_REPO}/actions/runs/<positiveID>` URL, matched
  as a WHOLE whitespace-delimited token (missing / multiple / wrong-repo /
  non-canonical, e.g. a digit-truncated suffixed token =>
  `SYNC_DISPATCH_URL_INVALID`, no list fallback); each dispatched run is
  then REST-fetched by ID and its metadata (id, workflow_id, path,
  event=workflow_dispatch, head_sha, head_branch, repository,
  head_repository) validated; faults fail closed.
- R-3: the dispatch poll targets the exact dispatched run IDs until both
  are completed-success within the existing 1800s/30s budget; queued /
  in_progress / requested / waiting / pending wait; any other completed
  conclusion fails; unknown or malformed states are fatal; identity is
  re-checked on every poll (the old name+max_by(.run_number) poll is
  removed).
- R-4: every tick of BOTH the dispatch wait and the separate final required
  gate sweeps parked `pull_request` runs (`status=action_required`,
  `per_page=100`, raw JSON + jq, bounded — no latest/list fallback): only
  the fixed three workflow id+path pairs on the current head/ref/repository
  and head_repository, with a `pull_requests` association matching this PR
  (number, head.ref, head.sha, head.repo.id, base.ref=main, base.repo.id),
  completed + conclusion action_required and a positive run_attempt, are
  eligible; each candidate's run detail and the PR are re-fetched and
  revalidated before the approve POST, and the re-fetched detail's own
  `.id` must equal the requested run id (a list/detail id mismatch fails
  closed before any approve POST); each (run id, attempt) is approved at
  most once even when the stale action_required state repeats; an approve
  403 fails the step promptly. Security stays approval-eligible and is
  never dispatched.
- R-5: the required gate is a separate 900s/30s phase after dispatch
  success, reading `gh pr checks "${PR_NUMBER}" --required --json
  bucket,name,state,event,workflow,link`: only CLI exit codes 0 (finished)
  and 8 (pending) are accepted — any other exit code fails promptly and
  loudly BEFORE the payload is interpreted (never masked as a pending
  wait, never empty-green). Within rc 0/8: a non-empty array whose buckets
  are all pass/skipping with rc 0 is the only green; rc 8 / pending /
  empty arrays wait bounded; fail/cancel wins over mixed pending; invalid
  JSON and API/auth errors fail loudly (never masked, never empty-green).
  PR identity is revalidated during the gate, and
  `SYNC_EXPECTED_HEAD_SHA` is exported to `GITHUB_ENV` only after both
  gates plus a final identity pass.
- R-6: the adjacent "Squash-merge the auto-sync PR" step keeps strict shell
  options, requires a valid 40-hex `SYNC_EXPECTED_HEAD_SHA` export,
  independently REST-revalidates the same PR identity including
  `head.sha == SYNC_EXPECTED_HEAD_SHA`, then merges with the preserved
  squash/delete-branch/subject form plus `--match-head-commit
  "${SYNC_EXPECTED_HEAD_SHA}"`; never `--admin`. A head drift after the
  wait produces no merge call.
- R-7: the test-protected #604 material in tests/test_sync_tasks_md_flow.py
  (class `SyncWaitMergeShellTests`, frozen at git blob
  6db6b1d4710c487d9add9c73456e327a2d52b488) passes unmodified during the
  code/GREEN phase, together with the structural pin and the whole module.

## Acceptance criteria

- AC-001: the real wait+merge run blocks, executed verbatim against the
  stateful fake gh/git/date/sleep harness, pin `SYNC_EXPECTED_HEAD_SHA` to
  the `git rev-parse HEAD` value (not SOURCE_SHA), dispatch exactly two
  workflows by path, poll both exact dispatched run IDs via run-detail
  GETs, and merge with `--match-head-commit <expected head>` after an
  isolated merge-side PR revalidation
  (test_happy_wait_merge_pins_expected_head_and_exact_polls).
- AC-002: stale history with higher run numbers can neither cause an early
  green nor a failure while the exact current dispatch is pending
  (test_stale_history_cannot_cause_early_green_or_fail).
- AC-003: dispatch outputs that are absent, duplicated, wrong-repo,
  malformed, numeric-suffixed (non-canonical) or CLI-failed are rejected
  with no export and no merge; a canonical URL on stderr is accepted
  (test_dispatch_url_validation).
- AC-004: a closed/draft/human-authored/head-sha-mismatch/fork-head/
  wrong-base-ref/wrong-base-repo/wrong-head-ref PR fails closed with no
  approval, no export and no merge (test_invalid_pr_no_approval_no_merge).
- AC-005: late-visibility eligible parked runs (PR Validation at t+30,
  Security at t+120) are approved exactly once each at the correct tick,
  while fork / wrong-PR / unknown-workflow / null-association / stale-head
  candidates are never approved; Security is approval-eligible but not
  dispatched (test_late_approval_security_and_narrow_approve).
- AC-006: a failed/cancelled/timed_out exact dispatch fails closed with no
  export and no merge (test_dispatch_failure_no_merge).
- AC-007: the structured required-checks gate goes green only on rc 0 with
  a non-empty all-pass/skipping array; a failed required check fails the
  wait (test_required_checks_gate).
- AC-008: fake-clock timeouts run the 1800s dispatch budget to its deadline
  with 30s sleeps and no merge (test_fake_clock_timeouts_no_merge).
- AC-009: the merge pins `--match-head-commit` with its own PR revalidation
  GET; a head drift after the wait and a missing export each block the
  merge with no merge call (test_merge_head_changed_and_missing_export).
- AC-010: corrupting any exact dispatch-metadata field fails the wait
  closed via the workflow's own run-detail validation, with the detail GET
  observed and no fake rejection
  (test_dispatch_metadata_mismatch_fails_closed).
- AC-011: malformed-JSON and 401 run-detail and workflow-metadata GETs fail
  the wait closed (test_run_detail_malformed_json_and_401,
  test_workflow_metadata_malformed_and_401).
- AC-012: an approve POST 403 fails promptly (well under the 900s gate
  budget), targets only the eligible candidate, and exports nothing
  (test_approval_403_fails_closed).
- AC-013: required-phase faults (fail-with-pending, malformed JSON, API
  401, unknown CLI rc — including unknown rc with valid all-pass JSON)
  fail promptly with the checks query reached
  (test_required_checks_faults).
- AC-014: the required gate runs exactly 900s from its own phase start with
  30s sleeps, and an empty checks array with rc 0 is never green
  (test_required_gate_900s_deadline_from_phase_start).
- AC-015: safety preservation — the committed workflow keeps its pinned
  safety shape (token split, strict shell options, push retry, tasks.md
  pathspec, REST-only PR lifecycle, squash merge, no direct main push, no
  name-max poll) and `scripts/quality/validate_workflow_policy.py` accepts
  it (WorkflowStructuralPinTests + policy validator).
- AC-016: runtime acceptance (automatic, orchestrator-owned, PENDING live —
  never dropped): after merge, the next real sync run with a tasks.md delta
  exercises the new flow live on the open bot auto-sync PR — automatic
  branch/PR reuse, required checks green on the exact PR head, the
  exact-green-head squash merge — and the FOLLOWING sync run on the merged
  main is a GENUINE no-op. Evidence must bind the exact sync run id/URL and
  source SHA, including a fresh natural push/main Quality run on the bot
  merge SHA and the follow-up sync actually running its marker stage (not
  a stale guard); observed and recorded on issue #604 after merge. Not
  producible at code-worker time; never dropped and never faked.

## Runtime feedback

- CONTROL_PLANE only: api/**, worker/**, deploy/**, frontend/** untouched;
  VPS and Ubuntu runtime contours unaffected; no deployment transaction
  audit (the validator derives that requirement only for deploy/** paths,
  deployment workflows, or a PRODUCTION_LEARNING trigger — none apply).
  The workflow itself is the runtime surface: after merge, the next merge
  carrying a tasks.md delta exercises the new wait/approval/merge flow live
  against real GitHub. All failure paths fail closed and loud. Rollback of
  the change itself goes through the normal PR/CI gates (a revert PR); no
  manual `git revert`/push directly on main.

## NFR assessment

- NFR-001 | Area: exact-head safety | Target: approvals and the merge are bound to the NEW local bot head (git rev-parse HEAD, 40-hex validated), never to SOURCE_SHA or a name-max history pick | Validation: the #604 class executes the real run blocks against the fake harness (happy path, stale history, head-drift, metadata-mismatch cases) | Evidence: a2 review-fix round, code-worker-observed: focused class "Ran 16 tests / OK"; full module "Ran 31 tests / OK" (parent re-run pending); earlier phase counts retained in tasks.md | Status: PASS
- NFR-002 | Area: narrow approval | Target: only allowlisted workflow id+path on the expected head/ref/repository with the intended PR association is approved, once per (run id, attempt), after detail+PR revalidation with the detail's own .id bound to the requested run id; ineligible runs are never approved | Validation: late-approval, 403 and detail-id-mismatch cases assert the exact approved/posted id sets and clock intervals | Evidence: test_late_approval_security_and_narrow_approve, test_approval_403_fails_closed, test_candidate_detail_id_mismatch_no_post observed ok | Status: PASS
- NFR-003 | Area: fail-closed errors | Target: dispatch URL (incl. non-canonical suffixed tokens), metadata, run-detail, workflow-metadata, approval and required-check faults fail the step nonzero, promptly, with no export and no merge; unknown states and unknown CLI exit codes are never masked as pending | Validation: fault scenarios assert rc, no export, no merge, prompt clock advance and observed API calls | Evidence: test_dispatch_url_validation, test_dispatch_metadata_mismatch_fails_closed, test_run_detail_malformed_json_and_401, test_workflow_metadata_malformed_and_401, test_approval_403_fails_closed, test_required_checks_faults observed ok | Status: PASS
- NFR-004 | Area: bounded waits | Target: 1800s/30s dispatch poll and a separate 900s/30s required gate measured from each phase's own start; empty checks with rc 0 never green | Validation: fake-clock timeout and 900s-deadline cases assert exact clock arithmetic and sleep intervals | Evidence: test_fake_clock_timeouts_no_merge and test_required_gate_900s_deadline_from_phase_start observed ok | Status: PASS
- NFR-005 | Area: minimality | Target: only the two run blocks (plus the merge step's env) change; no new helper file, module, dependency or framework; bash builtins + jq only | Validation: exact git diff inspection of the workflow; ruff and git diff --check clean | Evidence: gates observed in the completion gate; diff limited to the wait and merge steps | Status: PASS
