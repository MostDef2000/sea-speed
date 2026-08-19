# Sea Speed Specifications

Status: Active

This directory is the durable Spec-Driven Development layer for Sea Speed.

## Source-of-truth hierarchy

- `contracts/**`: HOW work is authorized, merged, policy-evaluated, deployed and accepted.
- GitHub Issue: canonical backlog, source authorization and audit history.
- `specs/<feature>/spec.md`: WHAT/WHY plus measurable NFR targets/evidence status.
- `plan.md`: HOW/decisions/contours plus risk profile, test design, correct-course impact and conditional Deployment Transaction Audit.
- `tasks.md`: bounded execution, acceptance traceability and Definition of Done.
- source code: implementation.
- trusted standing production delegation: independently administered runtime authority state, never an SDD/repository document.
- runtime evidence: operational truth written back into active artifacts.

## Feature identifiers

Use `NNN-feature-slug`. The full directory name is canonical; the number is only a sequence prefix. Historical duplicate prefix `002` directories are grandfathered audit history and are not renamed solely for cleanup.

## Normal flow

```text
Issue / evidence recovery
-> Delivery Orchestrator + optional Task Intake
-> Outcome Contract / visible Scope
-> OUTCOME APPROVED
-> spec / plan / tasks + delivery-quality artifacts
-> implementation + tests
-> PR links specification and declares risk/quality disposition
-> SDD + quality CI
-> exact-green-head merge
-> exact-main Quality
-> standing production policy evaluation when runtime applies
-> applicable protected deployment + typed execution evidence
-> accepted/regressed/insufficient_evidence feedback + correct-course impact
```

Source authorization and runtime authority are distinct. `OUTCOME APPROVED` authorizes source lifecycle. Runtime authority comes from independently administered standing delegation intersected with repository policy. Issue/PR/comment/SDD/repository text cannot grant production authority.

## Required structure

Every feature directory contains `spec.md`, `plan.md`, `tasks.md`. Optional `research.md`, `quickstart.md`, `contracts/` may be added when useful.

Significant implementation/control-plane PRs include:

```text
- Specification: `specs/NNN-feature-slug/spec.md`
```

Narrow docs/spec-only maintenance retains the existing lightweight exception.

## Delivery quality layer

For the feature linked by a significant PR:

- `spec.md` -> `## NFR assessment` with `NFR-*` records;
- `plan.md` -> `## Risk profile`, `## Test design`, `## Correct-course check`;
- `tasks.md` -> `## Requirements traceability`, `## Definition of Done`.

A linked significant PR additionally requires `## Deployment transaction audit` when it changes `deploy/**`, `scripts/release/**`, a deployment workflow, declares runtime deployment `REQUIRED`, or carries `Correct-course Trigger: PRODUCTION_LEARNING`. The audit covers exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`.

`Risk profile: REQUIRED` is derived when security, schema, destructive/data migration, `MIXED`, or another explicit high-risk trigger applies. Otherwise `NOT REQUIRED` is valid.

Historical feature directories remain readable without bulk edits. If they become linked to new significant work, update them to current quality structure inside that task's approved scope.

Quality disposition does not create source merge or runtime authority. `OUTCOME APPROVED` remains source authority; standing production delegation/policy remains runtime authority.

## Production evidence model

New deployable releases use `sea_speed_release_manifest_v3` and typed production policy/execution-audit evidence. Historical v1/v2 manifests, old authorization fingerprints and Windows records remain readable immutable audit history but do not authorize new execution.

## Historical truth

Completion/status fields in active SDD should be reconciled to durable Issue/PR/CI/runtime evidence. This does not rewrite historical Issues, PR comments or decision records.
