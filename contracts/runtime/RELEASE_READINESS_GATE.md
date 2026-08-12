# Sea Speed Release Readiness Gate

Version: 1.4.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Outcome Contract / approved scope current: YES/NO
- Approved source committed to main: YES/NO
- Changed files match approved scope: YES/NO
- Aggregate quality context successful for exact commit: YES/NO
- Secrets/runtime artifacts absent: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest valid: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- Worker update required: YES/NO
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Production safety envelope available: YES/NO/NOT APPLICABLE
- Production envelope still matches outcome/contour/boundaries: YES/NO/NOT APPLICABLE
- Final exact 40-character source SHA bound to envelope: YES/NO/NOT APPLICABLE
- Acceptance evidence plan available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify the complete approved file set and delivery lifecycle. Do not accept partial delivery as a substitute for a blocked mandatory path.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. A skipped, cancelled or failed dependency is not success.

## Release provenance gate

When runtime delivery applies, validate canonical Issue, current Outcome Contract, exact base/source commits, approved changed-file set/scope hash, deployable artifact inventory, deterministic rebuild where supported, SHA-256/size, component classification, contract set and quality evidence.

Package creation is not deployment evidence.

## Production authorization gate

Production must not run because of a pull request, push, merge or source Outcome Authorization alone.

A production safety envelope must be separately recorded. It may cover the final exact gated deployment, declared necessary restart/reload operations, bounded smoke checks and an explicitly declared safe rollback condition/target.

Before each production execution, bind that envelope to the final exact source SHA by verifying:

- the source SHA is a full 40-character commit on `main` attributable to the same canonical task/outcome;
- aggregate quality succeeded for that exact SHA;
- exact artifacts, release manifest and quality evidence validate;
- product outcome, runtime contour, protected boundaries, deployment method and rollback semantics still match the approved envelope;
- the rollback target is known.

Bounded source/CI remediation inside the same Outcome Contract does not automatically stale the production envelope. A material change to outcome, contour, protected boundary, deployment target, secret/security handling, destructive behavior or rollback semantics does stale it and requires fresh production authorization.

## VPS gate

When VPS deployment is required, verify authorized automation ran, deployment identity matches the exact bound commit, health/source identity is correct, applicable frontend/storage checks pass and rollback target remains known.

## Worker gate

When worker update is required, verify exact package/install identity, preservation of local protected state, valid deployment evidence, restart, matching worker source identity, freshness/frame advancement and applicable telemetry semantics.

GitHub-hosted CI does not prove physical camera/GPU/runtime behavior.

## Mixed-contour gate

When both VPS and worker updates apply, verify declared compatibility and execute the authorized rollout/rollback order.

## Media-boundary gate

The active `mvp_v1` and target `edge_v2` storage boundary remain unchanged; activating `edge_v2` remains a separate protected migration.

## Evidence review gate

After runtime verification, return exactly one product verdict: `accepted`, `regressed`, or `insufficient_evidence`. A regression requires a linked Issue and rollback decision unless the exact safe rollback was already included in the active production envelope.

## Documentation-only rule

Changes limited to governance, SDD, documentation, quality tooling, skills or README require aggregate PR validation and authorized merge only. VPS and worker release states must be `NOT REQUIRED`.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
