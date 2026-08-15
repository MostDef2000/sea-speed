# Sea Speed Specifications

Status: Active

This directory is the durable Spec-Driven Development layer for Sea Speed.

## Source-of-truth hierarchy

- `contracts/**`: HOW work is authorized, merged, deployed and accepted.
- GitHub Issue: canonical backlog, authorization and audit history.
- `specs/<feature>/spec.md`: WHAT/WHY plus measurable NFR targets/evidence status.
- `plan.md`: HOW/decisions/contours plus risk profile, test design and correct-course impact.
- `tasks.md`: bounded execution, acceptance traceability and Definition of Done.
- source code: implementation.
- runtime evidence: operational truth written back into active artifacts.

## Feature identifiers

Use `NNN-feature-slug`. The **full directory name** is the canonical identifier; the number is only a sequence prefix.

The historical directories `002-camera-preview-gallery` and `002-sdd-adoption` are grandfathered audit history. They must not be renamed solely for cleanup. `scripts/ci/validate_sdd.py` rejects any new duplicate numeric prefix.

## Normal flow

```text
Issue / evidence recovery
-> Delivery Orchestrator + optional Task Intake lens
-> Outcome Contract / scope check
-> OUTCOME APPROVED
-> spec / plan / tasks + delivery-quality artifacts
-> implementation + tests
-> PR links specification and declares risk/quality disposition
-> SDD + quality CI
-> exact-green-head merge
-> separately authorized runtime delivery when applicable
-> accepted/regressed/insufficient_evidence feedback + correct-course impact
```

Domain/release contracts are review lenses; SDD does not require chat-agent handoffs.

## Required structure

Every feature directory contains `spec.md`, `plan.md`, `tasks.md`. Optional `research.md`, `quickstart.md`, `contracts/` may be added when useful.

Significant implementation/control-plane PRs include:

```text
- Specification: `specs/NNN-feature-slug/spec.md`
```

Narrow docs/spec-only maintenance retains the existing lightweight exception.

## Delivery quality layer

For the feature linked by a significant PR, current templates additionally require:

- `spec.md` -> `## NFR assessment` with `NFR-*` records;
- `plan.md` -> `## Risk profile`, `## Test design`, `## Correct-course check`;
- `tasks.md` -> `## Requirements traceability`, `## Definition of Done`.

`Risk profile: REQUIRED` is derived by the PR Change Contract when security, schema, destructive/data-migration, `MIXED` runtime, or another explicit high-risk trigger applies. Otherwise `NOT REQUIRED` is valid.

Historical feature directories remain readable and repository-valid without bulk edits. If they become the linked significant feature in a new PR, update them to the current quality structure inside that task's approved scope.

Quality disposition does not create merge or production authority. `OUTCOME APPROVED` and the production exact-SHA envelope retain those boundaries.

## Historical truth

Completion/status fields in active SDD should be reconciled to durable Issue/PR/CI/runtime evidence. This does not rewrite historical Issues, PR comments or decision records; those remain the audit trail.
