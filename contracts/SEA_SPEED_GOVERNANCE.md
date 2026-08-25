# Sea Speed Governance

Version: 1.20.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth for repository/product state.
- GitHub Issues are the canonical persistent backlog, source-authorization record, delivery-control checkpoint and task history.
- Feature specifications under `specs/**` are durable product-intent artifacts and complement Issues.
- All GitHub repository lifecycle writes use the connected GitHub Connector. Local `gh`, local GitHub authentication, `git push` and direct manual publication are not part of Sea Speed delivery.
- VPS and Worker hosts are runtime environments, not editable source stores.
- Task Intake is read-only and is for new/materially invalidated work, not the default resume path for an existing valid checkpoint.
- Before asking for `OUTCOME APPROVED`, the Delivery Orchestrator presents the complete six-field visible Scope as the last substantive assistant content; approval must be the immediately following user decision.
- Source admission is fail closed: before first repository write require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- After valid admission, persist a durable source-authorization receipt plus machine-readable `Sea Speed Delivery Checkpoint v2` in the canonical Issue.
- Maintain a structured todo list for significant, multi-step and resumed delivery as a current visible transient projection of the durable Issue checkpoint; todo never creates authority or replaces the checkpoint.
- `skills/**` additionally requires `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch from current `main`.
- Material scope expansion, destructive action, security-boundary/secret redesign, protected behavior change, incompatible schema change, data migration or behavior redesign requires fresh source authorization.
- Secrets, credentials, runtime logs, snapshots, overlays, media, model binaries, `.env` and virtual environments are never committed.
- Tool selection is fail closed and deny by default.
- The canonical OpenCode environment uses GitHub's official MCP endpoint and performs an exact Actions capability preflight; generic Connector availability does not prove status/log/rerun/dispatch capability.

## 2. Delivery Orchestrator ownership

The single active role is **Sea Speed Delivery Orchestrator**. It owns one task context across Task Intake, visible Scope, source admission, branch, implementation, integrity, PR/CI, exact-green-head merge, standing-policy runtime continuation when applicable, acceptance and terminal Issue evidence.

For an existing task, that context is durably resumable from the canonical Issue checkpoint. `contracts/branches/project-manager.md` and `docs/agents/PM_BOOTSTRAP.md` are compatibility paths. Other files under `contracts/branches/` are review lenses.

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

Initial visible-Scope adjacency is the source-authority **admission condition**. Once that valid admission is durably receipted, the authorization receipt may continue only the **same exact admitted scope** after context/session loss. The receipt cannot create, widen, or replace source authority and never grants production authority.

## 4. Resumable delivery control

Sea Speed separates three truth classes:

- **Repository/product truth**: current `main`, committed contracts/specs/source and accepted runtime evidence.
- **Delivery-control truth**: canonical Issue Outcome, source-authorization receipt, `Sea Speed Delivery Checkpoint v2`, exact branch/PR/head, completed gates and evidence cursors.
- **Transient interaction state**: live conversation used to present a new Scope and receive the immediately-following `OUTCOME APPROVED`, plus the structured todo projection used to expose current synchronous execution.

A known task with a valid checkpoint uses a bounded **Resume Probe** before any full project recovery. The probe reads current `main`, the canonical Issue checkpoint, exact referenced PR/head/status or other evidence whose cursor may have changed, and `Next admissible action`.

Full project recovery / repeated Task Intake is allowed only when no checkpoint exists, task identity cannot be resolved, the checkpoint is invalid, or durable evidence materially contradicts it. Context compaction, session restart, response truncation, Connector truncation, or model-memory loss does not by itself invalidate source authorization, return an admitted task to `DISCUSSION`, or require another `OUTCOME APPROVED`.

Lifecycle state is monotonic. Backward/source-reauthorization transitions require a recorded material reason such as `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`. `CONTEXT_LOSS` is not an invalidation reason.

Checkpoint updates are event-driven at meaningful phase/evidence transitions, not after every tool call, and include an explicit `Next admissible action`.

Connector retrieval after task resolution follows:

```text
known object -> metadata -> targeted detail -> failure fragment
```

A read is admissible only when it advances the task, validates a mandatory gate, or resolves an explicit evidence gap. Repeating an equivalent read for the same question with the same evidence identity is forbidden unless a canonical gate requires a fresh read.

### 4.1 GitHub Actions Connector control

The repository-owned `opencode.json` MUST remain secret-free and configure `https://api.githubcopilot.com/mcp/` with `{env:GH_TOKEN}` plus only the `context`, `repos`, `issues`, `pull_requests`, and `actions` toolsets. The deprecated `@modelcontextprotocol/server-github` package is not an admitted delivery dependency.

