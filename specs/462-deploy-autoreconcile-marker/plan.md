# Plan: deploy.sh auto-reconcile accepts both helper outcomes (exit-44 marker fix)

- Issue: #462
- Specification: specs/462-deploy-autoreconcile-marker/spec.md

## Implementation approach

1. RECON-established facts: the real privileged helper's `run_cutover` prints `SEA_SPEED_AUTH_RECOVERY=PASS` exactly when the bounded broken-500 recovery path ran (helper.py:487); the normal reconcile path returns `SEA_SPEED_AUTH_CUTOVER=PASS`, `WORKER_PRIVATE_ROAD_API_BASE=`, `ROLLBACK_CAPABILITY=VERIFIED` with NO recovery marker (helper.py:489-507); `execute_request` appends `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS` on both paths; deploy.sh demanded the recovery marker unconditionally at :386 (`check_auth_privilege_boundary`) and :467 (`recover_auth_boundary_before_source_mutation`); the fake helper printed it on the normal path too (tests:280), masking the defect in CI.
2. Tests-first RED: fix the fake helper's normal path FIRST (remove the recovery-marker print, add a contract-fidelity comment) and run the file against base deploy.sh — expected RED exactly on the two mismatch auto-reconcile tests with rc 44. Observed: `Ran 20 tests ... FAILED (failures=2)`, both `AssertionError: 44 != 0` (test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation, test_privilege_boundary_mismatch_plain_error_also_auto_reconciles); the other 18 stayed green with the faithful fake.
3. Implementation: replace the unconditional recovery-marker grep at BOTH sites with the conditional check — if the output contains `SEA_SPEED_AUTH_RECOVERY=` at all it must be `=PASS` (any other value fails closed with return 44); absence is admissible. All five fixed marker greps byte-unchanged; per-site comments explain the two helper outcomes.
4. Regression coverage: new fake mode `recovery-marker-fail` (status mismatch + reconcile prints `SEA_SPEED_AUTH_RECOVERY=FAIL` with rc 0); new test mismatch+broken-500 (recovery path keeps its dedicated marker, deploy completes); new test FAIL-shaped output aborts before live source mutation; strengthen the mismatch-normal test (`assertNotIn` of any recovery marker — fake-fidelity pin) and the public-500 recovery test (`assertIn SEA_SPEED_AUTH_RECOVERY=PASS`). No existing assertion weakened.
5. Verification battery: file battery 22/22 OK (RED→GREEN); full discover suite; bash -n; validate_repo; validate_sdd; ruff.
6. Peer review (APPROVE) hardening F-1: strengthen both recovery-marker checks from existential to UNIVERSAL — every occurrence of `SEA_SPEED_AUTH_RECOVERY=` in the output must be `=PASS`; a stray `=PASS` line must not rescue a `=FAIL` occurrence. Implemented as capture-then-single-grep (no pipeline, so the verdict is exact under `set -o pipefail`; `[[ -n ]]` guard because a herestring of an empty capture is one empty line that `grep -Fv` would otherwise select — caught by the mismatch-normal tests going RED 44 during development). RED proof for the hardening: the new mixed-marker fake mode + test fail `0 == 0` under the existential check (the stray `=PASS` rescues the gate, deploy mutates source) → GREEN after the hardening; file battery 23/23 OK.

## Architecture

- Discriminator derived from the real helper's output grammar: `SEA_SPEED_AUTH_RECOVERY=PASS` iff the bounded recovery ran; the normal reconcile ends with `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS` and no recovery token. Therefore "presence requires =PASS, absence is admissible" is a total check: it admits both outcomes, still fails closed on corrupted/FAIL-shaped output, and keeps the recovery path's dedicated marker enforced.
- `grep -Fq 'SEA_SPEED_AUTH_RECOVERY='` cannot false-positive on `SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS` (the fixed string requires `=` directly after `RECOVERY`), so rollback diagnostics never trip the check.
- Both pre-mutation sites carry the identical conditional (mirrored per-site style, each with its own comment; return 44 preserved), so the two verification blocks stay locally readable and their failure semantics unchanged.
- `run_auth_boundary` (post-mutation reconcile, :847) is intentionally unchanged: it already requires no recovery marker and enforces its own marker set (CUTOVER, WORKER_PRIVATE_ROAD_API_BASE, ROLLBACK_CAPABILITY=VERIFIED, RECONCILE).
- Fake-helper recovery branch stays faithful to the real recovery path: it prints `SEA_SPEED_AUTH_RECOVERY=PASS` and (like the real recovery path) does not print `ROLLBACK_CAPABILITY=VERIFIED`.

