# Feature Specification: Main Quality status evidence

- Feature: 023-main-quality-status-evidence
- Issue: #216
- Status: Implementing
- Owner outcome: Make exact-main Quality admission machine-readable through Connector-visible commit status evidence.

## Product outcome

After the existing `Quality integration gate` completes for a `push` to `main`, a separate least-privilege workflow publishes one commit status on the exact `workflow_run.head_sha`. The fixed context is `sea-speed/quality-push-main`; the status carries the source run number, run ID, conclusion and run URL. Delivery Orchestrator can then prove exact-main Quality through commit-status lookup without requiring an operator to copy a GitHub Actions run ID.

## User scenarios

### Scenario 1 - successful main Quality is self-reporting
Given `Quality integration gate` completes successfully from a push to `main`, the exact source SHA receives `sea-speed/quality-push-main=success` with source run identity and URL.

### Scenario 2 - unsuccessful main Quality fails closed
Given the same main-push Quality workflow completes with any non-success conclusion, the exact source SHA receives a non-success status and cannot be mistaken for accepted Quality evidence.

### Scenario 3 - PR Quality does not publish main evidence
Given `Quality integration gate` completes for a pull request, no `sea-speed/quality-push-main` status is published by this workflow.

## Requirements

- FR-001: The publisher MUST trigger only from completed `workflow_run` events for workflow name `Quality integration gate`.
- FR-002: The publishing job MUST execute only when the source run event is `push` and source branch is `main`.
- FR-003: The status target MUST be the exact lowercase 40-character `workflow_run.head_sha`; malformed or non-lowercase SHA input MUST fail closed.
- FR-004: The status context MUST be `sea-speed/quality-push-main`.
- FR-005: A source conclusion of `success` MUST map to status state `success`; every other terminal source conclusion MUST map to non-success state `failure`.
- FR-006: Status evidence MUST include source run number, run ID, conclusion and GitHub-owned run URL.
- FR-007: Workflow permissions MUST be limited to `statuses: write`; all unspecified permissions remain none.
- FR-008: The publisher MUST NOT check out repository code, execute repository code, consume artifacts/caches/secrets, or receive deployment/runtime credentials.
- FR-009: Existing `quality-integration.yml`, deployment workflows, runtime source and production authorization semantics MUST remain unchanged.

## Acceptance criteria

- AC-001: Static regression proves `workflow_run`, `Quality integration gate` and `completed` are the only source-workflow trigger markers.
- AC-002: Static regression proves job admission checks source event `push` and source branch `main`.
- AC-003: Static regression proves exact `workflow_run.head_sha` binding plus lowercase full-SHA validation.
- AC-004: Static regression proves only `statuses: write` is declared and checkout/third-party actions are absent.
- AC-005: Static regression proves fixed context, run ID, run number, conclusion and run URL are included in publication inputs/payload.
- AC-006: Static regression proves success maps to `success` and all non-success terminal conclusions map to `failure`.
- AC-007: Exact PR diff contains only the five authorized repository paths and passes exact-head PR Validation plus aggregate Quality.
- AC-008: After expected-head merge, the new exact `main` SHA receives `sea-speed/quality-push-main=success` from its own successful push/main Quality run and the status is readable through Connector combined-status lookup without manual run-ID input.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: publisher has only commit-status write capability and executes no repository or artifact content | Validation: static workflow regression plus workflow policy gate | Evidence: `.github/workflows/main-quality-status.yml`, `tests/test_quality_status.py` | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: Quality evidence is cryptographically scoped by exact 40-character source SHA and cannot accept PR-triggered Quality | Validation: guard/SHA/status mapping regressions plus end-to-end merged-main status | Evidence: `tests/test_quality_status.py` and Issue #216 | Status: CONCERNS
- NFR-003 | Area: OPERABILITY | Target: Delivery Orchestrator needs zero manual run-ID handoffs for future exact-main Quality admission | Validation: Connector combined-status lookup on merged exact main | Evidence: Issue #216 completion evidence | Status: CONCERNS

## Runtime feedback

- Current authorization base is `a43ad7bec5bbcd80887bad842ab28c20b135381a`.
- The GitHub Connector can read combined commit status for an exact SHA but cannot enumerate push/main Actions runs by SHA through its currently exposed surface. Repository script `scripts/quality/verify_quality_status.py` can perform the Actions query when executed with a token, demonstrating that the missing capability is Connector read exposure rather than absent GitHub data.
- This Outcome moves the minimum required Quality identity into Connector-readable commit status metadata without changing runtime or deployment behavior.
