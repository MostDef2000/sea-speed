# Sea Speed Delivery Policy

Version: 1.21.0
Status: Active

## 1. Purpose

Define source admission, resumable source continuation, release provenance, runtime applicability, standing production authority, autonomous policy execution and completion evidence for the two active production contours: **VPS** and **Ubuntu Worker/relay**.

Windows Worker is retired. The historical name **Windows AI Worker** may still appear in immutable compatibility/audit evidence; it does not identify an active production contour. Historical Windows evidence remains readable audit history only.

## 2. Applicability

| Changed paths | VPS | Ubuntu Worker/relay |
|---|---:|---:|
| `api/**`, `frontend/**`, `deploy/vps/**` | YES | NO unless a more-specific rule applies |
| `deploy/vps/authentik/blueprints/**` | NO | YES |
| `deploy/worker/ubuntu/**`, `worker/ubuntu_*`, shared executable `worker/**` | NO | YES |
| API contract plus shared Worker consumer | YES | YES |
| contracts/docs/specs/control tooling | NO | NO |
| Windows-specific scripts/docs | NO | NO |

`MIXED` means both active contours and never replaces the exact contour flags.

## 3. Source admission and continuation

New tasks use `OUTCOME APPROVED` only after complete visible Scope immediately precedes the approval. Before first repository write require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.

After valid admission, the canonical Issue records a durable source-authorization receipt and machine-readable `Sea Speed Delivery Checkpoint v2`. The receipt is continuation evidence for the **same exact admitted scope** only. It cannot create, widen, or replace source authority and never grants production authority.

PR admission requires exact Change Contract, exact changed-file match, valid SDD for significant work, required CI and unchanged protected boundaries. Merge requires fresh base/head comparison, zero unresolved review threads and expected-head protection when supported.

After valid source approval, in-scope defects/tests/CI/metadata remediation continue automatically. Tool capability does not expand source authority.

Context compaction, session restart, response truncation, Connector truncation, or model-memory loss does not itself invalidate an admitted source scope, return a task to `DISCUSSION`, or require another `OUTCOME APPROVED`. Material scope/outcome/security/protected-boundary/destructive changes still require fresh Scope plus immediately-following approval.

## 4. Resumable delivery and Connector discipline

Truth classes are distinct:

- **Repository/product truth**: current `main`, committed source/contracts/specs and accepted runtime evidence.
- **Delivery-control truth**: canonical Issue Outcome, authorization receipt, Delivery Checkpoint, exact branch/PR/head, completed gates and evidence cursors.
- **Transient interaction state**: live conversation used for initial source-admission decisions.

A known task with a valid checkpoint resumes through a bounded **Resume Probe**: current `main`, canonical Issue checkpoint, exact referenced PR/head/status or other evidence whose cursor may have changed, then `Next admissible action`. Full project recovery is allowed only if the checkpoint is absent, task identity cannot be resolved, the checkpoint is invalid, or durable evidence materially contradicts it.

Lifecycle state is monotonic. Backward/source-reauthorization transition requires one concrete material reason such as `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`. `CONTEXT_LOSS` is not an invalidation reason.

Checkpoint updates occur at meaningful lifecycle/evidence transitions, not after every tool call.

`WAITING_EXTERNAL` is a nonterminal synchronous-session disposition. It is admissible only after all safe work executable now is exhausted and one machine-observable external condition is the sole prerequisite for continuation. The checkpoint records that condition, its resume trigger, exact evidence cursor and next action. No background execution or polling is implied.

On a later invocation the Resume Probe observes that exact cursor once. Unchanged evidence preserves the wait without repeated planning, equivalent reads or checkpoint-generation change. Changed evidence produces valid `ACTIVE` state and resumes execution. Human/protected input is `HUMAN DECISION REQUIRED`, and a concrete external blocker is `BLOCKED`; neither may be represented as `WAITING_EXTERNAL`.

Persisted v1 checkpoints remain readable for their exact admitted scopes and are upgraded by the repository validator at the next meaningful transition without source reauthorization.

Connector reads after task resolution follow:

```text
known object -> metadata -> targeted detail -> failure fragment
```

A read must advance the task, validate a mandatory gate, or resolve an explicit evidence gap. Repeating an equivalent read for the same question with the same evidence identity is forbidden unless a canonical gate explicitly requires a fresh read.

## 5. Release identity

New deployable releases use `sea_speed_release_manifest_v3`. The manifest binds Issue, merged PR, exact source/base, Outcome/Change Contract hashes, approved/actual files, scope hash, artifacts, exact-artifact/quality evidence, delegation ID, policy version/hash and policy decision ID.

Historical v1/v2 and Windows records remain readable but cannot authorize new execution.

