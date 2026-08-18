# Implementation Plan: Deny-by-default Tool Routing Allowlist

- Specification: specs/025-tool-routing-contract/spec.md
- Issue: #221
- Status: In implementation

## Architecture

The Tool Routing Allowlist is a control-plane contract layered above the existing source/release/runtime gates. It does not add a new execution engine. Instead, it makes tool selection itself an admission decision before an existing Sea Speed action is attempted.

The model has four rules:

1. **Closed admission**: each Sea Speed task class has one explicitly permitted primary route. Everything else is forbidden unless that same row names a fallback.
2. **Row-local fallback**: fallbacks do not generalize. A read-only GitHub API command allowed for a missing CI endpoint does not authorize ad-hoc GitHub publication, SSH, Gmail, Drive, or another channel.
3. **Control-plane separation**: ephemeral local tooling may prepare/test content but cannot publish repository state or mutate runtime. GitHub writes remain Connector-only; runtime mutation remains repository-owned deployment tooling.
4. **Fail-closed capability gap**: when the allowed primary and allowed fallback cannot safely complete the task, the next state is `HUMAN DECISION REQUIRED`. The Delivery Orchestrator does not search for, install, probe, or opportunistically use another connector/service.

The canonical route matrix is duplicated only where necessary for agent admission and otherwise normatively referenced across the five entry points. `AGENTS.md` provides the concise operational table; Governance defines the normative deny-by-default rule; Delivery Policy defines lifecycle-specific routes; Delivery Orchestrator defines agent behavior; Release Readiness adds the release-time tool-routing gate.

## Decisions

### D-001 - Deny by default

- Decision: Treat every unlisted tool/service/channel as forbidden for Sea Speed development and deployment.
- Reason: An allowlist that permits implicit substitutions is not an allowlist and cannot prevent side-channel drift.
- Alternatives rejected: maintain a blacklist; allow any read-only connector; infer permission from installed tools.

### D-002 - Availability is not authorization

- Decision: A connector/plugin/service being connected or technically callable does not permit its use for Sea Speed.
- Reason: Tool availability is environment state, not project policy.
- Alternatives rejected: opportunistic use of available services followed by retrospective documentation.

### D-003 - GitHub Connector remains the repository control plane

- Decision: Repository lifecycle reads/writes, Issues, PRs, branch/source publication and merge remain GitHub Connector only.
- Reason: Existing governance already establishes the Connector as the sole publication interface; the new contract extends the same fail-closed principle to adjacent tooling.
- Alternatives rejected: `gh`, local GitHub authentication, assistant-side `git push`, manual GitHub web publication.

### D-004 - Permit one narrow CI evidence fallback

- Decision: When the exact GitHub Actions endpoint is not exposed through the Connector, allow exactly one bounded read-only GitHub API/PowerShell command to the operator.
- Reason: Some evidence is still GitHub-owned but may not be exposed by the Connector wrapper; the fallback preserves source-of-truth locality without introducing another service.
- Alternatives rejected: email notifications, browser scraping, Gmail/Drive/Calendar/Notion, `gh`.

### D-005 - Local tooling is preparation only

- Decision: Ephemeral local tooling/container may patch, build, test, hash and statically inspect, but cannot publish repository state or mutate production.
- Reason: This keeps high-throughput local computation separate from authoritative state transitions.
- Alternatives rejected: local assistant-side push, direct production scripts from a scratch environment.

### D-006 - Runtime mutation stays repository-owned

- Decision: VPS deployment remains GitHub Actions -> `deploy-vps.yml`; Ubuntu remains GitHub Actions -> `deploy-ubuntu-worker.yml` -> `deploy-authorized.sh`. Manual fallbacks are allowed only when those canonical paths explicitly expose repository-owned actions.
- Reason: Deployment authorization, exact-SHA checks, rollback and evidence belong to reviewed repository tooling, not ad-hoc commands.
- Alternatives rejected: arbitrary SSH sessions, manual file copies, direct DB changes, cloud-console mutation.

### D-007 - Runtime diagnostics are read-only unless routed through deployment tooling

- Decision: Repository-owned diagnostics are primary; only one bounded read-only host command may be handed to the operator when necessary.
- Reason: Incident evidence should not silently become runtime mutation authority.
- Alternatives rejected: open-ended shell exploration, unbounded command sequences, side-channel monitoring services.

### D-008 - New tools require governance change

