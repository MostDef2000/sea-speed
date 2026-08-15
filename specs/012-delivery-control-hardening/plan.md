# Implementation Plan: Delivery Control Hardening

Specification: specs/012-delivery-control-hardening/spec.md
Issue: #172
Status: Accepted / completed

## Architecture

Change Contract derives exact contours. Aggregate quality validates Change Contract + SDD + repository/security/workflow/tests/artifacts/evidence. Production admission independently proves exact first-parent main, exact `push/main` quality, canonical Issue/merged PR and durable authorization before SSH.

## Decisions

### D-001 - Three exact runtime contours
VPS, Ubuntu Worker/relay, Windows AI Worker; `MIXED` preserves exact flags.

### D-002 - Exact-main production admission
No SHA normalization; first-parent main membership required.

### D-003 - Workflow-run quality provenance
PR check name alone is insufficient; require successful `quality-integration.yml` `push/main` exact SHA.

### D-004 - Durable production fingerprint
Issue/PR/Outcome/contours/security/deployment/rollback semantics bind approval.

### D-005 - Release manifest v2
Approved/actual scope are separate and exact artifacts/evidence are hash-bound; v1 remains readable.

## Affected contours

- Repository: CONTROL_PLANE.
- VPS: NONE runtime payload.
- Ubuntu Worker/relay: NONE runtime payload.
- Windows AI Worker: NONE runtime payload.
- Public interfaces: NONE.

## Validation

Focused tests plus PR Validation/Quality integration on exact head and post-merge exact main.

## Runtime feedback

Issue #172 closed completed. Exact 34-path Stage A source was merged with no runtime deployment and post-merge exact-main quality success.
