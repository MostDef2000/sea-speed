# Plan — Issue #631 bootstrap capture of the overlay-canvas module state

- Issue: #631
- Specification: specs/631-bootstrap-overlay-canvas-capture/spec.md

## Architecture

Two additive insertions in `deploy/vps/deploy.sh`, both copying existing
in-function idioms verbatim, plus transaction-fixture coverage:

- `bootstrap_current_release` (capture path): one file-or-marker branch for
  overlay-canvas.js between the road/main.js branch and the unavailable.js
  branch — `install -m 0644 "$OVERLAY_CANVAS_TARGET"
  "$bootstrap_release/frontend/sea-speed/overlay-canvas.js"` when the live
  file exists, otherwise `touch
  "$bootstrap_release/frontend/sea-speed/overlay-canvas.js.absent"` — the
  exact idiom of the seven sibling modular `.js` branches.
- `verify_frontends` (post-activation): one presence-conditional block for
  overlay-canvas.js between the road-main module block and the unavailable
  module block — empty live file fails closed, present file smoke-checked
  through `verify_public_url "Overlay canvas module" "$OVERLAY_CANVAS_URL"`,
  absent file logged as absent in this rollback release.
- URL constant `OVERLAY_CANVAS_URL` after `LIVE_SYNC_URL`, env-overridable
  via `SEA_SPEED_OVERLAY_CANVAS_URL`, mirroring the `OVERLAY_CANVAS_TARGET`
  placement next to `LIVE_SYNC_TARGET`.
- `tests/test_vps_deploy_transaction.py`: the `SEA_SPEED_OVERLAY_CANVAS_URL`
  fixture override and two new tests through the existing
  fake-binary/subprocess fixture idioms.

## Decisions

- **Capture branch copied verbatim from the sibling `.js` branches**: the
  bootstrap capture already records file-or-`.absent` state for every other
  modular frontend asset; overlay-canvas.js was the only live-sync-era
  module missing from the capture, so `install_release`'s :651 module-state
  requirement (`file OR .absent marker`) rejected every bootstrap-captured
  release whose live tree lacked the module — the rollback target of the
  very deploy that created it. The branch restores the invariant "every
  captured release carries an explicit module state" with zero new
  machinery.
- **Placement after road/main.js, before unavailable.js**: the work order
  pins the position to the existing branch ordering of the capture function;
  the branch is byte-identical in shape to its siblings (no comment, same
  install/touch idiom).
- **Presence-conditional verify check, #629 idiom**: identical shape to the
  six #626 module checks — a present module must be non-empty and publicly
  reachable; an absent module is expected in a rollback release and is
  logged, not failed. Empty live files still fail closed. The check sits in
  the healthy path; the Authentik-outage fallback branch keeps its own
  narrower verification and is not extended.
- **URL constant next to LIVE_SYNC_URL**: the `*_TARGET` constants pair
  LIVE_SYNC_TARGET with OVERLAY_CANVAS_TARGET (lines 26-27); the URL
  constants mirror that pairing, keeping the env-override surface
  self-describing.
- **Fixture-only transaction coverage**: the bootstrap scenario is exercised
  by deleting the `current-release` state file and the live overlay-canvas
  module in the existing fixture, then running the standard
  fail-candidate deploy — the bootstrap branch is guarded by
  `[[ -s "$CURRENT_FILE" ]]`, so the empty state file is the documented
  trigger; no new harness, no production script duplication.
- **RED-authenticity before the fix**: the new bootstrap test was run
  against the unmodified deploy.sh and observed failing on the
  overlay-canvas module-state check (the deploy exits during the rollback
  `install_release` with `Release bootstrap-<name> has no overlay-canvas
  module state`); the fix was applied only after the RED run was recorded.

## Affected contours

- VPS contour: `deploy/vps/deploy.sh` — one capture branch in
  `bootstrap_current_release`, one presence-conditional check in
  `verify_frontends`, one URL constant; reaches production through
  deploy-vps.yml after merge (lane A, authorized chain).
- Test contour: `tests/test_vps_deploy_transaction.py` — one env override,
  two new test methods; no fixture machinery changes.
- SDD contour: `specs/631-bootstrap-overlay-canvas-capture/` trio (this
  spec/plan/tasks).
