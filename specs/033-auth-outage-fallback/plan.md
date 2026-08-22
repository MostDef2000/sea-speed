# Implementation Plan: Auth outage fallback

- Specification: specs/033-auth-outage-fallback/spec.md
- Issue: #250
- Status: Active
- Source authorization: OUTCOME APPROVED
- Authorization base main: 7eebfb265b86c6594ed3a447ba7707047f6587be

## Architecture

Extend the VPS nginx Auth v1 boundary with a fail-closed 503 outage fallback that preserves every `auth_request` while adding a VPS-local error handling path. The fallback page lives on VPS at `frontend/sea-speed/unavailable.html` and is installed to `/var/www/mostdef.ru/sea-speed-unavailable.html` by the existing VPS release staging. Nginx renders `error_page 500 =503 /sea-speed-unavailable.html` inside each protected `/sea-speed/**` location together with an `internal` outage location that serves the local file with `Cache-Control: no-store` and `Retry-After: 30`. The fallback fires only when the Forward Auth dependency fails; ordinary upstream application 500 with a healthy Authentik remains a plain 500. Verification continues to require exact-source rendering, `nginx -t`, and service health.

The VPS deployment transaction is extended with an outage-safe preflight: when the protected boundary already reports `500` due to an unreachable private Authentik, the transaction may still proceed through the exact-source, digest-verified, and bounded rollback path. The already-degraded `500` state is therefore not a fatal gate but an admissible baseline that is upgraded to the deterministic `503` fallback.

## Decisions

### D-001 - Do not move Authentik

- Decision: Keep Authentik/PostgreSQL on Ubuntu Worker; Worker IPs and ZeroTier topology stay fixed.
- Reason: Scope intentionally forbids relocation; VPS remains TLS ingress and fail-closed presenter.

### D-002 - VPS-local asset only

- Decision: Outage page is a static file shipped in the release archive and installed by staging; no runtime fetch from Worker.
- Reason: Worker is the failing dependency and must not be required to render its own outage UX.

### D-003 - 503 not 200, scoped to auth dependency failure

- Decision: Map auth-dependency failure `500 -> 503` via `error_page 500 =503` inside protected locations; keep an `internal` dedicated location.
- Reason: `503` is the correct unavailable semantic with bounded retry; `internal` prevents direct anonymous bypass; scoping to auth locations prevents masking real application 500.

### D-004 - Bounded degraded-state deploy

- Decision: Extend `deploy/vps/deploy.sh` preflight and recovery to accept an initial `500 + private Authentik unreachable` state as admissible, then verify transition to `503` fallback after mutation.
- Reason: Current production is already in that state; requiring a healthy Worker first would make the fix undeployable.

### D-005 - No new standing-delegation shape

- Decision: Keep existing `SEA_SPEED_PRODUCTION_DELEGATION_V1` evaluation and protected source gates unchanged.
- Reason: This is a security/operability refinement, not a new production-authority model.

## Affected contours

- VPS: REQUIRED - nginx renderer, fallback asset, cutover staging, privileged helper, deployment transaction, tests, docs.
- Ubuntu Worker/relay: NOT REQUIRED - remains the Authentik origin and may stay unavailable during deployment.
- Windows Worker: retired / NOT APPLICABLE.
- Production deployment: VPS deployment REQUIRED; Production safety envelope REQUIRED.

## Validation

- Static: `nginx_sea_speed_auth` renderer unit tests prove every protected location retains Forward Auth and gains the exact 503 fallback mapping; public `/` and outpost behaviour unchanged.
- Integration: deterministic tests for unavailable Authentik `503` vs healthy Authentik `302/401/403` vs healthy-auth real app `500`.
- Deployment: `validate_repo`, `validate_contracts`, `validate_sdd`, `validate_change_contract`, `validate_delivery_checkpoint`, syntax checks, and existing `test_vps_deploy_transaction` extensions.
- CI: PR Validation + aggregate Quality integration must both succeed on exact head; exact-main Quality after merge.
- Runtime acceptance: manual `https://mostdef.ru/sea-speed/ -> 503` with outage page while Worker unreachable, `/ -> 200`, no anonymous content, automatic return after Worker recovery.

