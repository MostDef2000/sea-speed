# Implementation Plan: VPS nginx ZeroTier startup resilience

- Specification: specs/068-vps-nginx-zerotier-startup/spec.md
- Issue: #327
- Status: ACTIVE

## Current behavior

The Auth v1 renderer intentionally binds Worker ingress to `10.123.239.101:18080`. Ubuntu's inherited nginx `ExecStartPre` runs `nginx -t`; when that address is absent, preflight returns `EADDRNOTAVAIL`, nginx fails, and later ZeroTier recovery does not start it again. The public root, protected UI and TLS ingress share the same nginx service, so the failed private bind takes all public HTTPS offline.

## Architecture

Install one fixed no-argument helper and one nginx systemd drop-in through the existing exact-source root privilege-boundary transaction. The drop-in uses `ExecCondition` so the address check runs before inherited nginx `ExecStartPre`, waits at most 120 seconds, and returns status 255 after timeout; unlike statuses 1..254, this marks the unit failed rather than skipped. `Restart=on-failure`, `RestartSec=10s`, and unit-level `StartLimitIntervalSec=0` make later address recovery observable without a tight loop or permanent failed state. `Wants=`/`After=` improve startup order while deliberately avoiding `Requires=` so a later ZeroTier service transition does not stop an already-serving public nginx.

## Decisions

### D-001 - Preserve exact bind and wait before nginx preflight

- Decision: keep `10.123.239.101:18080` unchanged and gate nginx preflight with a fixed helper.
- Reason: fixes the observed ordering race without exposing Worker ingress on public interfaces.
- Alternatives rejected: wildcard `0.0.0.0:18080` widens network exposure; `ip_nonlocal_bind` changes global kernel policy; nginx `transparent` grants unnecessary capability.

### D-002 - ExecCondition plus controlled retry

- Decision: use `ExecCondition`, bounded wait, `Restart=on-failure`, ten-second retry and no start-limit exhaustion.
- Reason: `ExecCondition` executes before inherited `ExecStartPre`; a service-failure exit permits systemd retry after later address recovery.
- Alternatives rejected: appending `ExecStartPre` may run after inherited `nginx -t`; one-shot boot ordering alone does not handle delayed address assignment.

### D-003 - Wants/After, never Requires

- Decision: order nginx after `zerotier-one.service` with `Wants=` and `After=` only.
- Reason: public nginx must not be stopped solely because the private overlay service changes state.
- Alternatives rejected: `Requires=` couples public availability to ZeroTier lifecycle.

### D-004 - Extend existing exact-source root transaction

- Decision: install, back up, activate and roll back the helper/drop-in in `install-auth-privilege-boundary.sh`.
- Reason: reuses the existing narrow root-owned path, exact checkout checks and transactional backup model without adding sudo authority.
- Alternatives rejected: manual `/etc/systemd` edits are not durable source or provenance; a new generic root command widens privilege.

## Affected contours

- VPS: REQUIRED — systemd/nginx startup control and exact-source bootstrap.
- Ubuntu Worker/relay: NOT REQUIRED — no source or service mutation.
- Public interfaces: paths unchanged; availability restored.
- Security boundary: fixed private listener and existing Auth v1 rules preserved.

## Validation

- Unit: fixed helper immediate/delayed/timeout behavior with fake `ip`/`sleep` executables.
- Integration: test-root installer writes modes/content and injected failure restores prior assets; production-source inspection proves the fixed-address wait precedes `MUTATED=1`; exact artifacts include both files.
- Systemd syntax: `systemd-analyze verify` loads a synthetic nginx base unit, ZeroTier unit and the exact drop-in through an isolated unit path.
- Static: shell syntax, fixed directives, no wildcard bind/`Requires=`/runtime topology.
- Repository: `validate_repo.py`, `validate_sdd.py`, `validate_contracts.py`, quality validators and full unittest discovery.
- Runtime: exact-source bootstrap markers, drop-in/helper digest and modes, nginx active, root 200, protected route contract, protected deployment manifest and authenticated Road acceptance.

## Risk profile

