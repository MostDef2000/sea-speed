# Plan — Issue #629 deploy validation coverage for the #626 external scripts

- Issue: #629
- Specification: specs/629-deploy-validation-coverage/spec.md

## Architecture

Two additive check sets in `deploy/vps/deploy.sh`, one scan-surface repoint in
the frontend session-contract test, and transaction-fixture coverage:

- `install_release` (pre-activation): six `.absent`-tolerant validation lines
  after the existing overlay-canvas check — a release must carry either
  `frontend/sea-speed/<module>.js` or its `<module>.js.absent` marker for
  crossing-line.js, main.js, cameras/cameras.js, road/config.js,
  road/main.js and unavailable.js, in the exact idiom and message style of
  the live-sync.js/overlay-canvas.js checks.
- `verify_frontends` (post-activation): six presence-conditional blocks in
  the healthy path, directly after the live-sync check and before the final
  root-frontend smoke — empty live file fails closed, present file is
  smoke-checked through `verify_public_url`, absent file is logged.
- URL constants `CROSSING_LINE_URL`, `MAIN_JS_URL`, `CAMERAS_JS_URL`,
  `ROAD_CONFIG_URL`, `ROAD_MAIN_URL`, `UNAVAILABLE_JS_URL` after
  `LIVE_SYNC_URL`, each env-overridable via `SEA_SPEED_*_URL`.
- `tests/test_auth_session_frontend_contract.py`: the X-authentik-username
  scan moves from `extract_inline_scripts` to
  `frontend_html.page_live_source(path)` — page HTML plus every connected
  local external `.js` body.
- `tests/support/frontend_html.py`: `page_live_source` returns the page HTML
  when the page ships no local external scripts (objects still ships inline
  blocks); a referenced-but-missing local script still raises.
- `tests/test_vps_deploy_transaction.py`: six `SEA_SPEED_*_URL` fixture
  overrides and three new tests through the existing fake-binary/subprocess
  fixture idioms.

## Decisions

