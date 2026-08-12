# Quickstart: Sea Speed SDD

- Specification: specs/002-sdd-adoption/spec.md

## Start a significant feature

1. Create or identify the canonical GitHub Issue and complete the existing Sea Speed scope/approval process.
2. Create `specs/NNN-feature-slug/spec.md` from the Sea Speed Spec Kit override and describe product outcome, user scenarios, requirements and acceptance criteria.
3. Create `plan.md` with architecture, decisions, affected contours and validation.
4. Create `tasks.md` with bounded implementation work.
5. Implement code and tests in the same feature branch.
6. Link the feature in the PR body with `- Specification: ` followed by the feature `spec.md` path.
7. Let PR Validation check both the Change Contract and SDD artifacts.
8. After runtime acceptance, update Runtime feedback in the feature artifacts with what production actually proved.

## With Spec Kit tooling

When an agent has GitHub Spec Kit available, use its `speckit.specify`, `speckit.plan`, `speckit.tasks` and `speckit.implement` flow. Sea Speed project-local constitution/templates guide the generated artifacts.

## Important boundary

Spec Kit does not authorize repository writes, merge, deployment or production operations. Those remain controlled by the Sea Speed governance contracts.
