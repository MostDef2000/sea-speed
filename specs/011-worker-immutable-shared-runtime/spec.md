# Specification: Immutable shared Ubuntu Worker runtime

Status: Active
- Issue: #170
Runtime contour: Ubuntu Worker deployment/runtime layer

## Problem

The Ubuntu Worker release model currently puts a complete Python virtualenv under every source SHA. A small source-only change therefore prepares another heavy CUDA/PyTorch/Ultralytics/OpenCV environment even when the runtime definition is unchanged. Production rollout evidence for `8cdf7d5d0a4b2b03ec26500bbfa15a20922c5fb4` showed repeated multi-gigabyte CUDA/PyTorch downloads for dependencies already present in the previously accepted release.

## Product outcome

Separate immutable source identity from immutable runtime identity. Multiple exact source releases may bind to one verified `RUNTIME_ID`. A source-only rollout with an unchanged runtime definition must reuse the existing runtime with zero package installation and zero dependency download.

## User scenarios

1. A small Worker source change is released without changing Python, PyTorch, torchvision, CUDA wheel channel or pinned runtime requirements. The new source release must bind the already-ready runtime and must not invoke pip or download heavyweight packages.
2. The existing production Worker is migrated from the legacy per-source venv layout. The installer verifies the active legacy venv against the new runtime definition and seeds the shared runtime from local bytes, reporting `RUNTIME_ADOPTED ... network_download=false`.
3. The active legacy venv does not exactly match the runtime definition. The first migration stops with explicit evidence instead of silently downloading a new multi-gigabyte runtime.
4. A future change intentionally modifies the runtime definition. A different runtime ID is produced and a new immutable runtime may be built once using the persistent local package cache without mutating prior ready runtimes.
5. A candidate source activation fails its runtime gate. The updater restores the previous exact systemd unit, preserving the previous source/runtime binding and protected shared state.
6. An operator explicitly rolls back across the migration boundary. New releases use their recorded shared runtime ID while legacy releases remain executable from their original per-release venv.

## Requirements

1. Runtime identity must depend on the canonical runtime lock and exact pinned runtime requirements, not on source commit identity.
2. `RUNTIME_ID` must be deterministic and must change whenever either canonical runtime-definition input changes.
3. An existing ready runtime must be verified and reused before any package-install or network-download path is reachable.
4. Ready-runtime reuse must emit `RUNTIME_REUSED runtime_id=<id>` and perform zero `pip install` operations.
5. First migration must prefer an exact matching local legacy per-release venv and emit `RUNTIME_ADOPTED ... network_download=false` when adoption succeeds.
6. If the active release is legacy and no matching local runtime can be safely adopted, preparation must fail closed with `RUNTIME_NETWORK_FALLBACK_BLOCKED`; network creation is forbidden for that migration attempt.
7. A genuinely new runtime may be created only when no ready runtime exists and the protected first-migration block does not apply.
8. New runtime creation must use a persistent package cache under `/opt/sea-speed-worker/cache/wheels`.
9. A new runtime must be prepared in a temporary sibling directory and published to its final runtime ID path only after version/import verification, manifest generation and ready-marker creation.
10. A published ready runtime must be treated as immutable and must never be modified by later source deployments.
11. Each new-format source release must record its exact `runtime-id` alongside source provenance and quality approval.
12. New-format source preparation must not create or populate a heavyweight `releases/<SOURCE_SHA>/venv`.
13. systemd must execute the interpreter from the exact shared runtime ID while executing runner/source paths from the exact source SHA.
14. The unit must expose both `SEA_SPEED_SOURCE_COMMIT` and `SEA_SPEED_RUNTIME_ID` without changing Worker API or event schemas.
15. Activation must retain the existing exact-main quality provenance checks and frame/state/AI runtime progression gate.
16. The active source marker must change only after the exact source/runtime candidate passes activation validation.
17. Automatic activation failure must restore the complete prior exact unit and service.
18. Explicit rollback must validate new-format target runtime readiness and must retain migration-era legacy per-release venv compatibility.
19. Shared config, models, datasets, output, source releases and runtime directories must be preserved.
20. The change must not alter Worker detection, motion, ROI, tracking, speed or event behavior.

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

## Runtime feedback

The accepted production rollout of source release `8cdf7d5d0a4b2b03ec26500bbfa15a20922c5fb4` exposed the deployment inefficiency directly: a fresh per-SHA venv caused the same canonical PyTorch/CUDA dependency family to be installed again, including large cuDNN, cuBLAS, NCCL, cuFFT, cuSolver, cuSPARSE and torch artifacts. The Worker itself subsequently passed its sustained frame/state/AI progression gate, so this feature does not remediate application-runtime instability; it specifically removes redundant dependency preparation from otherwise healthy source-only deployments. The currently accepted release is also the required local migration seed: the first shared-runtime rollout must verify/adopt its compatible venv locally or fail closed rather than redownload the same heavyweight stack.

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
