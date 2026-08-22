# Feature Specification: Auth outage fallback

- Feature: 033-auth-outage-fallback
- Issue: #250
- Status: Active
- Source authorization: OUTCOME APPROVED
- Authorization base main: 7eebfb265b86c6594ed3a447ba7707047f6587be

## Product outcome

When the private Ubuntu Worker/Authentik dependency is unavailable, Sea Speed keeps the protected browser boundary fail-closed but replaces the default nginx `500 Internal Server Error` with a VPS-hosted `HTTP 503 Service Unavailable` Sea Speed outage page. The page is served from VPS-local storage, reveals no protected frontend/API/media, offers a retry action, and automatically yields back to the normal Authentik authentication flow after the dependency recovers. The current production `HTTP 500 + private Authentik unreachable (10.123.239.102:19000)` state is an admissible bounded deployment baseline for this protection.

## User scenarios

### Scenario 1 - Authentik unavailable shows 503 fallback

Given an unauthenticated browser requests `https://mostdef.ru/sea-speed/` while the private Authentik path `10.123.239.102:19000` is unreachable, when nginx evaluates the Forward Auth dependency, then the response is `503` with the local VPS outage page, `Cache-Control: no-store` and a retry affordance, and no protected Sea Speed content is returned.

### Scenario 2 - Healthy Authentik keeps normal gating

Given the private Authentik path is healthy, when an unauthenticated browser requests any protected `/sea-speed/**` route, then the response remains `302/401/403` to the Authentik flow and not `503` or anonymous content.

### Scenario 3 - Real application 500 is not masked

Given the private Authentik path is healthy but the upstream application returns a genuine `500`, when the response is evaluated, then it is not classified as `WORKER UNAVAILABLE` and does not return the outage fallback page.

### Scenario 4 - Public root stays available during outage

Given the private Authentik dependency is unavailable, when a browser requests `https://mostdef.ru/`, then the response is `200` and the outage handling does not affect the public root.

### Scenario 5 - Automatic recovery

Given the outage fallback is active, when the private Authentik path recovers, then the next request to a protected route automatically returns to the normal `302/401/403` authentication flow without a manual nginx reload or redeploy.

## Requirements

- FR-001: Every protected `/sea-speed/**` location MUST retain `auth_request /outpost.goauthentik.io/auth/nginx;` and `error_page 401 = @goauthentik_proxy_signin;`.
- FR-002: When the Forward Auth dependency is unavailable for a browser-facing Sea Speed route, the response MUST be `503` with the VPS-local outage page and MUST NOT be `500` or anonymous protected content.
- FR-003: The fallback asset MUST be served only from VPS-local storage and MUST NOT require Worker availability or disclose protected data.
- FR-004: The fallback page MUST NOT be directly usable to bypass authentication and MUST be `internal` with `Cache-Control: no-store` and bounded `Retry-After` semantics.
- FR-005: Ordinary application `500` with a healthy Authentik dependency MUST remain distinguishable from an Authentik/Worker outage and MUST NOT return the outage page.
- FR-006: Public `/` MUST remain `200` during an Authentik outage; unrelated Worker outage MUST NOT affect other VPS surfaces.
- FR-007: After Authentik recovery, protected routes MUST automatically resume normal Authentik gating without manual intervention.
- FR-008: The already-degraded `HTTP 500 + private Authentik unreachable` production state MUST be a supported bounded starting condition for the VPS deployment transaction with exact-source, digest, `nginx -t`, and bounded rollback guarantees.

## Acceptance criteria

- AC-001: Deterministic tests prove every protected Sea Speed route retains Forward Auth and the outage fallback does not create an anonymous bypass.
- AC-002: Unavailable private Authentik for a browser-facing protected route yields `503`, the local outage page, `Cache-Control: no-store`, and bounded retry semantics instead of `500`.
- AC-003: Fallback location is `internal`, not directly requestable for auth bypass, and public `/` stays `200` under the same outage condition.
- AC-004: Protected frontend/API/media are never returned anonymously; ordinary application `500` with healthy Authentik remains a plain `500`.
- AC-005: Release staging/install/rollback carries the fallback asset and `nginx -t` plus service-health evidence is retained.
- AC-006: An already-broken HTTP 500 baseline can transition to the fallback without first restoring Worker/Authentik and the privileged helper remains exact-source/fixed-action/no-shell with byte-identical rollback.
- AC-007: SDD, PR Validation, exact-head aggregate Quality, exact-green-head merge, exact-main Quality, protected VPS deployment evidence, and production acceptance (`/sea-speed/ -> 503` with outage page while Worker unavailable, `/ -> 200`, automatic return after recovery) are recorded.

## NFR assessment

- NFR-SEC-001 | Area: SECURITY | Target: No authentication bypass: every protected route stays fail-closed and fallback does not expose protected content | Validation: renderer tests + negative bypass probe | Evidence: tests/test_sea_speed_auth_v1.py, tests/test_vps_auth_privilege_boundary.py | Status: PASS
- NFR-REL-001 | Area: RELIABILITY | Target: Deterministic 503 fallback for unavailable Authentik; healthy Authentik keeps 302/401/403 and real app 500 stays 500 | Validation: deterministic renderer and integration tests | Evidence: tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-OPS-001 | Area: OPERABILITY | Target: Bounded VPS deployment transaction with exact-source/digest, nginx -t, health checks, and byte-identical rollback; already-degraded 500 baseline is deployable | Validation: deployment transaction tests + VPS workflow | Evidence: tests/test_vps_deploy_transaction.py, deploy/vps/deploy.sh | Status: PASS
- NFR-OPS-002 | Area: OPERABILITY | Target: Fallback page served 100% from VPS-local file, no Worker dependency for outage UX | Validation: asset presence + deployment staging test | Evidence: frontend/sea-speed/unavailable.html | Status: PASS

## Compatibility and boundaries

- Stable interfaces: `mostdef.ru` TLS host, split-include materialization, Forward Auth to private `10.123.239.102:19000`, Worker private M2M listener, public `/`.
- Out of scope: Authentik/PostgreSQL relocation, ZeroTier topology/IP changes, Worker reboot, TOTP/roles/credentials/secrets, stale authentication, AI Water/Road, cameras/MediaMTX, public `/` behavior, `auth.mostdef.ru` topology, standing delegation/IAM/branch protection.
- Runtime impact: VPS only; Ubuntu Worker/relay update NOT REQUIRED and may remain unavailable during deployment.

## Runtime feedback

- Runtime acceptance: PENDING - production acceptance requires `/sea-speed/ -> 503` with Sea Speed outage page while `10.123.239.102:19000` unreachable, `/ -> 200`, no anonymous exposure, and automatic return to normal gating after recovery.
- Accepted production behavior: NOT YET - bounded degraded-state deployment to be proven after exact-main Quality and standing production policy allow.
- Regressions/learning: Current production shows `/sea-speed/ -> 500` with `No route to host` to private Authentik; VPS deploy preflight currently expects healthy Authentik and cannot pass without the bounded outage-safe path introduced here.
- Follow-up work: Wire renderer fallback, extend deployment preflight/test, and record VPS deployment + acceptance evidence in Issue #250.
