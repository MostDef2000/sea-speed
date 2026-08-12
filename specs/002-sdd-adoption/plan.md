# Implementation Plan: Spec Kit SDD Adoption

- Specification: specs/002-sdd-adoption/spec.md
- Issue: #99
- Status: Ready for final CI and merge approval

## Architecture

Add an SDD artifact layer beside the existing Sea Speed governance:

```text
contracts/                  process authority and protected delivery rules
.specify/                   Spec Kit constitution and Sea Speed template overrides
specs/<feature>/spec.md     product intent and acceptance
specs/<feature>/plan.md     architecture and decisions
specs/<feature>/tasks.md    bounded execution
source code                 implementation
runtime acceptance          operational truth fed back into specs
```

CI validates the durable artifacts directly. Spec Kit CLI remains optional tooling for generating/updating those artifacts rather than a runtime or CI dependency.

## Decisions

### D-001 - Spec Kit complements governance instead of replacing it

- Decision: retain Sea Speed contracts for approvals/delivery and use Spec Kit for product/architecture artifacts.
- Reason: governance and product intent solve different problems; merging them would create ambiguous authority.
- Alternatives rejected: replace current contracts with the upstream Spec Kit constitution/process.

### D-002 - Enforce linkage in CI

- Decision: significant implementation/control-plane PRs must link `specs/<feature>/spec.md`.
- Reason: documentation remains living only if code changes cannot silently bypass it.
- Alternatives rejected: rely on manual discipline alone.

### D-003 - Keep small documentation work lightweight

- Decision: changes that touch only `specs/**`, `.specify/**`, docs or tests do not automatically require a new feature spec.
- Reason: SDD should improve traceability, not force recursive paperwork.

### D-004 - Retrofit Camera Live first

- Decision: create a production-backed Camera Live specification from Issue #87 and runtime acceptance.
- Reason: it captures a real case where accepted architecture diverged from the original assumption and demonstrates the feedback loop.

## Affected contours

- Repository: governance adapter, PR template, PR CI, repository validator, new SDD validator/tests and SDD artifacts.
- VPS: NONE.
- Ubuntu worker/relay: NONE.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: Python compile, unit tests for SDD validator, existing repository/contract/quality workflows.
- Integration: PR Validation must accept this PR only when the linked `002-sdd-adoption` spec and all artifacts are present.
- Runtime acceptance: NOT REQUIRED; no runtime behavior changes.

## Rollout and rollback

- Rollout: merge repository-only SDD baseline after required CI and separate merge approval.
- Rollback: revert the SDD adoption commit/merge if the process proves harmful; no production rollback is involved.

## Runtime feedback

- Actual architecture after acceptance: pending merge.
- Differences from plan: none yet.
- Deferred cleanup: optional Spec Kit CLI installation/integration for local agents can be added later; CI remains independent of it.
