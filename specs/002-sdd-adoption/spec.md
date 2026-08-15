# Feature Specification: Spec Kit SDD Adoption

- Feature: 002-sdd-adoption
- Issue: #99
- Status: Accepted / completed

## Product outcome

Sea Speed keeps durable product intent, architecture, bounded tasks and runtime learning beside source so accepted behavior does not need to be reconstructed from chat or long Issue threads.

## User scenarios

1. Significant work has `spec.md`, `plan.md`, `tasks.md` before or alongside implementation.
2. Significant PRs link one valid feature specification and CI validates it.
3. Runtime evidence that changes accepted architecture is written back while historical Issues remain intact.

## Requirements

- SDD guidance lives under `.specify/` and `specs/`.
- Governance contracts remain authoritative for authorization/delivery.
- Significant implementation/control-plane PRs link one active spec.
- CI validates SDD structure/linkage without requiring a local Spec Kit CLI.
- docs/spec-only maintenance remains lightweight.
- runtime learning updates active artifacts; historical audit records remain unchanged.
- full feature directory names are canonical identifiers; numeric prefixes are sequencing aids.

## Acceptance criteria

- SDD constitution/templates and `specs/README.md` exist.
- Camera Live is represented by production-backed artifacts.
- `scripts/ci/validate_sdd.py` enforces structure/linkage.
- Issue #99 is closed `completed`; no runtime deployment was required.

## Compatibility and boundaries

Application/runtime behavior unchanged. Historical `002-camera-preview-gallery` and `002-sdd-adoption` remain grandfathered; new duplicate numeric prefixes are prohibited.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED.
- Repository acceptance: COMPLETE; Issue #99 closed completed on 2026-08-12.
- Stage B learning: SDD status fields must be reconciled to durable Issue/CI/runtime evidence and the full directory name is the canonical feature identity.
