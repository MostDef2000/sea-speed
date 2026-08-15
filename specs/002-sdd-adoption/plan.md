# Implementation Plan: Spec Kit SDD Adoption

- Specification: specs/002-sdd-adoption/spec.md
- Issue: #99
- Status: Accepted / completed

## Architecture

```text
Issues -> product authorization/audit
contracts -> delivery authority
.specify + specs -> product/architecture/tasks/runtime feedback
source -> implementation
CI -> structural/linkage enforcement
runtime evidence -> feedback into active SDD
```

## Decisions

### D-001 - SDD complements governance
Contracts remain process authority; specs carry product intent.

### D-002 - CI linkage
Significant PRs must link one spec; docs/spec-only maintenance stays lightweight.

### D-003 - Feature identity
The full `NNN-feature-slug` directory is canonical. The historical duplicate `002` pair is retained; new duplicate prefixes fail validation.

## Affected contours

- Repository: SDD/control plane.
- VPS: NONE.
- Ubuntu Worker/relay: NONE.
- Windows AI Worker: NONE.
- Public interfaces: NONE.

## Validation

SDD validator/tests plus aggregate quality. Runtime acceptance NOT REQUIRED.

## Rollout and rollback

Repository-only merge. Revert source changes if needed; no runtime rollback.

## Runtime feedback

Issue #99 is closed completed. Stage B updates active SDD identity/status rules without rewriting the historical Issue.
