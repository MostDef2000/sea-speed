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
- RF-001 continuation (gen 6, 2026-11-06; receipt: issue #604 comment
  6657166153): the same five-path scope continues after the live pinned
  merge of the open auto-sync PR was denied by base branch policy at
  2026-11-05 11:35:49Z ("base branch policy prohibits the merge") one
  second after the required checks exported green (11:35:48Z), with the
  PR-side Quality aggregate finishing at 11:36:15Z and later PR metadata
  CLEAN — readiness convergence is consistent, but the EXACT policy cause
  is unproven. The correction adds the conservative server-readiness oracle
  (R-5/R-6, AC-017). Its code base is the CURRENT origin/main
  968e402aeac8bcdc6bae90e744b341d4f4da3359 (the originally admitted base
  62323eea is historical; the #604 trio merged to main via the prior
  correction PR). The test module was re-frozen by the parent at git blob
  6feec92ae1f81a1398cb1a190f3c5fa8b7418644 (the 6db6b1d review-gap freeze
  plus ten additive RF-001 readiness cases) and stays byte-identical
  through this code phase; no rollback, no manual PR mutation, no retry.

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
runs the structured required-checks gate for its own 900s budget, requires
— inside that same gate, on checks-green — a fresh-GET server readiness
oracle (`.mergeable == true` && `.mergeable_state == "clean"`,
schema-validated; a valid explicit null / false / non-clean state waits
within the same budget; missing/mistyped fields and API/JSON faults are
fatal), exports `SYNC_EXPECTED_HEAD_SHA` only after checks AND readiness
pass on the same fresh fetch, and the merge step revalidates the PR
independently (identity AND the same readiness guard, failing before any
merge call on a readiness regression) and pins the head with
`--match-head-commit`. Readiness is a conservative additional oracle, never
merge authority: the actual merge policy can still reject. Everything
else — token split, push retry, PR
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
- SC-6 (RF-001): the required checks are green but the server is not yet
  ready to merge (the live 2026-11-05 denial: pinned merge rejected by
  base branch policy one second after the checks exported green, PR
  metadata CLEAN moments later) — the gate holds within the SAME 900s/30s
  budget until a fresh PR GET reports `mergeable == true` &&
  `mergeable_state == "clean"`, logging `SYNC_MERGE_NOT_READY` truth; a
  readiness regression between the wait and the merge blocks the merge
  with no merge call; the actual merge policy can still reject (nonzero,
  no success claim).

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
  JSON and API/auth errors fail loudly (never masked, never empty-green).
  PR identity is revalidated during the gate, and
  `SYNC_EXPECTED_HEAD_SHA` is exported to `GITHUB_ENV` only after both
  gates plus the fresh readiness-validated fetch of R-5a.
- R-5a (RF-001 readiness oracle, conservative ADDITIONAL gate inside the
  same 900s/30s phase — never merge authority): on a checks-green tick the
  gate fetches a FRESH PR raw (`repos/${GH_REPO}/pulls/${PR_NUMBER}`,
  the existing GET), re-validates the same HEAD/identity via the existing
  `validate_pr_raw`, then requires explicit field presence/types —
  `mergeable` present and a boolean OR an explicit null;
  `mergeable_state` present, a NONEMPTY string — and the affirmative
  `.mergeable == true && .mergeable_state == "clean"` as the only ready
  verdict. A schema-valid explicit null / false / any non-clean state
  (known or unknown) is a valid non-ready pending wait inside the SAME
  budget (no deadline reset, no extra budget), logged as `SYNC_MERGE_NOT_READY`
  truth with the observed values; required checks and identity keep being
  evaluated every iteration (check failure/cancel stays fatal; no latched
  old green). Missing/mistyped fields, invalid JSON and API/auth faults
  fail immediately. The post-loop identity-only revalidation is replaced by
  the green break's own fresh fetch (no duplicate GET after the positive
  oracle); the pre-merge GET in the merge step stays independent. The
  timeout message covers checks AND readiness.
- R-5b: the readiness schema check is a jq program reused verbatim in both
  the wait gate and the merge guard: object type, `has("mergeable")` with
  boolean-or-explicit-null type, `mergeable_state` present nonempty
  string, then the affirmative `mergeable == true && mergeable_state ==
  "clean"` verdict ("ready" vs a truth-logged non-ready string).
- R-6: the adjacent "Squash-merge the auto-sync PR" step keeps strict shell
  options, requires a valid 40-hex `SYNC_EXPECTED_HEAD_SHA` export,
  independently REST-revalidates the same PR identity including
  `head.sha == SYNC_EXPECTED_HEAD_SHA`, then merges with the preserved
  squash/delete-branch/subject form plus `--match-head-commit
  "${SYNC_EXPECTED_HEAD_SHA}"`; never `--admin`. A head drift after the
  wait produces no merge call.
