# Tasks — Issue #604 sync wait/approval/merge hardening

- Issue: #604
- Spec: specs/604-sync-check-wait/spec.md
- Plan: specs/604-sync-check-wait/plan.md
- Base: 62323eea (origin/main); working-tree workflow baseline blob 993abd7
  (carried the already-merged #595 one-line owner fix, preserved).
- RF-001 correction (gen 6, 2026-11-06): code base is the CURRENT origin/main
  968e402aeac8bcdc6bae90e744b341d4f4da3359 (62323eea is the historical
  admission base; the #604 trio merged to main via the prior correction
  PR). Triggering live failure: natural sync run 42019841101 (job
  127219543008) — required checks exported green 2026-11-05 11:35:48Z,
  pinned merge denied 11:35:49Z by base branch policy; EXACT policy cause
  unproven; no rollback / no manual PR #566 mutation / no retry performed.

## Delivery tasks

- [x] T-1 `.github/workflows/sync-merged-tasks.yml` — rewrite the run block
  of "Trigger and wait for the auto-sync PR required checks": expected-head
  pin + PR identity guard, REST workflow-identity resolution, two pinned
  dispatches with whole-token canonical-URL validation, exact-ID polling
  (1800s/30s), per-tick parked-run sweep with narrow approval (detail id
  bound to the requested run id), structured required gate (900s/30s, only
  CLI rc 0/8 accepted, others prompt-fatal), `SYNC_EXPECTED_HEAD_SHA`
  export only after both gates.
- [x] T-2 adjacent "Squash-merge the auto-sync PR" step — require the valid
  export, independently REST-revalidate the PR identity/head, add
  `--match-head-commit "${SYNC_EXPECTED_HEAD_SHA}"`, add the fixed `BRANCH`
  env; squash/delete/subject preserved, never `--admin`.
- [x] T-3 SDD trio (this directory) conforming to scripts/ci/validate_sdd.py.
- [x] T-4 Evidence battery — focused + full module runs and policy gates
  observed and recorded in the completion gate below. Whole-issue path
  accounting (FIVE paths): the two workflow run blocks (code worker);
  tests/test_sync_tasks_md_flow.py authored in RED by the test worker and
  preserved byte-identical by the code worker (current frozen git blob
  6db6b1d4710c487d9add9c73456e327a2d52b488 before/after the review-fix
  code phases; initial RED freeze d7307eec1e9ec96ae8e1d7f0ce8d893e3d45b822
  plus the test specialist's additive security-review gap cases); this SDD
  trio. The code worker's writable set is FOUR paths (workflow + trio);
  tests/** is frozen. All OTHER tests, scripts, workflows and specs
  untouched.
- [x] T-5 RF-001 readiness correction (gen 6, base 968e402…): wait step —
  on a checks-green tick inside the SAME 900s/30s gate, a FRESH PR GET
  re-validates identity and applies the schema-validating readiness oracle
  (`mergeable` present boolean-or-explicit-null, `mergeable_state` present
  nonempty string; only `mergeable == true && mergeable_state == "clean"`
  is ready; a valid explicit null / false / any non-clean state waits with
  a `SYNC_MERGE_NOT_READY` truth log; missing/mistyped fields, invalid
  JSON and API/auth faults fatal; no deadline reset, no extra budget;
  checks + identity still evaluated every iteration); the former post-loop
  identity-only GET is subsumed by the green break's fresh fetch;
  `SYNC_EXPECTED_HEAD_SHA` exports only after checks AND readiness.
  Adjacent merge step: the same oracle re-applied to its pre-merge GET — a
  readiness regression fails BEFORE any `gh pr merge` call; the single
  preserved squash/delete-branch/subject + `--match-head-commit` form
  unchanged, never `--admin`/`--auto`. Workflow stable GREEN blob
  5ec9ca3d4e7486e51e5ccbf9854e1797a615a43a (from db28b3ef…); tests/**
  untouched (frozen 6feec92ae1f81a1398cb1a190f3c5fa8b7418644 before/after).
- [ ] T-6 RF-001 fresh natural acceptance — orchestrator-owned, PENDING
  (unchecked so the fresh correction triggers the delta): the next real
  sync run with a tasks.md delta must pass the readiness gate live on the
  open bot auto-sync PR and complete the exact-green-head squash merge,
  and the follow-up sync on merged main must be a GENUINE no-op (fresh
  natural push/main Quality on the bot merge SHA + the marker stage
  actually running, not a stale guard; GITHUB_TOKEN push suppression may
  prevent it — if missing, record the blocker and admit separate scope,
  never fake it). RF-001 stays OPEN until that fresh end-to-end evidence
  is recorded on issue #604; no manual PR #566 repair, no token/trigger
  repair, no ad-hoc dispatch.

## Completion gate

- RED (initial, delivery-orchestrator-executed before the code fix): the
  RED run covered the WHOLE module — 30 test methods at that time (the new
  `SyncWaitMergeShellTests` class contributed 15), 37 sub-failures, exit 1
  against the old wait/merge blocks.
- Review-gap RED (parent-observed, after the test specialist additively
  added the security-review gap cases; module now 31 test methods): exactly
  3 authentic failures — (A) dispatch mode `numeric-suffix` accepted with
  rc 0; (B) parked candidate 960 approved although its detail `.id` (999)
  mismatched the requested id; (C) checks fault `rc-valid-json` (valid
  all-pass JSON, CLI rc 137) masked as a pending wait to the 900s deadline
  (parent log: "Ran 31 tests … FAILED (failures=3)").
- Peer truth: the test peer's PASS was a READ-ONLY STATIC review (shell
  execution denied); all test execution was parent/code-worker.
- Focused class `python3 -W error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow.SyncWaitMergeShellTests -v`: OBSERVED (a2
  review-fix round) "Ran 16 tests / OK" — 16/16 green.
- Full module `python3 -W error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow -v`: OBSERVED (a2 review-fix round) "Ran 31
  tests / OK" — 31/31 green, zero skips; no test edits by the code worker
  (frozen blob hash 6db6b1d4… unchanged before/after); parent re-runs the
  battery.
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed" (exit 0).
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow
  policy valid: protected public main -> exact quality -> standing policy ->
  restricted VPS/Ubuntu zero-touch execution" (exit 0).
- `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All checks
  passed!" (exit 0).
- `git diff --check`: clean; workflow YAML parses and both rewritten run
  blocks pass `bash -n`. Workflow stable GREEN blob db28b3ef… (a2 state,
  parent-observed).
- RF-001 records (gen 6 correction, 2026-11-06): RED parent-observed —
  whole module 41 methods, 17 failures, ALL inside the ten additive
  readiness methods, prior 31 green (Ruff configured PASS, git diff
  --check clean at RED); GREEN (a2 correction round, code-worker-observed;
  parent re-runs) — full module `python3 -W error::ResourceWarning -m
  unittest tests.test_sync_tasks_md_flow -v` "Ran 41 tests in 82.232s /
  OK" (41/41, zero skips) and focused class "Ran 26 tests / OK" (26/26);
  frozen test blob 6feec92ae1f81a1398cb1a190f3c5fa8b7418644 before/after
  (cmp against the parent's frozen copy OK); workflow stable GREEN blob
  5ec9ca3d4e7486e51e5ccbf9854e1797a615a43a (from db28b3ef…), both edited
  run blocks pass `bash -n`, YAML parses. The independent test peer's
  RF-001 PASS was READ-ONLY STATIC (shell execution denied) — not an
  executed run. RF-001 stays OPEN until the fresh natural end-to-end
  acceptance (T-6/AC-016) lands on issue #604; the EXACT policy cause of
  the 2026-11-05 denial (run 42019841101 / job 127219543008) remains
  unproven — the readiness oracle is conservative hold/fail-closed only.
- Pending by design (orchestrator-owned, NOT prechecked): required CI green
  on the exact PR head; exact-green-head merge; the live acceptance
  scenario — the next post-merge sync run with a delta exercises the new
  wait/sweep/gate/merge path on the open bot auto-sync PR, and the
  follow-up sync run on the merged main must be a GENUINE no-op (observe a
  fresh natural push/main Quality run on the bot merge SHA and actually
  run the marker stage — GITHUB_TOKEN push suppression may prevent the
  follow-up run from firing; if it does not, record the blocker and admit
  separate scope, never fake it) (evidence PENDING — to be observed and
  recorded on issue #604 after merge, not observed at code-worker time).
  The recognized completion markers below stay unchecked for the auto-sync
  flip; issues #604/#595 are not closed from here (no code-worker closure
  authority).

## Requirements traceability

- AC-001 | Task: T-1 | Evidence: test_happy_wait_merge_pins_expected_head_and_exact_polls observed ok | Coverage: COVERED
- AC-002 | Task: T-1 | Evidence: test_stale_history_cannot_cause_early_green_or_fail observed ok | Coverage: COVERED
- AC-003 | Task: T-1 | Evidence: test_dispatch_url_validation observed ok (7 subtests) | Coverage: COVERED
- AC-004 | Task: T-1 | Evidence: test_invalid_pr_no_approval_no_merge observed ok (8 subtests) | Coverage: COVERED
- AC-005 | Task: T-1 | Evidence: test_late_approval_security_and_narrow_approve observed ok | Coverage: COVERED
- AC-006 | Task: T-1 | Evidence: test_dispatch_failure_no_merge observed ok (3 subtests) | Coverage: COVERED
- AC-007 | Task: T-1 | Evidence: test_required_checks_gate observed ok (2 subtests) | Coverage: COVERED
- AC-008 | Task: T-1 | Evidence: test_fake_clock_timeouts_no_merge observed ok | Coverage: COVERED
- AC-009 | Task: T-2 | Evidence: test_merge_head_changed_and_missing_export observed ok (3 subtests) | Coverage: COVERED
- AC-010 | Task: T-1 | Evidence: test_dispatch_metadata_mismatch_fails_closed observed ok (8 subtests) | Coverage: COVERED
- AC-011 | Task: T-1 | Evidence: test_run_detail_malformed_json_and_401 and test_workflow_metadata_malformed_and_401 observed ok | Coverage: COVERED
- AC-012 | Task: T-1 | Evidence: test_approval_403_fails_closed observed ok | Coverage: COVERED
- AC-013 | Task: T-1 | Evidence: test_required_checks_faults observed ok (5 subtests) | Coverage: COVERED
- AC-014 | Task: T-1 | Evidence: test_required_gate_900s_deadline_from_phase_start observed ok (2 subtests) | Coverage: COVERED
- AC-015 | Task: T-2, T-4 | Evidence: WorkflowStructuralPinTests observed ok + `python3 scripts/quality/validate_workflow_policy.py` exit 0 + exact-diff inspection | Coverage: COVERED
- AC-016 | Task: T-4 | Evidence: required CI on the exact PR head, exact-green-head merge, the live wait/approve/merge of the open bot auto-sync PR by the next real sync run, and the FOLLOW-UP GENUINE no-op sync on merged main (fresh natural push/main Quality on the bot merge SHA + the follow-up sync actually running its marker stage, not a stale guard) — automatic, orchestrator-owned; PENDING — to be observed and recorded on issue #604 after merge, not observed at code-worker time; if the no-op does not fire naturally (GITHUB_TOKEN push suppression), record the blocker and admit separate scope — never fake it | Coverage: RUNTIME-MANUAL | Reason: live GitHub CI/merge/sync evidence cannot be produced locally; the auto-sync flow supplies it automatically after merge
- AC-017 | Task: T-5 | Evidence: test_readiness_blocked_until_clean_then_merge, test_readiness_null_unknown_then_clean, test_readiness_combinations_nonready (6 subtests), test_readiness_persistent_blocked_900s_deadline, test_check_failure_while_waiting_readiness, test_head_drift_while_waiting_readiness, test_readiness_schema_invalid (6 subtests), test_readiness_pr_get_faults, test_readiness_mutated_before_merge, test_merge_api_rejects_policy observed ok (a2 correction round, whole module 41/41, focused class 26/26) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified — whole-issue FIVE-path accounting:
  .github/workflows/sync-merged-tasks.yml (code worker: wait step + adjacent
  merge step run blocks incl. env), tests/test_sync_tasks_md_flow.py (test
  worker RED phase; frozen through the original code phases at
  6db6b1d4710c487d9add9c73456e327a2d52b488, re-frozen by the parent for
  RF-001 at 6feec92ae1f81a1398cb1a190f3c5fa8b7418644 and byte-identical
  through the a2 correction code phase), and
  specs/604-sync-check-wait/{spec,plan,tasks}.md; the code
  worker's writable set is the FOUR paths workflow + trio; all OTHER tests,
  scripts, workflows and specs untouched; prior foreign dirty/untracked
  files preserved untouched
- [x] Required tests and evidence complete (RF-001 correction round:
  focused class 26/26 OK; full module 41/41 OK, code-worker-observed;
  prior a2 round 16/16 and 31/31 HISTORICAL; SDD, workflow-policy and
  ruff gates observed; parent re-runs)
- [ ] Required CI green — orchestrator-owned (exact PR head)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (CONTROL_PLANE only; no VPS/Ubuntu deploy contour in this change)
- [ ] Runtime acceptance resolved — the next real sync run with a delta exercises the new wait/sweep/gate/merge path live AND the follow-up sync on merged main is a GENUINE no-op (observe fresh natural push/main Quality on the bot merge SHA and run the marker stage; GITHUB_TOKEN push suppression may prevent it — if missing, record the blocker and admit separate scope, never fake it; evidence on issue #604)
- [x] Deferred work recorded (no retry/fallback for dispatch or checks beyond the bounded budgets; no --admin; push/reuse/#595 behavior untouched; token/trigger behavior out of scope)
- [x] Risks resolved or explicitly accepted (plan.md Risk profile: REQUIRED, RISK-001..004; RISK-004 ACCEPTED — the EXACT policy cause of the 2026-11-05 denial (run 42019841101 / job 127219543008) is unproven; the RF-001 readiness oracle is conservative hold/fail-closed only, no rollback, no manual PR #566 mutation, no token/trigger repair)
- [x] Waivers resolved or current (no waivers)
