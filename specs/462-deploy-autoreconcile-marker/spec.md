# Spec: deploy.sh auto-reconcile accepts both helper outcomes (exit-44 marker fix)

- Issue: #462
- Specification: specs/462-deploy-autoreconcile-marker/spec.md

## Product outcome

Production VPS deploys of 22263dc (runs 38232673841 and 38232898985, 2026-10-12) aborted with exit 44 AFTER a functionally green bounded auto-reconcile: the privileged helper re-rendered the Auth v1 boundary, printed SEA_SPEED_AUTH_CUTOVER=PASS / ROLLBACK_CAPABILITY=VERIFIED / SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS, and the public probes were green — yet the deploy stopped before any live source mutation. Root cause: both pre-mutation verification sites in `deploy/vps/deploy.sh` (the auto-reconcile block in `check_auth_privilege_boundary` ~:386 and `recover_auth_boundary_before_source_mutation` ~:467) unconditionally required the marker `SEA_SPEED_AUTH_RECOVERY=PASS`. The real helper (`deploy/vps/sea-speed-auth-privileged-helper.py`, `run_cutover`) prints that marker ONLY on the bounded broken-500 recovery path; the normal reconcile path ends with `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS` and no recovery marker at all — the check was unsatisfiable precisely on the routine path, so every preflight SHA mismatch blocked a band-A deploy and forced a manual band-B bundle re-cut. Aggravating factor: the test fake helper printed the recovery marker on the normal reconcile path too, masking the defect in CI.

This change makes both verification sites accept both helper outcomes — the recovery marker is enforced whenever present (any non-PASS value fails closed) and never required when absent — while keeping the five security-relevant markers enforced unchanged, and restores the fake helper's contract fidelity so the suite can no longer mask drift.

## User scenarios

- US-1 (the production incident direction): a deploy preflight hits a privileged-bundle SHA mismatch with a healthy public boundary → the bounded auto-reconcile completes on the NORMAL path (no recovery marker in the output) → the gate accepts it and the deploy proceeds past the boundary check into live source mutation (previously: exit 44 before mutation).
- US-2: the auto-reconcile runs through the bounded broken-500 recovery path → `SEA_SPEED_AUTH_RECOVERY=PASS` is printed and still required (enforced whenever a recovery marker is present).
- US-3: the reconcile fails (non-zero rc) → the deploy still stops before live source mutation (unchanged behavior).
- US-4: the reconcile output carries a non-PASS recovery marker (SEA_SPEED_AUTH_RECOVERY=FAIL-shaped) → verification fails closed before any live source mutation.
- US-5: the fake helper in the test harness mirrors the real helper's marker contract (normal: no recovery marker; recovery: with it), so contract drift becomes visible to CI instead of masked.

## Scope

- `deploy/vps/deploy.sh`: ONLY the recovery-marker check in the two pre-mutation verification blocks (auto-reconcile block of `check_auth_privilege_boundary` and the marker block of `recover_auth_boundary_before_source_mutation`) plus their comments; every other byte of the deploy transaction unchanged.
- `tests/test_vps_deploy_transaction.py`: fake-helper fidelity fix (+ fidelity comment), new `recovery-marker-fail` fake mode, 2 new regression tests, 2 strengthened assertions; no existing assertion weakened.
- SDD trio `specs/462-deploy-autoreconcile-marker/` and the durable progress file (outside the repo tree).
- OUT of scope: privileged helper (`sea-speed-auth-privileged-helper.py`) semantics, `install-auth-privilege-boundary.sh`, sudoers, boundary re-render logic, `.github/workflows/**`, `api/**`, `worker/**`, `frontend/**`, live VPS state (the bundle was already re-cut to 22263dc by the band-B handoff 2026-10-12).

## Requirements

- R-1 (AC-1): with a faithful fake, the preflight-mismatch auto-reconcile on the normal path completes past the boundary gate (rc 0) and the deploy mutates live source; the recovery marker is NOT required when absent.
- R-2 (AC-2): the bounded broken-500 recovery path keeps its dedicated marker: `SEA_SPEED_AUTH_RECOVERY=PASS` must be accepted and enforced whenever a recovery marker is present; any non-PASS value fails closed.
- R-3 (AC-3): a failed reconcile (non-zero rc) still stops the deploy before live source mutation.
- R-4 (AC-4): all five fixed markers remain enforced at both sites on both outcomes (`SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS`, `SOURCE_SHA=<commit>`, `ACTION=reconcile`, `ARBITRARY_ROOT_EXECUTION=NO`, `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS`); the relaxation touches only the recovery marker's presence, never its value.
- R-5 (AC-5): the fake helper's marker contract equals the real helper's (normal reconcile: no recovery marker; recovery: `SEA_SPEED_AUTH_RECOVERY=PASS`).

## Acceptance criteria

- AC-1: Deploy with preflight SHA mismatch + normal reconcile (no broken-500) completes past the boundary gate and mutates the source (fake helper no longer prints the recovery marker on the normal path).
- AC-2: Deploy with preflight SHA mismatch + broken-500 recovery path still requires `SEA_SPEED_AUTH_RECOVERY=PASS` (recovery case keeps its dedicated marker).
- AC-3: Reconcile failure (non-zero rc) still stops before live source mutation.
- AC-4: All five fixed markers remain enforced on both paths.
- AC-5: Fake helper marker contract == real helper marker contract (normal: no recovery marker; recovery: with it).

## Runtime feedback

- RF-001: Operator actions expected: 0; runtime verification lands with the next routine band-A deploy (the bundle is already re-cut to 22263dc by the band-B handoff 2026-10-12); the orchestrator records runtime acceptance on issue #462.
- RF-002: Evidence: the next deploy log must show the auto-reconcile completing past the marker gate into source mutation (absence of the exit-44 pattern of runs 38232673841/38232898985); RED/GREEN unit transcripts are recorded in the durable progress file.

## NFR assessment

- NFR-001 | Area: security | Target: the five fixed security-relevant markers stay enforced on both reconcile outcomes at both sites; the recovery marker's VALUE is enforced whenever present (FAIL-shaped or corrupted output fails closed before live source mutation) | Validation: unit battery — recovery-marker-fail abort test (rc != 0, source unchanged, no manifest), recovery-path tests asserting SEA_SPEED_AUTH_RECOVERY=PASS, diff inspection of both marker blocks (five fixed greps byte-unchanged) | Evidence: tests/test_vps_deploy_transaction.py 22/22 OK | Status: PASS
- NFR-002 | Area: reliability/operations | Target: a routine deploy whose preflight hits a SHA mismatch no longer aborts with exit 44 after a functionally green reconcile; the bounded auto-reconcile (#377) becomes self-sufficient again, removing the manual band-B bundle re-cut loop | Validation: regression tests for the exact production direction (mismatch + normal reconcile → rc 0, source mutated); RED authenticity — both tests fail rc 44 against base deploy.sh with the faithful fake | Evidence: RED transcript (Ran 20, failures=2, 44 != 0) → GREEN 22/22 OK, recorded in the durable progress file | Status: PASS
- NFR-003 | Area: compatibility | Target: no helper/installer/sudoers/boundary re-render changes; deploy.sh behavior differs ONLY for the previously-unsatisfiable normal-reconcile outcome; every other failure path (non-zero rc, missing fixed markers, FAIL-shaped recovery) unchanged | Validation: full-file battery 22/22 OK including all pre-existing failure-path tests unchanged; bash -n deploy.sh rc 0 | Evidence: suite transcripts in the durable progress file | Status: PASS
