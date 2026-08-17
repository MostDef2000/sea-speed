# Sea Speed release and deployment provenance

Status: Active operational contract
Issue: #24

## Identity model

A release manifest proves what exact repository scope/artifacts were prepared. A deployment manifest proves what exact release/runtime identity was installed on one active contour and which checks passed.

`packaged`, `installed`, `deployed` and `runtime_verified` are distinct.

## Active production contours

New production delivery supports **VPS** and **Ubuntu Worker/relay**. A `mixed` release means both active contours are relevant.

Windows Worker is retired. Historical release/deployment manifests containing `windows-worker` remain readable through compatibility schemas/validators but no new Windows production release may be built or routed.

## New release provenance

New deployable releases use `sea_speed_release_manifest_v2` and bind:

- canonical Issue;
- applicable merged PR;
- exact base/source commits;
- Outcome Contract and Change Contract hashes;
- approved file set and actual Git diff separately;
- deterministic scope hash;
- active component/contour;
- exact artifact path, SHA-256 and size;
- exact-artifact and quality-evidence digests;
- production authorization fingerprint when production applies.

Generate/validate with `scripts/release/build_release_manifest.py` and `scripts/release/validate_release_manifest.py`. New builder component choices exclude `windows-worker`. Persisted v1/v2 manifests remain readable for historical rollback/audit compatibility.

## Deployment provenance

`schemas/deployment-manifest.schema.json` remains backward-compatible with `vps`, `ubuntu-worker`, and historical `windows-worker` records. New runtime acceptance is performed only for active VPS/Ubuntu contours.

## VPS

VPS deployment identifies exact first-parent `main` source, current `push/main` quality proof, installed release, previous release and health/smoke results. The normal production API origin is `127.0.0.1:8010`; protected public `/sea-speed/api/health` is an authentication-boundary check.

## Ubuntu Worker/relay

Ubuntu evidence records exact source release, runtime/package identity where applicable, systemd/service identity, previous/rollback source/runtime, and advancing frame/state/AI/relay evidence required by the task. Protected local config/models/datasets/output are not evidence payloads.

## Historical Windows evidence

Old Windows release/package/deployment evidence may include exact archive digest, installed source, process verification and freshness/telemetry. It remains immutable/readable history only and must not be interpreted as a supported current deployment target or prerequisite for new Worker source changes.

## Completion

Package creation is not installation. A runtime contour advances to `runtime_verified` only when its exact deployment evidence and acceptance checks pass. Evidence must contain no credentials, tokens, TOTP, private media or populated environment values.