- Risk profile: REQUIRED
- RISK-068-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: preserve exact bind; reject wildcard listener, nonlocal-bind sysctl, route/auth and sudo-surface changes | Validation: static tests and diff review | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-068-002 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: bounded 120-second wait, ten-second retry, no start-limit exhaustion, production service verification | Validation: deterministic timeout/recovery tests plus runtime evidence | Residual risk: MEDIUM | Owner: Sea Speed Delivery Orchestrator | Status: OPEN
- RISK-068-003 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: transactionally back up/restore both assets and prior nginx state | Validation: injected post-install failure | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-068-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: `Wants`/`After` without `Requires` prevents a ZeroTier lifecycle event from directly stopping active public nginx | Validation: systemd directive test | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-068-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: immediate, delayed and timeout helper subprocess tests
- TEST-068-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: exact systemd directive and forbidden-directive assertions
- TEST-068-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: test-root installer success and injected rollback tests
- TEST-068-004 | Covers: AC-004,AC-005 | Level: integration | Priority: P0 | Evidence: deterministic artifact build/validation, repository validators and full unittest
- TEST-068-005 | Covers: AC-006 | Level: end-to-end | Priority: P0 | Evidence: exact-source bootstrap, systemd state and public/protected HTTP probes
- TEST-068-006 | Covers: AC-007 | Level: runtime-manual | Priority: P0 | Evidence: deployment manifest/execution audit and authenticated browser Network/canvas observation

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #327 returns from runtime acceptance to a newly authorized protected-boundary remediation.
- Specification impact: new SDD 068 records the adjacent startup-order defect; SDD 065 history remains immutable.
- Plan impact: adds an exact-source root bootstrap before protected Connector deployment.
- Tasks impact: includes all eight deployment transaction stages and final 065b acceptance.
- Authorization impact: fresh six-field Scope immediately followed by `OUTCOME APPROVED commit approved`; durable receipt generation 8.
- Follow-up: process separation is deferred unless bounded retry fails acceptance.

## Deployment transaction audit

- TX-068-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current failed nginx/runtime unchanged | Retry: correct source/authorization evidence | Rollback: not applicable | Evidence: Issue #327 generation 8, exact main base and changed-file allowlist
- TX-068-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: existing helper/drop-in/nginx untouched | Retry: repair exact checkout, repository identity, required tool or asset | Rollback: not applicable | Evidence: installer exact SHA/origin, regular-file and user checks
- TX-068-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: installer cleanup restores prior files | Retry: rerun exact-source installer after root cause correction | Rollback: restore helper, drop-in and existing privilege assets | Evidence: atomic `.next` installs and transaction backup
- TX-068-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: cleanup restores prior files/service state | Retry: validate fixed address/systemd/nginx state then rerun | Rollback: transaction cleanup | Evidence: daemon-reload, nginx restart/is-active, modes and markers
- TX-068-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: `SUCCESS` remains false and cleanup runs | Retry: complete all checks | Rollback: prior bytes and state | Evidence: `SUCCESS=1` only after service verification
- TX-068-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST_EFFORT | State after failure: accepted assets remain; temporary directory cleanup retried | Retry: remove bounded temp files | Rollback: not required for temp cleanup | Evidence: installer EXIT trap
- TX-068-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: no runtime completion claim | Retry: rerun protected deployment/evidence collection | Rollback: source/runtime state unchanged | Evidence: exact artifacts, release manifest v3, deployment manifest and execution audit
- TX-068-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: escalate with exact prior service/file evidence | Retry: repository-owned installer rollback or prior exact release | Rollback: restore previous helper/drop-in and nginx state | Evidence: injected rollback test and production rollback target

## Rollout and rollback

- Rollout: exact-green PR -> exact-main Quality -> root exact-source privilege-boundary bootstrap -> protected autonomous VPS deployment -> public/protected/authenticated acceptance.
- Rollback: installer transaction restores prior startup assets before source deployment; after accepted deployment use previous runtime-verified exact commit and its matching privilege bundle.

## Runtime feedback

- Actual architecture after acceptance: PENDING.
- Differences from plan: NONE YET.
- Deferred cleanup: private-listener process separation is explicitly deferred.
