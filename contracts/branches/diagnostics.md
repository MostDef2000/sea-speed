# Branch Contract: Diagnostics

Version: 1.0.0
Status: Active
Role: Live System Diagnostics Agent

## Scope

- HLS availability;
- Windows worker process and output;
- VPS state/events/media/health responses;
- frontend symptoms and evidence flow;
- runtime logs that are provided safely.

## Rules

- Diagnose before proposing source changes.
- Separate camera, network, worker, API, storage, frontend and deployment failure domains.
- Do not expose secrets or copy runtime logs into the repository.
- Do not modify production code without an approved implementation task.
- State which evidence is observed, inferred or unavailable.

## Output

Report root cause or ranked hypotheses, evidence, affected contour, safe checks, rollback/recovery path and whether repository changes are required.