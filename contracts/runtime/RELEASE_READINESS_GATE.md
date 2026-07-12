# Sea Speed Release Readiness Gate

Version: 1.0.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Approved source committed to main: YES/NO
- Changed files match scope: YES/NO
- Secrets/runtime artifacts absent: YES/NO
- VPS deployment required: YES/NO
- Windows worker update required: YES/NO
- Compatibility and rollout order declared when schemas changed: YES/NO/NOT APPLICABLE
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## VPS gate

When VPS deployment is required, verify the deployed commit, API process, health endpoint, frontend smoke check when applicable, storage compatibility and rollback target.

## Worker gate

When a worker update is required, verify the released commit/version, preservation of local secrets/model/environment/output, successful restart, fresh VPS state and affected overlay/event behavior.

## Documentation-only rule

Changes limited to contracts, documentation, skills or README require PR validation and merge only. VPS and worker release states must be `NOT REQUIRED`.

## Evidence rule

A green PR is not evidence of deployment. Merge is not deployment. Deployment is not acceptance. Report only verified state.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
