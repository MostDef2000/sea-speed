# Sea Speed Release Readiness Gate

Version: 1.12.0
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
- Risk profile applicability correct: YES/NO/NOT APPLICABLE
- Quality verdict: PASS/CONCERNS/WAIVED/NOT APPLICABLE
- Secrets/runtime artifacts absent: YES/NO
- Tool routing allowlist respected: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest v3 valid: YES/NO/NOT APPLICABLE
- Standing delegation required: YES/NO
- Standing delegation state: VALID/MISSING/INVALID/NOT APPLICABLE
- Production policy decision: ALLOW/DENY/NOT APPLICABLE
- Policy decision ID bound to exact release: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- VPS execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Ubuntu worker/relay update required: YES/NO
- Ubuntu execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Operator actions expected: <non-negative integer>
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Acceptance evidence plan available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Active production contours are VPS and Ubuntu Worker/relay. Required contours need `CONNECTOR` or `ONE_COMMAND_FALLBACK`; non-required contours use `NOT APPLICABLE`. Windows is retired.

## Tool routing admission

Tool capability is not self-authorizing. GitHub lifecycle uses GitHub Connector only. Runtime policy evaluation and protected deployment use repository-owned GitHub Actions. Standing delegation administration uses independently controlled GitHub `production` environment settings by a human administrator and has no agent fallback. Protected credential entry remains operator-local.

If the required route is unavailable and no exact fallback exists, return `HUMAN DECISION REQUIRED`; do not discover another service.

## Terminal interaction gate

Return control only as `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`. `FAILED` is an internal observation. PR created, CI running, merge ready, release built and deployment prepared are not terminal.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. Workflow presence does not prove branch protection.

## Delivery quality gate

Significant work includes current NFR assessment, risk/test design, correct-course, acceptance traceability and Definition of Done. Full risk profile derives from security/schema/destructive/data-migration/MIXED/other explicit high-risk triggers. Waivers never bypass hard gates.

## Release provenance gate

New runtime delivery uses `sea_speed_release_manifest_v3`, binding Issue, PR, Outcome/Change Contract hashes, exact base/source, approved/actual files, scope hash, artifacts, quality evidence, delegation ID, policy version/hash and policy decision ID. Historical v1/v2/Windows evidence remains readable audit history only.

## Standing production policy gate

Production never runs merely because of source approval, push, merge, Issue/PR/comment text or a known hash. Runtime authority is a current independently administered standing delegation intersected with repository policy.

Before transport verify:

- exact lowercase current-main first-parent SHA;
- successful exact `push/main` Quality;
- exactly one applicable merged PR and canonical Issue;
- valid current standing delegation for repository/environment/principal/mode;
- requested action present in both trusted permissions and repository allowed actions;
- delegation `policyHash` equals current repository policy hash;
- deterministic typed policy decision is `allow` and bound to exact release metadata;
- exact artifacts/release evidence and rollback target are valid.

The standing action set is `deploy`, `rollback` only. IAM/secrets/settings administration is excluded. Missing/invalid delegation is deny. Legacy per-release comment authorization is non-authoritative historical evidence.

`.github/workflows/deploy-runtime-autonomous.yml` routes only after successful main Quality. VPS/Ubuntu protected workflows independently re-evaluate policy before transport.

## VPS gate

When VPS is required, `.github/workflows/deploy-vps.yml` remains protected. Verify exact source/Quality/policy/provenance, health/source identity, applicable product/security smoke and rollback target.

## Ubuntu Worker/relay gate

When Ubuntu is required, `.github/workflows/deploy-ubuntu-worker.yml` verifies exact source/Quality/policy/artifacts before transport. `deploy/worker/ubuntu/deploy-authorized.sh` owns target mutation, verification, evidence and rollback. A one-command fallback is transport, not approval.

## Mixed-contour gate

When both active contours apply, exact VPS/Ubuntu flags remain authoritative. Completion of one contour never substitutes for the other.

## Documentation/control-plane rule

Governance, SDD, documentation and control tooling with `CONTROL_PLANE` impact require authorized source lifecycle and PR/post-merge Quality only. Runtime deployment is `NOT REQUIRED` unless the Outcome explicitly includes later settings/runtime acceptance evidence.

## Deployment transaction gate

Deployment/release-affecting significant work covers `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`, including mutation possibility, failure disposition, safe retry, rollback and evidence.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. A successful runtime execution must retain typed policy-decision, release-manifest-v3, deployment and execution-audit evidence before terminal acceptance.
