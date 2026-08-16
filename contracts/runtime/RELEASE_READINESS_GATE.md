# Sea Speed Release Readiness Gate

Version: 1.8.0
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
- Delivery quality layer valid: YES/NO/NOT APPLICABLE
- Deployment transaction audit valid: YES/NO/NOT APPLICABLE
- Production-learning adjacent-stage review complete: YES/NO/NOT APPLICABLE
- Risk profile applicability correct: YES/NO/NOT APPLICABLE
- Quality verdict: PASS/CONCERNS/WAIVED/NOT APPLICABLE
- Secrets/runtime artifacts absent: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest v2 valid: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- VPS execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Ubuntu worker/relay update required: YES/NO
- Ubuntu execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Windows AI worker update required: YES/NO
- Windows execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Operator actions expected: <non-negative integer>
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Production safety envelope available: YES/NO/NOT APPLICABLE
- Durable production authorization matches current fingerprint: YES/NO/NOT APPLICABLE
- Production execution intent: EXECUTE/AUTHORIZE_ONLY/NOT APPLICABLE
- Final exact lowercase 40-character source SHA bound to envelope: YES/NO/NOT APPLICABLE
- Acceptance evidence plan available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify the complete approved file set and delivery lifecycle. Do not accept partial delivery as a substitute for a blocked mandatory path.

The exact Change Contract must declare one runtime execution capability per contour. A required contour with `MISSING` or `NOT APPLICABLE` fails admission. A non-required contour must be `NOT APPLICABLE`. `Operator actions expected` must equal the number of required `ONE_COMMAND_FALLBACK` contours.

For VPS, the repository already has Connector-addressable protected execution. For Ubuntu, `.github/workflows/deploy-ubuntu-worker.yml` plus `deploy/worker/ubuntu/deploy-authorized.sh` provide the protected workflow/target transaction. Zero-touch Ubuntu transport is `CONNECTOR` only when a restricted production transport/privilege boundary is independently provisioned and reachable; otherwise the truthful capability is `ONE_COMMAND_FALLBACK`. Do not infer a secret, route, sudo policy or runner from source alone.

If a mandatory runtime contour has neither Connector execution nor one repository-owned exact fallback action, stop `BLOCKED` before partial delivery.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. The static/contract domain executes `scripts/ci/validate_sdd.py` for PR events, so a significant PR without valid linked SDD cannot produce aggregate success. The existing docs/spec lightweight exception remains in the validator. A skipped, cancelled or failed dependency is not success.

This workflow is the canonical repository gate; it does not imply that GitHub branch-protection settings are enabled.

## Delivery quality gate

For a significant PR, `scripts/ci/validate_sdd.py` validates the current linked feature's NFR assessment, risk profile/test design/correct-course sections, acceptance traceability and Definition of Done. Historical feature directories remain repository-valid without retrofit until they become the active linked significant work.

When a significant PR affects deployment/release execution, a deployment workflow, declares a runtime deployment `REQUIRED`, or carries `PRODUCTION_LEARNING`, the same validator also requires the full Deployment Transaction Audit. A production learning must record the root cause and a completed adjacent-stage review before the next production retry is proposed.

`scripts/ci/validate_change_contract.py` derives whether a full risk profile is required from security impact, API/event/state/storage schema impact, destructive/data migration, `MIXED` runtime impact, and an explicit other high-risk trigger. It also enforces runtime execution capability and operator-action budget, rejects quality verdict `FAIL`, and admits `WAIVED` only with a complete durable waiver record.

A quality waiver is never a hard gate bypass. It never bypasses source authorization, exact diff, runtime-contour derivation, protected-boundary reauthorization, secrets checks, aggregate CI, production authorization, release provenance, rollback or runtime acceptance.

## Release provenance gate

When runtime delivery applies, new release provenance uses `sea_speed_release_manifest_v2`. Validate canonical Issue, applicable PR, current Outcome Contract hash, Change Contract hash, exact base/source commits, approved changed-file set, actual Git diff, approved-scope hash, deployable artifact inventory, SHA-256/size, component classification, exact-artifact evidence and quality evidence.

Approved scope and actual diff are separate facts and must match at admission. A merge-message PR number is never a canonical Issue fallback. `ready_for_deployment` for a runtime component requires at least one exact artifact. The Ubuntu exact artifact must contain the repository-owned `deploy/worker/ubuntu/deploy-authorized.sh` transaction entrypoint. Persisted v1 release/deployment evidence remains readable for rollback compatibility.

Package creation is not deployment evidence.

## Production authorization and execution-intent gate

Production must not run because of a pull request, push, merge or source Outcome Authorization.

Durable authorization is canonical Issue evidence from a source-controlled authorized actor:

```text
PRODUCTION APPROVED <exact-sha>
Authorization-Fingerprint: <current-fingerprint>
```

That two-line record is authorize-only. Normal authorize-and-execute adds the exact third line:

```text
Execution-Intent: EXECUTE
```

Before each production execution, verify all of the following before SSH or other runtime mutation:

