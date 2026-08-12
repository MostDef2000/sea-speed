# Feature Specification: Spec Kit SDD Adoption

- Feature: 002-sdd-adoption
- Issue: #99
- Status: Ready for final CI and merge approval

## Product outcome

Sea Speed development has durable, versioned product artifacts next to the code so future work can answer what was intended, why an architecture was chosen, what tasks implemented it and what production actually proved without reconstructing the story from chat or long Issue threads.

## User scenarios

### Scenario 1 - Start a new significant feature

Given an approved Sea Speed Issue, when implementation starts, then the feature has a specification, implementation plan and task list in `specs/<feature>/` before or alongside code work.

### Scenario 2 - Review a pull request

Given a significant implementation/control-plane PR, when CI runs, then the PR links one existing feature specification and the required artifacts are structurally valid.

### Scenario 3 - Production differs from the original plan

Given runtime evidence proves a different architecture is accepted, when the task closes, then the feature artifacts record the accepted production behavior and the rejected/superseded assumption while the historical Issue remains intact.

## Requirements

- FR-001: Sea Speed MUST keep Spec Kit-compatible project guidance under `.specify/`.
- FR-002: Significant features MUST use `specs/NNN-feature-slug/` with at least `spec.md`, `plan.md` and `tasks.md`.
- FR-003: Existing Sea Speed governance MUST remain authoritative for repository write, merge, deployment and runtime authorization.
- FR-004: Significant implementation/control-plane PRs MUST declare a linked feature specification in the PR body.
- FR-005: CI MUST validate the SDD baseline, required feature artifacts and PR-to-spec linkage.
- FR-006: Spec-only/documentation-only maintenance MUST remain lightweight and MUST NOT require creating meaningless new feature specs.
- FR-007: Runtime learning MUST be written back to the relevant feature artifacts when it changes accepted behavior or architecture.
- FR-008: The first production-backed feature spec MUST capture the accepted Camera 1 live pipeline from Issue #87.
- FR-009: CI MUST NOT depend on a locally installed Spec Kit CLI; the durable GitHub artifacts remain the source of truth.

## Acceptance criteria

- AC-001: `.specify/memory/constitution.md` and project-local spec/plan/tasks template overrides exist.
- AC-002: `specs/README.md` documents the hierarchy and workflow.
- AC-003: `specs/001-camera-live-pipeline/` records the accepted Camera 1 architecture and runtime result.
- AC-004: This adoption is itself documented under `specs/002-sdd-adoption/`.
- AC-005: PR Validation runs `scripts/ci/validate_sdd.py`.
- AC-006: Tests prove significant PRs require a linked spec while spec-only changes remain exempt.
- AC-007: No production or runtime configuration changes are part of adoption.

## Compatibility and boundaries

- Stable governance: existing COMMIT/MERGE/deployment/runtime approval boundaries remain unchanged.
- Out of scope: installing Spec Kit on production, changing application behavior, changing GitHub repository settings, production deployment and changes under `skills/**`.
- Security constraints: existing secret rules continue unchanged; SDD artifacts must not capture secrets or runtime credentials.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED for this repository/process-only change.
- Accepted production behavior: unchanged.
- Learning: Issue #87 showed the need to treat accepted runtime architecture as a first-class durable artifact instead of leaving it only in comments and code.
- Follow-up work: use the SDD flow for AI worker controls and generic camera onboarding; consider deeper Spec Kit agent integration only when it adds value without duplicating governance.