## Risk profile

- Risk profile: REQUIRED
- RISK-033-001 | Category: SEC | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: keep fail-closed `auth_request` on every protected location; fallback is internal static file with no protected content read | Validation: renderer tests + negative bypass probe + manual acceptance | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-033-002 | Category: REL | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: scope fallback strictly to auth-dependency failure; keep real application 500 distinguishable via location-scoped error_page and dedicated internal page | Validation: deterministic fallback vs app-500 tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-033-003 | Category: OPS | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: extend deployment transaction to accept already-degraded 500 baseline with exact-source/digest/nginx -t/rollback guarantees; do not require Worker recovery before staging | Validation: deployment transaction tests + VPS workflow evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-033-004 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: privileged helper stays exact-source/fixed-action/no-shell with byte-identical rollback and ADMISSION/PRE-MUTATION gates before mutation | Validation: privilege boundary tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-033-001 | Covers: AC-001, FR-001 | Level: unit | Priority: P0 | Evidence: `tests/test_sea_speed_auth_v1.py` - every protected route retains auth_request and gains `error_page 500 =503 /sea-speed-unavailable.html` plus internal outage location
- TEST-033-002 | Covers: AC-002, FR-002, FR-004 | Level: unit | Priority: P0 | Evidence: renderer test - unavailable private Authentik yields 503 + local outage page + no-store/Retry-After, fallback is internal
- TEST-033-003 | Covers: AC-003, FR-004, FR-006 | Level: integration | Priority: P0 | Evidence: negative bypass probe + public `/` smoke stays 200
- TEST-033-004 | Covers: AC-004, FR-005 | Level: unit | Priority: P0 | Evidence: real application 500 with healthy Authentik does not map to Worker outage
- TEST-033-005 | Covers: AC-005, FR-003, FR-008 | Level: integration | Priority: P0 | Evidence: `tests/test_vps_deploy_transaction.py` - staging carries fallback asset; degraded 500 baseline can transition to 503 via exact-source transaction
- TEST-033-006 | Covers: AC-006, FR-008 | Level: unit | Priority: P0 | Evidence: privileged helper remains exact-source/fixed-action/no-shell and restores nginx on failure
- TEST-033-007 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: GitHub CI PR Validation + Quality integration on exact head
- TEST-033-008 | Covers: AC-007 | Level: runtime-manual | Priority: P0 | Evidence: VPS deployment manifest + production acceptance while Worker unreachable and after recovery

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #250 records the observed production 500 with `No route to host` to `10.123.239.102:19000` and the inability of the existing bounded recovery to pass without Worker recovery.
- Specification impact: FR-002/FR-008/AC-002/AC-006 add deterministic 503 fallback and admissible degraded-state deployment baseline.
- Plan impact: Adds fallback rendering path and extends deployment transaction preflight without widening standing authority.
- Tasks impact: Implementation tasks extended to renderer, asset staging, deployment transaction and acceptance; SDD quality sections added.
- Authorization impact: Remains inside Issue #250 approved Scope paths and OUTCOME APPROVED; standing delegation unchanged and environment/branch administration stays independent.
- Follow-up: Merge via protected flow, obtain VPS deployment evidence, and close only after production acceptance proves automatic recovery.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE - reviewed deploy/vps/deploy.sh ADMISSION/PRE-MUTATION gates, sea-speed-auth-cutover.sh prepare/activate, privileged helper, and existing transaction tests.
- Production-learning root cause: Existing VPS deploy preflight considered any protected `500` as non-recoverable except bounded Auth v1 reconcile; when the Worker is genuinely unreachable the reconcile itself cannot succeed, leaving the production `500` state undeliverable.
- Production-learning adjacent-stage findings: Renderer had no deterministic fallback path for auth-dependency failure; staging did not carry a VPS-local outage asset; privileged helper and rollback boundaries themselves remain intact.
- TX-033-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source or activation remains unapproved and production unchanged | Retry: retry only after exact Issue/scope/hash/artifact admission is valid | Rollback: not applicable | Evidence: Issue #250 scope, exact base 7eebfb2, public repository and risk classification
- TX-033-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: live nginx and releases unchanged; degraded 500 baseline may still be `500` until mutation | Retry: repair exact source/artifact/nginx -t/host-trust; bounded `500->503` transition is admissible without Worker recovery | Rollback: not applicable | Evidence: exact source/digest, `SEA_SPEED_AUTH_CONFIG=PASS`, `nginx -t` dry-run, privileged helper status PASS, plus `500` with unreachable private Authentik recognized as admissible baseline
- TX-033-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged release and candidate nginx may be partially written; live service still on previous release until verified | Retry: re-stage exact release and re-render candidate; remove partial staging before retry | Rollback: restore original nginx flat file from root-only backup; remove incomplete staging | Evidence: release staging includes `frontend/sea-speed/unavailable.html` -> `/var/www/mostdef.ru/sea-speed-unavailable.html`, candidate nginx with `error_page 500 =503` and internal outage location
- TX-033-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: mutation is not committed if verification fails; previous runtime remains live | Retry: re-verify `nginx -t`, `systemctl is-active`, protected `/sea-speed/ -> 503` fallback vs healthy `302/401/403`, `/ -> 200`, no anonymous content | Rollback: restore flat nginx backup and re-verify `PROTECTED_AUTH_BASELINE` or fallback baseline | Evidence: `nginx -t`, nginx reload, health smokes, `auth_request` retention, `503` fallback with `Cache-Control: no-store` + `Retry-After: 30` and `internal` guard
- TX-033-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: state commit is not declared until verification passes; previous `current-release` pointer remains | Retry: commit `current-release` only after successful verification | Rollback: keep previous `current-release` as rollback target; do not advance state on failed verification | Evidence: `current-release`/`previous-release` pointers and deployment manifest `state: runtime_verified`
- TX-033-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified release may remain active while stale releases await pruning | Retry: prune stale releases without touching current/previous | Rollback: no rollback required solely for leftover pruning residue | Evidence: `prune_releases` preserves current and previous; no private key or secret residue on VPS
- TX-033-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: acceptance remains incomplete even if files are installed | Retry: recollect sanitized deployment manifest, candidate SHA, and production smokes | Rollback: no evidence-only rollback; preserve runtime while recollecting evidence | Evidence: `deployment-manifest.json` with `auth_v1_road_private_m2m` plus `SEA_SPEED_AUTH_CONFIG=PASS`, candidate SHA, and fallback asset digest
- TX-033-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release and flat nginx remain the live rollback target | Retry: reinstall previous release and restore flat nginx, re-verify baseline | Rollback: byte-identical restore of API/frontend/index plus flat nginx conf; service health must return to `200` or `302/401/403`/`503` depending on Worker availability | Evidence: rollback install + `nginx -t` + health smokes and preserved backup ownership/mode

## Rollout and rollback

- Rollout: merge protected PR, verify exact-main Quality, run autonomous VPS deployment via standing policy allow; verify degraded `500 -> 503` transition and then healthy recovery without redeploy.
- Rollback: repository-owned `deploy/vps/deploy.sh` rollback installs previous release and restores flat nginx backup; `nginx -t` + health smokes must pass; no arbitrary root execution or anonymous fallback is left behind.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-main integration and VPS deployment.
- Differences from plan: Expected to extend renderer and deployment transaction exactly as scoped; no topology change.
- Deferred cleanup: NONE
