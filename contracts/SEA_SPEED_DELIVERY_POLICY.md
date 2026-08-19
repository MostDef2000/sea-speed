# Sea Speed Delivery Policy

Version: 1.18.0
Status: Active

## 1. Purpose

Define source admission, release provenance, runtime applicability, standing production authority, autonomous policy execution and completion evidence for the two active production contours: **VPS** and **Ubuntu Worker/relay**.

Windows Worker is retired. Historical Windows evidence remains readable audit history only.

## 2. Applicability

| Changed paths | VPS | Ubuntu Worker/relay |
|---|---:|---:|
| `api/**`, `frontend/**`, `deploy/vps/**` | YES | NO unless compatibility requires |
| `deploy/worker/ubuntu/**`, `worker/ubuntu_*`, shared executable `worker/**` | NO | YES |
| API contract plus shared Worker consumer | YES | YES |
| contracts/docs/specs/control tooling | NO | NO |
| Windows-specific scripts/docs | NO | NO |

`MIXED` means both active contours and never replaces the exact contour flags.

## 3. Source admission and continuation

New tasks use `OUTCOME APPROVED` only after complete visible Scope immediately precedes the approval. Before first repository write require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.

PR admission requires exact Change Contract, exact changed-file match, valid SDD for significant work, required CI and unchanged protected boundaries. Merge requires fresh base/head comparison, zero unresolved review threads and expected-head protection when supported.

After valid source approval, in-scope defects/tests/CI/metadata remediation continue automatically. Tool capability does not expand source authority.

## 4. Release identity

New deployable releases use `sea_speed_release_manifest_v3`. The manifest binds Issue, merged PR, exact source/base, Outcome/Change Contract hashes, approved/actual files, scope hash, artifacts, exact-artifact/quality evidence, delegation ID, policy version/hash and policy decision ID.

New release creation supports active components `vps`, `ubuntu-worker`, `mixed`, `governance`. Historical v1/v2 and Windows records remain readable.

## 5. Standing production authority

Source authorization never authorizes runtime mutation. Runtime authority comes from an independently administered standing delegation in trusted GitHub `production` environment state plus deterministic repository policy evaluation.

The trusted delegation is not a repository file, Issue field or comment. Repository policy may narrow but cannot widen it. Effective actions are the intersection of trusted permissions and repository allowed actions.

Allowed standing actions are exactly `deploy` and `rollback`. IAM, secret management, environment/settings administration, branch protection and arbitrary infrastructure mutation are not delegated.

Historical comment strings (`PRODUCTION APPROVED`, `Authorization-Fingerprint`, `Execution-Intent: EXECUTE`, `DEPLOY VPS`) have no authority effect for new execution. Hashes and decision IDs are not credentials.

Before runtime transport prove exact lowercase SHA, current-main first-parent ancestry, successful exact `push/main` Quality, one applicable merged PR/canonical Issue, allow policy decision from current trusted delegation/policy, exact artifacts/release evidence and known rollback.

## 6. Autonomous runtime routing

`.github/workflows/deploy-runtime-autonomous.yml` is the normal router. It runs only from successful `Quality integration gate` workflow-run evidence for `push` on `main`, evaluates exact merged release metadata and routes only required VPS/Ubuntu contours when policy allows.

Each protected runtime workflow independently re-evaluates standing policy with `--require-allow` before runtime transport. Manual workflow dispatch cannot bypass authority.

Missing/stale/invalid delegation denies without runtime mutation. Autonomous activation requires one independently administered environment-setting action after source integration; no per-run reviewer gate may recreate per-release approval.

## 7. Runtime execution capability

Every runtime-impacting Change Contract declares:

```text
VPS deployment: REQUIRED / NOT REQUIRED
Ubuntu worker/relay update: REQUIRED / NOT REQUIRED
VPS execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Ubuntu worker execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Operator actions expected: <integer>
```

A required contour cannot use `MISSING`/`NOT APPLICABLE`; a non-required contour must use `NOT APPLICABLE`. Operator actions equal required `ONE_COMMAND_FALLBACK` contours. A transport fallback is not a production approval.

## 8. Canonical operator targets and protected values

Non-secret targets, subject to runtime verification:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

