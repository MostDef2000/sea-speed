# Sea Speed Specifications

Status: Active

This directory is the durable Spec-Driven Development layer for Sea Speed.

## Source-of-truth hierarchy

- `contracts/**`: HOW work is authorized, resumed, merged, policy-evaluated, deployed and accepted.
- GitHub Issue: canonical backlog, source authorization, delivery checkpoint and audit history.
- `specs/<feature>/spec.md`: WHAT/WHY plus measurable NFR targets/evidence status.
- `plan.md`: HOW/decisions/contours plus risk profile, test design, correct-course impact and conditional Deployment Transaction Audit.
- `tasks.md`: bounded execution, acceptance traceability and Definition of Done.
- source code: implementation.
- trusted standing production delegation: independently administered runtime authority state, never an SDD/repository document.
- protected GitHub repository/environment settings: independently administered source/runtime control state, never granted by SDD text.
- runtime evidence: operational truth written back into active artifacts.

For recovery semantics, distinguish **Repository/product truth**, **Delivery-control truth**, and **Transient interaction state**. `main` supplies repository/product truth. The canonical Issue supplies durable delivery-control truth, including machine-readable `Sea Speed Delivery Checkpoint v2`. Initial source admission still requires the complete visible Scope immediately followed by `OUTCOME APPROVED`; a durable receipt can only resume the same exact admitted scope and cannot create new authority.

Synchronous orchestration uses `ACTIVE`, nonterminal `WAITING_EXTERNAL`, or `TERMINAL` as session disposition. A known GitHub Actions run or check that is `queued` or `in_progress` keeps the session `ACTIVE` with foreground rate-limited exact-cursor observation and does not justify `WAITING_EXTERNAL`. `WAITING_EXTERNAL` is valid only when no action is executable now and an exact non-CI external evidence transition is pending; it never implies background polling. Persisted v1 checkpoints remain readable and are upgraded by the repository validator at the next meaningful transition.

## Feature identifiers

Use `NNN-feature-slug`. The full directory name is canonical; the number is only a sequence prefix. Historical duplicate prefix `002` directories are grandfathered audit history and are not renamed solely for cleanup.

Current control-plane feature `031-resumable-delivery-orchestration` defines bounded Resume Probe, monotonic lifecycle state, durable checkpoint/evidence cursors and Connector loop guards. Feature `030-ubuntu-zero-touch-transport` remains the canonical GitHub Free public/protected-main and restricted Ubuntu zero-touch transport model.

## Normal flow

```text
Issue / evidence recovery
-> existing valid checkpoint: bounded Resume Probe
   OR new/materially invalidated task: Delivery Orchestrator + optional Task Intake
-> Outcome Contract / visible Scope when fresh source authorization is required
-> OUTCOME APPROVED
-> durable authorization receipt + Delivery Checkpoint
-> spec / plan / tasks + delivery-quality artifacts
-> implementation + tests
-> PR links specification and declares risk/quality disposition
-> SDD + quality CI
-> protected exact-green-head merge
-> exact-main Quality
-> protected-source verification
-> standing production policy evaluation when runtime applies
-> applicable protected deployment + typed execution evidence
-> accepted/regressed/insufficient_evidence feedback + correct-course impact
```

Source authorization and runtime authority are distinct. `OUTCOME APPROVED` authorizes source lifecycle. Runtime authority comes from independently administered standing delegation intersected with repository policy. Source protection and deployment credentials are also independently administered control state. Issue/PR/comment/SDD/repository text cannot grant production authority.

Context compaction, session restart and Connector truncation do not by themselves invalidate an admitted source scope or return the lifecycle to `DISCUSSION`. A valid checkpoint resumes through `Next admissible action`; full project recovery is reserved for an absent/unresolved/invalid checkpoint or material evidence contradiction.

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

The current GitHub Free production model additionally requires public protected `main` and required merge-facing checks before runtime policy/transport. A private repository or unprotected `main` is production deny until independently corrected.

## Historical truth

Completion/status fields in active SDD should be reconciled to durable Issue/PR/CI/runtime evidence. This does not rewrite historical Issues, PR comments or decision records.
