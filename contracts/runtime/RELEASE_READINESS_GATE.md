# Sea Speed Release Readiness Gate

Version: 1.10.0
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

The active production runtime contours are **VPS** and **Ubuntu Worker/relay**. New Change Contracts contain only those deployment and execution-capability fields. `MIXED` means both active contours apply.

A required active contour with `MISSING` or `NOT APPLICABLE` fails admission. A non-required active contour must be `NOT APPLICABLE`. `Operator actions expected` equals the number of required `ONE_COMMAND_FALLBACK` contours.

For VPS, repository-owned Connector execution exists. For Ubuntu, `.github/workflows/deploy-ubuntu-worker.yml` plus `deploy/worker/ubuntu/deploy-authorized.sh` provide protected orchestration and target transaction; zero-touch is `CONNECTOR` only when the restricted transport boundary is independently provisioned, otherwise `ONE_COMMAND_FALLBACK`.

Windows Worker is retired. Windows-specific scripts/documentation are deprecated non-production tooling and do not enter this gate. Historical Windows release/deployment manifests remain readable through historical schemas/validators but cannot create a new runtime requirement.

## Terminal interaction gate

Release readiness is internal and does not create a status handoff. The Delivery Orchestrator returns control only as:

- `DONE`: the approved Outcome has all mandatory evidence.
- `BLOCKED`: a concrete external blocker prevents safe authorized continuation; state the external blocker, evidence, unblock condition and next admissible action. A remediable source/test/CI/metadata defect or queued/running CI is not a blocker.
- `HUMAN DECISION REQUIRED`: continuation requires a genuine human decision, authorization or protected input, configured environment review, or irreversible/high-risk choice. State the exact decision, bounded options/consequences when relevant and exact reply/action format. Deterministic execution resumes after the decision.

`FAILED` is an internal event, not a terminal interaction state. Remediate it automatically when possible. “PR created”, “CI is running”, merge readiness and deployment preparation are not terminal while a safe authorized next action exists.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. The static/contract domain executes `scripts/ci/validate_sdd.py` for PR events. Workflow presence does not prove branch-protection settings.

## Delivery quality gate

For significant work, linked SDD includes NFR assessment, risk/test design, correct-course, acceptance traceability and Definition of Done. Full risk profile is derived from security, schema, destructive/data migration, `MIXED` runtime, or another explicit high-risk trigger.

A quality waiver is never a hard gate bypass. No waiver bypasses source authorization, exact diff, active runtime derivation, protected-boundary reauthorization, secret checks, aggregate CI, production authorization, release provenance, rollback or runtime acceptance.

## Release provenance gate

When runtime delivery applies, new release provenance uses `sea_speed_release_manifest_v2`. Validate Issue, PR, Outcome/Change Contract hashes, exact base/source, approved versus actual files, scope hash, artifacts, SHA-256/size and quality/exact-artifact evidence.

New release creation supports `vps`, `ubuntu-worker`, `mixed`, and `governance`. It must reject `windows-worker`. Persisted historical schemas and validators may continue reading Windows records solely for audit/rollback compatibility.

## Production authorization and execution-intent gate

Production never runs because of PR, push, merge or source authorization. Durable authority is:

```text
PRODUCTION APPROVED <exact-sha>
Authorization-Fingerprint: <current-fingerprint>
```

Authorize-and-execute adds:

```text
Execution-Intent: EXECUTE
```

Before execution verify exact lowercase SHA, current-main first-parent history, exact successful `push/main` quality, one applicable merged PR/canonical Issue, current fingerprint, explicit execution intent, valid artifacts/release evidence, unchanged active runtime contours/protected boundaries/rollback semantics and known rollback target.

Modern fingerprints contain only VPS/Ubuntu contour fields. Historical immutable PR bodies containing legacy Windows fields keep their historical fingerprint shape when read by `verify_production_authorization.py`.

`.github/workflows/deploy-runtime-request.yml` routes only VPS and/or Ubuntu and contains no SSH/runtime mutation logic.

## VPS gate

When VPS deployment is required, `.github/workflows/deploy-vps.yml` remains the single protected implementation. Verify exact source/quality/authorization/provenance, health/source identity, applicable product/security smokes and rollback target.

## Ubuntu Worker/relay gate

When Ubuntu update is required, `.github/workflows/deploy-ubuntu-worker.yml` validates exact main, quality, authorization, artifacts and release evidence before transport. `deploy/worker/ubuntu/deploy-authorized.sh` owns target mutation, verification, evidence and rollback. If restricted Connector transport is unavailable, one exact server-pull bootstrap may be emitted and the workflow must not claim runtime success before it executes.

Post-mutation evidence includes exact source/runtime identity, protected-local-state preservation, applicable service state and freshness/frame/AI/relay telemetry.

## Mixed-contour gate

When both active contours apply, `MIXED` is only the summary. Exact VPS and Ubuntu fields equal the derived set, compatibility and rollout/rollback order are explicit, and completion of one contour never substitutes for the other.

## Documentation/control-plane rule

Governance, SDD, documentation and delivery/quality tooling with derived `CONTROL_PLANE` impact require authorized source lifecycle and aggregate PR/post-merge quality only. VPS and Ubuntu deployment states and the production safety envelope are `NOT REQUIRED`. No production authorization is needed.

## Deployment transaction gate

Before merging deployment/release-affecting significant work, the linked plan covers exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`. Each stage states mutation possibility, failure disposition, state after failure, safe retry, rollback and evidence. Production learning additionally records root cause and completed adjacent-stage review.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. `DONE` requires every applicable transition plus terminal Issue evidence.

Internal release-gate verdicts may be `APPROVED FOR RELEASE`, `CHANGES REQUIRED`, or `BLOCKED`; they do not replace the terminal interaction states defined above.
