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
  invalid JSON fails loudly. RF-001: on a checks-green tick the gate
  fetches a FRESH PR raw, re-validates the same HEAD/identity, and applies
  a schema-validating readiness oracle — `mergeable` present boolean-or-
  explicit-null, `mergeable_state` present nonempty string, and only
  `mergeable == true && mergeable_state == "clean"` is ready; a valid
  non-ready state logs `SYNC_MERGE_NOT_READY` truth and waits inside the
  SAME 900s/30s budget (no deadline reset, no extension), while
  missing/mistyped fields, invalid JSON and API/auth faults fail closed
  immediately. `SYNC_EXPECTED_HEAD_SHA` is exported to
  `GITHUB_ENV` only after checks AND readiness pass on the same fresh
  fetch (the former post-loop identity-only revalidation is subsumed — no
  duplicate GET after the positive oracle).
- "Squash-merge the auto-sync PR" — requires a valid 40-hex
  `SYNC_EXPECTED_HEAD_SHA` export, independently REST-revalidates the PR
  (same identity guard plus `head.sha == SYNC_EXPECTED_HEAD_SHA`), then
  re-applies the SAME readiness oracle to that fresh pre-merge GET — a
  readiness regression after the wait fails the step BEFORE any
  `gh pr merge` call — then
  merges with the preserved squash/delete-branch/subject form plus
  `--match-head-commit "${SYNC_EXPECTED_HEAD_SHA}"`; never `--admin`. The
  export prevents drift between the phases; the gh flag closes the
  GET->merge race (a residual race after the GET remains; an actual
  merge-policy rejection must surface as a nonzero exit, never a success
  claim).

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
- **Readiness is an oracle, not authority (RF-001)**: the live 2026-11-05
  denial (pinned merge rejected by base branch policy one second after the
  checks exported green; PR metadata CLEAN moments later) showed
  checks-green is not merge-ready. The correction adds a conservative
  fresh-GET readiness oracle inside the SAME gate budget and re-applies it
  at the merge — it can only hold or fail the flow, never force a merge;
  the actual merge policy stays the final authority (its rejection is
  nonzero, never a success claim). The exact live policy cause remains
  unproven; no rollback, manual PR mutation or retry was performed.
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
  the delivery orchestrator / code worker. The same holds for the RF-001
  round: the independent test peer's PASS (session
  ses_e4ea98648ffev5YuuOPR3rSxkQ) was a READ-ONLY STATIC review — never an
  executed run.
- GREEN (a2 review-fix round, code-worker-observed; HISTORICAL — the
  pre-RF-001 module): full module `python3 -W error::ResourceWarning -m
  unittest tests.test_sync_tasks_md_flow -v` — "Ran 31 tests / OK"
  (31/31); focused class `... tests.test_sync_tasks_md_flow.
  SyncWaitMergeShellTests -v` — "Ran 16 tests / OK" (16/16); tests
  byte-frozen at 6db6b1d4… before/after.
- RF-001 RED (parent-observed, 2026-11-06, against the pre-readiness
  workflow db28b3ef… on source 968e402…): the parent personally ran the
  WHOLE re-frozen module (41 methods = 31 prior + 10 additive readiness
  cases) with `python3 -W error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow -v`: 17 failures, ALL inside the ten new
  readiness methods (blocked-until-clean, null/unknown, the 6 non-ready
  combos, persistent-block 900s, head-drift-while-waiting, the 6 schema
  cases, readiness-mutated-before-merge); the prior 31 methods green;
  Ruff (configured) PASS and `git diff --check` clean at RED.
