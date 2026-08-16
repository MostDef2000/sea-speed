# Sea Speed Delivery Policy

Version: 1.13.0
Status: Active

## 1. Purpose

Define quality admission, release provenance, runtime applicability, production authorization, fastest-safe operator execution and completion evidence for the three production contours: VPS, Ubuntu Worker/relay, and Windows AI Worker.

## 2. Applicability

| Changed paths | VPS | Ubuntu Worker/relay | Windows AI Worker |
|---|---:|---:|---:|
| `api/**`, `frontend/**`, `deploy/vps/**` | YES | NO unless compatibility requires | NO unless compatibility requires |
| `deploy/worker/ubuntu/**`, `worker/ubuntu_*` | NO | YES | NO |
| Windows-specific `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**` | NO | NO | YES |
| shared `worker/**` runtime source | NO | YES | YES |
| API contract plus shared worker consumer | YES | YES | YES |
| contracts/docs/specs/control tooling | NO | NO | NO |

`MIXED` means two or more contours apply; it never replaces exact contour fields. Ubuntu-only production source must not be reduced to CONTROL_PLANE by a generic `deploy/**` rule.

## 3. Source admission

New tasks use `OUTCOME APPROVED` after a canonical Outcome Contract / Implementation Scope Check. Historical legacy source/merge approvals remain audit evidence only.

PR admission requires an exact Change Contract, exact changed-file match, valid SDD linkage for significant work, required CI and unchanged protected boundaries. Merge additionally requires a fresh base/head comparison, zero unresolved review threads and expected-head protection when supported.

The merge-facing context remains `Quality integration gate / quality-integration`. PR checks validate source; they do not deploy production.

Deployment/release changes and production-learning correct-course work require the linked SDD Deployment Transaction Audit defined in section 16. A narrow source diff does not justify narrow failure analysis: after production learning, inspect neighboring transaction stages before the next production attempt.

## 4. Release identity

Every new deployable release uses `sea_speed_release_manifest_v2` and identifies canonical Issue, applicable merged PR, exact source/base commits, Outcome Contract hash, Change Contract hash, approved file set, actual Git diff, deterministic scope hash, component, exact artifacts, artifact SHA-256/size, exact-artifact evidence and quality evidence.

Approved scope and actual diff are separate facts and must match. A merge-message PR number is never a canonical Issue substitute. Persisted release/deployment v1 evidence remains readable for rollback compatibility.

Deployment manifest v1 supports explicit `vps`, `ubuntu-worker`, and `windows-worker` targets.

## 5. Production authorization

Source authorization never authorizes runtime mutation.

