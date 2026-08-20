# Feature Specification: Authentik 30-Day Session Retention

- Feature: 029-authentik-session-retention
- Issue: #231
- Status: Source implementation
- Owner outcome: Sea Speed users remain signed in for 30 days instead of being forced through the managed login flow after 12 hours, while explicit logout, Owner TOTP and the existing private Authentik topology remain unchanged.

## Product outcome

Set both Sea Speed Authentik User Login stages to `session_duration: days=30`. The ordinary authentication stage and post-enrollment stage must use the same duration. `remember_me_offset` and `remember_device` remain `seconds=0`; this is a single managed session lifetime, not a separate remember-me feature.

Production Authentik runs on the Ubuntu Worker. The canonical blueprint remains `deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml`, so source-derived change control must route that specific blueprint subtree to the Ubuntu contour before the generic VPS rule. Runtime application must use a bounded exact-source Ubuntu transaction that changes only the mounted blueprint and verifies the two managed User Login stage values from the running Authentik worker. Water/Road analytics services, PostgreSQL, nginx and the VPS are not runtime mutation targets for this Outcome.

Production authority is the already-configured standing delegation intersected with repository policy. This Outcome must not reintroduce per-release production approval text or widen standing permissions. Because the current Ubuntu target transaction still references the retired per-release verifier, it must be corrected so the protected workflow policy allow remains the runtime authority gate and the target transaction focuses on exact-source/runtime integrity.

## User scenarios

### Scenario 1 - Existing Sea Speed user signs in

Given the user completes the existing Sea Speed authentication flow, including Owner TOTP when applicable, when the User Login stage creates the authenticated session, then the session duration is 30 days and the existing roles/access policy are unchanged.

### Scenario 2 - Invited user completes enrollment

Given an invited Admin/Operator/Viewer completes the existing invite-only enrollment flow, when the post-enrollment User Login stage creates a session, then that session also uses 30 days and no remember-me/device extension is introduced.

### Scenario 3 - User explicitly logs out

Given an authenticated user chooses the existing Logout action, when logout completes, then the active authenticated session is terminated; the longer maximum session lifetime must not prevent explicit logout or revocation.

### Scenario 4 - Exact blueprint reaches the Ubuntu runtime

Given exact-main Quality succeeded and standing production policy returns `allow` for Issue #231, when the Ubuntu transaction receives the exact merged SHA, then it identifies the release as Authentik-blueprint-only, writes the exact canonical blueprint through the existing mounted file, waits for Authentik worker reconciliation, verifies both managed login stages as `days=30`, and leaves Water/Road service state unchanged.

### Scenario 5 - Authentik does not reconcile the new blueprint

Given the mounted blueprint bytes are changed but the expected runtime stage values do not become visible, when verification expires, then the previous blueprint bytes are restored, the previous two-stage runtime values must be observed again, and the transaction fails closed without restarting PostgreSQL or Water/Road services.

## Requirements

- FR-001: `sea-speed-authentication-login` MUST declare `session_duration: days=30`.
- FR-002: `sea-speed-enrollment-login` MUST declare `session_duration: days=30`.
- FR-003: The canonical blueprint MUST contain exactly two `session_duration: days=30` values and MUST NOT contain an active `session_duration: hours=12` value.
- FR-004: Both managed User Login stages MUST keep `remember_me_offset: seconds=0` and `remember_device: seconds=0`.
- FR-005: Owner TOTP fail-closed behavior, invite-only enrollment, role groups, password policy and application access policy MUST remain unchanged.
- FR-006: `deploy/vps/authentik/blueprints/**` MUST derive `UBUNTU_WORKER` impact before the generic `deploy/vps/**` rule; this Outcome MUST derive `VPS NOT REQUIRED` and `Ubuntu Worker/relay REQUIRED`.
- FR-007: The Ubuntu target transaction MUST NOT consume the retired `verify_production_authorization.py`; protected GitHub Actions standing-policy evaluation remains the runtime authority gate.
- FR-008: An Authentik-blueprint-only release MUST NOT run Water/Road analytics profile reconciliation, `update-exact.sh`, analytics source activation or analytics rollback.
- FR-009: The Authentik reconcile helper MUST require the exact source blueprint, fixed production runtime root and existing mounted runtime blueprint; test-only alternate roots MUST be explicitly gated.
- FR-010: Runtime mutation MUST write only the managed blueprint file; it MUST NOT run image pulls, restart PostgreSQL, restart nginx, restart Authentik containers, or mutate Water/Road service desired/active state.
- FR-011: Runtime verification MUST query exactly `sea-speed-authentication-login` and `sea-speed-enrollment-login` from the running Authentik worker and require duration/remember values `days=30|seconds=0|seconds=0` for both.
- FR-012: Failed verification MUST restore the previous blueprint bytes and require the pre-mutation runtime stage values to reappear before reporting bounded rollback success.
- FR-013: Successful Authentik-only execution MUST emit a standard runtime-verified Ubuntu deployment manifest with exact source, previous main rollback target and non-secret checks for the 30-day stages and unchanged Water/Road services.
- FR-014: Production execution MUST use standing delegation/policy and MUST NOT require or accept a new per-release `PRODUCTION APPROVED`/execution-intent comment.
- FR-015: When zero-touch Ubuntu transport remains unavailable, the protected workflow MAY emit `ONE_COMMAND_FALLBACK` only after policy allow; one operator-local root/sudo execution is transport, not authority.