Capability preflight requires exact tools `actions_list`, `actions_get`, `get_job_logs`, and `actions_run_trigger`. Allowed read operations cover workflow/run/job/artifact metadata and bounded job-log retrieval. Allowed trigger methods are only `run_workflow`, `rerun_workflow_run`, and `rerun_failed_jobs`, and only when the exact operation is the durable checkpoint's next admissible action. `cancel_workflow_run` and `delete_workflow_run_logs` are destructive and require a new six-field Scope that names the method followed by fresh `OUTCOME APPROVED`.

OpenCode configuration is loaded at process startup. Missing Actions tools are a concrete capability gap, not justification for a manual web button or another API client. Repair missing source configuration inside an admitted scope when possible; if current `main` is already correct but the live process is stale, record the restart prerequisite and exact post-restart capability probe.

### 4.2 Execution todo projection

For significant, multi-step or resumed work the Orchestrator maintains a structured todo list and updates it immediately when user instructions, lifecycle state, evidence cursor, blocker, session disposition or `Next admissible action` changes. While work remains, exactly one item truthfully identifies the current lifecycle concern. `ACTIVE` identifies executable work; wait/blocker/decision items explicitly identify their non-executable prerequisite and never claim background execution. `DONE` leaves no incomplete current item.

Todo is transient interaction/presentation state. It is reconstructed from the valid Checkpoint during Resume Probe, may be replaced when the operator switches active tasks, and cannot create source authorization, production authority, completed-gate evidence or durable continuation. The canonical Issue checkpoint wins every disagreement.

Every startup status and every user-visible `WAITING_EXTERNAL`, blocker, decision or terminal result includes the current todo item, items completed since the previous visible transition, and remaining/waiting work. A meaningful checkpoint transition updates todo before the corresponding user-visible result; individual tool calls do not require todo churn.

### 4.3 Synchronous external wait

`WAITING_EXTERNAL` is a nonterminal session disposition for synchronous execution. It is legal only when no safe authorized action is executable now and progress depends solely on a named machine-observable external condition. The v2 checkpoint records the condition, resume trigger, exact evidence cursor and next admissible action. A human decision uses `HUMAN DECISION REQUIRED`; a concrete external blocker uses `BLOCKED`.

The Orchestrator performs no background polling after returning `WAITING_EXTERNAL`. On a later invocation it observes the exact referenced evidence once. An unchanged cursor preserves `WAITING_EXTERNAL` without checkpoint-generation change, repeated planning, broad recovery or another equivalent read. A changed cursor produces a new valid `ACTIVE` checkpoint and resumes automatic execution.

Persisted v1 checkpoints remain readable continuation evidence for their exact admitted scopes. `scripts/ci/validate_delivery_checkpoint.py` upgrades active v1 evidence to v2 at the next meaningful checkpoint transition without repeating source authorization.

## 5. Active runtime topology

Sea Speed has exactly two active production runtime contours:

- **VPS** — FastAPI, frontend, public nginx/TLS and VPS deployment infrastructure.
- **Ubuntu Worker/relay** — Linux analytics Worker, private relay and Ubuntu deployment/service/runtime infrastructure.

Shared executable `worker/**` belongs to Ubuntu Worker/relay unless a more-specific archival rule applies. `MIXED` means both active contours.

Windows Worker is retired. Existing Windows scripts/docs are non-production archive/local tooling. Historical Windows Issue/PR/release/deployment evidence remains immutable/readable and never creates new production authority or routing.

## 6. Runtime applicability and Change Contract

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

## 7. Standing production delegation and policy

Source authorization is not runtime authority. Every runtime execution must be allowed by standing production delegation plus exact release policy.

The effective standing delegation is independently administered GitHub `production` environment state, exposed to protected workflows as `SEA_SPEED_PRODUCTION_DELEGATION_V1`. Repository content defines constraints only. Repository policy can narrow but cannot widen trusted permissions.

The delegation binds: delegation ID, principal, repository, `production` environment, sorted unique permissions, autonomous mode, policy hash and enabled state. The active standing actions are only `deploy` and `rollback`. IAM, secret management, environment/settings administration, branch protection and arbitrary infrastructure mutation remain outside delegated authority.

GitHub Issue/PR/comment/README/repository text is not production authority. Historical `PRODUCTION APPROVED`, authorization fingerprints, execution-intent and `DEPLOY VPS` text remains audit history only. Policy hashes and decision IDs are integrity identifiers, not bearer credentials.

