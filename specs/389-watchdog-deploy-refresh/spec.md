# Spec: Refresh stale camera1-h264 watchdog copy during Ubuntu deploy transaction

- Issue: #389
- Specification: specs/389-watchdog-deploy-refresh/spec.md

## Product outcome

Make the autonomous Ubuntu deploy transaction authoritative for the
`sea-speed-camera1-h264-freshness-watchdog` delivery. After preparing/activating
the exact release, the deploy copies
`deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py` from the release source
to `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` and idempotently
reinstalls the `.service`/`.timer` units, so the stale copy (which reads the legacy
`cam1` path and fails with HTTP 401) can never reproduce across deploys.

The watchdog **logic is not changed** — only its delivery. The real water stream
via the worker is unaffected.

## User scenarios

- US-1: An operator triggers a routine Ubuntu deploy; afterward the installed
  watchdog copy matches the release source and the freshness service is healthy.
- US-2: A deploy runs while the worker/road services are stopped; the watchdog
  refresh still completes because it is independent of those services.
- US-3: A watchdog refresh step fails; the deploy aborts fail-closed and the
  previous release is restored, leaving a safe (pre-fix) state.

## Requirements

- R-1: `update-exact.sh` activation must refresh the watchdog script copy from
  `$release_root/source/deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`
  to `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` (mode 0755, root:root).
- R-2: `update-exact.sh` activation must idempotently reinstall the
  `sea-speed-camera1-h264-freshness.service` and `.timer` units from the release
  source and `enable --now` the timer.
- R-3: Any failure in the watchdog refresh must fail-closed (abort activation),
  consistent with the rest of the transaction.
- R-4: The watchdog refresh must run regardless of the worker/road desired state
  (it is independent of those services).
- R-5: No change to watchdog internal logic, transcode argv credentials (#388),
  VPS, other cameras, or the worker reader fix (#384).

## Acceptance criteria

- AC-001: After deploy, the installed watchdog copy at
  `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` matches the release
  source `camera1-h264-freshness-watchdog.py` (cam1-h264, not cam1).
- AC-002: `sea-speed-camera1-h264-freshness.service` is healthy (no HTTP 401); the
  false alarm is gone.
- AC-003: `update-exact.sh` activation refreshes the watchdog copy, reinstalls the
  units, and enables the timer idempotently.
- AC-004: Any watchdog refresh failure aborts activation fail-closed.
- AC-005: No change to watchdog logic, transcode argv (#388), VPS, other cameras, or
  the worker reader fix (#384).

## Runtime feedback

- RF-001: Operator actions expected: 0; the deploy is autonomous (CONNECTOR).
- RF-002: Watchdog health is observable via `systemctl status
  sea-speed-camera1-h264-freshness.service`.

## NFR assessment

- NFR-001 | Area: reliability | Target: watchdog copy refreshed every deploy | Validation: post-deploy file compare | Evidence: deploy manifest + operator check | Status: PASS
- NFR-002 | Area: security | Target: no credentials introduced | Validation: source review | Evidence: code review | Status: PASS
- NFR-003 | Area: operability | Target: false alarm eliminated | Validation: systemctl status | Evidence: operator report | Status: PASS
- NFR-004 | Area: reversibility | Target: deploy aborts fail-closed; managed units restored | Validation: abort_activation path | Evidence: code review | Status: PASS
- NFR-005 | Area: observability | Target: watchdog health visible | Validation: systemctl status | Evidence: operator report | Status: PASS