- Decision: If a future task genuinely needs an unlisted tool, add it through a new visible Scope and source authorization rather than a one-off conversational exception.
- Reason: The allowlist must remain durable, reviewable and consistent across future conversations.
- Alternatives rejected: temporary implicit exceptions or per-turn tool improvisation.

## Affected contours

- Repository/control plane: REQUIRED — five canonical contracts plus feature 025 SDD.
- VPS runtime: NOT REQUIRED.
- Ubuntu Worker/relay runtime: NOT REQUIRED.
- Runtime application/API/frontend/Worker source: unchanged.
- GitHub Actions workflows: unchanged.
- Production mutation: NONE.

## Validation

Validation is contract/SDD/CI based because this Outcome intentionally changes no executable workflow or runtime code.

- Exact changed-file validation must show only the eight Issue #221 authorized paths.
- The five canonical entry points must agree on deny-by-default, row-local fallback, Connector-only GitHub publication, repository-owned deployment, protected-input locality, and `HUMAN DECISION REQUIRED` on an unresolvable capability gap.
- PR Change Contract must derive `CONTROL_PLANE`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: NOT REQUIRED`, execution capabilities `NOT APPLICABLE`, and `Operator actions expected: 0`.
- Existing repository/contract/SDD validation, behavioral tests, aggregate Quality, and exact-main Quality must remain green.
- No production authorization, deployment, runtime acceptance, deployment transaction audit, or runtime evidence is required for this control-plane-only Outcome.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Keep one closed route matrix synchronized across all five canonical entry points; require exact changed-file/SDD/Change Contract CI before merge | Validation: exact contract diff review plus PR Validation/aggregate Quality | Residual risk: a future tool requirement may be blocked until a new allowlist Scope is approved, which is intentional fail-closed behavior | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Explicitly prohibit unrelated private-service side channels, ad-hoc shells, direct DB/cloud-console mutation and unlisted connectors; keep protected inputs operator-local | Validation: cross-contract allowlist review and acceptance traceability | Residual risk: policy cannot prevent an external human from using tools outside the governed orchestrator, but such actions do not count as Sea Speed delivery evidence | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-010,RISK-001,RISK-002 | Level: integration | Priority: P0 | Evidence: exact contract diff review across `AGENTS.md`, Governance, Delivery Policy, Delivery Orchestrator, and Release Readiness
- TEST-002 | Covers: AC-003,AC-004,RISK-001 | Level: integration | Priority: P0 | Evidence: GitHub execution and CI fallback clauses in the five canonical contracts plus PR Change Contract review
- TEST-003 | Covers: AC-005,AC-006 | Level: integration | Priority: P0 | Evidence: local-tooling and public-HTTP route clauses in canonical contracts
- TEST-004 | Covers: AC-007,AC-008,AC-009,RISK-002 | Level: integration | Priority: P0 | Evidence: deployment/runtime-diagnostic/protected-input clauses in canonical contracts
- TEST-005 | Covers: AC-011,AC-012 | Level: integration | Priority: P0 | Evidence: Connector exact file comparison, PR Validation, aggregate Quality, expected-head merge and exact-main Quality

## Correct-course check

- Trigger: ARCHITECTURE_PIVOT
- Issue impact: Issue #221 isolates the tool-routing correction from product/runtime Issue #218 and records the exact eight-path control-plane scope.
- Specification impact: Feature 025 converts previously partial Connector-only rules into a closed task-to-tool allowlist with deny-by-default and row-local fallbacks.
- Plan impact: Tool selection becomes an explicit admission layer before existing source, CI, release, deployment and diagnostic actions.
- Tasks impact: Five canonical contracts and feature 025 SDD must be synchronized and validated on one exact PR head/main merge.
- Authorization impact: The operator supplied `OUTCOME APPROVED` immediately after the visible eight-path Scope on 2026-08-19; no production authorization is created or modified by this source task.
- Follow-up: Any future need for an unlisted tool/service must return to a new visible Scope and source authorization rather than an implicit exception.

## Runtime feedback

During Issue #218 delivery, a missing GitHub Connector route for an `issue_comment` Actions run led to consideration of Gmail notifications as a read-only evidence shortcut. No Gmail message was searched or read, but the incident demonstrated that repository-publication rules alone did not constrain all evidence channels.

The correction is deliberately control-plane only: it codifies tool admission without changing the existing VPS/Ubuntu workflows, runtime topology, application code, credentials, deployment ordering or production state.