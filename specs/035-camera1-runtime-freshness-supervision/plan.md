# Implementation Plan: Camera 1 Runtime Freshness Supervision

- Feature: 035-camera1-runtime-freshness-supervision
- Specification: specs/035-camera1-runtime-freshness-supervision/spec.md
- Issue: #255
- Status: Source implementation
- Runtime contour: VPS REQUIRED; Ubuntu Worker/relay NOT REQUIRED

## Architecture

Three fixed assets plus an installer extension, all under `deploy/vps/**`:

1. `camera1-h264-freshness-watchdog.py` — root-owned Python watchdog:
   - no CLI arguments and no environment topology overrides;
   - fixed local HLS URL `http://127.0.0.1:18889/cam1/index.m3u8`, fixed relay `rtsp://10.123.239.102:8554/cam1`, fixed service `sea-speed-camera1-h264.service`;
   - two media-sequence samples separated by three seconds decide freshness;
   - healthy output is a no-op; static output checks the 300-second cooldown, probes one relay frame, records the attempt atomically, restarts only the fixed H264 service, verifies active state and post-restart HLS progression;
   - private state `/var/lib/sea-speed-camera1-freshness` mode 0700, state/lock mode 0600;
   - non-blocking flock prevents overlapping recovery attempts.
2. `sea-speed-camera1-h264-freshness.service` — root oneshot, fixed ExecStart, no selectable arguments, basic systemd hardening while retaining network access and the ability to request the fixed restart.
3. `sea-speed-camera1-h264-freshness.timer` — first execution 20 seconds after activation, then 30 seconds after the previous oneshot becomes inactive; enabled only through the exact-source installer.
4. `install-auth-privilege-boundary.sh` extends its exact-source transaction to install the watchdog and both units atomically through `.next` files, record prior bytes and timer enabled/active state, daemon-reload, enable/start only the fixed timer, verify enabled/active, and restore prior state on failure. The test-root path installs bytes but never interacts with host systemd.

## Decisions

