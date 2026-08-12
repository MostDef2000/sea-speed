# Sea Speed SDD Constitution

Version: 1.0.0
Status: Active
Ratified: 2026-08-12

This constitution configures the Spec-Driven Development layer for Sea Speed. It does not replace `contracts/SEA_SPEED_GOVERNANCE.md` or delivery/runtime approval rules.

## I. Product outcome before implementation

Every significant feature starts from the user-visible or operator-visible outcome. A feature specification defines WHAT must be true and WHY it matters before implementation details are chosen.

## II. Specifications are durable product intent

For an active feature, `specs/<feature>/spec.md` is the canonical statement of product intent and acceptance criteria. GitHub Issues remain the canonical backlog, approval and task-history record. Code is the current implementation of the specification, not a substitute for it.

## III. Plans explain architecture and decisions

`plan.md` records HOW the feature is implemented, affected runtime contours, compatibility constraints, important rejected alternatives and validation strategy. Architectural decisions discovered during implementation must be written back to the plan instead of remaining only in chat, PR comments or operator memory.

## IV. Tasks are executable and bounded

`tasks.md` decomposes the approved plan into concrete work. Tasks must be traceable to requirements and should avoid speculative future work. New scope discovered during implementation requires the existing Sea Speed approval process.

## V. Runtime reality feeds the specification

Production acceptance, regressions and operational discoveries are inputs to the SDD artifacts. If production proves that the accepted architecture differs from the original assumption, the spec/plan/research artifacts must record the accepted reality. Historical Issues remain an audit trail and must not be silently rewritten to hide the earlier assumption.

## VI. Simplicity is preferred

Prefer the smallest architecture that satisfies the product outcome, preserves required compatibility and remains operable. Intermediate services, abstractions and future-proofing are not mandatory merely because they existed in a previous design.

## VII. Governance remains authoritative

Spec Kit is an artifact-generation and consistency tool. Repository write approval, merge approval, deployment authorization, secret handling, protected operations and runtime acceptance continue to be governed by the canonical Sea Speed contracts.

## VIII. Traceability is mandatory for significant changes

A significant implementation or control-plane PR must link one feature specification. The linked feature directory must contain at least `spec.md`, `plan.md` and `tasks.md`. CI validates the structure and link. Documentation/spec-only maintenance may remain lightweight.

## IX. Public compatibility is explicit

Stable public URLs, API contracts, persisted state, operator workflows and other compatibility guarantees must be named in the specification and plan when affected. A compatible implementation may change internally without changing those guarantees.

## X. Automation without hidden state

SDD artifacts live in GitHub next to the code. Agents may generate and update them automatically from approved work, but the durable result must be reviewable in the same branch and PR as the implementation. No required product decision may exist only in local agent memory.

## Standard lifecycle

```text
Issue / approved intent
-> spec.md
-> plan.md
-> tasks.md
-> implementation
-> CI consistency checks
-> merge
-> deployment/runtime acceptance when applicable
-> runtime feedback written back to the feature artifacts
```

## Minimum feature artifact set

Required:

- `spec.md` - product outcome, user scenarios, requirements, acceptance criteria and runtime feedback;
- `plan.md` - architecture, decisions, affected contours, validation and runtime feedback;
- `tasks.md` - bounded delivery work and completion gate.

Recommended when useful:

- `research.md` - alternatives, constraints and evidence;
- `quickstart.md` - validation and operator-facing acceptance steps;
- `contracts/` - normative API, runtime or integration contracts.

## Change policy

Amend this constitution through the normal Sea Speed repository workflow. Changes that alter governance or protected delivery rules must also update the canonical contracts and receive the corresponding approval.
