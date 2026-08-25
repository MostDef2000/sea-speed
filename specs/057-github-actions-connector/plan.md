# Implementation Plan: Deterministic GitHub Actions Connector control

- Specification: specs/057-github-actions-connector/spec.md
- Issue: #310
- Status: Active

## Architecture

Use GitHub's hosted official MCP endpoint as the single OpenCode GitHub API transport. Keep the project configuration secret-free through `{env:GH_TOKEN}`, restrict registered context to the five required toolsets, and pair tool exposure with repository contracts that distinguish capability from authority. Durable Checkpoint v2 remains the exact target/method cursor.

## Decisions

### D-001 - Official remote server

- Decision: Replace deprecated `@modelcontextprotocol/server-github` with `https://api.githubcopilot.com/mcp/`.
- Reason: The official server supports OpenCode and the required Actions surface without nested Docker requirements.
- Alternatives rejected: deprecated npm server lacks Actions control; local Docker introduces a second container-runtime dependency inside the current sandbox.

### D-002 - Least-context toolsets

- Decision: Enable only `context,repos,issues,pull_requests,actions`.
- Reason: These cover canonical lifecycle and Actions continuation while avoiding unrelated GitHub surfaces.
- Alternatives rejected: `all` increases prompt and privilege surface; default toolsets omit Actions.

### D-003 - Capability is not authority

- Decision: Bind trigger calls to the exact checkpoint method/target and require fresh authorization for cancellation/log deletion.
- Reason: `actions_run_trigger` consolidates safe retry and destructive methods in one transport tool.
- Alternatives rejected: unrestricted trigger use would allow irreversible evidence loss or cancellation outside the admitted Outcome.

### D-004 - Source-controlled startup contract

- Decision: Track root `opencode.json` and require post-change process restart/tool discovery.
- Reason: A local untracked configuration cannot prevent the same capability gap in later sessions.
- Alternatives rejected: operator-local undocumented configuration repeats drift; hot reload is not supported by OpenCode.

## Affected contours

- Repository: OpenCode config, governance/runtime/compatibility contracts, agent prompt, validator, tests and SDD.
- VPS: NONE
- Ubuntu Worker/relay: NONE
- Public interfaces: NONE

## Validation

- Unit: `python -m unittest tests.test_github_actions_connector_contract -v`.
- Integration: SDD, repository, contract and quality validators plus full unittest discovery.
- End-to-end: exact-head PR checks, merge, exact-main Quality, then restarted OpenCode tool discovery and bounded #305 run read/rerun.
- Runtime acceptance: CONTROL_PLANE capability smoke; no VPS/Ubuntu source deployment from this PR.

## Risk profile

- Risk profile: REQUIRED
- RISK-057-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: env-only credential reference, least-context toolsets, secret scan | Validation: tests/test_github_actions_connector_contract.py + validate_repo.py | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-057-002 | Category: SEC | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: method-level contract denies cancellation/log deletion without fresh authorization | Validation: cross-entrypoint static assertions | Residual risk: MEDIUM because the upstream tool is consolidated; governance remains fail closed | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-057-003 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: exact startup capability preflight and restart prerequisite | Validation: post-restart discovery | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-057-004 | Category: SUPPLY_CHAIN | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: use GitHub-owned hosted endpoint instead of deprecated npm package | Validation: config contract test | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-057-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: official endpoint/toolset/secret assertions
- TEST-057-002 | Covers: AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: canonical cross-entrypoint tool/method assertions
- TEST-057-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: canonical local validators and full unittest discovery
- TEST-057-004 | Covers: AC-005 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR checks and exact-main Quality
- TEST-057-005 | Covers: AC-006 | Level: runtime-manual | Priority: P0 | Evidence: restarted OpenCode tool discovery and bounded #305 run cursor probe

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: fresh `OUTCOME APPROVED` received immediately after the six-field Scope; push explicitly allowed in the same scope.
- Follow-up: resume Issue #305 only after the exact live capability probe (recorded deferred work, not a course correction).

## Deployment transaction audit

Not required: no `deploy/**`, `scripts/release/**`, deployment workflow, runtime deployment requirement or `PRODUCTION_LEARNING` source change is in scope.

## Rollout and rollback

- Rollout: merge exact green head, verify exact-main Quality, restart OpenCode, confirm tools, then use the exact #305 checkpoint cursor.
- Rollback: revert the source commit through protected lifecycle and restart OpenCode; no VPS/Ubuntu rollback applies.

## Runtime feedback

- Actual architecture after acceptance: PENDING
- Differences from plan: NONE YET
- Deferred cleanup: NONE
