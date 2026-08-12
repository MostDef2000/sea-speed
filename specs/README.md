# Sea Speed Specifications

Status: Active

This directory is the durable Spec-Driven Development (SDD) layer for Sea Speed, compatible with the GitHub Spec Kit workflow.

## Source-of-truth hierarchy

- `contracts/**` defines HOW Sea Speed work is authorized, merged, deployed and accepted.
- `specs/<feature>/spec.md` defines WHAT the product must do and WHY for that feature.
- `specs/<feature>/plan.md` records the accepted architecture and important technical decisions.
- `specs/<feature>/tasks.md` records the bounded implementation work.
- source code implements the feature.
- runtime acceptance proves what actually works in production and feeds that learning back into the feature artifacts.

GitHub Issues remain the canonical backlog, approval and audit history. A specification may supersede an obsolete technical assumption from an older Issue, but the change must be explicit and traceable.

## Feature directory format

Use `NNN-feature-slug`, for example:

```text
specs/003-ai-worker-control/
  spec.md
  plan.md
  research.md       # optional but recommended for non-trivial decisions
  tasks.md
  quickstart.md     # optional validation/operator guide
  contracts/        # optional normative API/runtime/integration contracts
```

Every feature directory MUST contain `spec.md`, `plan.md` and `tasks.md`.

## Normal development flow

```text
Issue and approved scope
-> specification
-> implementation plan
-> tasks
-> code and tests
-> PR links the specification
-> CI checks code + SDD structure
-> separate merge approval
-> runtime acceptance when applicable
-> actual outcome/learning written back into spec/plan/research
```

For significant implementation and control-plane changes, the PR body must include:

```text
- Specification: `specs/NNN-feature-slug/spec.md`
```

Narrow documentation/spec-only maintenance does not require a new feature specification.

## Spec Kit

The project follows the GitHub Spec Kit model (`https://github.com/github/spec-kit`) while keeping Sea Speed governance authoritative. When Spec Kit tooling is available, the normal sequence is:

```text
/speckit.specify
/speckit.plan
/speckit.tasks
/speckit.implement
```

Use `/speckit.clarify`, `/speckit.analyze`, `/speckit.checklist` and `/speckit.converge` when useful. Project-local behavior is defined by `.specify/memory/constitution.md` and `.specify/templates/overrides/`.

CI does not require the Spec Kit CLI itself. It validates the durable repository artifacts with `scripts/ci/validate_sdd.py` so the source of truth remains the GitHub repository rather than a local tool installation.
