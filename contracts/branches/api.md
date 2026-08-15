# Review Lens: API

Version: 1.1.0
Status: Active
Role: VPS FastAPI Review Lens

## Scope

Review state/events endpoints, ROI/speed configuration, media/storage references, authentication boundaries and API health within the approved task scope.

## Invariants

- no unapproved Worker/frontend/deploy/governance behavior changes;
- API/event/state/storage schema changes require explicit approved compatibility/migration handling;
- no secrets/runtime data in Git;
- preserve backward compatibility unless the Outcome Contract explicitly authorizes migration.

## Checks

Python syntax/imports where available; affected routes/storage/auth/health behavior; VPS applicability and rollback notes.

## Output

Return findings/checklist to the Sea Speed Delivery Orchestrator. This lens does not own branches, PRs, merges or runtime state.
