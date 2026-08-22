# Implementation Plan: Camera 1 Runtime Freshness Supervision

- Feature: 035-camera1-runtime-freshness-supervision
- Issue: #255
- Runtime contour: VPS REQUIRED; Ubuntu Worker/relay NOT REQUIRED
- Risk profile: production root timer + bounded single-service restart; availability-sensitive but narrow blast radius

## Correct-course decision

Issue #226 correctly made HLS freshness part of canonical VPS deployment acceptance, but it runs only inside `reconcile`. The 2026-08-22 incident proves the remaining gap is runtime lifetime supervision: FFmpeg can stay `active` while HLS stops advancing, so systemd `Restart=` never fires.

The correct course is an independent fixed watchdog rather than another deploy-time hook or browser workaround. It reuses the already-proven freshness predicate and relay-before-restart ordering, but runs continuously from a root-owned systemd timer. The existing privileged helper is intentionally left unchanged to keep deployment recovery and lifetime recovery as independent controls.

## Design

1. `camera1-h264-freshness-watchdog.py`
   - no CLI args or environment topology;
   - fixed local HLS URL, private relay URL and H264 service name;
   - two media-sequence samples separated by three seconds;
   - healthy output returns no-op;
   - static output checks 300-second cooldown, probes one relay frame, records attempt atomically, restarts only fixed H264 service, verifies active state and post-restart HLS progression;
   - private state `/var/lib/sea-speed-camera1-freshness`, mode 0700, state/lock mode 0600;
   - non-blocking flock prevents overlapping recovery attempts.
2. `sea-speed-camera1-h264-freshness.service`
   - root oneshot, fixed ExecStart, no selectable arguments;
   - basic systemd hardening while retaining network access and ability to request the fixed systemctl restart.
3. `sea-speed-camera1-h264-freshness.timer`
   - first execution 20 seconds after activation;
   - subsequent execution 30 seconds after the previous oneshot becomes inactive;
   - enabled only through the exact-source installer.
4. `install-auth-privilege-boundary.sh`
   - expands its exact-source transaction to install the watchdog and units;
   - records prior watchdog files and timer enabled/active state;
   - installs atomically through `.next` files;
   - production path runs daemon-reload, `enable --now` on the fixed timer and verifies enabled/active;
   - failure restores prior files and prior timer state;
   - test-root path installs bytes but intentionally does not interact with host systemd.
5. Tests cover healthy no-op, stale recovery, relay failure, cooldown, failed post-restart progression, fixed topology and timer/installer contracts.

## Risk-based test design

- Highest risk: restart storm after a persistent upstream/decoder fault. Test records cooldown before restart and proves a second stale observation suppresses restart.
- High risk: watchdog restarts wrong service. Test captures all command argv and requires one exact service literal.
- High risk: upstream outage is misdiagnosed as producer fault. Test relay failure before restart.
- High risk: watchdog itself overlaps. Implementation uses non-blocking flock in root-private state.
- Medium risk: unit installed but not scheduled. Unit/installer tests assert fixed timer activation and production bootstrap verifies enabled + active.
- Medium risk: bootstrap failure leaves a partially installed runtime controller. Installer rollback restores three watchdog assets plus prior timer enabled/active state.
- Regression risk: existing deployment-time recovery. Existing helper is byte-unchanged and remains independently tested by `tests/test_vps_auth_privilege_boundary.py`.

## Deployment Transaction Audit

### ADMISSION
- Source admission: immediately-following `OUTCOME APPROVED` for Issue #255 six-field Scope.
- Runtime authorization: standing production delegation intersected with repository production policy; Issue text is non-authoritative.
- Exact release: merged current-main SHA with required push/main Quality.

### PRE-MUTATION
- Require exact source checkout/repository identity through `install-auth-privilege-boundary.sh`.
- Capture prior watchdog executable/service/timer bytes if present.
- Capture prior timer enabled/active state.
- Validate required source assets are regular non-symlink files.
- Preserve existing helper bundle/sudoers preconditions.

### MUTATION
- Install exact watchdog executable mode 0755.
- Install exact service/timer units mode 0644.
- Preserve existing exact-source helper/bundle/sudoers installation behavior.
- `systemctl daemon-reload` then enable/start only `sea-speed-camera1-h264-freshness.timer`.

### VERIFICATION
- Timer must be enabled and active.
- Healthy HLS must produce watchdog no-op.
- Runtime acceptance must prove autonomous restart/recovery for stale HLS with healthy relay.
- No protected unrelated service may be restarted.

### STATE-COMMIT
- Installer sets success only after bundle validation and timer enabled/active verification.
- Runtime watchdog commits cooldown state atomically before its fixed restart attempt.

### HOUSEKEEPING
- Installer removes temporary staging on all exits.
- Watchdog atomically removes/replaces only its own temporary state file.
- No runtime media, credentials or logs are committed to repository state.

### EVIDENCE
- Source: exact PR head, required CI, merged main SHA, exact-main Quality.
- Bootstrap: `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact `SOURCE_SHA`, `CAMERA1_FRESHNESS_WATCHDOG=INSTALLED`, `CAMERA1_FRESHNESS_TIMER=ACTIVE`.
- Runtime: timer active, pre-recovery static sequence, fixed relay PASS, exactly one H264 restart, post-recovery advancing sequence and authenticated Camera 1 current motion.

### ROLLBACK
- Installer failure restores previous helper/bundle/sudoers plus watchdog executable/service/timer files.
- It daemon-reloads and restores the prior timer enabled/active state best-effort before reporting rollback PASS.
- Runtime watchdog performs no automatic restoration of an older H264 configuration because it changes no H264 configuration; cooldown bounds repeated restart attempts.
- Any deliberate removal/disable after accepted deployment is a separate production rollback decision under the canonical rollback path.

## Production acceptance procedure

After exact-main bootstrap and canonical VPS deployment, observe timer enabled/active. Establish a bounded stale-output test using only approved runtime diagnostics or a naturally occurring incident; do not alter camera/relay/Auth topology. Record local media sequence static while relay frame probe is healthy, then allow the timer to execute without operator restart. Acceptance requires one H264 restart and advancing local/authenticated Camera 1 within 90 seconds. Verify nginx, HLS HTTP, MediaMTX and AI worker service restart counters are unchanged by the watchdog transaction.
