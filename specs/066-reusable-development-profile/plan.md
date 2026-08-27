# Implementation Plan: Reusable health-aware development profile

- Specification: specs/066-reusable-development-profile/spec.md
- Issue: #331
- Status: ACTIVE

## Architecture

Add the minimal project marker consumed by the global `project-profile` plugin and a repository-owned delivery manifest consumed by the deterministic gate runner. Keep `opencode.json` and `sea-speed-delivery-orchestrator` authoritative: the plugin's non-overwriting configuration merge injects specialist agents and missing LSP defaults while preserving the existing default agent and GitHub MCP configuration. Extend the exact `.opencode/**` validator allowlist only for the two new declarative JSON files.

Dynamic FREE-model selection stays outside the repository. At OpenCode startup, the global provider plugin refreshes catalogs, excludes active health failures, resolves role chains and writes `~/.cache/opencode/model-assignment.json`; the project-profile plugin assigns those values to `profile-worker-*`. Sea Speed records role semantics and authority boundaries, not model IDs.

## Decisions

### D-001 - Preserve the project-specific primary agent

- Decision: Keep `sea-speed-delivery-orchestrator` as `default_agent`; use the reusable profile only for specialist workers, LSP augmentation and target guards.
- Reason: Sea Speed governance, durable checkpoints and production boundaries are stricter than the generic delivery profile.
- Alternatives rejected: replacing the primary agent would create a second orchestration contract and weaken project-specific lifecycle rules.

### D-002 - Repository-owned deterministic gate manifest

- Decision: Define direct argv gates for repository, contracts, SDD, quality contracts, workflow policy, full unittest, property, fuzz/recovery and quality architecture checks.
- Reason: These commands match existing CI domains and can run without a shell, dependency installation or hidden state.
- Alternatives rejected: the bootstrap npm template is invalid for this Python/mixed repository; wrapping all checks in a new script adds unnecessary indirection.

### D-003 - Exact OpenCode allowlist extension

- Decision: Admit only the canonical agent, project marker and delivery manifest under `.opencode/**`.
- Reason: The profile needs two durable declarative files while node modules, locks and local OpenCode state must remain untracked.
- Alternatives rejected: allowing the complete directory would weaken the existing local-state and secret boundary.

### D-004 - Global ownership of model health

- Decision: Do not copy model IDs, provider chains or health code into Sea Speed.
- Reason: Global assignment resolution already provides live fallback behavior and prevents repository drift.
- Alternatives rejected: project-local model chains duplicate transient provider state and require source changes for availability events.

## Affected contours

- Repository: exact OpenCode profile files, canonical agent guidance, repository validator/tests and linked SDD.
- VPS: NONE.
- Ubuntu worker/relay: NONE.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: repository, contract, SDD, quality-contract and workflow-policy validators.
- Integration: project doctor; delivery runner list/full execution; exact allowlist unit tests; full unittest, property, fuzz/recovery and quality-architecture suites.
- Runtime acceptance: restart OpenCode and verify the default agent plus six injected workers; no application runtime deployment.

## Risk profile

- Risk profile: REQUIRED
- RISK-066-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: extend `ALLOWED_EXACT_PATHS` with two literal files only and test rejection of every other path | Validation: repository contract tests and `validate_repo.py` | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-066-002 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: preserve the project-specific primary agent; permit code/test workers only after source admission; keep worker output advisory | Validation: static assertions across AGENTS and canonical agent prompt | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-066-003 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: mandatory runner secret scan and no project-local credentials/model configuration | Validation: runner preflight and changed-file secret review | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-066-004 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: health-aware global assignments, deterministic defaults and fresh-process discovery | Validation: assignment inspection, doctor and agent list | Residual risk: LOW; exact-main restart remains a release gate | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-066-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: project doctor output and mixed-stack LSP discovery
- TEST-066-002 | Covers: AC-002 | Level: runtime-manual | Priority: P0 | Evidence: post-restart OpenCode default-agent and six-worker discovery
- TEST-066-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: gate runner `--list` and full execution
- TEST-066-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_delivery_todo_contract.py` and `tests/test_github_actions_connector_contract.py`
- TEST-066-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: complete local validator and test outputs
- TEST-066-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact `git diff --name-only main...HEAD` comparison with Issue #331 approved paths

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: exact six-field Scope was immediately followed by `OUTCOME APPROVED`; Issue #331 contains the durable receipt and Checkpoint v2.
- Follow-up: NONE.

## Deployment transaction audit

Not required: no `deploy/**`, `scripts/release/**`, deployment workflow, runtime deployment requirement or `PRODUCTION_LEARNING` change is in scope.

## Rollout and rollback

- Rollout: validate locally, publish one bounded PR, merge exact green head, verify exact-main Quality, restart OpenCode and record control-plane acceptance.
- Rollback: revert the bounded source commit through the protected source lifecycle and restart OpenCode; no VPS or Ubuntu rollback applies.

## Runtime feedback

- Actual architecture after acceptance: pre-merge fresh process preserved the Sea Speed primary agent configuration and exposed all six dynamically configured workers; exact-main verification remains pending.
- Differences from plan: GitHub `rerun_failed_jobs` preserves the original `pull_request` event payload, and a bounded close/reopen did not create new check runs for the unchanged source SHA. After PR metadata repair, an in-scope source synchronization is required to validate the current Change Contract against a fresh event payload.
- Deferred cleanup: NONE.
