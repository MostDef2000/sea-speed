# Implementation Plan: Delivery Control Hardening

Specification: specs/012-delivery-control-hardening/spec.md
Issue: #172
Status: Active

## Architecture

Delivery admission is layered and fail closed. `scripts/ci/validate_change_contract.py` derives the exact runtime contour set from source paths. The aggregate quality workflow validates Change Contract, SDD linkage, repository contracts, security/workflow policy, tests, deterministic artifacts, and evidence. `deploy-vps.yml` independently proves exact current-main membership, exact successful main-push quality evidence, canonical Issue/merged-PR linkage, and durable production authorization before any SSH setup.

Release provenance v2 consumes non-secret authorization evidence generated from GitHub canonical data. It binds Issue, PR, source/base commits, Outcome Contract hash, Change Contract hash, approved files, actual Git diff, artifact SHA-256 values, and exact-artifact/quality evidence digests. Legacy v1 validators remain available for persisted rollback evidence.

## Decisions

- Runtime contours are `VPS`, `UBUNTU_WORKER`, and `WINDOWS_WORKER`; `MIXED` is the summary class when two or more apply, while the three deployment fields preserve the exact set.
- Shared `worker/**` Python/runtime source is treated as affecting both Ubuntu and Windows unless a more-specific rule classifies it.
- Production SHA input is not normalized: only an already-lowercase full 40-character SHA is accepted.
- Main membership is first-parent membership, preventing a merged feature-head SHA from masquerading as a deployable main release.
- Aggregate quality proof comes from the Actions workflow-run API with exact `push/main/head_sha` properties, not from a check-run name alone.
- Durable production approval is an Issue comment by a source-controlled authorized actor whose first line is exact `PRODUCTION APPROVED <sha>` and whose fingerprint matches current authorization-bound semantics.
- `production` environment approval remains defense in depth and does not replace durable authorization.
- New release writes use v2; legacy release/deployment v1 remains readable.
- No branch-protection setting change is part of Stage A; workflow policy is the canonical merge-facing gate but repository settings are not claimed to enforce it.

## Affected contours

Source task: CONTROL_PLANE only.

Production runtime contours modeled by the controls: VPS, Ubuntu Worker/relay, Windows AI Worker.

Runtime payload changes: none. No `api/**`, `frontend/**`, `deploy/vps/**`, `deploy/worker/ubuntu/**`, or `worker/**` runtime implementation payload is modified by Stage A.

## Validation

- Unit tests for exact contour derivation and deployment flags.
- Unit tests for quality workflow-run provenance and uppercase rejection.
- Unit tests for durable production authorization fingerprint boundaries.
- Unit tests for release manifest v2 scope/artifact constraints and v1 compatibility.
- Unit tests for deployment manifest three-target compatibility.
- SDD linkage tests and static workflow architecture checks.
- Repository contract, workflow policy, syntax, deterministic artifact, quality evidence, property/fuzz, and full behavioral test suites through `quality-integration`.
- PR Validation and Quality integration must both succeed for the exact final PR head.

## Runtime feedback

Production deployment is NOT REQUIRED and is forbidden for this Stage A source lifecycle. After merge, source evidence is recorded on Issue #172; no VPS/Ubuntu/Windows runtime mutation or acceptance run is performed.
