# Sea Speed Governance

Version: 1.16.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog, source-authorization record and task history.
- Feature specifications under `specs/**` are durable product-intent artifacts and complement Issues.
- All GitHub repository lifecycle writes use the connected GitHub Connector. Local `gh`, local GitHub authentication, `git push` and direct manual publication are not part of Sea Speed delivery.
- VPS and Worker hosts are runtime environments, not editable source stores.
- Task Intake is read-only.
- Before asking for `OUTCOME APPROVED`, the Delivery Orchestrator presents the complete six-field visible Scope as the last substantive assistant content; approval must be the immediately following user decision.
- Source admission is fail closed: before first repository write require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- `skills/**` additionally requires `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch from current `main`.
- Material scope expansion, destructive action, security-boundary/secret redesign, protected behavior change, incompatible schema change, data migration or behavior redesign requires fresh source authorization.
- Secrets, credentials, runtime logs, snapshots, overlays, media, model binaries, `.env` and virtual environments are never committed.
- Tool selection is fail closed and deny by default.

## 2. Delivery Orchestrator ownership

The single active role is **Sea Speed Delivery Orchestrator**. It owns one task context across Task Intake, visible Scope, source admission, branch, implementation, integrity, PR/CI, exact-green-head merge, standing-policy runtime continuation when applicable, acceptance and terminal Issue evidence.

`contracts/branches/project-manager.md` and `docs/agents/PM_BOOTSTRAP.md` are compatibility paths. Other files under `contracts/branches/` are review lenses.

## 3. Outcome Contract and source authorization

Mandatory visible scope:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

`OUTCOME APPROVED` authorizes only the bounded reversible repository lifecycle: branch/source/SDD writes, commits, integrity verification, PR creation/repair, CI, in-scope remediation and exact-green-head merge. It never by itself grants production execution.

Ordinary implementation defects inside approved scope continue automatically. A material outcome/path/protected-boundary change requires a new Scope and fresh immediately-following approval.

## 4. Active runtime topology

Sea Speed has exactly two active production runtime contours:

- **VPS** — FastAPI, frontend, public nginx/TLS and VPS deployment infrastructure.
- **Ubuntu Worker/relay** — Linux analytics Worker, private relay and Ubuntu deployment/service/runtime infrastructure.

Shared executable `worker/**` belongs to Ubuntu Worker/relay unless a more-specific archival rule applies. `MIXED` means both active contours.

Windows Worker is retired. Existing Windows scripts/docs are non-production archive/local tooling. Historical Windows Issue/PR/release/deployment evidence remains immutable/readable and never creates new production authority or routing.

## 5. Runtime applicability and Change Contract

Canonical classification:

- `api/**`, `frontend/**`, `deploy/vps/**` -> VPS.
- `deploy/worker/ubuntu/**`, `worker/ubuntu_*`, shared executable `worker/**` -> Ubuntu Worker/relay.
- Windows `.ps1`/`.cmd`, `worker/windows/**` and helper docs -> CONTROL_PLANE/archive.
- contracts/docs/specs/control tooling -> CONTROL_PLANE or NONE as policy derives.

New Change Contracts declare:

```text
VPS deployment: REQUIRED / NOT REQUIRED
Ubuntu worker/relay update: REQUIRED / NOT REQUIRED
Production safety envelope: REQUIRED / NOT REQUIRED
VPS execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Ubuntu worker execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Operator actions expected: <count of required ONE_COMMAND_FALLBACK contours>
```

A required contour cannot be `MISSING` or `NOT APPLICABLE`; a non-applicable contour must be `NOT APPLICABLE`.

## 6. Standing production delegation and policy

Source authorization is not runtime authority. Every runtime execution must be allowed by standing production delegation plus exact release policy.

The effective standing delegation is independently administered GitHub `production` environment state, exposed to protected workflows as `SEA_SPEED_PRODUCTION_DELEGATION_V1`. Repository content defines constraints only. Repository policy can narrow but cannot widen trusted permissions.

The delegation binds: delegation ID, principal, repository, `production` environment, sorted unique permissions, autonomous mode, policy hash and enabled state. The active standing actions are only `deploy` and `rollback`. IAM, secrets, environment/settings administration, branch protection and arbitrary infrastructure mutation remain outside delegated authority.

GitHub Issue/PR/comment/README/repository text is not production authority. Historical `PRODUCTION APPROVED`, authorization fingerprints, execution-intent and `DEPLOY VPS` text remains audit history only. Policy hashes and decision IDs are integrity identifiers, not bearer credentials.

`.github/workflows/deploy-runtime-autonomous.yml` responds only to successful `Quality integration gate` workflow runs for `push` on `main`. It resolves exact merged Issue/PR/Change Contract identity and evaluates standing policy. Applicable VPS/Ubuntu workflows independently re-evaluate the same trusted state with `--require-allow` before runtime transport.

Missing, disabled, malformed, stale, policy-hash-mismatched, wrong-repository/environment/principal/mode, or insufficient delegation produces deny and no runtime transport.

Standing-delegation administration is a protected settings operation outside Delivery Orchestrator repository authority. It is rare, not per release. Autonomous operation requires no per-run environment reviewer gate.

## 7. Branch, integrity and merge gates

Before implementation record current `main`, branch and freshness. After writes and before PR validate complete files, syntax/structure, exact diff/scope, secret/runtime-artifact absence and SDD linkage. Before merge re-read `main`, compare exact base/head, verify required exact-head CI, zero unresolved review threads and expected-head protection when available.

Successful CI does not replace source authorization. A still-current `OUTCOME APPROVED` is sufficient merge authority.

## 8. Provenance and historical compatibility

New deployable provenance uses `sea_speed_release_manifest_v3`. It binds canonical Issue/PR, exact source/base commits, Outcome/Change Contract hashes, approved and actual files, scope hash, exact artifacts, quality evidence, delegation ID, policy version/hash and policy decision ID.

Successful runtime execution also produces typed execution audit binding the policy decision to runtime-verified deployment evidence.

Persisted v1/v2 release/deployment evidence, including historical Windows records and old authorization fingerprints, remains readable for audit/rollback. Readability grants no new authority.

## 9. Interaction budget and terminal states

Normal delivery after standing delegation activation uses one source authorization and zero per-release production approvals. Runtime fallback operator commands remain zero target and at most one per required active fallback contour.

Return control only as `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`. A settings-administration step for standing delegation is `HUMAN DECISION REQUIRED` because the Orchestrator must not self-administer its authority. Deterministic PR/CI/merge/release/deploy stages are never terminal while a safe next action exists.

## 10. SDD and delivery quality

Significant PRs link one active specification with NFR assessment, risk/test design, correct-course check, requirements traceability and Definition of Done.

Deployment/release changes, deployment workflow changes, runtime deployment `REQUIRED`, or `PRODUCTION_LEARNING` require a Deployment Transaction Audit covering `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, `WAIVED`; `FAIL` blocks. Waivers never bypass source authorization, exact scope, secrets, CI, standing production policy, rollback or acceptance.

## 11. Tool Routing Allowlist — closed admission

| Task class | Primary route | Allowed fallback |
|---|---|---|
| GitHub repository lifecycle | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts | GitHub Connector | One bounded read-only GitHub API/PowerShell operator command when exact Connector endpoint is unavailable |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout for preparation/validation only; never publication or production mutation |
| Public Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only `curl`/PowerShell operator command |
| External technical documentation | Read-only web against primary/official sources | NONE |
| User-provided logs/screenshots/config/files | Direct read | NONE |
| Standing delegation administration | Independently controlled GitHub `production` environment settings by human administrator | NONE; Orchestrator cannot create/change its trusted delegation |
| Production policy evaluation | Repository-owned evaluator in protected GitHub Actions | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Repository-owned VPS action explicitly exposed by canonical path only |
| Ubuntu deployment | GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh` | Repository-owned sudo/root bootstrap emitted by canonical path only |
| VPS/Ubuntu runtime diagnostics | Repository-owned diagnostic/deployment tooling | One bounded read-only command to operator on corresponding host |
| Password/sudo/TOTP/SSH trust/credentials/tokens | Operator-local intended prompt/secret store | NONE |

Gmail, Calendar, Drive, Notion, `gh`, local GitHub auth, assistant-side `git push`, manual GitHub web publication, ad-hoc SSH/shell exploration, direct DB mutation, cloud-console mutation and every other unlisted connector/plugin/service are forbidden implicit fallbacks.
