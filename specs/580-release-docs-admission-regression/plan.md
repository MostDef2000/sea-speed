# Plan — Issue #580: release-process docs drift + admission regression

- Issue: #580
- Spec: specs/580-release-docs-admission-regression/spec.md
- Base: 8531f3e (branch fix/580-release-docs-admission-regression; verified
  current main tip at stage start via https one-shot fetch — SSH port 22 is
  dead in the sandbox, publication goes through the GitHub Connector)

## Architecture

Docs+tests-only change on the release-process surface: three docs files
corrected to the standing-delegation reality, one new stdlib-only regression
module pinning the admission decision, and this SDD trio. The regression
module loads the real evaluator (`scripts/release/evaluate_production_policy.py`)
via importlib and drives the real `evaluate()` and real `main()`. Isolation
has exactly two seams, both outside production code:

- Transport: `mock.patch.object(EVALUATOR, "github_json", ...)` — the
  evaluator resolves the module-global `github_json` at each call site
  (commit→PR lookup at evaluate_production_policy.py:151, canonical Issue at
  :178), so a module-attribute patch is sufficient; the fake asserts the
  exact expected API URLs and the fixture token, rejecting anything else.
- Exact diff: `exact_changed_files` (:59-70) shells out to
  `git diff --name-only {sha}^ {sha}` in the CWD, so each test builds a
  real temporary git repository (baseline
  commit → feature commit → `git merge --no-ff`), reads the real merge SHA,
  and runs the evaluator with the CWD temporarily switched into the fixture
  (GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE isolated and restored).

The delegation fixture reuses the shape of tests/test_production_policy.py
bound to the REAL hash of `data/contracts/production-autonomy-policy-v1.json`
(`validate_delegation` checks the production policy hash, not change-control).

## Decisions

- D-1: zero production-code seam. Monkeypatch + temp-git-repo fixture cover
  the whole evaluator path; the architect pass verified no default-argument
  capture or early binding exists that would force a seam.
- D-2: a NEW test file instead of extending existing suites — keeps the
  guarded-optional pin set in tests/test_run_tests_script.py untouched and
  the admission pins independently runnable; the module is stdlib-only with
  no try/except ImportError guarded imports.
- D-3: the PR is classified VPS REQUIRED by path (`deploy/vps/**` edit),
  not docs-only NOT REQUIRED — classification is path-derived by the
  change-control policy; content-level "docs-only" does not decide it. This
  corrects the orchestrator's initial classification and was disclosed to
  the owner before the first repository write; the merged runtime bits are
  identical to the deployed baseline.
- D-4: import side-effect hygiene — the evaluator's module-level import
  inserts scripts/release into sys.path and registers `production_policy`
  in sys.modules; the test module captures the pre-load state and restores
  it in a class cleanup so the one-process battery is not polluted.
- D-5: docs edits are minimal sentence-level replacements; the
  preserve-verbatim list (testing-policy intro + four bullets; vps README
  "Merge does not itself authorize a deployment.") is enforced by grep in
  validation, and the "## Manual run" section of the VPS README is untouched.

## Affected contours

- VPS: the PR classifies as a VPS-contour change by path
  (`deploy/vps/README.md`); no executable/runtime file changes, so the
  deployed runtime bits remain identical to the merged baseline — the
  post-merge autonomous deploy re-verifies policy and re-deploys
  byte-identical runtime content.
- Ubuntu worker/relay: NOT REQUIRED — no `worker/**` or relay paths.

## Validation

- Focused: `python3 -m unittest tests.test_release_admission_regression -v`
  → 6/6 green (orchestrator-observed).
- Full CI-pinned battery: `python3 -W error::ResourceWarning -m unittest
  discover -s tests -p 'test_*.py'` → Ran 1261 / OK (skipped=17 local with
  fastapi; CI expects skipped=50 without fastapi), EXIT=0, zero
  ResourceWarnings attributable to the new module (orchestrator-observed).
- Contract validators: `scripts/ci/validate_sdd.py --event <synthetic PR
  event>` and `scripts/ci/validate_change_contract.py --event <same>` exit 0
  on the exact PR body + diff.
- Preserved-verbatim greps: vps README:227 sentence; testing-policy intro +
  4 bullets.
- CI: exact-head Quality integration gate + security gates on the PR;
  post-merge autonomous router observation recorded on issue #580.

## Runtime feedback

