# Ubuntu worker local observability

Status: repository observability contract prepared; physical worker server is not commissioned.

## Scope

This stage adds local, non-secret evidence for one exact Ubuntu worker release. It does not deploy external monitoring, send alerts, expose environment values, delete media, or claim that the worker is operational.

The observability flow has three layers:

1. the exact-release observed runner starts the existing worker and preserves stdout, stderr, and graceful signals;
2. the runner writes an atomic heartbeat while watching frame-file progression and state/event post results;
3. a root-run health checker corroborates that heartbeat against systemd, release provenance, quality evidence, disk headroom, and NVIDIA visibility.

Detection, tracking, ROI, speed, event, API, and frontend semantics are unchanged.

## Files and evidence

Worker heartbeat:

```text
/opt/sea-speed-worker/shared/runtime/worker-heartbeat.json
```

The worker account owns this non-authoritative liveness signal. It contains only:

- schema version;
- exact source commit;
- UTC observation timestamps;
- lifecycle phase;
- frame progression sequence and last frame timestamp;
- state-post success/failure counters and last result;
- event-post success count;
- final exit code when the worker exits.

It does not include HLS URLs, API URLs, tokens, authorization values, environment contents, model contents, images, journal lines, or command output.

Root-owned health report:

```text
/opt/sea-speed-worker/observability/worker-health-report.json
```

This report is authoritative only for the instant at which the health checker ran. It records check outcomes and numeric counters, not raw environment or journal content.

## Exact-release worker runner

The worker systemd unit now executes:

```text
observed-worker-runner.py -> hls_motion_yolo_worker_events.py
```

The runner uses the exact release virtual environment and exact worker source. It forwards SIGTERM and SIGINT to the child process. A normal systemd SIGTERM therefore remains compatible with `SuccessExitStatus=143`.

Frame progression is inferred from changes to:

```text
shared/runtime/output/latest/latest_overlay.jpg
```

This proves that the worker is producing new processed frames without copying or opening media content.

## Install periodic checks

First activate the intended exact release using the updater and verify that the worker unit references `observed-worker-runner.py`. Then run from the same exact release checkout:

```bash
sudo bash deploy/worker/ubuntu/install-observability.sh \
  <active-commit> \
  /opt/sea-speed-worker
```

The installer validates:

- exact release provenance;
- exact `quality-approved` evidence;
- active source marker agreement;
- protected `worker.env` mode without reading the file;
- installed worker unit commit and observed-runner binding;
- checker, runner, service template, and timer template presence.

It installs:

```text
/etc/systemd/system/sea-speed-worker-health.service
/etc/systemd/system/sea-speed-worker-health.timer
```

The installer runs `systemd-analyze verify`, reloads systemd, and enables the timer. It does not start the timer.

## Commissioning activation

Only during Stage 8 commissioning, after the worker service, GPU, HLS, API, and model are verified:

```bash
sudo systemctl start sea-speed-worker-health.timer
sudo systemctl status sea-speed-worker-health.timer --no-pager
sudo systemctl list-timers sea-speed-worker-health.timer --no-pager
```

The timer runs approximately once per minute. The oneshot check requires:

- active marker, exact release provenance, and quality marker agreement;
- installed unit and running `ExecStart` agreement;
- active worker service;
- fresh heartbeat;
- running worker phase;
- fresh frame progression;
- recent successful state post;
- at least 10 GiB free under the installation filesystem;
- at least one NVIDIA GPU visible through `nvidia-smi`.

A failed check exits nonzero, which makes the latest oneshot unit result failed while the timer remains scheduled for the next check.

## Manual check

Run the exact checker directly:

```bash
sudo /opt/sea-speed-worker/releases/<commit>/venv/bin/python \
  /opt/sea-speed-worker/releases/<commit>/source/deploy/worker/ubuntu/check-worker-health.py \
  --install-root /opt/sea-speed-worker \
  --expected-commit <commit> \
  --require-gpu
```

The checker prints deterministic JSON and atomically updates the root-owned report. Exit code `0` means every configured check passed. Exit code `1` means one or more checks failed.

## Safe inspection

Non-secret status files:

```bash
sudo cat /opt/sea-speed-worker/observability/worker-health-report.json
sudo cat /opt/sea-speed-worker/shared/runtime/worker-heartbeat.json
```

Systemd state:

```bash
sudo systemctl status sea-speed-worker.service --no-pager
sudo systemctl status sea-speed-worker-health.service --no-pager
sudo systemctl status sea-speed-worker-health.timer --no-pager
```

Bounded journal inspection:

```bash
sudo journalctl -u sea-speed-worker.service -n 100 --no-pager
sudo journalctl -u sea-speed-worker-health.service -n 50 --no-pager
```

Do not use `systemctl show-environment`, print `/opt/sea-speed-worker/shared/config/worker.env`, or create unreviewed raw diagnostic archives. Current worker logs include operational endpoint text in some messages, so journal access must remain restricted to administrators.

## Failure interpretation

- `active_marker`, `release_provenance`, `quality_approved`, `installed_unit`, or `running_exec` failure indicates exact-release control-plane disagreement.
- `heartbeat_fresh`, `worker_phase`, or `frame_progress` failure indicates stalled or absent frame processing.
- `state_post` failure indicates the worker has not recently confirmed a successful state upload.
- `disk_headroom` failure requires operator action; automatic deletion is reserved for Stage 7.
- `gpu_visible` failure indicates that the commissioning GPU requirement is not met.

The health checker does not restart the worker, update releases, roll back, delete data, or send alerts.

## Runtime boundary

Repository CI validates Python syntax, shell syntax, exact-release bindings, heartbeat behavior, deterministic health evaluation, timer configuration, and secret exclusions. Runtime remains `UNKNOWN` until the physical server is installed and Stage 8 verifies actual GPU visibility, frame progression, API posting, timer execution, reboot recovery, and failure reporting.