## Decisions

- D-1: Conditional presence check instead of deleting the recovery-marker check: a pure check deletion would silently weaken the recovery-path enforcement (AC-2); the conditional keeps the fail-closed direction (FAIL-shaped output aborts) while admitting the normal outcome.
- D-2: Fake-first RED before touching deploy.sh: the fake's generosity was the masking factor named in issue #462, so fidelity is restored first and the RED is captured against the unmodified base script — proving the battery exercises the real defect (rc 44).
- D-3: Dedicated FAIL-shaped abort test (new `recovery-marker-fail` fake mode) guards the conditional fix against the opposite regression (a naive "remove the check" change would let corrupted output through).
- D-4: Duplicate the conditional verbatim at both sites instead of extracting a shared helper function: mirrors the existing per-site flat grep-block style with per-site return codes and keeps the diff minimal.
- D-5: `assertNotIn("SEA_SPEED_AUTH_RECOVERY=")` in the mismatch-normal test as the executable fake-fidelity pin: if the fake ever regresses to the generous marker contract, CI fails instead of masking deploy.sh behavior again.
- D-6: No changes to `run_auth_boundary` or the privileged helper: both are outside the issue's approved scope and already match the fixed marker contract.
- D-7: Peer-review F-1 universal semantics are implemented as capture-then-single-grep (`recovery_lines` captured with `|| true`, then `[[ -n ]] && grep -Fqv` in an if-condition) rather than the suggested `grep | grep -Fvq && return 44` pipeline: under `set -o pipefail` a pipeline verdict can be skewed (a `grep -q` early exit can SIGPIPE the producer into 141, masking a detected non-PASS occurrence on large outputs), while `grep -Fv` over a herestring of an EMPTY capture sees one empty line and would fail the normal-reconcile outcome — the `[[ -n ]]` guard excludes that case exactly. The if-condition context keeps `set -e` from exiting on no-match; the check still fails closed (return 44) on any non-PASS occurrence and accepts absence and all-`=PASS` outputs.

## Affected contours

- VPS: `deploy/vps/deploy.sh` (the two pre-mutation verification blocks only).
- Test harness: `tests/test_vps_deploy_transaction.py` (fake fidelity + `recovery-marker-fail` mode + 2 new tests + 2 strengthened assertions).
- SDD trio `specs/462-deploy-autoreconcile-marker/` (+ durable progress file outside the repo tree).
- No change to: `deploy/vps/sea-speed-auth-privileged-helper.py`, `deploy/vps/install-auth-privilege-boundary.sh`, `.github/workflows/**`, `api/**`, `worker/**`, `frontend/**`, live VPS state (bundle already re-cut to 22263dc by the band-B handoff 2026-10-12).

## Validation

- RED (fake fidelity restored, deploy.sh @ base 22263dc): `python3 -m unittest tests.test_vps_deploy_transaction` → `Ran 20 tests ... FAILED (failures=2)`: test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation and test_privilege_boundary_mismatch_plain_error_also_auto_reconciles, both `AssertionError: 44 != 0` (normal reconcile output green, no recovery marker, deploy exits 44 before source mutation).
- GREEN: the same file after the deploy.sh fix → `Ran 22 tests ... OK` (20 pre-existing + 2 new).
- F-1 hardening RED→GREEN: the mixed-marker test (FAIL + stray =PASS) fails `0 == 0` under the existential check (stray =PASS rescues the gate) → after the universal hardening the same test aborts rc != 0 before source mutation; file battery → `Ran 23 tests ... OK` (20 pre-existing + 3 new).
- Full suite: `python3 -m unittest discover -s tests` → `Ran 907 tests ... OK (skipped=4)` (906 before the mixed-marker test).
- `bash -n deploy/vps/deploy.sh` → rc 0.
- `python3 scripts/ci/validate_repo.py` → "Sea Speed repository validation passed" (652 files tracked after the trio landed).
- `python3 scripts/ci/validate_sdd.py` → passed (this trio).
- `python3 -m ruff check . --config scripts/quality/ruff.toml` → clean.