- No CONTROL_PLANE files touched: api/**, frontend/**, worker/**,
  scripts/renderers/** (nginx_sea_speed_auth.py byte-untouched),
  .github/workflows/**, scripts/ci/**, contracts/** stay out of the diff.
- Frozen renderer oracles (test_589, test_618, edge-vhost renderer),
  tests/test_626_csp_no_inline_scripts.py,
  tests/test_auth_session_frontend_contract.py,
  tests/support/frontend_html.py and specs/629-*/** byte-untouched.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the capture branch copies the sibling idiom verbatim and is pinned by a dedicated transaction test that exercises the full bootstrap → failed-candidate → rollback re-activation chain, so the marker record cannot silently regress | Validation: tests/test_vps_deploy_transaction.py (23 tests) + full battery | Residual risk: a bootstrap capture on a tree where the target directory lacks the module records the marker — the intended explicit-absent state, re-activatable by design | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the post-activation check reuses verify_public_url with the same accepted status set as the existing module checks; an absent module logs instead of failing, so degraded rollback verification stays admissible | Validation: transaction tests covering the present-smoke and absent-log paths | Residual risk: an overlay-canvas URL answering an unexpected status fails the deploy closed — same semantics as the existing live-sync check | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: both insertions are strictly additive and copy in-function idioms; existing releases and state files are unaffected, and trees with a non-empty current-release state never enter the bootstrap path | Validation: full battery green (baseline tests unchanged and passing) + bash -n | Residual risk: none identified beyond the existing deploy pipeline semantics | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_transaction.py — test_bootstrap_capture_records_overlay_canvas_module_state: live tree without overlay-canvas.js and no current-release state; the bootstrap capture records the .absent marker; the failed candidate deploy rolls back to the bootstrap release successfully (rolled_back manifest, absent-module log, no module-state failure); RED-authenticity: observed failing line before the deploy.sh fix recorded in the Validation section
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: same file — test_success_smoke_checks_overlay_canvas_module asserts the healthy deploy logs `Overlay canvas module public smoke check passed with HTTP 200` through the new env-overridable URL fixture
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: full battery + ruff + validate_sdd + bash -n observed in the Validation section; git diff scope limited to deploy.sh, the transaction test file and this trio

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, owner authorization recorded in the canonical Issue checkpoint
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while the current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while the active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers; on a fresh tree the bootstrap capture now records the overlay-canvas module state before any candidate staging
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after the existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores the previous deployed release — for a bootstrap-captured target the capture now carries the overlay-canvas marker so the rollback install succeeds | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after the actual current release is known | Rollback: automatic previous-release verification through the accepted loopback origin and protected public smoke, including the overlay-canvas smoke check and absent-module logging for rollback releases | Evidence: origin health, public smoke, exact front release identity (module URLs served or logged absent)
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous deployed main SHA remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: replay the #631 probes without redeployment when exact runtime identity is unchanged | Rollback: decide from actual served bytes, not evidence upload alone | Evidence: deployment manifest plus external probes (overlay-canvas URL 200 or logged absent in a rollback release) and the deploy workflow run record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed release cannot be restored or verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous deployed release — the bootstrap capture now satisfies the module-state requirement that previously dead-ended this stage | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- RED-authenticity (bootstrap test before the deploy.sh fix): OBSERVED —
  `Ran 2 tests in 0.699s` → `FAILED (failures=2)`; the bootstrap test failed
  with `AssertionError: False is not true` on the `.absent`-marker assertion
  and the attached deploy stdout contains the observed failure line
  `Release bootstrap-20261110T000824Z has no overlay-canvas module state`
  (the deploy exits during the rollback `install_release` of the bootstrap
  release); the healthy-deploy smoke test failed on the missing
  `Overlay canvas module public smoke check passed with HTTP 200` line.
- Focused transaction run after the fix `python3 -W error::ResourceWarning
  -m unittest tests.test_vps_deploy_transaction`: OBSERVED — `Ran 23 tests
  in 7.774s` → `OK` (baseline 21 + exactly the 2 new methods).
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p "test_*.py"` → recorded in tasks.md Completion gate.
- ruff (CI config scripts/quality/ruff.toml, repo-wide): OBSERVED — `All
  checks passed!`.
- `bash -n deploy/vps/deploy.sh`: OBSERVED — clean exit.
- validate_sdd: recorded in tasks.md Completion gate.

## Runtime feedback

- RF-001: after merge → deploy-vps.yml dispatch (full merged-main SHA) → the
  bootstrap capture branch and the verify_frontends check run on the next
  VPS deploy; acceptance probes then cover the overlay-canvas URL (200 or
  logged absent on rollback).
- RF-002: rollback for the front = redeploy previous main SHA; the fix is
  rollback-safe by construction — the bootstrap capture records the marker
  state and the verify check is presence-conditional, pinned by the
  bootstrap-capture transaction test.
