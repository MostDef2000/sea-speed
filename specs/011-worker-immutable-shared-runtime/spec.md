# Specification: Immutable shared Ubuntu Worker runtime

Status: Active
- Issue: #170
Runtime contour: Ubuntu Worker deployment/runtime layer

## Problem

The Ubuntu Worker release model currently puts a complete Python virtualenv under every source SHA. A small source-only change therefore prepares another heavy CUDA/PyTorch/Ultralytics/OpenCV environment even when the runtime definition is unchanged. Production rollout evidence for `8cdf7d5d0a4b2b03ec26500bbfa15a20922c5fb4` showed repeated multi-gigabyte CUDA/PyTorch downloads for dependencies already present in the previously accepted release.

## Product outcome

Separate immutable source identity from immutable runtime identity. Multiple exact source releases may bind to one verified `RUNTIME_ID`. A source-only rollout with an unchanged runtime definition must reuse the existing runtime with zero package installation and zero dependency download.

## Runtime identity

1. `deploy/worker/ubuntu/runtime-lock.json` defines the canonical Python ABI family, PyTorch version, torchvision version, CUDA wheel index and verification imports.
2. The exact bytes of `deploy/worker/ubuntu/requirements-runtime.txt` are part of the runtime definition.
3. `RUNTIME_ID` is the lowercase SHA-256 of `runtime-lock.json + NUL + requirements-runtime.txt`.
4. Any byte change in either canonical runtime input produces a different runtime ID.
5. A ready runtime lives at `/opt/sea-speed-worker/runtimes/<RUNTIME_ID>` and contains a venv, the runtime definition, an installed-runtime manifest and a ready marker.
6. A ready runtime is immutable. Preparation must never run pip against an already-ready runtime.

## Runtime preparation order

Preparation must use this order:

1. If the exact runtime ID exists and verifies, return `RUNTIME_REUSED` immediately without pip or network access.
2. If no ready runtime exists, inspect existing legacy per-release venvs for an exact match to the runtime definition. A matching venv may be copied locally into the new shared runtime and returns `RUNTIME_ADOPTED` with `network_download=false`.
3. During the first migration from an active legacy per-release venv, failure to verify a safe local adoption must stop explicitly. It must not silently fall back to a large network reinstall.
4. Outside that protected legacy-migration case, a genuinely new runtime ID may be created once. Package installation uses a persistent cache rooted at `/opt/sea-speed-worker/cache/wheels`.
5. Runtime creation occurs in a temporary sibling directory. The final runtime path is published only after exact package/import verification, manifest generation and ready-marker creation.

## Source release contract

A prepared source release contains:

- `/opt/sea-speed-worker/releases/<SOURCE_SHA>/source/`;
- `source-commit` with the exact 40-character source SHA;
- `quality-approved` after the existing quality gate succeeds;
- `runtime-id` with the exact 64-character runtime ID.

The source release does not own or install a heavyweight per-SHA venv in the new format.

## systemd contract

The installed unit binds both immutable identities simultaneously:

- Worker Python: `/opt/sea-speed-worker/runtimes/<RUNTIME_ID>/venv/bin/python`;
- Worker source/runner: `/opt/sea-speed-worker/releases/<SOURCE_SHA>/source/...`.

The unit exposes both `SEA_SPEED_SOURCE_COMMIT` and `SEA_SPEED_RUNTIME_ID`. Existing protected `worker.env`, shared runtime working directory, models, datasets and output paths remain unchanged.

## Activation and rollback

- Activation keeps the existing exact-main ancestry check, quality check, service restart and runtime progression/AI readiness gate.
- The active source marker changes only after the exact source/runtime unit passes the runtime gate.
- On activation failure, the updater restores the complete previous systemd unit, which restores its exact source/runtime binding.
- Explicit rollback validates the target source provenance and quality marker.
- New-format rollback targets must reference a ready shared runtime ID.
- Legacy rollback targets without `runtime-id` remain supported through their existing per-release venv during migration.
- Shared config, models, datasets, output, source releases and runtime directories are preserved.

## Protected behavior

This feature must not change:

- Worker motion/ROI/detection/tracking/speed/event algorithms;
- YOLO model, class or confidence configuration;
- RTSP/media relay behavior;
- Worker API/event schemas;
- VPS/frontend behavior;
- authentication, nginx, Authentik or ZeroTier topology;
- NVIDIA driver or host CUDA driver installation;
- protected models, datasets, config or output contents.

## Failure behavior

- A ready runtime that fails provenance or import/version verification is rejected and never mutated in place.
- An incomplete new runtime is kept only in a temporary staging path and is not selectable by systemd.
- First-migration adoption mismatch fails closed with explicit evidence rather than network fallback.
- A new runtime creation failure leaves any previously ready runtime and active service untouched.
- Activation failure restores the prior exact unit/service before the updater returns failure whenever a prior accepted release exists.

## Acceptance criteria

1. Two source SHAs with unchanged runtime inputs derive the same runtime ID.
2. An already-ready runtime returns `RUNTIME_REUSED` before any pip path and performs no package download.
3. First migration can adopt the currently installed compatible per-release venv from local bytes and returns `RUNTIME_ADOPTED ... network_download=false`.
4. Unsafe first-migration adoption stops explicitly and cannot fall through to network creation.
5. A genuinely new runtime uses the persistent local package cache and returns `RUNTIME_CREATED` only after verification.
6. Runtime publication is atomic with respect to the ready marker.
7. New source releases record `runtime-id` and do not create a release-specific heavy venv.
8. systemd ExecStart proves exact source SHA and exact runtime ID simultaneously.
9. Existing frame/state/AI runtime progression gate remains mandatory.
10. Automatic activation failure restores the previous source/runtime binding.
11. Explicit rollback supports both new shared-runtime targets and migration-era legacy targets.
12. Existing Worker application behavior and protected shared state are unchanged.
13. PR Validation and Quality integration pass on the exact final head.
14. After separate production authorization, first migration completes without redownloading the unchanged CUDA/PyTorch stack.
15. A subsequent source-only production rollout demonstrates `RUNTIME_REUSED` with no heavyweight dependency installation/download.