Credentials, keys, passwords, TOTP and populated environment values remain local/trusted and never enter chat/Git.

## 9. Repository-owned server-pull model

The default target fallback is repository-owned server-pull of exact source followed by the canonical target entrypoint. Substantive deployment logic must not be embedded in ad-hoc operator commands.

## 10. Interaction budget

Normal successful task after standing delegation activation:

```text
OUTCOME APPROVED: 1
per-release production approval: 0
standing delegation administration: rare protected settings action, not per release
manual runtime command: 0 target, <=1 fallback per required active contour
intermediate deterministic confirmations: 0
```

Extra interaction is reserved for source reauthorization, standing-delegation/settings administration, password/sudo/TOTP/secret entry, host trust, configured environment review, irreversible/high-risk choice or evidence unavailable to safe automation.

## 11. VPS execution and evidence

`.github/workflows/deploy-vps.yml` remains the single protected VPS implementation. It verifies exact main, Quality, standing policy, artifacts/release provenance and rollback before SSH. VPS completion requires exact deployed source, health/smoke/product/security evidence and known rollback target.

## 12. Ubuntu Worker/relay execution and evidence

`.github/workflows/deploy-ubuntu-worker.yml` remains the protected reusable Ubuntu orchestrator. `deploy/worker/ubuntu/deploy-authorized.sh` owns target mutation, verification, evidence and rollback. Restricted zero-touch transport is `CONNECTOR` only when independently provisioned; otherwise one repository-owned fallback may be emitted.

Ubuntu completion requires exact source/runtime identity, protected-local-state preservation, deployment evidence, service state and applicable freshness/frame/AI/relay evidence. Hosted CI alone does not prove physical runtime.

## 13. Execution audit

A successful protected runtime execution produces `sea_speed_production_execution_audit_v1` binding policy decision/delegation/policy identity, exact source/Issue/PR, target, runtime-verified deployment manifest and evidence hashes. The audit records execution; it does not create authority.

## 14. Retired Windows and media/security boundaries

Windows has no active runtime gate. Historical Windows manifests remain readable. Active media mode remains `mvp_v1`; `edge_v2` is a separate protected migration. Runtime authority changes do not alter detection/tracking/calibration/speed/event formulas.

## 15. Completion and terminal interaction

Merge is not release. Release is not deployment. Deployment is not acceptance.

Return control only as `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`. `FAILED` is internal and must be remediated or classified at the actual boundary.

## 16. Delivery quality admission

Significant work requires NFR assessment, risk/test design, correct-course check, traceability and Definition of Done. Full risk profile is required for security/schema/destructive/migration/MIXED/other high-risk triggers. `FAIL` blocks; `WAIVED` never bypasses hard gates.

## 17. Deployment transaction audit

Linked significant work requires the eight-stage Deployment Transaction Audit when `deploy/**`, `scripts/release/**`, deployment workflows, runtime deployment requirements, or `PRODUCTION_LEARNING` apply. Stages are exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`.

## 18. Tool Routing Allowlist

Sea Speed is DENY BY DEFAULT.

| Task class | Allowed primary route | Allowed fallback |
|---|---|---|
| Repository/Issue/PR/comment/branch/source/merge lifecycle | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts | GitHub Connector | One bounded read-only GitHub API/PowerShell operator command when exact endpoint unavailable |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout for preparation/validation only |
| Public Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only curl/PowerShell operator command |
| External technical documentation | Read-only web, primary/official sources | NONE |
| User-provided logs/screenshots/config/files | Direct read | NONE |
| Standing delegation administration | Independently controlled GitHub `production` environment settings by human administrator | NONE |
| Production policy evaluation | Repository-owned evaluator in protected GitHub Actions | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Repository-owned VPS action exposed by canonical path only |
| Ubuntu deployment | GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh` | Repository-owned sudo/root bootstrap emitted by canonical path only |
| VPS/Ubuntu runtime diagnostics | Repository-owned tooling | One bounded read-only host command to operator |
| Password/sudo/TOTP/SSH trust/credentials/tokens | Operator-local intended prompt/secret store | NONE |

All unlisted connectors/plugins/services and ad-hoc mutation paths are forbidden implicit fallbacks.
