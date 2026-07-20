# Sea Speed Release Readiness Gate

Version: 1.1.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Approved source committed to main: YES/NO
- Changed files match scope: YES/NO
- Secrets/runtime artifacts absent: YES/NO
- VPS deployment required: YES/NO
- Windows worker update required: YES/NO
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Acceptance evidence available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify that the complete approved file set can be written and reviewed and that required branch, PR, CI, merge, delivery, verification and rollback operations are available. Do not accept a partial multi-file delivery as a substitute for a blocked mandatory path.

## VPS gate

When VPS deployment is required, verify the deployed commit, API process, health endpoint, frontend smoke check when applicable, storage compatibility and rollback target.

## Worker gate

When a worker update is required, verify the released commit/version, preservation of local secrets/model/environment/output, successful restart, fresh VPS state, advancing heartbeat or frame evidence when available, and affected overlay/event behavior.

## Mixed-contour gate

When both VPS and worker updates are required, verify compatibility for old/new component combinations and execute the declared rollout order. The default is backward-compatible VPS/API first, API acceptance second, worker update third, and worker runtime acceptance last.

## Documentation-only rule

Changes limited to contracts, documentation, skills or README require PR validation and merge only. VPS and worker release states must be `NOT REQUIRED`.

## Evidence rule

A green PR is not evidence of deployment. Merge is not deployment. Deployment is not acceptance. Report only verified state. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`