- Independent fixed watchdog instead of another deploy-time hook or browser workaround: the 2026-08-22 incident proves systemd `Restart=` cannot observe a live process with stale HLS output.
- Reuse the proven freshness predicate and relay-before-restart ordering from Issue #226, but run it continuously from a root-owned timer.
- Leave `deploy/vps/sea-speed-auth-privileged-helper.py` byte-unchanged so deployment-time recovery (#226) and lifetime recovery remain independent controls.
- Media-sequence sampling rather than playlist mtime: mtime can update without sequence advancement.
- Cooldown persisted in the root-private state directory so repeated invocations cannot storm restarts.

## Affected contours

- VPS deployment: REQUIRED
- Ubuntu worker/relay update: NOT REQUIRED
- Production safety envelope: REQUIRED

## Validation

- `python3 scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`
- `python3 -m unittest tests.test_camera1_h264_freshness_watchdog -v` — focused watchdog/unit/installer contract tests
- `python3 -m unittest discover -s tests -p test_*.py` — full suite must stay green
- Required CI: Repository validation + quality-integration on exact PR head
- Post-merge: exact-main push Quality, standing policy evaluation, exact-source bootstrap, runtime acceptance per spec AC-012/AC-013

## Risk profile

- Risk profile: REQUIRED
- RISK-035-001 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: 300-second persisted cooldown plus non-blocking lock bound restart amplification | Validation: cooldown and overlap unit tests | Residual risk: persistent upstream fault yields one bounded restart attempt per cooldown window | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-035-002 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fixed constants, no CLI/env overrides, root-owned units, argv capture assertions forbid other service names | Validation: unsupported-caller-control and forbidden-name tests | Residual risk: none known | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-035-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: mandatory healthy-relay frame probe before any restart avoids misdiagnosing upstream outage as producer fault | Validation: relay-failure no-restart test | Residual risk: transient relay flap delays recovery by one timer cycle | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-035-004 | Category: DATA | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: watchdog writes only its own mode-0600 state files in a root-private directory; no media or credentials persisted | Validation: housekeeping assertions in unit tests | Residual risk: minimal local state files | Owner: Sea Speed Delivery Orchestrator | Status: ACCEPTED

## Test design

- TEST-035-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: advancing-HLS no-op test asserts zero relay probes and zero restarts
- TEST-035-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: static-HLS + healthy-relay test asserts exact FFmpeg argv and exactly one fixed-service restart then post-restart progression
- TEST-035-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: relay-failure test asserts no restart
- TEST-035-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: cooldown test asserts suppressed probe and restart within window
- TEST-035-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: post-restart static HLS fails while retaining cooldown evidence
- TEST-035-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: static analysis proves no selectable URL/service/command and no unrelated protected service names
- TEST-035-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: unit-file tests prove root oneshot runs fixed executable and timer auto-invokes on bounded cadence
- TEST-035-008 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: installer contract tests prove exact-source ownership of only the three watchdog assets plus rollback of prior state
- TEST-035-009 | Covers: AC-009 | Level: unit | Priority: P0 | Evidence: diff-scope assertion keeps final PR inside authorized paths with no secrets/media
- TEST-035-010 | Covers: AC-010, AC-011 | Level: integration | Priority: P0 | Evidence: required CI green on exact head; exact-main push Quality after merge
- TEST-035-011 | Covers: AC-012, AC-013 | Level: runtime-manual | Priority: P0 | Evidence: production bootstrap markers plus autonomous <=90s recovery observation on the VPS

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: New canonical Issue #255 created from the 2026-08-22 active-producer/static-HLS incident evidence.
- Specification impact: New specs/035-camera1-runtime-freshness-supervision specification authored with lifetime-gap outcome.
- Plan impact: Independent continuous watchdog added alongside the unchanged Issue #226 deployment-time reconcile.
- Tasks impact: Tasks 035 cover watchdog, units, installer extension, tests and runtime acceptance.
- Authorization impact: Fresh OUTCOME APPROVED received 2026-08-22 immediately after the six-field Scope; no widening of any other task scope.
- Follow-up: Runtime acceptance after exact-main bootstrap/deploy; relay-side HEVC decoder robustness remains outside this scope.

## Runtime feedback

- Runtime acceptance: REQUIRED — VPS contour; production acceptance must demonstrate autonomous recovery from active-producer/static-HLS to advancing authenticated Camera 1 within 90 seconds.
- Accepted production behavior: only `sea-speed-camera1-h264.service` is restartable, by the fixed root-owned timer installed through the exact-source privilege-boundary installer.
- Regressions/learning: 2026-08-22 incident (media sequence 405 static, relay PASS) recorded as lifetime-gap evidence that deploy-time reconcile cannot cover.
- Follow-up work: relay-side HEVC decoder robustness remains outside the authorized scope.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: FFmpeg producer stays systemd-active while HLS output stalls after HEVC reference/GOP decoder errors; systemd `Restart=` observes process state only and cannot detect media-sequence staleness.
- Production-learning adjacent-stage findings: Issue #226 privileged reconcile covers deployment-time freshness only; no continuous lifetime supervision existed; the fixed private relay was verified healthy during the incident, isolating the fault to the VPS producer lifetime.
- TX-035-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source remains unapproved, nothing installed | Retry: retry after exact Issue/scope/hash admission | Rollback: not applicable | Evidence: Issue #255 six-field Scope, OUTCOME APPROVED receipt, base main 9b569dc84a6fb87d9e48d75d84ed65f260da1ede
- TX-035-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: VPS unchanged, prior watchdog assets and timer enabled/active state captured | Retry: repair preconditions and re-run installer | Rollback: not applicable | Evidence: install-auth-privilege-boundary.sh precondition and regular-file checks
- TX-035-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next files only, live units unchanged until commit point | Retry: re-run exact-source installer transaction | Rollback: installer restores prior files and prior timer state | Evidence: atomic .next install of watchdog executable mode 0755 and units mode 0644
- TX-035-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: installation reported failed and rolled back if verification fails | Retry: re-run daemon-reload and enable --now verification | Rollback: restore prior timer enabled/active state best-effort | Evidence: timer enabled+active check, healthy HLS no-op check
- TX-035-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: success reported only after bundle validation and timer enabled/active verification | Retry: repeat installer transaction | Rollback: prior bytes remain rollback target | Evidence: SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS, CAMERA1_FRESHNESS_WATCHDOG=INSTALLED, CAMERA1_FRESHNESS_TIMER=ACTIVE
- TX-035-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: installed units remain while temporary staging removed | Retry: remove temp staging on all exits | Rollback: no rollback required | Evidence: installer cleanup path; watchdog removes/replaces only its own temp state file
- TX-035-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: acceptance incomplete without evidence | Retry: recollect bootstrap/runtime evidence | Rollback: no evidence-only rollback | Evidence: sanitized pre/post media-sequence values, exactly-one-restart marker, unrelated service restart counters unchanged
- TX-035-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous watchdog assets and timer state restorable | Retry: restore previous bytes and re-verify | Rollback: byte restore of prior executable/service/timer plus prior timer state; deliberate removal after acceptance is a separate canonical rollback decision | Evidence: installer rollback path; runtime watchdog changes no H264 configuration so no automatic config restoration applies
