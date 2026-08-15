# Implementation Plan: Server-Pull Runtime Deployment Handoff

- Specification: specs/006-server-pull-deployment/spec.md
- Issue: #135
- Status: Source authorized

## Architecture

This task changes only delivery/control-plane contracts and SDD. It defines a two-layer operator/runtime model for future production work:

1. **Control plane:** canonical GitHub `main`, exact approved 40-character SHA, quality evidence, repository-owned deployment/operation entrypoints.
2. **Runtime target:** operator opens the applicable VPS or Ubuntu-worker shell; a short bootstrap retrieves the exact reviewed source target-locally and invokes the repo-owned entrypoint.

The bootstrap is intentionally thin. It may choose the canonical repository and exact SHA, create a temporary target-local staging directory, retrieve/extract the exact source and invoke an entrypoint. Deterministic deployment mechanics remain in the reviewed repository operation.

No runtime script is added in this task. If a future rollout lacks a suitable per-contour entrypoint, that absence becomes explicit source work before production continuation.

## Decisions

### D-001 - Make exact-SHA server-pull the default interactive runtime transport

- Decision: VPS and Ubuntu-worker operator handoff defaults to target-local retrieval of the canonical repository at the exact production-approved/gated SHA.
- Reason: The deployment program remains reviewable, reproducible and directly tied to repository source truth while the operator performs only the unavoidable target-access action.
- Alternatives rejected: treating control-laptop downloaded launchers as the normal path; embedding deployment programs directly in chat.

### D-002 - Keep substantive deployment logic repository-owned

- Decision: The bootstrap contains transport/bootstrap only; preflight, backup, mutation, rollback preparation, smoke and evidence logic belongs in a repo-owned entrypoint.
- Reason: Large inline commands or transient launchers bypass normal source review/provenance and make production behavior harder to reproduce.
- Alternatives rejected: generating a bespoke `.sh`/`.ps1` for every production handoff when equivalent logic can be versioned in GitHub.

### D-003 - Preserve VPS and worker as independent failure domains

- Decision: Mixed rollout normally has one independently executable command/entrypoint per affected contour in safe order.
- Reason: Reducing operator clicks is not sufficient reason to give either server unnecessary orchestration responsibility or credentials for the other contour.
- Alternatives rejected: forcing VPS-to-worker or worker-to-VPS deployment chaining solely to make a single command.

### D-004 - Retain control-laptop artifacts only as an explicit fallback

- Decision: WSL/PowerShell download paths remain documented only for cases where target-local server-pull is unavailable or unsafe, and fallback artifacts must remain exact-source/release derived.
- Reason: Some connectivity or distribution failures can require transport fallback, but that must not become a second unreviewed source of deployment logic.
- Alternatives rejected: deleting all fallback capability; allowing chat-generated substantive deployment programs as fallback.

### D-005 - Do not make GitHub Actions dispatch mandatory for operator deployment

- Decision: GitHub Actions deployment remains supported where configured, but repository-owned server-pull is a valid normal operator path independent of assistant `workflow_dispatch` connector coverage.
- Reason: Connector capability should not determine production architecture or force control-laptop staging when the target can safely retrieve reviewed source.
- Alternatives rejected: blocking every deployment on Actions dispatch availability in the assistant environment.

## Affected contours

- Repository: `contracts/branches/project-manager.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `specs/006-server-pull-deployment/**`.
- VPS: NONE; this task does not mutate runtime or deployment scripts.
- Ubuntu worker/relay: NONE; this task does not mutate runtime or deployment scripts.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: repository/contract/SDD validation, PR Change Contract validation, PR Validation and aggregate Quality integration on the exact final head.
- Integration: exact branch-to-current-main comparison must be `behind_by=0` and contain only the approved five files.
- Runtime acceptance: NOT REQUIRED because this is a control-plane/contracts/SDD-only change.

## Rollout and rollback

- Rollout: update canonical Issue #135 -> fresh branch from current `main` -> update both contracts -> add feature SDD -> verify exact five-file scope -> PR -> exact-head CI -> merge under the current `OUTCOME APPROVED` authorization.
- Rollback: revert the merged contract/SDD PR if the policy is found to create an unsafe or unusable operator boundary. No runtime rollback is applicable because this task performs no production mutation.

## Runtime feedback

- Actual architecture after acceptance: contracts define GitHub exact-SHA server-pull as the default interactive VPS/Ubuntu-worker deployment transport; actual runtime entrypoint adoption is deferred to future runtime-changing tasks.
- Differences from plan: NONE YET.
- Deferred cleanup: existing runtime helpers may need future source changes to expose uniform safe per-contour server-pull entrypoints; those changes are explicitly outside Issue #135.
