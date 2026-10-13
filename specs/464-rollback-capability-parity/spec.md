# Spec: run_auth_boundary accepts the bounded recovery outcome (rollback-capability parity)

- Issue: #464
- Specification: specs/464-rollback-capability-parity/spec.md

## Product outcome

Peer review finding F-4 on the deploy transaction: the two pre-mutation verification sites in `deploy/vps/deploy.sh` (`check_auth_privilege_boundary` auto-reconcile :406-426 and `recover_auth_boundary_before_source_mutation` :502-523) accept an identical privileged-helper success under the universal =PASS recovery rule, but the post-mutation site `run_auth_boundary` (:972-1010) unconditionally required `ROLLBACK_CAPABILITY=VERIFIED` at :1007. The real helper's bounded broken-500 recovery path re-runs the cutover WITHOUT `--require-protected-baseline` (`sea-speed-auth-privileged-helper.py` run_cutover :448-487), so the cutover honestly prints `ROLLBACK_CAPABILITY=MANUAL` (prepare :598 / activate :665-666, with `AUTOMATIC_ROLLBACK=NO`) and the helper appends `SEA_SPEED_AUTH_RECOVERY=PASS` (:487). The post-mutation gate therefore rejected exactly the helper success it mirrors pre-mutation: rc=0, bounded recovery, honest MANUAL — the deploy aborted after the live source mutation, rolled back, and the workflow went red. Aggravating factor (same masking class as issue #462): the test fake helper's recovery branch omitted the `ROLLBACK_CAPABILITY=MANUAL` line that the real recovery output carries, so the suite could not see the capability gate interact with recovery-shaped output at all.

This change makes the post-mutation capability gate honor the same two-outcome contract as the rest of the transaction: `ROLLBACK_CAPABILITY=MANUAL` is accepted only when recovery markers are present and UNIVERSALLY `=PASS` (the bounded recovery genuinely ran); every other outcome keeps requiring `ROLLBACK_CAPABILITY=VERIFIED` exactly as before. The gate stays fail-closed in both directions — missing or FAIL-shaped recovery output still returns 1, and a recovery success without the honest MANUAL marker also returns 1.

## User scenarios

