# Plan: Immutable shared Ubuntu Worker runtime

Status: Active
Issue: #170
Specification: `specs/011-worker-immutable-shared-runtime/spec.md`

## Decisions

- Keep source release identity and AI dependency identity independent.
- Fingerprint the exact runtime lock bytes and existing pinned requirements bytes rather than the source commit.
- Reuse a verified ready runtime before any package-management path.
- Seed the first shared runtime from an exact matching local legacy venv. Do not permit a network fallback during that migration if local compatibility cannot be proven.
- Keep a persistent pip artifact cache under `/opt/sea-speed-worker/cache/wheels` for genuinely new runtime IDs.
- Publish a new runtime only after package/version/import verification and manifest/ready generation in a temporary sibling directory.
- Preserve legacy per-release venvs so rollback remains safe across the migration boundary.
- Continue to use the existing source quality check and runtime progression gate; this change optimizes runtime preparation, not release safety.

## Architecture

The Worker deployment layer is split into two independently immutable identities:

- **source release**: exact Git source SHA under `releases/<SOURCE_SHA>/source` with source/quality provenance and a recorded `runtime-id`;
- **shared runtime**: exact runtime fingerprint under `runtimes/<RUNTIME_ID>` with its Python environment, canonical definition, installed manifest and ready marker.

`update-exact.sh` remains the orchestration boundary. It verifies exact source provenance and quality, delegates source/runtime preparation, renders the systemd unit with both identities, restarts the service, and advances the active marker only after the existing runtime progression gate passes. `prepare-runtime.sh` is the only component allowed to create a shared runtime and is structured as reuse -> local legacy adoption -> protected failure or new-runtime creation. `install-systemd.sh` consumes an already-prepared source/runtime pair and does not perform package installation. `rollback-exact.sh` resolves the target release's runtime binding and preserves compatibility with legacy per-release venv targets during migration.

This keeps the large dependency layer stable across ordinary source changes while preserving exact source rollout and rollback semantics.

## Target layout

```text
/opt/sea-speed-worker/
  releases/
    <SOURCE_SHA>/
      source/
      source-commit
      quality-approved
      runtime-id
  runtimes/
    <RUNTIME_ID>/
      venv/
      runtime-lock.json
      requirements-runtime.txt
      runtime-manifest.json
      ready
  cache/
    wheels/
  shared/
    config/
    models/
    datasets/
    output/
    runtime/
```

## Preparation flow

1. Exact updater fetches and verifies the requested source SHA against `origin/main` and the existing quality integration gate.
2. `install-manual.sh` archives the exact source into its immutable release directory.
3. `prepare-runtime.sh` derives `RUNTIME_ID` from `runtime-lock.json` and `requirements-runtime.txt`.
4. If the runtime is already ready, verify definition + imports/versions and emit `RUNTIME_REUSED`.
5. Otherwise scan local legacy release venvs. If one verifies exactly, copy it locally with reflink support when available, generate manifest/ready, publish atomically, and emit `RUNTIME_ADOPTED`.
6. If the active release is legacy but no local exact match can be adopted, stop with `RUNTIME_NETWORK_FALLBACK_BLOCKED`.
7. If this is not a protected legacy migration and the runtime is genuinely new, create a staging venv and install through the persistent cache, verify it, publish atomically and emit `RUNTIME_CREATED`.
8. Record the runtime ID on the source release.
9. After quality approval, optional activation renders systemd with exact source + runtime IDs, restarts, and runs the existing frame/state/AI progression gate.
10. Only after the gate passes does the updater advance `active-source-commit`.

## systemd and runtime immutability

- `sea-speed-worker.service.template` uses the shared runtime interpreter and exact source runner/entrypoint.
- `SEA_SPEED_RUNTIME_ID` accompanies the existing `SEA_SPEED_SOURCE_COMMIT` for runtime evidence.
- `PYTHONDONTWRITEBYTECODE=1` avoids interpreter bytecode writes into the non-writable ready runtime.
- Runtime preparation makes the ready venv non-writable and never invokes pip against a ready runtime path.

## Rollback plan

`rollback-exact.sh` remains the explicit rollback entrypoint and supports two target formats:

- new target: validate `runtime-id`, ready shared runtime and exact source quality/provenance, then render the target's new-format unit;
- legacy target: validate its existing per-release venv and invoke its legacy `install-systemd.sh` unchanged.

The current unit is backed up before target activation. Failure restores that exact unit and clears systemd start-limit state before restart. This preserves rollback across the migration boundary without rewriting old release directories.

## Validation

Focused tests cover:

- deterministic runtime fingerprinting;
- exact runtime lock contents;
- ready-runtime reuse before pip paths;
- local legacy adoption and blocked network fallback;
- persistent cache and atomic ready publication;
- source release `runtime-id` binding with no per-SHA pip path;
- exact source/runtime systemd binding;
- updater runtime evidence and progression gate;
- runtime-aware plus legacy-compatible rollback.

Repository CI remains authoritative. PR Validation and Quality integration must pass on the exact final head before merge, followed by fresh post-merge gates.

## Affected contours

- Repository change-control classification: `CONTROL_PLANE` for this source diff.
- Ubuntu Worker deployment/runtime layout: affected when a separately authorized exact merged SHA is rolled out.
- Worker application detection/motion/ROI/tracking/speed/event logic: unchanged.
- Protected Worker config/models/datasets/output: unchanged and preserved.
- Camera/RTSP/media relay: unchanged.
- VPS/API/frontend/auth/network topology: unchanged; no VPS deployment required.
- Production mutation: not part of source integration and requires separate exact-SHA authorization.

## Runtime feedback

The previous production rollout demonstrated that exact source deployment itself was healthy but preparation was inefficient: the new source SHA received a new per-release venv and the same large CUDA/PyTorch stack was installed again before the Worker passed its sustained runtime gate. That evidence is the reason for the migration-first guard in this plan. The first shared-runtime production rollout must use the accepted existing venv as a verified local seed (or reuse an already-ready shared runtime); if that cannot be proven, it must stop instead of repeating the heavyweight network download. The existing successful frame/state/AI progression behavior remains the activation acceptance gate after the runtime-layout change.

## Production rollout

Production remains separately protected. After merge and exact-SHA authorization, use one largest-safe Worker step. The first rollout must show `RUNTIME_ADOPTED ... network_download=false` (or `RUNTIME_REUSED` if a ready runtime already exists), exact source/runtime systemd binding, and a passing runtime progression gate. A later source-only release with the same runtime definition must prove the steady-state `RUNTIME_REUSED` fast path.

VPS deployment is not required.
