# Plan — Issue #604 exact-head/run wait + safe late approval + head-pinned merge

- Issue: #604
- Spec: specs/604-sync-check-wait/spec.md
- Base: 62323eea (origin/main); the working-tree workflow baseline blob
  993abd7 carried the already-merged #595 one-line owner fix as an
  uncommitted change that this task preserves (never reset/stashed).

## Architecture

Two run blocks in `.github/workflows/sync-merged-tasks.yml`:

- "Trigger and wait for the auto-sync PR required checks" — rewritten around
  four primitives: (1) an identity guard (`EXPECTED_HEAD_SHA` from
  `git rev-parse HEAD`, 40-hex validated; PR REST-validated as open,
  non-draft, bot-authored, on `BRANCH@EXPECTED_HEAD_SHA`, head/base in
  `GH_REPO` with equal repo ids, base `main`; the cached `base.sha` is
  deliberately not compared with `SOURCE_SHA`); (2) REST-resolved workflow
  identities for the three fixed paths with only the two required ones
  dispatched via the pinned `gh workflow run <file>.yml --ref "${BRANCH}"`
  literals, each dispatch accepted only with exactly one canonical
  `https://github.com/${GH_REPO}/actions/runs/<positiveID>` URL extracted
  from combined stdout+stderr as a WHOLE whitespace-delimited token
  matching the full canonical form (bash regex; a digit-truncated suffixed
  token such as `…/runs/<id>garbage` is not canonical and fails;
  `SYNC_DISPATCH_URL_INVALID` otherwise, no latest/list fallback); (3) an
  exact-ID poll of the two dispatched runs (detail GETs, metadata
  re-validated every poll, known pending statuses wait, completed
  non-success fails, unknown fatal, 1800s/30s); (4) a parked-run sweep on
  every tick of both phases — `status=action_required` list at
  `per_page=100` parsed as raw JSON by real jq against a fixed workflow
  id+path allowlist, current head/ref/repository/head_repository and the
  intended minimal PR association (number, head.ref, head.sha, head.repo.id,
  base.ref=main, base.repo.id), each candidate re-fetched (run detail + PR)
  before its `gh api -X POST .../actions/runs/<id>/approve`, the re-fetched
  detail's own `.id` bound to the requested run id (mismatch fails closed
  before the POST), deduplicated per (run id, attempt), with a bounded
  single-page guard (total_count > 100 fails closed). The separate required
  gate (900s/30s) reads `gh pr checks --required --json
  bucket,name,state,event,workflow,link`: only CLI exit codes 0 (finished)
  and 8 (pending) are accepted — any other code fails promptly BEFORE the
  payload is interpreted; within rc 0/8, non-empty + all pass/skipping with
  rc 0 is the only green, rc 8 / pending / empty wait, fail/cancel wins,
  invalid JSON fails loudly. `SYNC_EXPECTED_HEAD_SHA` is exported to
  `GITHUB_ENV` only after both gates plus a final identity pass.
- "Squash-merge the auto-sync PR" — requires a valid 40-hex
  `SYNC_EXPECTED_HEAD_SHA` export, independently REST-revalidates the PR
  (same identity guard plus `head.sha == SYNC_EXPECTED_HEAD_SHA`), then
  merges with the preserved squash/delete-branch/subject form plus
  `--match-head-commit "${SYNC_EXPECTED_HEAD_SHA}"`; never `--admin`. The
  export prevents drift between the phases; the gh flag closes the
  GET->merge race.

## Decisions

- **Exact IDs over names**: the old `max_by(.run_number)` name poll could
  observe a stale run's conclusion; polling the dispatched run IDs removes
  the whole stale-history class (proven by the stale-history test).
- **Whole-token canonical URLs**: the dispatch URL must be an entire
  whitespace-delimited token matching the full canonical form — a numeric
  prefix truncated out of a suffixed token (`…/runs/<id>garbage`) must
  never be accepted as a run id.
- **Detail id bound to the requested id**: a parked candidate is selected
  by its list id; before its approve POST the re-fetched detail must still
  carry `.id == <requested rid>` — a list/detail id mismatch fails closed.
- **Allowlist, not blanket approval**: the old step approved every parked
  run on the branch. The sweep approves only the fixed three workflows on
  the intended PR/head; Security stays approval-eligible but is never
  dispatched (it is not a required dispatch target, only an approval
  candidate).
- **Revalidate before every POST and every poll**: list data is stale by
  construction; the detail GET plus PR GET before each approve, and the
  per-tick identity checks, keep decisions on fresh evidence. Dedup is per
  (run id, attempt) so a stale action_required state cannot cause a second
  POST.
