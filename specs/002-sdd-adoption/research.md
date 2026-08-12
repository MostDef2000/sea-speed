# Research: Spec Kit SDD Adoption

- Specification: specs/002-sdd-adoption/spec.md
- Issue: #99

## Upstream fit

GitHub Spec Kit is designed around specification -> plan -> tasks -> implementation, with project principles/constitution and optional consistency commands. It stores feature artifacts in the repository and supports project-local template overrides.

## Sea Speed fit

Sea Speed already has stronger-than-default governance for approvals, deployment boundaries and runtime evidence. Replacing those controls would lose useful project-specific safety and provenance. The best fit is therefore a parallel artifact layer:

- governance answers who/when/how work is authorized and released;
- SDD answers what the feature means, why decisions were made and what production proved.

## Automation boundary

Automatic generation is useful, but the canonical result must be files committed to GitHub. CI should validate those files without requiring a particular local AI agent or Spec Kit installation. This keeps the repository portable and reviewable.

## Camera 1 as evidence

Issue #87 accumulated many diagnostic iterations and its original MediaMTX assumption no longer matches the accepted runtime architecture. The Camera Live retrofit demonstrates why production feedback must update a durable feature spec rather than remain only in comments.
