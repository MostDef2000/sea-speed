# Sea Speed Delivery Policy

Version: 1.11.0
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

For VPS, `.github/workflows/deploy-vps.yml` remains `workflow_dispatch` only and retains `environment: production`; admission checks run before SSH.

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

The operator establishes the target shell/SSH boundary. Credentials, private keys, passwords, camera secrets, TOTP and populated environment values remain local/trusted and never enter chat or Git.

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

Default budget: **one copy-paste action and one sanitized result per deployment contour or independently authorized stage whenever safe**.

Expose the largest safe authorized step. Do not split deterministic internal phases merely because they are separate scripts. Keep extra human checkpoints only for a genuine protected interaction: authorization, password/sudo/TOTP/IdP secret entry, host-key trust, irreversible/high-risk review, or a result that cannot safely be handled by internal guards.

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
