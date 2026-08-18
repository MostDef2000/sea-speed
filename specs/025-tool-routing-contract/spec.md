# Feature Specification: Deny-by-default Tool Routing Allowlist

- Feature: 025-tool-routing-contract
- Issue: #221
- Status: In implementation
- Owner outcome: Make Sea Speed development and deployment tool use explicit, closed, and fail-closed so the Delivery Orchestrator cannot drift into unrelated services or ad-hoc fallbacks.

## Product outcome

Sea Speed uses a closed Tool Routing Allowlist. For development, CI, release, deployment, diagnostics, evidence collection, and protected input handling, a tool, connector, service, CLI, side-channel, publication path, or runtime mutation path is permitted only when this contract explicitly lists it for the current task class.

The default is denial. Tool availability does not grant permission. A fallback is valid only for the exact row that declares it. If the approved primary route is unavailable and no declared fallback exists, or the declared fallback cannot complete safely, the Delivery Orchestrator returns `HUMAN DECISION REQUIRED` instead of probing or selecting another service.

Local ephemeral tooling is preparation/validation infrastructure only. It may build patches, run tests, calculate hashes, or inspect user-provided material, but it is not a GitHub publication control plane and is not a production mutation path.

## User scenarios

### Scenario 1 - normal GitHub lifecycle stays inside the Connector
Given a repository read or write is needed, the Delivery Orchestrator uses the connected GitHub Connector. It does not switch to `gh`, local GitHub authentication, assistant-side `git push`, manual GitHub web publication, or another service because one route is inconvenient.

### Scenario 2 - a CI endpoint is not exposed by the Connector
Given CI evidence is required and the exact GitHub Actions endpoint is not available through the Connector, the only allowed fallback is one bounded read-only GitHub API/PowerShell command for the operator. Email notifications, calendar events, Drive files, browser scraping, or unrelated connectors are not substitutes.

### Scenario 3 - public HTTP needs independent verification
Given `mostdef.ru` or another approved public Sea Speed endpoint needs a status check, the Delivery Orchestrator may use read-only HTTP/web access. If that cannot produce reliable evidence, the only allowed fallback is one bounded read-only `curl`/PowerShell command for the operator.

### Scenario 4 - production diagnostics need host-local evidence
Given VPS or Ubuntu runtime evidence is missing after an incident, repository-owned diagnostic/deployment tooling is the primary route. If no machine-observable route is available, the operator may receive one bounded read-only host command. The Delivery Orchestrator does not open an ad-hoc SSH shell, run arbitrary production commands, mutate a database, or use a cloud console as an implicit fallback.

### Scenario 5 - a secret or protected prompt is required
Given password, sudo, TOTP, SSH trust, deploy key, token, or other protected input is required, the operator enters it locally in the intended prompt or secret store. The value is never requested into chat, committed to Git, or copied into unrelated tooling.

### Scenario 6 - a new tool appears useful
Given an unlisted connector/plugin/service would make a task easier, the Delivery Orchestrator does not search for, install, probe, or use it. A future allowlist change requires a new bounded source Scope and authorization.

## Requirements