## Acceptance criteria

- AC-001: Source tests prove exactly two `session_duration: days=30` values and no active 12-hour duration in the canonical blueprint.
- AC-002: Source tests prove exactly two `remember_me_offset: seconds=0` and two `remember_device: seconds=0` values, with Owner TOTP/roles/password policy markers preserved.
- AC-003: Policy tests prove the canonical Authentik blueprint path derives only the Ubuntu Worker active contour.
- AC-004: Ubuntu transaction tests prove the retired per-release verifier is absent and exact current-main first-parent validation occurs before mutation.
- AC-005: Ubuntu transaction tests prove Authentik-only execution bypasses analytics config/update/rollback and preserves Water/Road service state.
- AC-006: Reconcile-helper tests prove successful update, idempotent no-op and failed-apply rollback using the exact mounted file boundary.
- AC-007: Reconcile-helper source tests prove no image pull, PostgreSQL restart, Water/Road restart or unrelated runtime mutation exists.
- AC-008: Exact branch diff stays within Issue #231 authorized paths and PR Change Contract exact changed-file list.
- AC-009: PR Validation and aggregate Quality succeed on one exact head; expected-head merge is followed by exact-main Quality success.
- AC-010: Standing production policy returns `allow` for the exact merged release with `UBUNTU_WORKER` runtime contour and no per-release production prompt.
- AC-011: Canonical Ubuntu deployment reaches `runtime_verified` and records `authentik-login-session-days-30`, two-stage verification and unchanged Water/Road state; if zero-touch transport is absent, the exact policy-allowed one-command fallback completes the same transaction.
- AC-012: Post-deployment authenticated browser acceptance proves Sea Speed remains protected/usable, Owner TOTP semantics remain, explicit Logout terminates the session, and the applied Authentik User Login stages report 30-day duration.
- AC-013: Successful #231 runtime execution also supplies the first ordinary post-#230 autonomous-release evidence required by Issue #229: exact-main Quality -> standing policy allow -> applicable deployment -> runtime_verified -> typed execution audit without per-release approval.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: extend only authenticated session lifetime; no remember-me extension, role/TOTP/password-policy weakening or standing-authority widening | Validation: blueprint contract tests, policy tests, runtime ORM verification, browser logout/TOTP acceptance | Evidence: `tests/test_sea_speed_auth_v1.py`, `tests/test_autonomous_execution_policy.py`, runtime deployment/browser evidence | Status: PASS
- NFR-002 | Area: FAIL_CLOSED | Target: a blueprint that does not reconcile to the exact two-stage 30-day state restores previous bytes/runtime and fails; combined Authentik+analytics mutation is rejected | Validation: reconcile rollback test and transaction source tests | Evidence: `tests/test_ubuntu_authentik_blueprint_reconcile.py`, `tests/test_ubuntu_worker_deploy_authorized.py` | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: normal session expiry no more frequent than 30 days; deployment requires zero per-release production approvals and at most one Ubuntu root/sudo fallback action when zero-touch transport is absent | Validation: source policy/transaction tests plus production policy/deployment evidence | Evidence: #231 Change Contract and production execution audit | Status: CONCERNS
- NFR-004 | Area: CHANGE_ISOLATION | Target: Authentik-only release changes the mounted identity blueprint only and leaves VPS, PostgreSQL and Water/Road runtime state unchanged | Validation: helper/transaction tests and production service-state evidence | Evidence: deployment manifest and helper markers | Status: PASS
- NFR-005 | Area: PROVENANCE | Target: exact merged SHA, exact source-derived Ubuntu contour, policy allow, deployment manifest and typed audit bind the runtime change | Validation: existing v3 release/policy workflow gates plus #231 exact runtime evidence | Evidence: protected Ubuntu workflow artifacts | Status: CONCERNS

## Runtime feedback

- Current production symptom: browser authentication expires frequently enough to require daily sign-in from the operator perspective.
- Current canonical source before this Outcome uses two 12-hour User Login stage durations while remember-me/device offsets are disabled.
- Production Authentik is already healthy on the Ubuntu Worker; full Authentik restaging is unnecessary for this configuration-only change.
- The current autonomous Ubuntu workflow has durable `ONE_COMMAND_FALLBACK` capability evidence because restricted zero-touch Ubuntu transport is not yet provisioned. The Outcome therefore plans one operator-local fallback action unless capability changes before deployment.