- R-6a (RF-001): the merge step's existing pre-merge REST GET guard is
  extended with the SAME readiness presence/type checks and the SAME
  affirmative condition (R-5b) on that fresh GET; a readiness regression
  after the wait fails the step (`SYNC_MERGE_NOT_READY`, schema faults
  `SYNC_API_INVALID`) WITHOUT any `gh pr merge` call. The single preserved
  merge form stays exactly
  `gh pr merge --squash --delete-branch --subject … --match-head-commit`;
  never `--auto`/`--admin`, no retry, no token/trigger/settings change.
  The residual race after the GET remains: an actual merge-policy
  rejection must surface as a nonzero exit, never a success claim.
- R-7: the test-protected #604 material in tests/test_sync_tasks_md_flow.py
  (class `SyncWaitMergeShellTests`, currently frozen at git blob
  6feec92ae1f81a1398cb1a190f3c5fa8b7418644 — the RF-001 readiness freeze;
  historical chain: initial RED freeze d7307eec…, review-gap freeze
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
- AC-017: RF-001 server readiness — the wait exports/merges only after a
  fresh-GET readiness oracle affirms `mergeable == true` &&
  `mergeable_state == "clean"` on a checks-green tick inside the SAME
  900s/30s budget: blocked-until-clean holds past the checks-green moment
  and merges exactly once with the pinned head after readiness converges;
  explicit null/unknown waits then succeeds; every other schema-valid
  combination (true/dirty, true/unknown, true/behind, false/clean,
  false/dirty, null/clean) never exports and never merges; persistent
  block times out at exactly 900s from the gate's own start; a check
  failure while waiting readiness fails promptly; a head drift while
  waiting readiness fails via the identity guard; all six invalid schema
  shapes (missing field, mistyped/empty/null state, string mergeable) and
  malformed/401 PR GETs fail closed with the PR GET observed and no fake
  rejection; a readiness mutation before the merge blocks the merge with
  no merge call; an actual merge-API policy rejection yields exactly ONE
  pinned merge call, nonzero, no echoed success
  (test_readiness_blocked_until_clean_then_merge,
  test_readiness_null_unknown_then_clean, test_readiness_combinations_nonready,
  test_readiness_persistent_blocked_900s_deadline,
  test_check_failure_while_waiting_readiness,
  test_head_drift_while_waiting_readiness, test_readiness_schema_invalid,
  test_readiness_pr_get_faults, test_readiness_mutated_before_merge,
  test_merge_api_rejects_policy).

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

- NFR-001 | Area: exact-head safety | Target: approvals and the merge are bound to the NEW local bot head (git rev-parse HEAD, 40-hex validated), never to SOURCE_SHA or a name-max history pick | Validation: the #604 class executes the real run blocks against the fake harness (happy path, stale history, head-drift, metadata-mismatch cases) | Evidence: RF-001 correction round, code-worker-observed: full module "Ran 41 tests / OK" and focused class "Ran 26 tests / OK" (`python3 -W error::ResourceWarning`, frozen blob 6feec92… before/after); HISTORICAL (pre-RF-001, a2 review-fix round): focused class 16/16 OK, full module 31/31 OK | Status: PASS
- NFR-002 | Area: narrow approval | Target: only allowlisted workflow id+path on the expected head/ref/repository with the intended PR association is approved, once per (run id, attempt), after detail+PR revalidation with the detail's own .id bound to the requested run id; ineligible runs are never approved | Validation: late-approval, 403 and detail-id-mismatch cases assert the exact approved/posted id sets and clock intervals | Evidence: test_late_approval_security_and_narrow_approve, test_approval_403_fails_closed, test_candidate_detail_id_mismatch_no_post observed ok | Status: PASS
- NFR-003 | Area: fail-closed errors | Target: dispatch URL (incl. non-canonical suffixed tokens), metadata, run-detail, workflow-metadata, approval, required-check and readiness-schema/readiness-GET faults fail the step nonzero, promptly, with no export and no merge; unknown states and unknown CLI exit codes are never masked as pending | Validation: fault scenarios assert rc, no export, no merge, prompt clock advance and observed API calls | Evidence: test_dispatch_url_validation, test_dispatch_metadata_mismatch_fails_closed, test_run_detail_malformed_json_and_401, test_workflow_metadata_malformed_and_401, test_approval_403_fails_closed, test_required_checks_faults, test_readiness_schema_invalid, test_readiness_pr_get_faults observed ok | Status: PASS
- NFR-004 | Area: bounded waits | Target: 1800s/30s dispatch poll and a separate 900s/30s required gate measured from each phase's own start; empty checks with rc 0 never green; RF-001 readiness waits share the gate's own 900s budget (no deadline reset, no extra budget) | Validation: fake-clock timeout, 900s-deadline and persistent-readiness-block cases assert exact clock arithmetic and sleep intervals | Evidence: test_fake_clock_timeouts_no_merge, test_required_gate_900s_deadline_from_phase_start and test_readiness_persistent_blocked_900s_deadline observed ok | Status: PASS
- NFR-005 | Area: minimality | Target: only the two run blocks (plus the merge step's env) change; no new helper file, module, dependency or framework; bash builtins + jq only | Validation: exact git diff inspection of the workflow; ruff and git diff --check clean | Evidence: gates observed in the completion gate; diff limited to the wait and merge steps | Status: PASS