- FR-001: Sea Speed tool routing MUST be `DENY BY DEFAULT`: any tool, connector, service, CLI, side-channel, publication path, or runtime mutation path not explicitly listed for the current task class is forbidden.
- FR-002: Availability of an installed/connected tool MUST NOT be treated as permission to use it for Sea Speed delivery.
- FR-003: Fallbacks MUST be row-specific. A fallback allowed for one task class MUST NOT be reused for another class by analogy.
- FR-004: If the primary route is unavailable and no allowed fallback exists, or the allowed fallback cannot complete safely, the Delivery Orchestrator MUST return `HUMAN DECISION REQUIRED` rather than discover an alternate channel.
- FR-005: GitHub repository lifecycle reads/writes, Issue/PR/comments/branches/source publication and merge MUST use the GitHub Connector only. Local `gh`, local GitHub authentication, assistant-side `git push`, and manual GitHub web publication are forbidden.
- FR-006: CI status/jobs/logs/artifacts MUST use the GitHub Connector. Only when the exact required endpoint is unavailable through the Connector MAY the operator receive one bounded read-only GitHub API/PowerShell command. No notification or unrelated-service side-channel is allowed.
- FR-007: Patch generation, local build/test/hash/static analysis MAY use ephemeral local tooling/container. A user checkout MAY be used when required for preparation or validation. Neither path may publish GitHub state or mutate production.
- FR-008: Public Sea Speed HTTP verification MAY use read-only HTTP/web access. Its only fallback is one bounded read-only `curl`/PowerShell command supplied to the operator.
- FR-009: External technical documentation MAY use read-only web access only to primary/official sources relevant to the technical question. It MUST NOT become a repository or runtime evidence side-channel.
- FR-010: User-provided logs, screenshots, configs, or files MAY be read directly as provided evidence; the Delivery Orchestrator MUST NOT silently fetch related private services to augment them.
- FR-011: Production authorization MUST be the exact three-line canonical Issue record written through the GitHub Connector. No alternate message, email, document, or UI action substitutes for it.
- FR-012: VPS deployment MUST use GitHub Actions -> `.github/workflows/deploy-vps.yml`. A fallback is allowed only when the canonical deployment path explicitly exposes one repository-owned VPS action.
- FR-013: Ubuntu deployment MUST use GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh`. Its only manual fallback is the repository-owned sudo/root bootstrap emitted by the canonical path.
- FR-014: VPS/Ubuntu runtime diagnostics MUST use repository-owned diagnostic/deployment tooling. The only manual fallback is one bounded read-only command on the corresponding host. Ad-hoc SSH/shell sessions, direct DB mutation, and cloud-console operations are forbidden implicit fallbacks.
- FR-015: Password/sudo/TOTP/SSH trust/credentials/tokens MUST be entered by the operator locally into the intended prompt or secret store and MUST NOT enter chat or Git.
- FR-016: Gmail, Calendar, Drive, Notion and every other unlisted connector/plugin/service are forbidden implicit Sea Speed development/deployment fallbacks. They require a future explicit allowlist source change before use in this lifecycle.
- FR-017: All five canonical agent/governance/delivery entry points MUST state or normatively reference the same deny-by-default rule and task-to-tool routes without contradictory fallback language.
- FR-018: This Outcome MUST NOT change `.github/workflows/**`, runtime deployment order, application/runtime source, production topology, or current runtime state.

## Acceptance criteria

- AC-001: `AGENTS.md`, Governance, Delivery Policy, Delivery Orchestrator, and Release Readiness explicitly establish that unlisted tools/services/routes are forbidden.
- AC-002: The canonical text states that tool availability alone does not grant permission and that the agent may not search for or probe an alternative service when the allowlist is insufficient.
- AC-003: GitHub repository lifecycle is Connector-only with no `gh`, local auth, assistant-side push, or manual-web fallback.
- AC-004: CI evidence has exactly one declared non-Connector fallback: one bounded read-only GitHub API/PowerShell command when the exact Connector endpoint is unavailable.
- AC-005: Local ephemeral tooling is explicitly non-publication and non-production.
- AC-006: Public HTTP verification has exactly one declared fallback: one bounded read-only `curl`/PowerShell command.
- AC-007: VPS and Ubuntu execution remain bound to their existing repository-owned GitHub Actions/deployment entrypoints and only their explicitly emitted repository-owned fallbacks.
- AC-008: Runtime diagnostics prohibit ad-hoc SSH/shell, direct DB mutation, cloud-console operations, and unrelated-service side channels as implicit fallbacks.
- AC-009: Secrets/protected inputs stay local to the operator and never enter chat or Git.
- AC-010: Gmail, Calendar, Drive, Notion and all other unlisted connectors/services are explicitly non-admissible implicit fallbacks.
- AC-011: Exact PR diff is limited to the eight Issue #221 authorized paths and derives `CONTROL_PLANE` with VPS/Ubuntu deployment `NOT REQUIRED`.
- AC-012: Exact-head PR Validation and aggregate Quality pass, expected-head merge succeeds, and exact-main Quality passes without any production mutation.

## NFR assessment

- NFR-001 | Area: SAFETY | Target: Every Sea Speed tool use is admitted by an explicit task-class allowlist row or rejected fail-closed | Validation: cross-contract review plus exact PR diff and SDD traceability | Evidence: Issue #221, five canonical contracts, PR Change Contract | Status: PASS
- NFR-002 | Area: PRIVACY | Target: Unrelated private services are never queried as implicit evidence channels | Validation: explicit forbidden-side-channel rules and fallback inventory | Evidence: AGENTS/Governance/Delivery Policy tool-routing sections | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: Normal source -> CI -> release -> deployment -> incident workflows retain at least one safe route for every currently supported Sea Speed task class | Validation: route matrix review against current VPS/Ubuntu delivery contracts | Evidence: `specs/025-tool-routing-contract/plan.md` | Status: PASS
- NFR-004 | Area: MAINTAINABILITY | Target: A future new tool requires one visible allowlist source change rather than an implicit convention | Validation: deny-by-default and future-expansion requirements | Evidence: Issue #221 and canonical contracts | Status: PASS

## Runtime feedback

The immediate trigger was a delivery-orchestration drift during Issue #218: after a GitHub Connector endpoint gap, an unrelated Gmail notification path was considered as a possible read-only evidence source even though email is not part of the Sea Speed control plane. No Gmail message search/read occurred, but the incident exposed that existing Connector-only publication rules were not a complete closed tool-routing policy.

This Outcome makes the tool boundary explicit without changing runtime workflows, production hosts, application behavior, or the already established VPS/Ubuntu deployment implementations.