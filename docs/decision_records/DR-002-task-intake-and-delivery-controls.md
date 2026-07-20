# DR-002: Task Intake and Capability-Aware Delivery Controls

Status: Accepted
Date: 2026-07-20

## Context

Sea Speed already separates GitHub source from the VPS and Windows worker runtime contours and requires explicit approval, fresh branches, pull-request validation, release applicability, and runtime evidence. However, incoming requests could still move directly into implementation planning without a canonical intake record, and multi-file work did not explicitly require a capability preflight before the first write.

This creates avoidable risks:

- requirements can remain only in chat history;
- approval can be interpreted before the final implementation scope is visible;
- implementation can begin before the full file set can be edited and published safely;
- mixed API and worker changes can lack a declared rollout order;
- completion can be claimed from merge or CI without contour-specific evidence.

## Decision

Sea Speed adopts the following controls:

1. GitHub Issues are the canonical persistent backlog and task history for repository work.
2. A read-only Task Intake Agent converts unstructured requests into a canonical Task Brief.
3. Repository-write approval is valid only after an Implementation Scope Check states the exact intended files, exclusions, risks, impact, checks, release applicability, and acceptance criteria.
4. Before the first write, the Project Manager performs a capability preflight for the complete approved file set and the expected branch, PR, CI, merge, release, verification, and rollback path.
5. Partial implementation is prohibited when the full mandatory file set cannot be changed safely.
6. Mixed API and worker work must document compatibility in both old/new directions and an explicit rollout order.
7. COMPLETE is evidence-based and requires source integration plus every applicable delivery and runtime-acceptance proof.
8. Existing task-runtime states remain unchanged; intake occurs during DISCUSSION and produces READY_FOR_IMPLEMENTATION only after specification readiness and approval requirements are satisfied.

## Consequences

- Repository work becomes easier to resume, audit, and hand off.
- Governance-only tasks remain release-free for both runtime contours.
- Some tasks may become BLOCKED before implementation when required capabilities, credentials, target access, rollback, or verification paths are unavailable.
- Additional documentation is required for mixed-contour and schema-changing work.
- Task Intake remains advisory and read-only; it cannot authorize repository writes.

## Alternatives rejected

### Keep requirements only in chat

Rejected because chat history is not a durable project backlog and does not provide stable links between requirements, implementation, PRs, releases, and final evidence.

### Begin with any available subset of files

Rejected because partial multi-file changes can leave governance, runtime behavior, schemas, or delivery tooling inconsistent.

### Treat green CI or merge as completion

Rejected because Sea Speed has independent VPS and Windows runtime contours whose deployed state must be verified separately.