- **Structured required gate**: `gh pr checks --json` replaces the text
  grep; bucket semantics (pass/fail/pending/skipping/cancel) are evaluated
  explicitly, empty arrays are never green, and the CLI's own exit code is
  authoritative — only 0/8 are accepted, any other code fails promptly
  before the JSON is used rather than being masked as pending.
- **Head pin at the merge**: `SYNC_EXPECTED_HEAD_SHA` is exported only
  after both gates and revalidated by the merge step; `--match-head-commit`
  closes the residual race. No push/reuse/#595 behavior is touched.
- **No new dependencies**: bash builtins, jq and the existing gh/git/date
  surface only; the test harness proves curl/wget sentinels stay unused.

## Affected contours

- CONTROL_PLANE — `.github/workflows/sync-merged-tasks.yml` (wait step run
  block + adjacent merge step run block, incl. the merge step's added
  `BRANCH` env) and this SDD trio; classified CONTROL_PLANE by
  data/contracts/change-control-policy-v1.json (`.github/workflows/`).
- VPS / Ubuntu worker — NOT affected: api/**, frontend/**, deploy/**
  untouched; no deployment transaction audit (the validator derives that
  requirement only for deploy paths, deployment workflows or a
  PRODUCTION_LEARNING trigger — none apply).
- tests/test_sync_tasks_md_flow.py — whole-issue scope (five paths) but
  test-protected in the code phase: authored in RED by the test specialist
  (current frozen git blob 6db6b1d4710c487d9add9c73456e327a2d52b488; the
  initial RED freeze was d7307eec1e9ec96ae8e1d7f0ce8d893e3d45b822) and
  preserved byte-identical by the code worker; no other tests/** path is
  touched.
- All other workflows, scripts, specs, source and config untouched; the
  prior foreign dirty/untracked working-tree files (583/595/594 artifacts)
  are preserved as-is.

## Validation

- RED (delivery orchestrator-executed, before the code fix): the initial
  frozen module failed against the old workflow — the RED run covered the
  WHOLE module, 30 test methods at that time (the new
  `SyncWaitMergeShellTests` class contributed 15 of them), 37 sub-failures,
  exit 1.
- Review-gap RED (parent-observed, after the test specialist additively
  added the security-review gap cases — the module is now 31 test methods):
  exactly 3 authentic failures — (A) dispatch mode `numeric-suffix`
  accepted with rc 0; (B) parked candidate 960 approved although its detail
  `.id` (999) mismatched the requested id; (C) checks fault `rc-valid-json`
  (valid all-pass JSON, CLI rc 137) masked as a pending wait to the 900s
  deadline (parent log: "Ran 31 tests … FAILED (failures=3)").
- Peer truth: the test peer's PASS was a READ-ONLY STATIC review only
  (shell execution denied to the peer); the peer never re-ran the suite.
  All test execution — the RED runs and the GREEN runs — was performed by
  the delivery orchestrator / code worker.
- GREEN (a2 review-fix round, code-worker-observed; parent re-runs): full
  module `python3 -W error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow -v` — "Ran 31 tests / OK" (31/31); focused
  class `... tests.test_sync_tasks_md_flow.SyncWaitMergeShellTests -v` —
  "Ran 16 tests / OK" (16/16); tests byte-frozen at 6db6b1d4… before/after.
- Gates: `python3 scripts/ci/validate_sdd.py`,
  `python3 scripts/quality/validate_workflow_policy.py`,
  `ruff check --config scripts/quality/ruff.toml .`,
  `git diff --check` — observed outputs in the completion gate.
- Pending by design (not prechecked): PR CI, exact-green-head merge, and
  the live wait/approve/merge + genuine no-op follow-up of the next real
  sync run (see RISK-002) — the auto-sync flips the recognized completion
  markers after merge.

## Runtime feedback

- CI is the first runtime for this change (workflow policy + structural
  pins on the PR head). The real acceptance scenario is automatic and
  PENDING observation: the first post-merge sync run with a tasks.md delta
  runs the new wait/sweep/gate/merge path against real GitHub on the open
  bot auto-sync PR, and the follow-up sync run on the merged main must be
  a GENUINE no-op. Runtime acceptance must observe a fresh natural
  push/main Quality run on the bot merge SHA and the follow-up sync
  actually running its marker stage (not a stale guard) before #604/#595
  are closed; see RISK-002 for the push-suppression boundary. Failure modes
  fail closed (identity, dispatch, approval, gate and drift faults all exit
  nonzero before any merge); rollback of the change itself is a normal
  revert PR through the standard review/CI gates — never a manual
  `git revert`/push directly on main.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: every selection is exact (run IDs, whole-token canonical URLs, workflow id+path pairs, PR association, head SHA, detail .id == requested id) and every fault path fails closed; the 16-method class executes the real run blocks against a stateful fake REST gh with real jq | Validation: a2 review-fix round observed full module "Ran 31 tests / OK" and focused class "Ran 16 tests / OK" (parent re-run pending) | Residual risk: a GitHub API shape change outside the faked surface would fail the step loudly (fail-closed), never merge wrongly | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the live wait/approve/merge path is exercised automatically by the next post-merge sync run; until then the live claim is explicitly pending, not asserted. Documented boundary (architect chain review): the merge credentials are unchanged (GITHUB_TOKEN), and push events authored by github-actions[bot] may be suppressed from triggering follow-up workflows — the follow-up no-op sync run may not fire after the automatic merge; token/trigger/env/secret behavior is out of scope for this change | Validation: PENDING — runtime acceptance must observe a fresh natural push/main Quality run on the bot merge SHA and the follow-up sync actually running its marker stage (not a stale guard) before #604/#595 close; if the no-op does not fire naturally, record the blocker and admit separate scope for transport/triggers — never fake it via ad-hoc dispatch or manual PR #566 mutation | Residual risk: until that observation, behavior is proven only against the fake harness (accepted; it reproduces the documented REST semantics) | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the sweep cannot widen authority — it only approves parked runs of the intended PR via the existing actions:write token, with the detail id bound to the requested id before each POST; a 403 fails the run promptly and no --admin path exists | Validation: 403 and detail-id-mismatch cases assert prompt failure, exact POST target and no export | Residual risk: none identified | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: happy path — expected-head export after both gates, two path dispatches, exact-ID polling, isolated merge revalidation with --match-head-commit | Level: integration | Priority: P0 | Evidence: tests/test_sync_tasks_md_flow.py::SyncWaitMergeShellTests::test_happy_wait_merge_pins_expected_head_and_exact_polls observed ok
- TEST-002 | Covers: stale history immunity — higher-run-number stale runs can neither green nor fail the exact-ID poll | Level: integration | Priority: P0 | Evidence: test_stale_history_cannot_cause_early_green_or_fail observed ok
- TEST-003 | Covers: dispatch URL contract — absent/two-ids/wrong-repo/malformed/numeric-suffix/nonzero rejected, stderr URL accepted | Level: integration | Priority: P0 | Evidence: test_dispatch_url_validation observed ok (7 URL subtests)
- TEST-004 | Covers: PR identity guard — eight invalid-PR mutations fail closed with no approval/export/merge | Level: integration | Priority: P0 | Evidence: test_invalid_pr_no_approval_no_merge observed ok (8 subtests)
- TEST-005 | Covers: late approval — phased visibility, once-per-(id,attempt), ineligible candidates never approved, Security eligible but not dispatched | Level: integration | Priority: P0 | Evidence: test_late_approval_security_and_narrow_approve observed ok
- TEST-006 | Covers: dispatch failure and metadata mismatch fail-closed paths incl. detail/workflow-metadata faults and the candidate detail-id-mismatch no-POST case | Level: integration | Priority: P0 | Evidence: test_dispatch_failure_no_merge, test_dispatch_metadata_mismatch_fails_closed, test_candidate_detail_id_mismatch_no_post, test_run_detail_malformed_json_and_401, test_workflow_metadata_malformed_and_401 observed ok
- TEST-007 | Covers: approval 403 prompt failure with narrow POST target | Level: integration | Priority: P0 | Evidence: test_approval_403_fails_closed observed ok
- TEST-008 | Covers: required gate — pending-then-pass, fail-wins, fault prompts (incl. unknown CLI rc with valid all-pass JSON failing promptly), 900s phase deadline, empty-never-green | Level: integration | Priority: P0 | Evidence: test_required_checks_gate, test_required_checks_faults, test_required_gate_900s_deadline_from_phase_start, test_fake_clock_timeouts_no_merge observed ok
- TEST-009 | Covers: merge pinning — head drift and missing export block the merge | Level: integration | Priority: P0 | Evidence: test_merge_head_changed_and_missing_export observed ok (3 subtests)
- TEST-010 | Covers: safety preservation — structural pins (token split, strict shell, push retry, REST-only PR lifecycle, squash merge, no name-max poll) and the generic workflow policy | Level: integration | Priority: P0 | Evidence: WorkflowStructuralPinTests observed ok + validate_workflow_policy.py exit 0

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none required — the security-review REQUEST_CHANGES round
  (three workflow shell gaps + SDD truth gaps) was fixed inside the
  admitted scope in the a2/a3 review-fix rounds with zero test edits by
  the code worker: no production learning, architecture pivot, material
  scope change or scope expansion surfaced (the code phase stayed inside
  its admitted four-path file set: the two workflow run blocks plus this
  trio, with tests/** frozen). The only open item is the pending live
  acceptance (AC-016 / RISK-002).
