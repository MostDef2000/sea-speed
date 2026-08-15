# Feature Specification: Server-Pull Runtime Deployment Handoff

- Feature: 006-server-pull-deployment
- Issue: #135
- Status: Source authorized
- Owner outcome: For VPS and Ubuntu worker deployment, the operator opens the named target shell and pastes one short command while all substantive deployment logic remains reviewed, versioned and reproducible from the exact GitHub source SHA.

## Product outcome

Sea Speed production handoff no longer depends on transient deployment programs downloaded to the operator control laptop or pasted as large shell blocks in chat. The normal runtime model keeps deployment logic in the canonical repository, pins execution to an exact approved and quality-gated `main` SHA, and asks the operator only to open the applicable target shell and run one short target-local bootstrap command per deployment contour.

This makes the operational boundary explicit: GitHub owns reviewed deployment logic, the operator owns access to the target shell and protected local inputs, and the target host retrieves and executes the exact reviewed source.

## User scenarios

### Scenario 1 - Deploy the VPS from reviewed source

Given a production-approved exact `main` SHA and a repository-owned VPS deployment entrypoint, when the operator opens the production VPS shell and pastes the provided bootstrap command, then the VPS retrieves the exact canonical repository source locally and the repo-owned entrypoint performs the authorized VPS operation and emits sanitized evidence.

### Scenario 2 - Deploy the Ubuntu worker independently

Given an authorized worker update and a repository-owned worker entrypoint at the exact approved SHA, when the operator opens the commissioned Ubuntu worker shell and runs the provided bootstrap command, then the worker retrieves and runs only the exact reviewed source without requiring a launcher file to be staged on the Windows/WSL control laptop.

### Scenario 3 - Deliver a mixed VPS and worker change

Given a task that affects both runtime contours, when rollout reaches production, then the operator receives one independently executable command for the VPS and one for the worker in the declared safe order. Neither host becomes the other's deployment controller solely to reduce the number of operator actions.

### Scenario 4 - Required deployment logic is missing from the approved SHA

Given production authorization but no suitable repository-owned entrypoint for a required operation, when handoff is prepared, then the Project Manager stops production continuation and returns the missing operation to the normal source Issue/branch/PR/CI/merge lifecycle rather than generating substantive deployment logic only in chat or a transient local file.

### Scenario 5 - Target-local server-pull is unavailable

Given a target cannot safely retrieve exact reviewed source from the canonical repository/distribution path, when deployment must continue, then any control-laptop/manual artifact route is explicitly treated as fallback, is pinned to the exact approved source/release, preserves integrity/provenance, and transports repository-owned logic rather than introducing an unreviewed deployment program.

## Requirements

