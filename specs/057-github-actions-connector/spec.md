# Spec: Deterministic GitHub Actions Connector control

- Issue: #310
- Status: ACTIVE
- Runtime contour: NONE / CONTROL_PLANE

## Product outcome

Make GitHub Actions evidence, failed-job logs, bounded rerun and workflow dispatch available through the canonical GitHub Connector in local OpenCode, eliminating avoidable manual Actions-button handoffs while preserving every source and production authority gate.

## User scenarios

### Scenario 1 - Exact capability at startup

Given a new or resumed delivery, when workflow evidence or control is required, then the Orchestrator verifies the exact official Actions tools before claiming Connector capability.

### Scenario 2 - Deterministic failed-run continuation

Given a checkpoint names one failed workflow run and `rerun_failed_jobs` as the next action, when the live tool exists, then the Orchestrator invokes it through the Connector without asking the operator to press a web button.

### Scenario 3 - Destructive method guard

Given the consolidated trigger tool also exposes cancellation and log deletion, when no fresh method-specific authorization exists, then those methods remain forbidden.

### Scenario 4 - Stale OpenCode process

Given current `main` contains the correct configuration but the running process loaded an older one, when Actions tools are absent, then the task records an exact restart and post-restart probe rather than inventing another GitHub route.

## Requirements

- R1: Track a schema-shaped, secret-free `opencode.json` using GitHub's official remote MCP endpoint and `{env:GH_TOKEN}`.
- R2: Enable only `context,repos,issues,pull_requests,actions` toolsets.
- R3: Require exact startup capability tools `actions_list`, `actions_get`, `get_job_logs`, and `actions_run_trigger`.
- R4: Allow `run_workflow`, `rerun_workflow_run`, and `rerun_failed_jobs` only for the exact checkpoint-admitted target.
- R5: Deny `cancel_workflow_run` and `delete_workflow_run_logs` without fresh destructive authorization.
- R6: Preserve source admission, protected source, exact-main Quality, standing delegation, production policy, provenance, rollback and runtime acceptance.
- R7: Repository validation admits tracked root `opencode.json` without relaxing exact-path restrictions under `.opencode/**`.
- R8: Missing live tools after current-main configuration is correct produces an exact restart/tool-discovery prerequisite, never a manual mutation fallback.

## NFR assessment

- NFR-057-001 | Area: security | Target: no credential value is tracked and destructive Actions methods remain fail closed | Validation: static config/contract tests + secret scan | Evidence: tests/test_github_actions_connector_contract.py and scripts/ci/validate_repo.py | Status: PASS
- NFR-057-002 | Area: reliability | Target: workflow status, logs and rerun/dispatch capability are detected before they become the next delivery action | Validation: exact tool-name assertions and post-restart smoke probe | Evidence: tests/test_github_actions_connector_contract.py | Status: PASS
- NFR-057-003 | Area: operability | Target: ordinary failed-run continuation requires zero manual Actions-button operations | Validation: Connector `rerun_failed_jobs` against the persisted #305 run cursor after OpenCode restart | Evidence: Issue #305/#310 runtime cursor (pending live probe) | Status: CONCERNS
- NFR-057-004 | Area: maintainability | Target: deprecated npm MCP package is absent and one official configuration is canonical | Validation: static config test | Evidence: opencode.json | Status: PASS

## Acceptance criteria

- AC-001: `opencode.json` uses the official endpoint, bounded toolsets, env interpolation and no literal token.
- AC-002: Canonical contracts and local agent require the four exact Actions tools and bounded trigger methods.
- AC-003: Cancellation/log deletion require fresh explicit destructive authorization.
- AC-004: Repository, SDD, contract, quality and full unit suites pass with exact changed-file scope.
- AC-005: Exact-head PR checks, exact-green-head merge and exact-main Quality pass.
- AC-006: A restarted OpenCode session discovers all four tools and performs a bounded read/rerun against #305 run `32807077099`.

## Out of scope

PAT values/administration, GitHub settings, workflow source, application/runtime source, Issue #305 source, standing delegation/policy changes, cancellation and log deletion.

## Runtime feedback

- Runtime acceptance: OpenCode capability smoke only; no application deployment required by this source change.
- Accepted production behavior: PENDING post-restart Connector probe.
- Regressions/learning: deprecated generic MCP availability did not imply Actions capability.
- Follow-up work: resume #305 runtime acceptance after the capability probe.