## Runtime feedback

- RF-001: Operator actions expected: 0; runtime verification is the next routine band-A VPS deploy (the bundle is already re-cut to 22263dc by the band-B handoff 2026-10-12); the orchestrator records runtime acceptance on issue #462.
- RF-002: Evidence: the next deploy log shows the auto-reconcile completing past the marker gate into source mutation; RED/GREEN unit transcripts recorded in the durable progress file.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: deploy/** change gating the protected-boundary verification of the VPS deploy transaction (deployment transaction audit required); Security impact declared LOW in the PR body (verification-only relaxation derived from the real helper's output grammar; the five fixed markers are untouched).
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the check is derived from the real helper's output grammar (recovery marker iff bounded recovery ran, helper.py:487) and is fail-closed in both directions — absence is the only admissible alternative to =PASS, and UNIVERSALLY every occurrence must be =PASS (peer review F-1): any non-PASS value (FAIL-shaped or corrupted output, even alongside a stray =PASS line) aborts before live source mutation | Validation: test_privilege_boundary_reconcile_recovery_fail_marker_stops_before_live_source_mutation + test_privilege_boundary_reconcile_recovery_fail_with_stray_pass_stops_before_live_source_mutation (both rc != 0, api/road unchanged, current unchanged, no manifest) + recovery-path tests asserting SEA_SPEED_AUTH_RECOVERY=PASS + diff inspection (five fixed greps byte-unchanged at both sites) | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: regression tests pin the exact production direction (mismatch + normal reconcile → rc 0 and source mutated) and the failure directions (reconcile rc != 0 stops; FAIL-shaped marker aborts); RED authenticity proven against base deploy.sh with the faithful fake | Validation: mismatch-normal tests RED rc 44 at base → GREEN after the fix; recovery and reconcile-failure tests unchanged and green | Residual risk: LOW — the live end-to-end proof arrives with the next routine band-A deploy | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: fake-helper contract drift is pinned executably (assertNotIn of any recovery marker on the normal path; assertIn of SEA_SPEED_AUTH_RECOVERY=PASS on the recovery paths) plus an in-file fidelity comment binding the fake to helper.py run_cutover | Validation: the fake-fidelity pins fail CI if the fake regresses to the generous normal-path marker again; PrivilegedAuthRecoveryTests (3 methods) pin the real helper contract | Residual risk: LOW — a future real-helper contract change could drift again; fake-side drift is now loud, real-side drift surfaces at the next live deploy | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the site-2 (`recover_auth_boundary_before_source_mutation`) normal-reconcile outcome is not directly reachable in the fake harness (public broken-500 and the fake's recovery branch key on the same recovery-marker file: marker absent → helper takes the recovery branch; marker present → public probe returns 302 and site 2 short-circuits), so site 2's mirrored check is covered by exact code symmetry with the behaviorally tested site 1 plus bash -n | Validation: diff review (identical conditional at both sites), bash -n rc 0, site-1 behavioral battery | Residual risk: LOW — a site-2-specific regression of the mirrored block would not be caught behaviorally pre-merge | Owner: Delivery Orchestrator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: RISK-001,RISK-002 | Level: unit | Priority: P0 | Evidence: test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation + test_privilege_boundary_mismatch_plain_error_also_auto_reconciles (rc 0, current=CANDIDATE, assertNotIn of any SEA_SPEED_AUTH_RECOVERY= marker; RED rc 44 at base with the faithful fake)
- TEST-002 | Covers: RISK-001,RISK-003 | Level: unit | Priority: P0 | Evidence: test_privilege_boundary_mismatch_broken_500_recovery_keeps_recovery_marker_required (recovery path prints SEA_SPEED_AUTH_RECOVERY=PASS, deploy completes) + test_public_500_is_recovered_before_live_source_mutation (strengthened with assertIn SEA_SPEED_AUTH_RECOVERY=PASS)
- TEST-003 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: recovery-marker-fail fake mode + test_privilege_boundary_reconcile_recovery_fail_marker_stops_before_live_source_mutation (FAIL-shaped output → rc != 0, api/road bytes unchanged, current=OLD, no deployment-manifest.json) + recovery-marker-mixed fake mode + test_privilege_boundary_reconcile_recovery_fail_with_stray_pass_stops_before_live_source_mutation (FAIL + stray =PASS → still aborts; RED `0 == 0` under the existential check, universal semantics pinned)
- TEST-004 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: fake normal path prints exactly CUTOVER/WORKER_PRIVATE_ROAD_API_BASE/ROLLBACK_CAPABILITY=VERIFIED/RECONCILE=PASS with no recovery marker (assertNotIn pin in TEST-001) while the recovery branch keeps SEA_SPEED_AUTH_RECOVERY=PASS (TEST-002); PrivilegedAuthRecoveryTests (3 methods) pin the real helper run_cutover contract
- TEST-005 | Covers: RISK-002 | Level: unit | Priority: P1 | Evidence: test_privilege_boundary_mismatch_reconcile_failure_stops_before_live_source_mutation + test_public_500_recovery_failure_stops_before_live_source_mutation (non-zero reconcile rc still stops before live source mutation) + test_other_priv_status_error_without_bootstrap_aborts_before_live_source_mutation
- TEST-006 | Covers: RISK-002,RISK-004 | Level: unit | Priority: P1 | Evidence: full-file battery 23/23 OK (20 pre-existing + 3 new) + full discover suite 907 OK (skipped=4) + bash -n rc 0 + validate_repo (652 files) + validate_sdd + ruff clean
- TEST-007 | Covers: RISK-002 | Level: runtime-manual | Priority: P1 | Evidence: the next routine band-A VPS deploy with a preflight SHA mismatch completes past the marker gate into source mutation (production direction of runs 38232673841/38232898985) | Reason: requires the production VPS; pre-merge proof is the unit battery

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: issue #462 (ops evidence: deploy runs 38232673841/38232898985 exit 44 after a functionally green reconcile) with owner OUTCOME APPROVED recorded in the issue Outcome Contract (2026-10-12); the exact file scope (deploy/vps/deploy.sh, tests/test_vps_deploy_transaction.py, this SDD trio) enforced before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged repository state | Retry: NO | Rollback: NONE | Evidence: RED-first sequence — the fake-helper fidelity fix alone produced exactly the two predicted failures (rc 44) against base deploy.sh before any deploy.sh edit; no deploy-side gate was reordered or weakened before the RED capture
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior repository state — each bounded commit lands whole or not at all; the on-VPS deploy transaction itself is unchanged (the fix restores its pre-mutation admission) | Retry: NO | Rollback: git revert of the commits restores the unsatisfiable check and the exit-44 behavior it caused | Evidence: two local commits on sdd/462-deploy-autoreconcile-marker (ae86b86 fix; review-hardening commit for F-1); diff limited to deploy.sh (two verification blocks), the test file (fake fidelity + 3 new tests + 2 strengthened assertions) and this SDD trio
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: file battery 23/23 OK (RED→GREEN, then F-1 mixed-marker RED `0 == 0` → GREEN), full discover 907 OK (skipped=4), bash -n rc 0, validate_repo 652 files passed, validate_sdd passed, ruff clean
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: exact-green-head merge after required CI on the exact head (orchestrator-owned); release identity bound by the PR Change Contract (issue #462)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing temporaries | Retry: NO | Rollback: NONE | Evidence: the fix adds no temporaries and no cleanup; test fixtures live in per-test TemporaryDirectory cleanup; verification scratch stays outside the repository tree
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: issue #462 + PR (orchestrator-owned) + this SDD trio + RED/GREEN transcripts in the durable progress file; the next routine deploy log carries the live completion evidence
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: revert of this commit restores the pre-fix verification (exit 44 on the normal reconcile outcome — the observed production behavior of runs 38232673841/38232898985); no runtime state needs cleanup | Evidence: Rollback target in the PR Change Contract; automatic rollback is not authorized beyond the unchanged deploy fault paths