- FR-001: The canonical `MostDef2000/sea-speed` repository MUST remain the source of truth for substantive VPS and Ubuntu-worker deployment/operation logic used by the normal interactive production path.
- FR-002: Normal production handoff MUST bind to an exact approved and quality-gated full 40-character `main` SHA before runtime mutation.
- FR-003: Normal operator instructions MUST state the target execution context and provide one short copy-paste bootstrap command for the current deployment contour.
- FR-004: The operator MUST establish the target shell/SSH session themselves; the normal deployment command MUST execute target-local after that boundary is established.
- FR-005: The bootstrap MUST select the canonical repository and exact SHA, retrieve/stage that exact source on the target, and invoke a repository-owned entrypoint from the retrieved source.
- FR-006: The bootstrap MUST contain transport/bootstrap logic only and MUST NOT embed a large ad-hoc deployment program, backup algorithm, configuration mutation or acceptance suite in chat.
- FR-007: Repository-owned entrypoints MUST own applicable deterministic preflight, exact-source/integrity/provenance checks, host identity validation, known-path discovery, backup/rollback preparation, mutation, restart/reload, smoke/health checks and sanitized evidence collection.
- FR-008: If the approved exact SHA lacks the operation required for safe deployment, production MUST stop for source implementation through the normal repository lifecycle rather than synthesizing a substantive transient launcher.
- FR-009: VPS and Ubuntu worker MUST remain independent execution/failure contours unless the approved architecture explicitly requires host-to-host orchestration.
- FR-010: Mixed-contour rollout MUST normally expose one independently executable repo-owned operation/bootstrap per affected contour in the declared safe order.
- FR-011: Secrets, passwords, sudo credentials, SSH private keys, TOTP material, API tokens, OAuth state and populated runtime `.env` values MUST remain outside GitHub, chat and command arguments/logs; protected inputs occur only on the target runtime or trusted UI.
- FR-012: GitHub Actions deployment MAY remain an additional supported path, but lack of workflow-dispatch capability in an assistant connector MUST NOT by itself force a transient control-laptop launcher when a safe server-pull entrypoint exists.
- FR-013: Generated/downloaded `.sh`, `.ps1`, `.zip` or companion artifacts on the control laptop MUST be fallback-only for runtime deployment and MUST preserve exact-source/release provenance and integrity.
- FR-014: Fallback artifacts SHOULD be exact repository-derived archives/files or CI-produced artifacts and MUST NOT introduce new substantive deployment logic that exists only outside the repository.
- FR-015: Existing source authorization, production authorization, exact-SHA, rollback, fail-closed, host identity, quality and runtime-acceptance gates MUST remain unchanged.

## Acceptance criteria

- AC-001: The Project Manager contract states that the normal VPS/worker handoff is `where to execute` plus one short target-local server-pull bootstrap command per deployment contour.
- AC-002: The Delivery Policy defines exact-SHA server-pull from the canonical repository as the default interactive VPS/Ubuntu-worker runtime transport when technically available and safe.
- AC-003: Both contracts require substantive deployment logic to be repository-owned before production handoff and treat a missing entrypoint as source work rather than a reason for an ad-hoc launcher.
- AC-004: Both contracts distinguish a small bootstrap from substantive deployment implementation and reject large inline chat deployment programs as the normal path.
- AC-005: Mixed VPS/worker deployment preserves independent failure domains and normally requires separate commands/entrypoints in the declared rollout order.
- AC-006: Control-laptop download/WSL artifact staging is explicitly fallback-only rather than a normal runtime prerequisite.
- AC-007: Fallback transport remains pinned to exact repository/release provenance and does not permit unreviewed substantive deployment logic outside GitHub.
- AC-008: Secrets and protected inputs remain target-local/trusted-UI-only and no security or authorization boundary is weakened.
- AC-009: Contract versions advance from 1.7.0 to 1.8.0 and the exact PR scope contains only the two contracts plus this feature's three SDD artifacts.
- AC-010: PR Validation and Quality integration pass on the exact final PR head; runtime deployment/acceptance is NOT REQUIRED for this control-plane-only feature.

## Compatibility and boundaries

- Stable public interfaces: Production URLs, APIs, Authentik behavior, nginx topology, camera paths, worker M2M, AI behavior and current runtime state remain unchanged.
- Out of scope: implementing or modifying deployment scripts/entrypoints; VPS/worker mutation; Issue #152 rollout; Authentik/nginx/camera/AI/API/M2M changes; secrets or credential changes.
- Security constraints: server-pull cannot waive source/production authorization, exact-SHA binding, quality admission, trusted repository identity, host identity, integrity/provenance, backup/rollback, fail-closed or runtime-acceptance requirements.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED for this contracts/SDD-only feature.
- Accepted production behavior: unchanged.
- Regressions/learning: transient downloaded launchers and large inline shell handoffs created unnecessary operator staging and made reviewed deployment logic less clearly tied to repository source truth.
- Follow-up work: future runtime tasks should add or normalize repository-owned per-contour entrypoints where the exact approved source does not yet provide a safe server-pull operation.