- US-1 (the F-4 production direction): the post-mutation privileged reconcile runs through the bounded broken-500 recovery path → the helper output carries `SEA_SPEED_AUTH_RECOVERY=PASS` plus the honest `ROLLBACK_CAPABILITY=MANUAL` → the gate accepts it, the deploy completes, and the manifest records the auth check as passed (previously: abort → rollback → workflow red).
- US-2: the post-mutation reconcile completes on the normal path → `ROLLBACK_CAPABILITY=VERIFIED` with no recovery marker → accepted unchanged (today's behavior).
- US-3: the post-mutation reconcile output carries NO capability marker and NO recovery marker → the gate fails closed: source rolled back, manifest state=rolled_back, non-zero exit (current behavior preserved).
- US-4: the output carries a non-PASS recovery occurrence (SEA_SPEED_AUTH_RECOVERY=FAIL-shaped, even alongside a stray =PASS line) → the recovery rule is not satisfied → `ROLLBACK_CAPABILITY=VERIFIED` is still required, keeping the gate fail-closed (universal semantics of peer review F-1 preserved; the pre-mutation sites already abort such output before mutation).
- US-5: the fake helper mirrors the real recovery output shape (bounded recovery success ends with `ROLLBACK_CAPABILITY=MANUAL` + `SEA_SPEED_AUTH_RECOVERY=PASS`), so capability/recovery contract drift becomes visible to CI instead of masked.

## Scope

- `deploy/vps/deploy.sh`: ONLY the capability check in `run_auth_boundary` (the post-mutation reconcile block, the `ROLLBACK_CAPABILITY=VERIFIED` grep) plus its comment; the function itself is kept (byte-pinned by `tests/test_sea_speed_auth_v1.py:467`), every other byte of the deploy transaction unchanged. `deploy/vps/sea-speed-auth-cutover.sh` is NOT touched (its output strings are byte-pinned by `tests/test_sea_speed_auth_v1.py:438`).
- `tests/test_vps_deploy_transaction.py`: fake-helper fidelity fix for the recovery branch (+ fidelity comment), new `reconcile-recovery` and `capability-missing` fake modes, 2 new regression tests; no existing assertion weakened.
- SDD trio `specs/464-rollback-capability-parity/` and the durable progress file (outside the repo tree).
- OUT of scope (residual, D-note): the degraded-503 fallback branch in `run_auth_boundary` (deploy.sh:982-990) returns success with NO capability marker at all — untouched by this change, to be flagged on issue #464 as residual scope. Also out of scope: privileged helper (`sea-speed-auth-privileged-helper.py`) semantics, `install-auth-privilege-boundary.sh`, sudoers, boundary re-render logic, `.github/workflows/**`, `api/**`, `worker/**`, `frontend/**`, live VPS state.

## Requirements

- R-1 (AC-1): a post-mutation reconcile whose output ends with the bounded-recovery success shape (UNIVERSALLY `=PASS` recovery markers + honest `ROLLBACK_CAPABILITY=MANUAL`) completes the deploy (rc 0) with the candidate active and the manifest auth check passed.
- R-2 (AC-2): the normal post-mutation reconcile outcome is unchanged: `ROLLBACK_CAPABILITY=VERIFIED` with no recovery marker is accepted, and the five fixed markers stay enforced (`SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS`, `ACTION=reconcile`, `SEA_SPEED_AUTH_CUTOVER=PASS`, `WORKER_PRIVATE_ROAD_API_BASE=`, `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS`).
- R-3 (AC-3): fail-closed preserved for the non-recovery case: output without any capability marker and without a recovery marker rolls the source back (manifest state=rolled_back, non-zero exit).
- R-4 (AC-4): fail-closed preserved under corrupted recovery output: any non-`=PASS` recovery occurrence means the recovery rule is not satisfied, so `ROLLBACK_CAPABILITY=VERIFIED` is still required and a recovery success without the honest MANUAL marker returns 1.
- R-5 (AC-5): the fake helper's recovery-branch output equals the real helper's recovery output shape (`ROLLBACK_CAPABILITY=MANUAL` + `SEA_SPEED_AUTH_RECOVERY=PASS`), pinned by in-file fidelity comments and the new `reconcile-recovery`/`capability-missing` modes.

## Acceptance criteria

- AC-1: Post-mutation reconcile with bounded recovery output (containing =PASS recovery markers + MANUAL) → deploy completes, auth_status reflects recovery (manifest check auth_v1_road_private_m2m passed), capability MANUAL accepted.
- AC-2: Normal reconcile (VERIFIED, no recovery marker) still accepted with all five fixed markers enforced.
- AC-3: VERIFIED absent AND no valid recovery marker → rolled_back (current behavior preserved for the non-recovery case).
- AC-4: Non-`=PASS` recovery occurrences keep the gate fail-closed (VERIFIED required; recovery success without MANUAL returns 1).
- AC-5: Fake recovery branch output == real helper recovery output shape (MANUAL + RECOVERY=PASS).

## Runtime feedback

- RF-001: Operator actions expected: 0; runtime verification lands with the next routine band-A VPS deploy; the orchestrator records runtime acceptance on issue #464.
- RF-002: Evidence: the next deploy log showing a post-mutation bounded recovery completing into a green deploy (no abort-after-mutation pattern) carries the live proof; RED/GREEN unit transcripts are recorded in the durable progress file.

## NFR assessment

- NFR-001 | Area: security | Target: the post-mutation capability gate stays fail-closed in both directions — ROLLBACK_CAPABILITY=MANUAL is accepted ONLY when recovery markers are present and UNIVERSALLY =PASS (bounded recovery genuinely ran); every other outcome (no capability marker, FAIL-shaped recovery output, recovery success without MANUAL) still returns 1 and rolls the source back; the five fixed markers and the rc gate are byte-unchanged | Validation: unit battery — post-mutation recovery acceptance test (rc 0, candidate active, manifest auth passed), capability-missing abort test (rc 1, rolled_back), diff inspection of the capability block (fixed markers + rc gate unchanged) plus the pre-existing recovery-marker-fail/mixed abort tests still green | Evidence: tests/test_vps_deploy_transaction.py 25/25 OK | Status: PASS
- NFR-002 | Area: reliability/operations | Target: an identical privileged-helper success is accepted consistently pre- and post-mutation — a bounded broken-500 recovery at the post-mutation reconcile no longer aborts the deploy after the source mutation and forces a rollback (the F-4 asymmetry that turns a recovered boundary into a red workflow) | Validation: regression test for the exact F-4 direction (post-mutation reconcile-recovery → rc 0, current=CANDIDATE); RED authenticity — the test fails 1 != 0 against base deploy.sh with the fidelity-fixed fake | Evidence: RED transcript (Ran 25, failures=1, 1 != 0) → GREEN 25/25 OK, recorded in the durable progress file | Status: PASS
- NFR-003 | Area: compatibility | Target: no helper/cutover/installer/sudoers/boundary changes; deploy.sh behavior differs ONLY for the previously-rejected post-mutation recovery outcome; the byte-pinned contracts stay intact (`test_sea_speed_auth_v1.py:438` cutover strings — cutover.sh untouched; `:467` `run_auth_boundary()` presence — function kept); every other failure path unchanged including the degraded-503 fallback branch (residual, D-note in plan.md) | Validation: full-file battery 25/25 OK including all pre-existing failure-path tests unchanged; test_sea_speed_auth_v1.py green; bash -n deploy.sh rc 0 | Evidence: suite transcripts in the durable progress file | Status: PASS