- The production admission denials (#590 2026-11-01, #582 2026-11-02) were
  correct fail-closed behavior; they are now pinned as regression cases 1
  and 4 so any future evaluator regression reds at the quality gate instead
  of surfacing as an admission denial on a real release.

## Risk profile

- Risk profile: NOT REQUIRED

Rationale: docs+tests only; Production impact VPS is path-derived with
byte-identical runtime bits; Security impact NONE; API/event/state/storage
schema impact NONE; no destructive/data-migration or other high-risk
trigger. Per the change-control policy this impact class does not require
the full risk-profile table (no risk rows).

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_release_admission_regression.py — 6 tests green through real evaluate()/main() with a real temp git repo fixture and mocked transport (orchestrator-observed: Ran 6, OK); pin bites demonstrated by fixture flips (Outcome Contract heading present/absent changes the verdict both ways)
- TEST-002 | Covers: AC-002, AC-003, AC-004 | Level: unit | Priority: P1 | Evidence: preserved-verbatim grep checks on the final tree (vps README:227 sentence; testing-policy intro + 4 bullets) + full-diff inspection against the work orders (6 hunks, no other lines touched)
- TEST-003 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: full CI-pinned battery green on the stage tree — Ran 1261 / OK (skipped=17) / EXIT=0, delta exactly the new module, zero admission-prefix ResourceWarnings (orchestrator-observed); CI Quality gate re-checks on the PR head

## Correct-course check

- Trigger: NONE
- Issue impact: NONE — no course change during this delivery; the
  pre-existing production admission denials were correct fail-closed
  behavior and are pinned as regression coverage, not a course correction.
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE — scope as admitted; the VPS REQUIRED
  classification correction was disclosed to the owner before the first
  repository write and does not change the approved file set.
- Follow-up: pre-existing battery ResourceWarning noise from
  tests/test_line_crossing.py:272 (TemporaryDirectory without
  addClassCleanup; present on the 8531f3e baseline, exit 0) is a follow-up
  candidate outside this scope.

## Deployment transaction audit

This audit models the full delivery transaction of this stage: local
source/SDD writes, Connector publication, exact-green-head merge, and the
autonomous post-merge VPS rollout of byte-identical runtime bits. Zero
operator actions are expected.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no branch, no writes; the stage stays unadmitted | Retry: re-present the complete visible scope and obtain a fresh `commit approved` | Rollback: NOT REQUIRED (read-only stage) | Evidence: `commit approved` in the owner message immediately following the scope presentation; VPS REQUIRED classification disclosed before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: no local edits on an unverified base | Retry: re-fetch main via the https one-shot and re-verify the tip before branching | Rollback: delete the stage branch if it was created from a stale base | Evidence: verified main tip 8531f3e recorded in the session log; branch fix/580-release-docs-admission-regression created from it
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: depends on the gated sub-step — uncommitted working-tree edits (source writes), or a remote branch/PR without merge (publication), or main advanced without green exact-head CI (merge — forbidden, never reached) | Retry: source writes — bounded worker re-dispatch; publication — re-publish the exact tree via the Connector; merge — only after fresh base/head/scope/review re-verification | Rollback: source writes — git checkout/delete untracked; publication — delete the remote branch pre-merge; merge — a revert commit on main (never a force push) | Evidence: orchestrator-inspected git diff (6 hunks, +6/−6) + the new test module; tree-identity check and PR head SHA; exact-green-head merge on the reviewed head SHA
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: changes stay local or the PR stays open and unmerged | Retry: fix the failing check and re-run the gate; CI flakes get rerun_failed_jobs only, real failures get a fresh commit | Rollback: close the PR and delete the remote branch | Evidence: focused module 6/6 green; full battery Ran 1261 / OK / EXIT=0; validate_sdd.py + validate_change_contract.py exit 0; peer review verdict; required checks green on the exact head SHA
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: main is merged while the durable delivery-control record is incomplete | Retry: complete the issue checkpoint from the recorded merge/CI/deploy evidence | Rollback: the merge revert path (TX-008) remains available | Evidence: merge SHA on main; issue #580 checkpoint comment with the evidence cursor
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: merged main is correct while branch cleanup, the JOURNAL/KB chronicle record or the vector-index refresh may remain pending | Retry: complete housekeeping independently of the merged state | Rollback: NOT REQUIRED for housekeeping failure | Evidence: JOURNAL entry, refreshed vector index, deleted stage branch
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: main is merged and the deploy may be healthy while the stage evidence cursor is incomplete | Retry: recollect evidence without redeployment when the exact runtime identity is unchanged | Rollback: decide from actual runtime state, not evidence upload alone | Evidence: merge SHA, autonomous deploy run observation, battery identity in tasks.md
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if a post-merge defect is found, stop automated mutation and recover actual state read-only first | Retry: only after the actual main/runtime state is known | Rollback: revert commit on main for source; previous main SHA as the deploy rollback target through the standing delegation path (runtime bits identical, so deploy rollback is not expected to be needed) | Evidence: revert/rollback evidence recorded on issue #580