- the input is already a lowercase full 40-character SHA; normalization is not admission;
- the source SHA is on current `main` **first-parent** history;
- the exact `quality-integration.yml` workflow has a successful completed run with event `push`, branch `main`, and the same head SHA;
- the exact source commit resolves to exactly one applicable merged PR and its Change Contract binds the requested canonical Issue;
- durable `PRODUCTION APPROVED <full-sha>` evidence from an authorized actor carries the current authorization fingerprint;
- execution intent is explicit either in the exact third Issue line or in an independently protected manual dispatch/fallback action;
- exact artifacts, release manifest and quality evidence validate;
- product outcome, runtime contours, protected boundaries, deployment method and rollback semantics still match the approved envelope;
- the rollback target is known.

`.github/workflows/deploy-runtime-request.yml` may trigger only from a newly created exact three-line canonical-Issue record. Its parser validates comment shape/actor/Issue context, then `verify_production_authorization.py --require-execution-intent` independently validates the same durable record and emits the exact required contour set. The router contains no runtime SSH/mutation logic.

GitHub/API errors, missing linkage, ambiguity or stale fingerprints fail closed. The protected `production` environment remains an additional gate, not a replacement for durable authorization.

## VPS gate

When VPS deployment is required, `.github/workflows/deploy-vps.yml` remains the single protected implementation and retains `environment: production`. It supports `workflow_call` from the two-intent runtime router and legacy VPS request path, plus `workflow_dispatch` as an emergency/operator fallback.

Legacy `DEPLOY VPS <exact-sha>` remains a compatible execution request after separate durable authorization, but new normal delivery should use the combined production authorization plus `Execution-Intent: EXECUTE` record to avoid a third user decision.

Verify the called workflow ran from the default/main workflow definition, deployment identity matches the exact bound first-parent main commit, health/source identity is correct, applicable frontend/storage checks pass and rollback target remains known.

## Ubuntu Worker/relay gate

When Ubuntu Worker/relay update is required, `.github/workflows/deploy-ubuntu-worker.yml` must validate exact main, push/main quality, durable authorization, exact artifacts and release manifest before resolving runtime transport.

The target mutation is owned by `deploy/worker/ubuntu/deploy-authorized.sh`. It must re-stage the exact current-main target, re-verify durable authorization and explicit execution intent, invoke the exact target updater for preparation+activation as one transaction, verify exact worker/runtime/control identities, preserve the desired worker state, write deployment-manifest evidence and restore the previously active exact release if post-activation verification fails.

When restricted Connector transport is not provisioned, the workflow may produce one exact server-pull bootstrap action and must remain non-successful until that action actually executes. Do not split the fallback into preparation, inspection and activation confirmations.

After mutation verify exact source/package/runtime identity, preservation of protected local state, valid deployment evidence, applicable service state, freshness/frame advancement when desired state is running and relay/AI telemetry semantics.

## Windows AI Worker gate

When Windows AI Worker update is required, verify exact package/install identity, preservation of local protected state, valid deployment evidence, restart, matching worker source identity, freshness and applicable telemetry. Until dedicated Connector execution exists, the Change Contract must truthfully declare a repository-owned one-command fallback rather than `MISSING`.

GitHub-hosted CI does not prove physical camera/GPU/runtime behavior.

## Mixed-contour gate

When two or three runtime contours apply, `MIXED` is only the summary classification. The exact VPS, Ubuntu Worker/relay and Windows AI Worker deployment fields must equal the exact derived contour set. Verify declared compatibility and execute the authorized rollout/rollback order. Successful completion of one contour never substitutes for a required contour that remains fallback-pending or failed.

## Media-boundary gate

The active `mvp_v1` and target `edge_v2` storage boundary remain unchanged; activating `edge_v2` remains a separate protected migration.

## Evidence review gate

After runtime verification, return exactly one product verdict: `accepted`, `regressed`, or `insufficient_evidence`. A regression requires a linked Issue and rollback decision unless the exact safe rollback was already included in the active production envelope.

## Deployment transaction gate

Before merging deployment-affecting work, inspect the full transaction rather than the latest failure only. The linked plan must cover `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`, including mutation possibility, fatal/best-effort/conditional failure disposition, state after failure, safe retry, rollback and evidence.

Production-equivalent CI should execute the real repository-owned transaction entrypoint against isolated fake external/runtime boundaries when deterministic shell/order/rollback behavior can be modeled. Source-string assertions alone are not sufficient evidence for executable transaction semantics.

After a production failure, do not issue the next retry merely because the final error line was patched. Require a concrete root cause plus adjacent-stage findings and execute deterministic fault-path tests where the repository can model the transaction without touching production. Any newly discovered source defect outside the approved scope returns to normal scope/authorization rather than being hidden in the current remediation.

## Documentation/control-plane rule

Changes limited to governance, SDD, documentation and delivery/quality tooling require aggregate PR validation and authorized merge only when their derived production impact is CONTROL_PLANE. All three runtime deployment states and production safety envelope must be `NOT REQUIRED`. A path that actually mutates a runtime contour is not converted to control-plane-only by this rule.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