`.github/workflows/deploy-runtime-autonomous.yml` responds only to successful `Quality integration gate` workflow runs for `push` on `main`. It resolves exact merged Issue/PR/Change Contract identity and evaluates standing policy. Applicable VPS/Ubuntu workflows independently re-evaluate the same trusted state with `--require-allow` before runtime transport.

Missing, disabled, malformed, stale, policy-hash-mismatched, wrong-repository/environment/principal/mode, or insufficient delegation produces deny and no runtime transport.

Standing-delegation administration is a protected settings operation outside Delivery Orchestrator repository authority. It is rare, not per release. Autonomous operation requires no per-run environment reviewer gate.

## 8. Branch, integrity and merge gates

Before implementation record current `main`, branch and freshness. After writes and before PR validate complete files, syntax/structure, exact diff/scope, secret/runtime-artifact absence and SDD linkage. Before merge re-read `main`, compare exact base/head, verify required exact-head CI, zero unresolved review threads and expected-head protection when available.

Successful CI does not replace source authorization. A still-current `OUTCOME APPROVED` or its valid same-scope durable receipt is sufficient continuation/merge authority.

Mandatory fresh reads at explicit merge/release gates are not Connector-loop violations because the evidence identity is intentionally being revalidated.

## 9. Provenance and historical compatibility

New deployable provenance uses `sea_speed_release_manifest_v3`. It binds canonical Issue/PR, exact source/base commits, Outcome/Change Contract hashes, approved and actual files, scope hash, exact artifacts, quality evidence, delegation ID, policy version/hash and policy decision ID.

Successful runtime execution also produces typed execution audit binding the policy decision to runtime-verified deployment evidence.

Persisted v1/v2 release/deployment evidence, including historical Windows records and old authorization fingerprints, remains readable for audit/rollback. Readability grants no new authority.

## 10. Interaction budget and session disposition

Normal delivery after standing delegation activation uses one source authorization and zero per-release production approvals. Runtime fallback operator commands remain zero target and at most one per required active fallback contour.

Return control only as nonterminal `WAITING_EXTERNAL`, or as terminal `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`. `FAILED` is not a terminal interaction state; it is an internal event. `BLOCKED` requires a concrete external blocker, blocker evidence, unblock condition and next admissible action. A settings-administration step for standing delegation is `HUMAN DECISION REQUIRED` because the Orchestrator must not self-administer its authority. Deterministic stages cannot end an invocation while a safe next action is executable now; an exclusively external pending transition uses `WAITING_EXTERNAL` without polling.

## 11. SDD and delivery quality

Significant PRs link one active specification with NFR assessment, risk/test design, correct-course check, requirements traceability and Definition of Done.

Deployment/release changes, deployment workflow changes, runtime deployment `REQUIRED`, or `PRODUCTION_LEARNING` require a Deployment Transaction Audit covering `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, `WAIVED`; `FAIL` blocks. A waiver never bypasses a hard gate: source authorization, exact scope, secrets, required CI, standing production policy, rollback and acceptance remain mandatory.

For historical audit vocabulary, the former per-release production hard gate used text beginning `PRODUCTION APPROVED`. That string is retained here only so old evidence remains intelligible; it is not active authority.

## 12. Tool Routing Allowlist — closed admission

| Task class | Primary route | Allowed fallback |
|---|---|---|
| GitHub repository lifecycle | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts and bounded workflow rerun/dispatch | GitHub Connector Actions tools | One bounded read-only GitHub API/PowerShell operator command for read evidence when the exact Connector endpoint is unavailable; no mutation fallback |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout for preparation/validation only; never publication or production mutation |
| Public Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only `curl`/PowerShell operator command |
| External technical documentation | Read-only web against primary/official sources | NONE |
| User-provided logs/screenshots/config/files | Direct read | NONE |
| Standing delegation administration | Independently controlled GitHub `production` environment settings by human administrator | NONE; Orchestrator cannot create/change trusted delegation |
| Production policy evaluation | Repository-owned evaluator in protected GitHub Actions | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Repository-owned VPS action explicitly exposed by canonical path only |
| Ubuntu deployment | GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh` | Repository-owned sudo/root bootstrap emitted by canonical path only |
| VPS/Ubuntu runtime diagnostics | Repository-owned tooling | One bounded read-only command to operator on corresponding host |
| Password/sudo/TOTP/SSH trust/credentials/tokens | Operator-local intended prompt/secret store | NONE |

Gmail, Calendar, Drive, Notion, `gh`, local GitHub auth, assistant-side `git push`, manual GitHub web publication, ad-hoc SSH/shell exploration, direct DB mutation, cloud-console mutation and every other unlisted connector/plugin/service are forbidden implicit fallbacks.
