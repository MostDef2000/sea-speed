# Sea Speed Specifications

Status: Active

This directory is the durable Spec-Driven Development layer for Sea Speed.

## Source-of-truth hierarchy

- `contracts/**`: HOW work is authorized, merged, deployed and accepted.
- GitHub Issue: canonical backlog, authorization and audit history.
- `specs/<feature>/spec.md`: WHAT/WHY.
- `plan.md`: HOW/decisions/contours.
- `tasks.md`: bounded execution and completion evidence.
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
-> spec / plan / tasks
-> implementation + tests
-> PR links specification
-> SDD + quality CI
-> exact-green-head merge
-> separately authorized runtime delivery when applicable
-> accepted/regressed/insufficient_evidence feedback
```

Domain/release contracts are review lenses; SDD does not require chat-agent handoffs.

## Required structure

Every feature directory contains `spec.md`, `plan.md`, `tasks.md`. Optional `research.md`, `quickstart.md`, `contracts/` may be added when useful.

Significant implementation/control-plane PRs include:

```text
- Specification: `specs/NNN-feature-slug/spec.md`
```

Narrow docs/spec-only maintenance retains the existing lightweight exception.

## Historical truth

Completion/status fields in active SDD should be reconciled to durable Issue/PR/CI/runtime evidence. This does not rewrite historical Issues, PR comments or decision records; those remain the audit trail.
