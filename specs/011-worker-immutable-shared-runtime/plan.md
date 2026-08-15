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

## Production rollout

Production remains separately protected. After merge and exact-SHA authorization, use one largest-safe Worker step. The first rollout must show `RUNTIME_ADOPTED ... network_download=false` (or `RUNTIME_REUSED` if a ready runtime already exists), exact source/runtime systemd binding, and a passing runtime progression gate. A later source-only release with the same runtime definition must prove the steady-state `RUNTIME_REUSED` fast path.

VPS deployment is not required.
