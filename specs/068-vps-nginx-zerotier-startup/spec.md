# Feature Specification: VPS nginx ZeroTier startup resilience

- Feature: 068-vps-nginx-zerotier-startup
- Issue: #327
- Status: ACTIVE
- Owner outcome: Public `mostdef.ru` recovers automatically when nginx starts before the fixed VPS ZeroTier address exists, without weakening the private Worker ingress boundary.

## Product outcome

Keep nginx from remaining permanently failed after boot or a service restart races ZeroTier address assignment. A repository-owned, exact-source systemd boundary waits a bounded time for `10.123.239.101`, retries nginx at a controlled cadence when the address is still absent, and preserves the exact private listener `10.123.239.101:18080`.

## Runtime evidence and problem statement

On 2026-08-27 nginx stopped and failed to restart with `bind() to 10.123.239.101:18080 failed (99: Cannot assign requested address)`. ZeroTier later reported network `OK` and `10.123.239.101/24`, and private Authentik health returned HTTP 200, but nginx remained `failed`; public HTTPS refused connections until a manual start. This is a `PRODUCTION_LEARNING` startup-order defect, not a Road frontend defect.

## User scenarios

### Scenario 1 - Address arrives during bounded startup

Given nginx starts before `10.123.239.101` is assigned, when the address appears within the bounded wait, then nginx proceeds with its existing configuration and becomes active without changing the private bind.

### Scenario 2 - Address remains unavailable

Given the exact address remains unavailable through the bounded wait, when the wait expires, then nginx start fails closed and systemd schedules a controlled retry instead of exhausting the start limit or entering an unbounded tight loop.

### Scenario 3 - Exact-source installation and rollback

Given the protected root installer applies the new startup boundary, when installation succeeds, then the fixed helper and systemd drop-in are installed from the exact authorized checkout, systemd is reloaded, nginx is active, and evidence markers are emitted. If any post-install activation check fails, prior files and prior nginx service state are restored.

## Requirements

- R1: The startup helper MUST contain the fixed address `10.123.239.101`, accept no arguments, expose no runtime-selectable topology, and return success only after the address is locally assigned.
- R2: The wait MUST be bounded to 24 attempts at five-second intervals and MUST return status 255 after the final attempt so systemd marks `ExecCondition` failed and applies `Restart=on-failure` rather than treating the condition as a skipped unit.
- R3: The nginx systemd drop-in MUST order after and want `zerotier-one.service`, run the helper before inherited nginx preflight commands, use `Restart=on-failure` with a ten-second delay, and disable start-limit exhaustion without using `Requires=`.
- R4: The private nginx listener MUST remain exactly `10.123.239.101:18080`; no wildcard listener, auth bypass, firewall relaxation or nonlocal-bind sysctl is permitted.
- R5: `install-auth-privilege-boundary.sh` MUST run the fixed-address wait before root-owned mutation, install and back up the helper/drop-in transactionally, daemon-reload systemd, restart and verify nginx on production installs, and restore prior bytes plus prior service state on failure.
- R6: New startup-boundary assets MUST enter deterministic VPS exact artifacts and syntax validation.
- R7: Ubuntu Worker/relay, API, frontend behavior, Authentik policy, detection, tracking, calibration and speed formulas MUST remain unchanged.

## Acceptance criteria

- AC-001: Unit tests prove immediate success, delayed-address success and exact bounded timeout with no selectable topology.
- AC-002: Static/systemd tests prove `ExecCondition` precedes inherited nginx preflight semantics, fixed ordering, controlled retry and absence of `Requires=` or wildcard binding.
- AC-003: Installer tests prove exact-source asset installation, modes, production activation markers and restoration of prior helper/drop-in bytes on injected failure.
- AC-004: Exact-artifact tests prove both new assets are digest-bound in the VPS artifact and shell syntax is valid.
- AC-005: Repository validators, full unit tests, exact-head CI and exact-main Quality pass.
- AC-006: Exact-source VPS bootstrap installs the boundary, nginx becomes active, public `/` returns HTTP 200, and protected `/sea-speed/` returns 302/401/403 or the contract-defined 503 fallback.
- AC-007: Protected deployment evidence reports `runtime_verified`; authenticated Road loads `/sea-speed/live-sync.js` with HTTP 200 and displays current detection boxes.

## NFR assessment

- NFR-068-001 | Area: RELIABILITY | Target: nginx automatically retries after a missing fixed ZeroTier address and becomes active within one bounded wait/retry cycle after address availability | Validation: helper/systemd tests plus production service evidence | Evidence: `tests/test_vps_nginx_zerotier_startup.py`, `systemctl` and HTTP probes | Status: PENDING
- NFR-068-002 | Area: SECURITY | Target: zero widening of the fixed private listener, peer/auth boundary or sudo command surface | Validation: static assertions, exact changed-file review and protected deployment | Evidence: helper/drop-in tests, existing Auth v1 tests and independent review | Status: PASS
- NFR-068-003 | Area: OPERABILITY | Target: no permanent failed state after transient startup ordering and no retry interval below ten seconds | Validation: systemd directive assertions and production restart evidence | Evidence: `sea-speed-nginx-zerotier.conf` and runtime journal/service state | Status: PENDING
- NFR-068-004 | Area: ROLLBACK | Target: prior helper/drop-in bytes and nginx state restored after any failed installer transaction | Validation: injected-failure test and installer transaction review | Evidence: `tests/test_vps_nginx_zerotier_startup.py` | Status: PASS

## Compatibility and boundaries

- Stable interfaces: public URLs, Authentik flow, private Worker API paths and exact IP/port remain unchanged.
- VPS deployment: REQUIRED.
- Ubuntu Worker/relay update: NOT REQUIRED.
- Production safety envelope: REQUIRED.
- Out of scope: route/auth renderer changes, `0.0.0.0:18080`, firewall/sysctl changes, credentials, Ubuntu source, product UI/API logic and analytics formulas.

## Runtime feedback

- Runtime acceptance: PENDING.
- Accepted production behavior: PENDING.
- Regressions/learning: nginx and public HTTPS remained down after ZeroTier recovered because systemd had already left nginx failed.
- Follow-up work: evaluate private-listener process separation only if bounded startup retry proves insufficient; it is not admitted in this task.