## 6. Standing production authority and protected source

Source authorization never authorizes runtime mutation. Runtime authority comes from an independently administered standing delegation in trusted GitHub `production` environment state plus deterministic repository policy evaluation.

The trusted delegation is not a repository file, Issue field or comment. Repository policy may narrow but cannot widen it. Effective actions are the intersection of trusted permissions and repository allowed actions. Allowed standing actions are exactly `deploy` and `rollback`; IAM, secret management, environment/settings administration, branch protection and arbitrary infrastructure mutation are not delegated.

Production execution additionally requires a protected source boundary. On the GitHub Free control plane Sea Speed production source MUST remain public, `main` MUST report `protected=true`, and the required merge-facing check `quality-integration` (Quality integration gate) MUST be present. `.github/workflows/deploy-runtime-autonomous.yml`, `.github/workflows/deploy-vps.yml` and `.github/workflows/deploy-ubuntu-worker.yml` fail closed through `scripts/release/verify_source_protection.py` before production policy evaluation or transport.

Branch/ruleset administration is independently controlled and cannot be performed by the Delivery Orchestrator. The administrative target is: PR required, required checks enabled, force-push/delete disabled, no bypass that can silently skip those controls, and no mandatory per-release human reviewer.

Historical comment strings (`PRODUCTION APPROVED`, `Authorization-Fingerprint`, `Execution-Intent: EXECUTE`, `DEPLOY VPS`) have no authority effect. Hashes and decision IDs are integrity identifiers, not credentials.

## 7. Autonomous runtime routing

`.github/workflows/deploy-runtime-autonomous.yml` is the normal router. It runs only from successful `Quality integration gate` workflow-run evidence for `push` on `main`, requires the Quality SHA to remain the current main tip, verifies source protection, evaluates exact merged release metadata and routes only required VPS/Ubuntu contours when policy allows.

Each protected runtime workflow independently verifies source protection and re-evaluates standing policy with `--require-allow` before transport. Manual workflow dispatch cannot bypass source protection, Quality or standing policy.

Missing/stale/invalid delegation, private repository visibility, unprotected main or missing required status checks deny without runtime mutation.

## 8. Runtime execution capability

Every runtime-impacting Change Contract declares:

```text
VPS deployment: REQUIRED / NOT REQUIRED
Ubuntu worker/relay update: REQUIRED / NOT REQUIRED
VPS execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Ubuntu worker execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Operator actions expected: <integer>
```

After zero-touch Ubuntu transport activation, the normal Ubuntu capability is `CONNECTOR` and operator actions are `0`. Historical Change Contracts that recorded `ONE_COMMAND_FALLBACK` remain immutable evidence; transport capability may improve without changing their runtime authority.

A required contour cannot use `MISSING`/`NOT APPLICABLE`; a non-required contour must use `NOT APPLICABLE`. A transport capability never creates production authority.

## 9. Canonical production targets and transport

