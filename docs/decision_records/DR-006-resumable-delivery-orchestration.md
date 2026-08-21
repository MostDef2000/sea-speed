# DR-006: Resumable Delivery Orchestration

Status: Accepted
Date: 2026-08-21
Issue: #240

## Context

The single Delivery Orchestrator already owns one task from intake through terminal evidence and is forbidden to stop at deterministic intermediate stages. That model still depended too heavily on transient conversational context. After context compaction, session restart, Connector truncation, or another loss of working memory, the Orchestrator could no longer distinguish a new task from an already-authorized task and could repeat project recovery, Task Intake, authorization checks, or equivalent Connector reads. Those repeated reads increase context pressure and can amplify the same failure.

GitHub `main` remains the long-term source of truth for repository/product state. The canonical Issue remains durable backlog, source-authorization record, and task history. Neither role alone defines the transient execution cursor needed to resume an admitted task efficiently.

## Decision

Introduce **Sea Speed Delivery Checkpoint v1** as durable execution-control evidence inside the canonical Issue and a bounded **Resume Probe** for recovery.

The control plane distinguishes three truth classes:

1. **Repository/product truth** — current `main`, committed contracts/specs/source and accepted runtime evidence.
2. **Delivery-control truth** — canonical Issue Outcome Contract, source-authorization receipt, Delivery Checkpoint, branch/PR/head identities, completed gates and evidence cursors.
3. **Transient interaction state** — the live conversation in which a new Scope is presented and a new source authorization is initially admitted.

The initial visible-Scope -> immediately-following `OUTCOME APPROVED` rule remains mandatory for creating source authority. After that admission is durably receipted in the canonical Issue, loss of conversational context does not revoke or recreate the authorization. The receipt may prove continuation of the same exact admitted scope; it can never create, expand, or replace authorization.

A valid checkpoint records at minimum:

- task/Issue identity and checkpoint generation;
- approved scope identity and authorization base `main`;
- current lifecycle phase;
- branch, PR and exact working head when they exist;
- completed gates;
- evidence cursors for Issue/PR/CI/policy/runtime evidence as applicable;
- `Next admissible action`;
- `State invalidation reason`.

Recovery of a known task begins with a Resume Probe, not full Task Intake. The probe reads only current `main`, the canonical Issue checkpoint, and the exact referenced PR/head/status or evidence that may have changed since the recorded cursor. Full project recovery is permitted only when no valid checkpoint exists, the task identity cannot be resolved, or evidence materially contradicts the checkpoint.

Lifecycle state is monotonic. Context loss, session restart, Connector truncation, response truncation, or model compaction are not state-invalidation reasons and do not return a task to `DISCUSSION`. Backward transition or fresh authorization requires a concrete invalidation such as `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`.

Connector retrieval is progressive and cursor-bound: `known object -> metadata -> targeted detail -> failure fragment`. Re-reading the same object for the same question with the same evidence identity is forbidden unless a mandatory gate explicitly requires a fresh read.

## Consequences

- A compact durable state can survive conversation compaction and session restart.
- Repeated repository archaeology is no longer the normal recovery path.
- Source authorization remains fail closed at initial admission while continuation becomes resumable.
- Connector calls must justify advancement, a mandatory gate, or an explicit evidence gap.
- `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` remain the only terminal interaction states.
- Checkpoint updates are event-driven at meaningful lifecycle/evidence transitions rather than after every tool call.

## Runtime impact

CONTROL_PLANE only. No VPS or Ubuntu Worker/relay deployment or runtime mutation is required.