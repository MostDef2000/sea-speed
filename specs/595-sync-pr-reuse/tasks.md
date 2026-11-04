# Tasks — Issue #595 owner-qualified auto-sync PR reuse lookup

- Issue: #595
- Spec: specs/595-sync-pr-reuse/spec.md
- Plan: specs/595-sync-pr-reuse/plan.md
- Base: 53d61d41 (origin/main content baseline; local HEAD f7d485f is
  content-identical to it on the workflow path; the test module carries the
  test specialist's uncommitted RED additions on top of that baseline)

## Delivery tasks

- [x] T-1 `.github/workflows/sync-merged-tasks.yml` — narrow the reuse
  lookup's head filter from `${GH_REPO}:${BRANCH}` (owner/repo:branch,
  matches nothing) to `${GH_REPO%%/*}:${BRANCH}` (owner:branch); endpoint
  `repos/${GH_REPO}`, `base=main`, `state=open`, jq and every other step
  byte-identical; one explanatory #595 comment.
- [x] T-2 SDD trio (this directory) conforming to scripts/ci/validate_sdd.py.
- [x] T-3 Evidence battery — RED/GREEN test runs and policy gates observed
  and recorded in the completion gate below. Whole-issue path accounting
  (five paths): the workflow query fix (code worker);
  tests/test_sync_tasks_md_flow.py changed by the test worker in the RED
  phase (+419/-1 lines vs the git base: #595 class, fake-gh harness,
  corrected structural pin) and preserved byte-identical by the code worker
  (hash ee433890c437fab0a8fa01f810020e0cdc188d5a before/after the code
  phase); this SDD trio. All OTHER tests, scripts, workflows and specs
  untouched.

## Completion gate

- RED (before the fix, observed on the base): `python3 -W
  error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow.SyncPrLookupReuseCreateTests -v` —
  "Ran 5 tests in 0.271s / FAILED (failures=3)" (reuse, create, repeat);
  the module-level structural pin failed too (orchestrator-observed
  "Ran 15 ... FAILED (failures=4) exit 1").
- Focused module `python3 -W error::ResourceWarning -m unittest
  tests.test_sync_tasks_md_flow -v`: OBSERVED "Ran 15 tests in 0.452s /
  OK" — 15/15 green, zero skips; no test edits during the GREEN/code phase
  (the RED state was authored by the test specialist).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed" (exit 0).
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow
  policy valid: protected public main -> exact quality -> standing policy ->
  restricted VPS/Ubuntu zero-touch execution" (exit 0).
- `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All checks
  passed!" (exit 0).
- `git diff -- .github/workflows/sync-merged-tasks.yml`: only the
  head-filter owner component (`${GH_REPO}` -> `${GH_REPO%%/*}`) plus the
  three-line #595 comment; nothing else.
- Pending by design (orchestrator-owned, NOT prechecked): required CI green
  on the exact PR head; exact-green-head merge; the live acceptance
  scenario — the next post-merge sync run reuses/updates/merges the open
  bot PR #566 through the fixed lookup (automatic; evidence PENDING — to be
  observed and recorded on issue #595 by the orchestrator after merge, not
  observed at code-worker time). The recognized completion markers below
  stay unchecked for the auto-sync flip.

## Requirements traceability

- AC-001 | Task: T-1 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_existing_open_pr_is_reused_via_patch_never_post observed ok (lookup URL + PATCH-only + export) | Coverage: COVERED
- AC-002 | Task: T-1 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_no_open_pr_creates_exactly_once_and_exports_number observed ok (one POST + export) | Coverage: COVERED
- AC-003 | Task: T-1 | Evidence: test_lookup_401_fails_closed_without_create_or_export and test_lookup_network_failure_fails_closed_without_create_or_export observed ok (lookup-only, nonzero, no export) | Coverage: COVERED
- AC-004 | Task: T-1 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_repeated_invocation_reuses_created_pr_never_second_post observed ok (exactly one POST across two runs) | Coverage: COVERED
- AC-005 | Task: T-1, T-3 | Evidence: WorkflowStructuralPinTests observed ok + `python3 scripts/quality/validate_workflow_policy.py` exit 0 + exact-diff inspection | Coverage: COVERED
- AC-006 | Task: T-3 | Evidence: required CI on the exact PR head, exact-green-head merge and the live reuse of open bot PR #566 by the next real sync run — automatic, orchestrator-owned; PENDING — to be observed and recorded on issue #595 after merge, not observed at code-worker time | Coverage: RUNTIME-MANUAL | Reason: live GitHub CI/merge/sync evidence cannot be produced locally; the auto-sync flow supplies it automatically after merge while PR #566 is open

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified — whole-issue five-path accounting:
  .github/workflows/sync-merged-tasks.yml (code worker: one-line query fix
  + #595 comment), tests/test_sync_tasks_md_flow.py (test worker, RED
  phase: +419/-1 lines vs the git base — #595 class, fake-gh harness,
  corrected structural pin; byte-identical through the code phase, hash
  ee433890c437fab0a8fa01f810020e0cdc188d5a), and
  specs/595-sync-pr-reuse/{spec,plan,tasks}.md; all OTHER tests, scripts,
  workflows and specs untouched
- [x] Required tests and evidence complete (focused module 15/15 OK; SDD, workflow-policy and ruff gates observed)
- [ ] Required CI green — orchestrator-owned (exact PR head)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — NOT REQUIRED (CONTROL_PLANE only; no deploy contour in this change)
- [ ] Runtime acceptance resolved — the next real sync run with a delta reuses/updates/merges the open bot PR #566 via the owner-qualified lookup (live evidence on issue #595)
- [x] Deferred work recorded (no retry/422-fallback/race fixes — explicitly out of scope; lookup failure after the push stays fail-closed without rollback)
- [x] Risks resolved or explicitly accepted (plan.md Risk profile: REQUIRED, RISK-001..003)
- [x] Waivers resolved or current (no waivers)