- RF-001 GREEN (a2 correction round, code-worker-observed; parent re-runs):
  full module — "Ran 41 tests in 82.232s / OK" (41/41, zero skips); focused
  class — "Ran 26 tests / OK" (26/26); tests byte-frozen at
  6feec92ae1f81a1398cb1a190f3c5fa8b7418644 before/after (cmp against the
  parent's frozen copy OK); no test edits by the code worker.
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
- RISK-004 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: RF-001 adds ONLY a conservative server-readiness oracle — a fresh-GET schema check (mergeable boolean-or-explicit-null, mergeable_state nonempty string) plus the affirmative mergeable==true && mergeable_state=="clean" verdict, holding inside the SAME 900s/30s gate budget and re-applied by the merge step before any gh pr merge call; no rollback was performed, no manual PR #566 mutation, no retry, no token/trigger repair — none is authorized. The triggering live failure is recorded as evidence, not explained away: natural sync run 42019841101 (job 127219543008) on source 968e402… exported the required checks green at 2026-11-05 11:35:48Z and the pinned merge was denied at 11:35:49Z ("base branch policy prohibits the merge"), with the PR-side Quality aggregate finishing 11:36:15Z and later PR metadata CLEAN | Validation: the ten additive frozen readiness cases (AC-017) execute the real run blocks against the fake harness; the live policy behavior stays PENDING the fresh natural end-to-end acceptance (AC-016) | Residual risk: the EXACT GitHub-side policy cause of the 2026-11-05 denial remains UNPROVEN — readiness convergence is consistent with it, but the oracle can only hold or fail the flow closed, never prove the policy cause or force a merge; an actual merge-policy rejection must stay a nonzero exit with no success claim | Owner: delivery orchestrator | Status: ACCEPTED

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
- TEST-011 | Covers: RF-001 readiness oracle — blocked-until-clean holds past checks-green then one pinned merge after convergence; null/unknown pending then clean; six schema-valid non-ready combos never export/merge; persistent block times out at exactly 900s from the gate's own start; check failure and head drift while waiting readiness fail promptly; six invalid schema shapes and malformed/401 PR GETs fail closed with the PR GET observed; readiness mutation before the merge blocks with no merge call; actual merge-API policy rejection = exactly one pinned call, nonzero, no echoed success | Level: integration | Priority: P0 | Evidence: test_readiness_blocked_until_clean_then_merge, test_readiness_null_unknown_then_clean, test_readiness_combinations_nonready, test_readiness_persistent_blocked_900s_deadline, test_check_failure_while_waiting_readiness, test_head_drift_while_waiting_readiness, test_readiness_schema_invalid, test_readiness_pr_get_faults, test_readiness_mutated_before_merge, test_merge_api_rejects_policy observed ok (a2 correction round, whole module 41/41)

## Correct-course check

- Trigger: NONE
  Classification rationale: RF-001 is live control-plane CI feedback (the
  sync workflow's own merge step denied a mergeable-looking run), not a
  production runtime or deployment failure, so PRODUCTION_LEARNING does not
  apply; the readiness-oracle architecture is unchanged in kind (no
  ARCHITECTURE_PIVOT) and the admitted five-path file scope is unchanged
  (no MATERIAL_SCOPE_CHANGE). The trigger is therefore NONE, but the live
  failure still produced real, non-NONE impacts recorded below.
- Issue impact: RF-001 live failure recorded as the correction cause — sync
  run 42019841101 (job 127219543008) went checks-green at 2026-11-05
  11:35:48Z, then the pinned merge was denied at 11:35:49Z ("base branch
  policy prohibits the merge") while the run still exported success; the
  gate trusted checks-green alone and never consulted PR mergeability.
- Specification impact: RF-001 continuation block added (live base 968e402
  vs historical 62323eea), outcome restated, SC-6, rules R-5a/R-5b, R-6
  guard extension, R-7 frozen-test hash 6feec92, AC-017, NFR-001/003/004.
- Plan impact: readiness-oracle architecture and decision records, Validation
  section RF-001 RED/GREEN evidence (41/17 parent-observed RED; 41/41 module
  plus 26/26 focused GREEN), RISK-004, TEST-011.
- Tasks impact: T-5 marked done, T-6 added unchecked (fresh natural
  acceptance), completion-gate RF-001 records, AC-017 traceability row, DoD
  updated to frozen-test hash 6feec92 with counts 41/26.
- Authorization impact: UNCHANGED — same five admitted paths; original
  receipt issue #604 comment 6626966726 (base 62323eea); RF-001 continuation
  receipt comment 6657166153 (base 968e402 = current origin/main, reached
  via own prior PR #605). No new paths, no scope expansion, no new approvals.
- Follow-up: T-6 fresh natural end-to-end acceptance is pending — RF-001
  stays open until a live sync run converges and merges under the new
  readiness gate. Historical note: the earlier security-review
  REQUEST_CHANGES round (three workflow shell gaps + SDD truth gaps) was
  already fixed inside the admitted scope in the a2/a3 review-fix rounds
  with zero test edits by the code worker.
