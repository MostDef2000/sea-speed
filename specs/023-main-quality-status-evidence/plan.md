# Implementation Plan: Main Quality status evidence

- Specification: specs/023-main-quality-status-evidence/spec.md
- Issue: #216
- Status: Implementing

## Architecture

Add one standalone GitHub Actions workflow subscribed to `workflow_run` completion for `Quality integration gate`. The job guard admits only source runs with `event=push` and `head_branch=main`. It uses GitHub event metadata only, validates the exact lowercase source SHA, maps the source conclusion to commit-status state, builds a compact JSON payload with inline Python, and posts the status through GitHub REST using the ephemeral `github.token`.

The workflow declares only `statuses: write`, performs no checkout, uses no external actions, reads no artifacts/caches/secrets and executes no repository source. Existing Quality and deployment workflows remain unchanged.

## Decisions

- D-001: Use commit status rather than Issue comments because combined-status lookup is already Connector-readable and natively bound to an exact commit SHA.
- D-002: Use a separate `workflow_run` publisher instead of granting write permissions to the aggregate Quality workflow.
- D-003: Publish only after completion; `success` maps to `success`, every other terminal conclusion maps to `failure` fail-closed.
- D-004: Bind publication exclusively to `workflow_run.head_sha` after lowercase full-SHA validation.
- D-005: Keep a fixed context `sea-speed/quality-push-main` so automation can select one stable evidence channel.
- D-006: Include run number, run ID, conclusion and run URL so the status remains both machine-readable and auditable.

## Affected contours

- Control plane: REQUIRED — GitHub Actions metadata publication only.
- VPS: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Windows Worker: retired; NOT APPLICABLE.
- Operator actions expected: 0.

## Validation

Validation requires exact five-path scope against authorization base `a43ad7bec5bbcd80887bad842ab28c20b135381a`, focused workflow-source regressions in `tests/test_quality_status.py`, repository workflow-policy validation, SDD validation, exact-head PR Validation, aggregate Quality, expected-head merge and end-to-end Connector combined-status evidence on the resulting exact main SHA.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: `tests/test_quality_status.py` trigger and main-push guard assertions
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_quality_status.py` exact head-SHA binding and lowercase SHA assertion
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_quality_status.py` least-privilege permission and no-checkout/no-actions assertions
- TEST-004 | Covers: AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: `tests/test_quality_status.py` fixed context/run identity and fail-closed conclusion mapping assertions
- TEST-005 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: exact Connector compare, PR Validation and aggregate Quality
- TEST-006 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: merged exact-main combined commit status with context `sea-speed/quality-push-main` and source run identity

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: Complete the approved exact five-path source lifecycle and prove the first self-reported merged-main Quality status.

## Runtime feedback

- Current Connector read surface rejects repository/workflow Actions run-list endpoints needed to discover a push/main run from SHA, while exact run reads work only after the ID is known.
- Combined commit status is already exposed by Connector and therefore becomes the durable interoperability boundary.
- No VPS or Ubuntu mutation is required for this control-plane-only change.