- **`.absent`-tolerant install_release validation, copied verbatim from the
  live-sync/overlay-canvas idiom**: the bootstrap capture path records
  `.absent` markers for the six modules when the live tree lacks them
  (pre-#626 rollback releases such as ba590050), so a hard file requirement
  would break rollback re-activation; the marker alternative preserves the
  defense-in-depth goal (an explicit module state is required) without
  breaking rollback.
- **Presence-conditional verify_frontends checks**: identical shape to the
  objects/cameras/road/live-sync checks — a present module must be non-empty
  and publicly reachable; an absent module is expected in a pre-#626 rollback
  release and is logged, not failed. Empty live files still fail closed.
- **Healthy-path placement**: the new checks sit next to the live-sync check
  in the healthy path; the Authentik-outage fallback branch keeps its own
  narrower verification and is not extended.
- **Scan-surface repoint instead of assertion removal**: post-#626 the water,
  cameras and road pages ship no inline scripts, so the inline-only scan was
  vacuum; `page_live_source` covers the HTML plus every connected local
  external `.js` body, keeping the spoofable-header invariant load-bearing
  (RED-authenticity demonstrated by injection, then reverted).
- **Harness tolerance for inline-only pages**: `page_live_source` returns the
  HTML when a page has no local external scripts; a missing referenced script
  still raises, so the scan surface never silently narrows.
- **Fixture-only transaction coverage**: the new checks are exercised by
  extending the existing fixture file (release-shape mutation of the rollback
  release, log assertions, manifest state) — no new harness, no production
  script duplication.

## Affected contours

- VPS contour: `deploy/vps/deploy.sh` — validation-only additions to
  `install_release` and `verify_frontends` plus six URL constants; reaches
  production through deploy-vps.yml after merge (lane A, authorized chain).
- Test contours: `tests/test_auth_session_frontend_contract.py`,
  `tests/support/frontend_html.py`, `tests/test_vps_deploy_transaction.py`.
- No CONTROL_PLANE files touched: api/**, frontend/**, worker/**,
  scripts/renderers/** (nginx_sea_speed_auth.py byte-untouched),
  .github/workflows/**, scripts/ci/**, contracts/** stay out of the diff.
- Frozen renderer oracles (test_589, test_618, edge-vhost renderer) and
  tests/test_626_csp_no_inline_scripts.py byte-untouched.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: both check sets copy the existing `.absent`-tolerant and presence-conditional idioms verbatim; the marker-tolerant rollback path is pinned by a dedicated transaction test so pre-#626 rollback re-activation cannot silently regress | Validation: tests/test_vps_deploy_transaction.py (21 tests) + full battery | Residual risk: a future release shape carrying neither file nor marker for a module fails closed at activation — the intended defense-in-depth behavior | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the post-activation smoke checks reuse verify_public_url with the same accepted status set as the existing module checks; absent modules log instead of failing, so degraded rollback verification stays admissible | Validation: transaction tests covering the present, empty-fail and absent paths | Residual risk: a module URL answering an unexpected status fails the deploy closed — same semantics as the existing live-sync check | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: SEC | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the repointed session-contract scan was proven load-bearing by injecting the spoofable header name into a shipped external .js and observing the test fail; the injection was reverted and hash-verified against the pre-injection bytes | Validation: RED-authenticity demonstration + focused green run | Residual risk: absolute /sea-speed/ script sources remain excluded from the scan surface by the harness design (unchanged since #626); those modules are covered by the deploy-level checks added here | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_transaction.py — each of the six modules unlinked from the rollback release (neither file nor marker) fails the deploy closed with the module-state message, no manifest, current release unchanged
- TEST-002 | Covers: AC-001 + AC-002 | Level: integration | Priority: P0 | Evidence: same file — a pre-#626 rollback release carrying only `.absent` markers re-activates, the live modules are removed, the six absent-module logs appear and the manifest records rolled_back
- TEST-003 | Covers: AC-002 + AC-003 | Level: integration | Priority: P0 | Evidence: same file — a healthy deploy logs all six module smoke checks as passed with HTTP 200 through the six new env-overridable URL fixtures
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: tests/test_auth_session_frontend_contract.py — scan repointed to page_live_source; RED-authenticity demonstrated by injecting the header string into frontend/sea-speed/main.js (observed FAIL), then reverted with hash equality
- TEST-005 | Covers: AC-004 + AC-005 | Level: integration | Priority: P1 | Evidence: tests/support/frontend_html.py tolerance (objects page scans as HTML; missing referenced script still fails closed) exercised by the repointed scan; full battery + ruff + validate_sdd observed in the Validation section

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
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while the current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while the active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers; the new install_release module-state validation rejects a malformed candidate before any staging
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after the existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores the previous deployed main SHA | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after the actual current release is known | Rollback: automatic previous-release verification through the accepted loopback origin and protected public smoke, including the six module smoke checks and absent-module logging for pre-#626 rollback releases | Evidence: origin health, public smoke, exact front release identity (six module URLs served or logged absent)
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous deployed main SHA remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: replay the #629 probes without redeployment when exact runtime identity is unchanged | Rollback: decide from actual served bytes, not evidence upload alone | Evidence: deployment manifest plus external probes (six module URLs 200 or logged absent in a rollback release) and the deploy workflow run record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed main SHA cannot be restored or verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous deployed main SHA | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused transaction run `python3 -W error::ResourceWarning -m unittest
  tests.test_vps_deploy_transaction`: OBSERVED — `Ran 21 tests in 7.058s` →
  `OK` (baseline 18 + exactly the 3 new methods).
- RED-authenticity demonstration: with the header string injected into
  frontend/sea-speed/main.js, `python3 -W error::ResourceWarning -m unittest
  tests.test_auth_session_frontend_contract -v` OBSERVED — `FAIL:
  test_all_protected_frontends_use_same_origin_session_api ...
  (path=frontend/sea-speed/index.html)`, `AssertionError:
  'X-authentik-username' unexpectedly found in '<!doctype html>...'`,
  `FAILED (failures=1)`; after revert the file hash equals the recorded
  pre-injection sha256 9fa6fe32fb63c6243aa4b88b0085446a19efd670622160baa5bbb8086cddb2e7
  and the focused run is `Ran 4 tests / OK`. The demonstration is not part of
  the final diff.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p "test_*.py"` → `Ran 1424 tests in 172.768s`, `OK (skipped=2)` —
  baseline 1421 OK (skipped=2) + exactly the 3 new transaction methods.
- ruff (CI config scripts/quality/ruff.toml, repo-wide): OBSERVED — `All
  checks passed!`.
- validate_sdd: recorded in tasks.md Completion gate.

## Runtime feedback

- RF-001: after merge → deploy-vps.yml dispatch (full merged-main SHA) → the
  new install_release and verify_frontends checks run on the next VPS deploy;
  acceptance probes then cover the six module URLs (200 or logged absent on
  rollback).
- RF-002: rollback for the front = redeploy previous main SHA; the new
  validation is rollback-safe by construction (marker-tolerant
  install_release, presence-conditional verify_frontends), pinned by the
  pre-#626 rollback transaction test.
