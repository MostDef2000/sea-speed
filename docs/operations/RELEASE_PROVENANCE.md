# Sea Speed release and deployment provenance

Status: Active operational contract
Issue: #24

## Identity model

A release manifest proves what exact repository scope/artifacts were prepared. A deployment manifest proves what exact release/runtime identity was installed on one contour and which checks passed.

`packaged`, `installed`, `deployed` and `runtime_verified` are distinct.

## New release provenance

New deployable releases use `sea_speed_release_manifest_v2` and must bind:

- canonical Issue;
- applicable merged PR;
- exact base/source commits;
- Outcome Contract and Change Contract hashes;
- approved file set and actual Git diff separately;
- deterministic scope hash;
- component/contour;
- exact artifact path, SHA-256 and size;
- exact-artifact and quality-evidence digests;
- production authorization fingerprint when production applies.

Generate/validate with `scripts/release/build_release_manifest.py` and `scripts/release/validate_release_manifest.py`. Persisted v1 manifests remain readable for rollback compatibility.

## Deployment provenance

`schemas/deployment-manifest.schema.json` supports `vps`, `ubuntu-worker`, and `windows-worker`. Runtime acceptance requires a valid manifest plus contour-specific identity/health/freshness evidence.

## VPS

VPS deployment must identify exact first-parent `main` source, current `push/main` quality proof, installed release, previous release and health/smoke results. The normal production API origin is `127.0.0.1:8010`; protected public `/sea-speed/api/health` is an authentication-boundary check.

## Ubuntu Worker/relay

Ubuntu evidence records exact source release, runtime/package identity where applicable, systemd/service identity, previous/rollback source/runtime, and advancing frame/state/AI/relay evidence required by the task. Protected local config/models/datasets/output are not evidence payloads.

## Windows AI Worker

Windows evidence records exact package/archive digest, installed source identity, previous/rollback version, process verification and applicable freshness/telemetry.

## Completion

Package creation is not installation. A runtime contour advances to `runtime_verified` only when its exact deployment evidence and acceptance checks pass. Evidence must contain no credentials, tokens, TOTP, private media or populated environment values.
