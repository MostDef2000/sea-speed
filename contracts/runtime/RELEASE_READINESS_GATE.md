# Sea Speed Release Readiness Gate

Version: 1.5.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Applicable merged PR linked: YES/NO
- Outcome Contract / approved scope current: YES/NO
- Approved source committed to main: YES/NO
- Exact source is on current main first-parent history: YES/NO
- Changed files match approved scope: YES/NO
- Aggregate quality push run on main successful for exact commit: YES/NO
- SDD linkage valid for significant change: YES/NO/NOT APPLICABLE
- Secrets/runtime artifacts absent: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest v2 valid: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- Ubuntu worker/relay update required: YES/NO
- Windows AI worker update required: YES/NO
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Production safety envelope available: YES/NO/NOT APPLICABLE
- Durable production authorization matches current fingerprint: YES/NO/NOT APPLICABLE
- Final exact lowercase 40-character source SHA bound to envelope: YES/NO/NOT APPLICABLE
- Acceptance evidence plan available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify the complete approved file set and delivery lifecycle. Do not accept partial delivery as a substitute for a blocked mandatory path.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. The static/contract domain executes `scripts/ci/validate_sdd.py` for PR events, so a significant PR without valid linked SDD cannot produce aggregate success. The existing docs/spec lightweight exception remains in the validator. A skipped, cancelled or failed dependency is not success.

This workflow is the canonical repository gate; it does not imply that GitHub branch-protection settings are enabled.

## Release provenance gate

When runtime delivery applies, new release provenance uses `sea_speed_release_manifest_v2`. Validate canonical Issue, applicable PR, current Outcome Contract hash, Change Contract hash, exact base/source commits, approved changed-file set, actual Git diff, approved-scope hash, deployable artifact inventory, SHA-256/size, component classification, exact-artifact evidence and quality evidence.

Approved scope and actual diff are separate facts and must match at admission. A merge-message PR number is never a canonical Issue fallback. `ready_for_deployment` for a runtime component requires at least one exact artifact. Persisted v1 release/deployment evidence remains readable for rollback compatibility.

Package creation is not deployment evidence.

## Production authorization gate

Production must not run because of a pull request, push, merge or source Outcome Authorization alone.

A production safety envelope must be separately recorded. Durable authorization is canonical Issue evidence from a source-controlled authorized actor. It must bind the canonical Issue, applicable merged PR, exact source SHA, Outcome Contract, exact runtime contour set, security impact, deployment target and rollback target. Material change to any bound semantic makes the previous authorization stale.

Before each production execution, verify all of the following before SSH or other runtime mutation:

- the input is already a lowercase full 40-character SHA; normalization is not admission;
- the source SHA is on current `main` **first-parent** history, so a merged feature-head or synthetic/non-main commit is rejected;
- the exact `quality-integration.yml` workflow has a successful completed run with event `push`, branch `main`, and the same head SHA; a PR check-run name is insufficient;
- the exact source commit resolves to exactly one applicable merged PR and its Change Contract binds the requested canonical Issue;
- durable `PRODUCTION APPROVED <full-sha>` evidence from an authorized actor carries the current authorization fingerprint;
- exact artifacts, release manifest and quality evidence validate;
- product outcome, runtime contours, protected boundaries, deployment method and rollback semantics still match the approved envelope;
- the rollback target is known.

GitHub/API errors, missing linkage, ambiguity or stale fingerprints fail closed. The protected `production` environment remains an additional gate, not a replacement for durable authorization.

## VPS gate

When VPS deployment is required, `deploy-vps.yml` remains manually dispatched. Verify authorized automation ran from the main workflow definition, deployment identity matches the exact bound first-parent main commit, health/source identity is correct, applicable frontend/storage checks pass and rollback target remains known.

## Ubuntu Worker/relay gate

When Ubuntu Worker/relay update is required, verify exact source/package/runtime identity, preservation of protected local state, valid deployment evidence, applicable service restart, matching source/runtime identity, freshness/frame advancement and relay/AI telemetry semantics.

## Windows AI Worker gate

When Windows AI Worker update is required, verify exact package/install identity, preservation of local protected state, valid deployment evidence, restart, matching worker source identity, freshness/frame advancement and applicable telemetry semantics.

GitHub-hosted CI does not prove physical camera/GPU/runtime behavior.

## Mixed-contour gate

When two or three runtime contours apply, `MIXED` is only the summary classification. The exact VPS, Ubuntu Worker/relay and Windows AI Worker deployment fields must equal the exact derived contour set. Verify declared compatibility and execute the authorized rollout/rollback order.

## Media-boundary gate

The active `mvp_v1` and target `edge_v2` storage boundary remain unchanged; activating `edge_v2` remains a separate protected migration.

## Evidence review gate

After runtime verification, return exactly one product verdict: `accepted`, `regressed`, or `insufficient_evidence`. A regression requires a linked Issue and rollback decision unless the exact safe rollback was already included in the active production envelope.

## Documentation/control-plane rule

Changes limited to governance, SDD, documentation and delivery/quality tooling require aggregate PR validation and authorized merge only when their derived production impact is CONTROL_PLANE. All three runtime deployment states and production safety envelope must be `NOT REQUIRED`. A path that actually mutates a runtime contour is not converted to control-plane-only by this rule.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