A runtime change requires durable exact-SHA authorization on the canonical Issue, normally:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
```

The fingerprint binds Issue, applicable merged PR, exact source SHA, Outcome Contract, exact runtime contour set, security impact, deployment target, rollout and rollback semantics. Material change makes authorization stale. Missing/ambiguous GitHub data or actor mismatch fails closed.

Before mutation prove:

- input is already a lowercase full SHA;
- source is on current `main` first-parent history;
- exact `quality-integration.yml` has a completed successful `push` run on `main` for that SHA;
- exactly one applicable merged PR binds the canonical Issue;
- durable authorization fingerprint is current;
- exact artifacts/release/quality evidence validate;
- rollback target and semantics are known.

For VPS, `.github/workflows/deploy-vps.yml` is the single protected deployment implementation. It supports reusable `workflow_call` execution and retains manual `workflow_dispatch` as an emergency/operator fallback; its deploy job retains `environment: production`, and all admission checks run before SSH.

The normal Delivery Orchestrator execution request is a Connector-written, exact one-line comment on the open canonical Issue:

```text
DEPLOY VPS <full-lowercase-40-character-sha>
```

`.github/workflows/deploy-vps-request.yml` admits only newly created comments on Issues, not pull requests, and repository-owned `scripts/release/parse_deployment_request.py` requires an actor from the production authorization policy plus the exact lowercase SHA command. The request workflow may only parse and delegate to the reusable deployment implementation; it must not contain SSH or production mutation logic.

A `DEPLOY VPS` request is execution intent, not authorization. It never substitutes for the separate durable `PRODUCTION APPROVED` evidence, fingerprint, exact-main quality/provenance checks, protected environment or rollback gate that `deploy-vps.yml` verifies again before mutation.

## 6. Mixed-contour rollout

Before a mixed runtime merge, declare compatibility, schema/migration requirements, exact contour set, rollout order, acceptance checks and rollback order. VPS, Ubuntu Worker/relay and Windows AI Worker are independent failure domains unless an approved architecture explicitly requires host-to-host orchestration.

## 7. Canonical operator execution context

Current non-secret operator targets, subject to fresh runtime verification:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

The operator establishes a target shell/SSH boundary only when a runtime contour still needs an interactive handoff. Credentials, private keys, passwords, camera secrets, TOTP and populated environment values remain local/trusted and never enter chat or Git.

For VPS, once the durable production envelope is current, the Delivery Orchestrator should normally create the canonical Issue `DEPLOY VPS <sha>` request through the connected GitHub Connector instead of asking the operator to click GitHub Actions. A human Actions click is fallback-only unless a genuine protected interaction such as an environment reviewer is configured.

## 8. Repository-owned server-pull model

The default interactive VPS/Ubuntu runtime handoff is target-local server-pull from canonical GitHub source at the exact approved SHA when technically available and safe:

```text
operator opens named target shell
-> short bootstrap selects repository + exact SHA
-> target retrieves/stages exact source
-> repository-owned entrypoint performs bounded operation
-> sanitized acceptance evidence is returned
```

Substantive deployment logic must be repository-owned before production handoff. The bootstrap is transport only; it must not embed a large deployment program, backup algorithm, configuration mutation or acceptance suite.

Repository-owned entrypoints own applicable exact-source/integrity checks, host validation, prerequisite discovery, backups/rollback preparation, mutation, restart/reload, bounded health/smoke checks, evidence and safe retry/restore logic.

If the exact approved SHA lacks a required safe operation, production stops for normal source implementation. Control-laptop `.sh`/`.ps1`/`.zip` staging is fallback-only and must preserve exact provenance/integrity.

## 9. Fastest-safe operator UX

Default budget: **one copy-paste action and one sanitized result per deployment contour or independently authorized stage whenever safe**. For VPS, a valid Connector-written Issue deployment request is preferable to any operator copy-paste or Actions click when the GitHub execution path is available.

Expose the largest safe authorized step. Do not split deterministic internal phases merely because they are separate scripts. Keep extra human checkpoints only for a genuine protected interaction: authorization, password/sudo/TOTP/IdP secret entry, host-key trust, environment reviewer, irreversible/high-risk review, or a result that cannot safely be handled by internal guards.

Known deterministic prerequisites, integrity checks, backups, restart, smoke, evidence collection and safe retry should be encoded in the repository entrypoint rather than emitted as serial operator commands. Never reduce exact-SHA binding, host validation, authorization, backup, rollback, integrity or fail-closed behavior for convenience.

## 10. VPS evidence

A VPS release is complete only when exact deployed source, successful exact `push/main` aggregate quality evidence, current durable authorization, exact release/artifact/evidence identity, applicable API/frontend checks and known rollback target are proven.

The known production FastAPI loopback origin is `127.0.0.1:8010`; public protected `/sea-speed/api/health` is an authentication-boundary check, not origin-health proof.

## 11. Ubuntu Worker/relay evidence

Ubuntu completion requires exact source/package/runtime identity, preservation of protected local state, valid deployment evidence, successful service state, matching source/runtime identity, advancing freshness/frame state and applicable relay/AI telemetry. Hosted CI does not prove NVIDIA/CUDA/physical-camera behavior.

## 12. Windows AI Worker evidence

Windows completion requires exact package/install identity, preservation of local protected state, valid deployment evidence, restart/process verification, matching source identity, freshness and applicable telemetry.

## 13. Media and security boundaries

The active media mode remains `mvp_v1`; `edge_v2` is a separate protected migration. Runtime identity fields are additive and must not redefine detection/tracking/calibration/speed/event formulas.

## 14. Completion

Merge is not release. Release is not deployment. Deployment is not acceptance. `COMPLETE` requires evidence for every applicable contour and the product verdict rules in `docs/evidence/POST_RELEASE_REVIEW.md`.

## 15. Delivery quality admission

A linked significant PR is quality-enabled only when its canonical SDD includes the current NFR, risk/test-design, correct-course, traceability and Definition-of-Done sections and the Change Contract declares the derived `Risk profile` applicability plus a quality verdict.

Full risk profiling is required for security impact, API/event/state/storage schema impact, destructive/data migration, `MIXED` runtime impact, or an explicit other high-risk trigger. Risk records use categories `TECH`, `SEC`, `PERF`, `DATA`, `BUS`, `OPS`; probability and impact are scored 1-5 and the score is their product. Test design identifies `unit`, `integration`, `end-to-end`, or `runtime-manual` evidence with priority `P0` through `P3`.

The quality verdict is advisory with respect to product confidence but machine-enforced for admission: `FAIL` blocks; `PASS` and `CONCERNS` proceed subject to all hard gates; `WAIVED` proceeds only with a complete durable waiver record. A waiver never changes runtime applicability or production authorization and never converts missing mandatory evidence into success.

## 16. Deployment transaction audit

For linked significant work, `scripts/ci/validate_sdd.py` requires a Deployment Transaction Audit when any of the following is true:

- a changed path is under `deploy/**` or `scripts/release/**`;
- a changed workflow is a deployment workflow;
- any Change Contract runtime deployment field is `REQUIRED`;
- the correct-course trigger is `PRODUCTION_LEARNING`.

The audit contains exactly one record for each stage: `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`. Every stage declares mutation possibility, failure disposition, state after failure, safe retry, rollback semantics and evidence.

A `PRODUCTION_LEARNING` additionally requires `Adjacent-stage review: COMPLETE`, a concrete root cause, and concrete adjacent-stage findings. Before proposing the next production retry, review the entire transaction around the failure rather than only the final error line. Minimal source scope remains desirable, but analysis and fault-path testing must be broad enough to expose neighboring failure modes.
