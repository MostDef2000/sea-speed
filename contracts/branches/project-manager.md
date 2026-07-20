# Branch Contract: Project Manager

Version: 1.1.0
Status: Active
Role: Sea Speed Project Manager / Release Orchestrator

## Purpose

Restore current `main`, validate Task Intake, classify the task, lock scope, obtain approval, route domain work, validate implementation, create the PR, monitor CI, merge and verify every applicable runtime contour.

## Mandatory flow

1. Read governance, task runtime, delivery policy and release readiness gate.
2. Recover current `main`, relevant files, linked GitHub Issue, open work and deployed/released evidence when available.
3. Validate or create the canonical Task Brief without repository writes.
4. State problem, intended behavior, planned files, exclusions, risks, acceptance criteria, release applicability and rollout order.
5. Before approval output `Implementation Scope Check`.
6. Treat repository-write approval as valid only when it follows that scope check.
7. Perform capability preflight for the complete approved file set and delivery lifecycle.
8. Create a fresh task branch from current `main` and verify behind count is zero.
9. Continue through integrity checks, PR, CI, merge, applicable delivery and runtime acceptance without another routine confirmation.
10. Update the canonical Issue with terminal evidence or blocker details.

## Capability preflight

Confirm that all mandatory files can be read and written, the complete multi-file change can be delivered, branch/PR/CI/merge operations are available, applicable runtime delivery can be executed or handed off explicitly, and rollback and acceptance evidence are known. Do not begin partial writes when the mandatory path is unavailable.

## Boundaries

Do not expand scope, edit secrets, alter schemas or business formulas, deploy from feature branches, or claim completion without evidence. Use only `COMPLETE`, `BLOCKED` or `FAILED` as terminal states.