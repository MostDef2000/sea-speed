# Implementation Plan: Todo model display

- Specification: specs/067-todo-model-display/spec.md
- Issue: #333
- Status: ACTIVE

## Architecture

Extend the existing todo projection contract with two additional rendered lines. Keep `Sea Speed Delivery Checkpoint v2` durable; model values are rendered at block time from the global health-aware assignment cache and are not persisted as authority. No new tool, dependency or runtime contour is introduced.

## Decisions

### D-001 - Two lines under todo triad

- Decision: Require `Model / orchestrator:` and `Model / active worker:` immediately after `Todo / pending or waiting:`.
- Reason: Distinguishes session primary from transient delegation without a new tool.
- Alternatives rejected: single `Model:` hides orchestrator; plugin-injected field requires hidden state.

### D-002 - Render-time resolution

- Decision: Resolve orchestrator from the configured default (`openai/gpt-5.6-sol`) and worker from `~/.cache/opencode/model-assignment.json` at render time.
- Reason: Model IDs are transient health-aware state already owned globally.
- Alternatives rejected: hardcoding IDs in contracts/SDD creates drift on fallback.

### D-003 - Contract-enforced, not plugin

- Decision: Enforce via static contract text and unit tests.
- Reason: Cheapest deterministic gate; plugin would be hidden state.
- Alternatives rejected: changing `todowrite` tool shape is unsupported.

## Affected contours

- Repository: contracts, AGENTS, agent prompt, contract tests, linked SDD.
- VPS: NONE.
- Ubuntu worker/relay: NONE.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: `tests/test_delivery_todo_contract.py` plus `scripts/ci/validate_repo.py`, `validate_sdd.py`, `validate_contracts.py`.
- Integration: `scripts/quality/validate_quality_contracts.py`, `validate_workflow_policy.py`, full `unittest` discovery, project doctor, delivery runner full execution.
- Runtime acceptance: fresh-process status block renders both model lines after restart.

## Risk profile

- Risk profile: REQUIRED
- RISK-067-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: extend allowlist with no new tracked file types and assert no hardcoded model IDs in tests | Validation: tests/test_delivery_todo_contract.py + secret scan | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-067-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: keep exactly one current todo item and two deterministic model lines; checkpoint wins disagreement | Validation: status block and Resume Probe assertions | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-067-001 | Covers: AC-001,AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_todo_contract.py model-line assertions
- TEST-067-002 | Covers: AC-004,AC-005 | Level: integration | Priority: P0 | Evidence: validate_repo, validate_sdd, full unittest and delivery runner
- TEST-067-003 | Covers: AC-001,AC-002 | Level: runtime-manual | Priority: P1 | Evidence: fresh-process startup and WAITING_EXTERNAL block rendering after restart

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: exact six-field Scope immediately followed by OUTCOME APPROVED; Issue #333 contains durable receipt and Checkpoint v2.
- Follow-up: NONE.

## Deployment transaction audit

Not required: no `deploy/**`, `scripts/release/**`, deployment workflow, runtime deployment requirement or `PRODUCTION_LEARNING` change is in scope.

## Rollout and rollback

- Rollout: validate locally, publish bounded commit, merge exact green head, verify exact-main Quality, restart OpenCode, verify model lines in status block.
- Rollback: revert the bounded source commit through protected lifecycle and restart OpenCode; no VPS or Ubuntu rollback applies.

## Runtime feedback

- Actual architecture after acceptance: PENDING.
- Differences from plan: NONE YET.
- Deferred cleanup: NONE.