Non-secret targets, subject to runtime verification:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu operator target: seaspeedadmin@10.123.239.102:22
Ubuntu automated deploy target: sea-speed-deploy@10.123.239.102:22
Worker transport: ZeroTier
Automated worker route: GitHub-hosted runner -> VPS SSH ProxyJump -> ZeroTier -> Ubuntu Worker
```

The VPS is a transport bridge for Ubuntu zero-touch delivery and does not become Ubuntu production authority.

Credentials, private keys, passwords, TOTP and populated environment values remain trusted/local and never enter repository/chat evidence.

## 10. Restricted Ubuntu zero-touch boundary

The Ubuntu production deploy key is dedicated to one account, `sea-speed-deploy`. Its `authorized_keys` entry MUST use OpenSSH `restrict` plus a forced command pointing to root-owned `/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate`.

The gate accepts exactly:

```text
sea-speed-ubuntu-deploy-v1 <40-char-sha> <canonical-issue> <artifact-sha256>
```

The unprivileged entrypoint validates syntax and may invoke only the same root-owned gate through one narrowly-scoped `sudo -n` rule. Root mode re-fetches public `main`, requires the target on current main first-parent history, checks out exact source, recomputes the deterministic Ubuntu exact-artifact digest, requires digest equality, and then invokes `deploy/worker/ubuntu/deploy-authorized.sh`. Successful stdout is only the validated runtime deployment manifest; diagnostic output goes to stderr.

The key MUST NOT provide a general shell, PTY, forwarding, agent forwarding, arbitrary sudo or public Internet exposure of the Worker.

## 11. Repository-owned server-pull model

VPS and Ubuntu target transactions may fetch exact public repository source after protected workflow admission. Public source bytes are not authority; the protected source state, exact Quality, standing policy decision and restricted runtime credential are the security boundary.

Substantive deployment logic must remain in repository-owned target entrypoints rather than ad-hoc operator commands.

## 12. Interaction budget

Normal successful task after zero-touch activation:

```text
OUTCOME APPROVED: 1
per-release production approval: 0
standing delegation administration: rare protected settings action, not per release
manual runtime command: 0
Operator actions expected: 0
intermediate deterministic confirmations: 0
```

One-time bootstrap of branch protection, environment secret material and the dedicated Worker forced-command boundary is independent administration, not a recurring release step.

## 13. VPS execution and evidence

`.github/workflows/deploy-vps.yml` remains the single protected VPS implementation. It verifies public protected main, exact main/Quality, standing policy, artifacts/release provenance and rollback before SSH. VPS completion requires exact deployed source, health/smoke/product/security evidence and known rollback target.

## 14. Ubuntu Worker/relay execution and evidence

`.github/workflows/deploy-ubuntu-worker.yml` remains the protected reusable Ubuntu orchestrator. It verifies protected source, exact main/Quality/policy/artifacts, configures strict host-key VPS ProxyJump transport and sends only the restricted three-argument deployment request.

`deploy/worker/ubuntu/deploy-authorized.sh` owns target mutation, verification, evidence and rollback. Ubuntu completion requires exact source/runtime identity, protected-local-state preservation, deployment evidence, service state and applicable freshness/frame/AI/relay evidence. Hosted CI alone does not prove physical runtime.

## 15. Execution audit

A successful protected runtime execution produces `sea_speed_production_execution_audit_v1` binding policy decision/delegation/policy identity, exact source/Issue/PR, target, runtime-verified deployment manifest and evidence hashes. The audit records execution; it does not create authority.

## 16. Retired Windows and media/security boundaries

Windows has no active runtime gate. Historical Windows manifests remain readable. Active media mode remains `mvp_v1`; `edge_v2` is a separate protected migration. Runtime authority changes do not alter detection/tracking/calibration/speed/event formulas.

## 17. Completion and session disposition

Merge is not release. Release is not deployment. Deployment is not acceptance.

Return control only as nonterminal `WAITING_EXTERNAL`, or as terminal `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`. `FAILED` is not a terminal interaction state; it is an internal observation that must be remediated or classified at the actual boundary. `BLOCKED` requires a concrete external blocker, evidence, unblock condition and next admissible action. Progress is not terminal while a safe authorized next action is executable now. If progress depends only on an external pending transition, persist `WAITING_EXTERNAL` instead of polling or replanning.

## 18. Delivery quality admission

Significant work requires NFR assessment, risk/test design, correct-course check, traceability and Definition of Done. Full risk profile is required for security/schema/destructive/migration/MIXED/other high-risk triggers. `FAIL` blocks. A waiver never bypasses a hard gate: source authorization, exact scope, protected source, secrets, required CI, standing production policy, rollback and runtime acceptance remain mandatory.

## 19. Deployment transaction audit

Linked significant work requires the eight-stage Deployment Transaction Audit when `deploy/**`, `scripts/release/**`, deployment workflows, runtime deployment requirements, or `PRODUCTION_LEARNING` apply. Stages are exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`.

## 20. Tool Routing Allowlist

Sea Speed is DENY BY DEFAULT.

| Task class | Allowed primary route | Allowed fallback |
|---|---|---|
| Repository/Issue/PR/comment/branch/source/merge lifecycle | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts | GitHub Connector | One bounded read-only GitHub API/PowerShell operator command when exact endpoint unavailable |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout for preparation/validation only |
| Public Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only curl/PowerShell operator command |
| External technical documentation | Read-only web, primary/official sources | NONE |
| User-provided logs/screenshots/config/files | Direct read |
| Standing delegation administration | Independently controlled GitHub `production` environment settings by human administrator | NONE |
| Branch/ruleset administration | Independently controlled GitHub repository settings by human administrator | NONE |
| Production policy evaluation | Repository-owned evaluator in protected GitHub Actions | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Repository-owned VPS action exposed by canonical path only |
| Ubuntu deployment | GitHub Actions -> VPS ProxyJump -> restricted `sea-speed-deploy` forced command -> `deploy/worker/ubuntu/deploy-authorized.sh` | NONE after zero-touch activation |
| VPS/Ubuntu runtime diagnostics | Repository-owned tooling | One bounded read-only host command to operator |
| Password/sudo/TOTP/SSH trust/credentials/tokens | Operator-local intended prompt/secret store | NONE |

All unlisted connectors/plugins/services and ad-hoc mutation paths are forbidden implicit fallbacks.
