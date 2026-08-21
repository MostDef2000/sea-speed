# Sea Speed Control Plane

Version: 2.4.0
Status: Active

## Overview

GitHub `main` is the source of truth for repository/product state. Sea Speed has exactly two active production runtime contours: VPS and Ubuntu Worker/relay. The Delivery Orchestrator owns one task context from source intake through acceptance, while production execution authority is a separately administered standing delegation.

The canonical Issue is the durable delivery-control record for an existing task: Outcome Contract, source-authorization receipt, `Sea Speed Delivery Checkpoint v1`, exact branch/PR/head identities, completed gates and evidence cursors. The live conversation is transient interaction state used for new authorization decisions; it is not the durable execution cursor.

On the GitHub Free plan the production repository remains public so branch protection, required checks and the `production` environment can form the control plane. Public source is not a secret boundary; credentials, private keys, populated environment values and runtime secrets remain outside Git.

Windows Worker is retired from production. Historical Windows evidence remains immutable/readable audit history.

## Truth classes

1. **Repository/product truth** — current `main`, committed contracts/specs/source and accepted runtime evidence.
2. **Delivery-control truth** — canonical Issue, admitted scope/authorization receipt, Delivery Checkpoint, exact branch/PR/head and evidence cursors.
3. **Transient interaction state** — current chat used to present a new Scope and receive its immediately-following `OUTCOME APPROVED`.

These layers are complementary. Delivery-control evidence can resume the same already-admitted scope but cannot create or widen source authority and never grants production authority.

## Control layers

1. GitHub Issues: canonical backlog, source authorization, task history and durable Delivery Checkpoint.
2. Task Intake and Implementation Scope Check for new/materially invalidated work.
3. SDD: product intent, architecture, bounded tasks and runtime feedback.
4. Canonical governance/runtime contracts.
5. Public GitHub `main` protected by PR and required merge-facing checks.
6. Sea Speed Delivery Orchestrator: scope lock, source implementation, PR/CI, merge, policy-driven runtime continuation and terminal evidence.
7. GitHub Connector: repository lifecycle transport with cursor-bound progressive retrieval.
8. Trusted GitHub `production` environment state: independently administered standing production delegation and runtime credentials.
9. Repository production policy: deterministic constraint/evaluation layer that can narrow but not widen trusted delegation.
10. Protected VPS/Ubuntu workflows and bounded target transactions.

## Source flow

```text
User request
-> new task: current-main recovery + Task Intake
   OR existing task: bounded Resume Probe
-> Outcome Contract + visible Scope when new/fresh authorization is required
-> OUTCOME APPROVED
-> durable authorization receipt + Delivery Checkpoint
-> fresh branch + SDD/source
-> PR + validation + aggregate Quality
-> protected exact-green merge
-> exact-main Quality
```

`OUTCOME APPROVED` remains source authority only. Initial admission requires the complete visible Scope immediately followed by that decision. Once durably receipted, the receipt may continue only the same exact scope after context/session loss. Branch/ruleset settings are independent administrative state and cannot be self-issued by repository text or the Delivery Orchestrator.

## Resume flow

```text
known canonical task
-> current main identity
-> canonical Issue Delivery Checkpoint
-> exact referenced PR/head/status evidence whose cursor may have changed
-> validate checkpoint against durable evidence
-> execute Next admissible action
```

A valid checkpoint prevents repeated Task Intake/full project recovery. Context compaction, session restart, response truncation and Connector truncation are not source-authority or phase invalidation. Full project recovery is reserved for an absent/unresolved/invalid checkpoint or material evidence contradiction.

Lifecycle state is monotonic. Material reauthorization/backward transitions require an explicit reason such as `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`.

Connector reads after task resolution follow `known object -> metadata -> targeted detail -> failure fragment`. An equivalent read for the same question at the same evidence identity is forbidden unless a mandatory gate requires a fresh read.

## Runtime flow

```text
successful Quality integration gate for push/main
-> exact current main check
-> public/protected main + required-check verification
-> exact merged Issue/PR/Change Contract resolution
-> trusted standing delegation + repository policy
-> typed allow/deny decision
-> applicable protected VPS/Ubuntu workflow
-> independent source-protection + policy re-check
-> exact artifact/release v3
-> restricted runtime transport
-> target transaction + verification
-> typed execution audit
```

Issue/PR/comment/README/repository prose is not a runtime authority input. Historical `PRODUCTION APPROVED`, authorization fingerprints, execution-intent text and `DEPLOY VPS` comments remain audit-only.

## Trust boundary

The effective delegation and deployment credentials live outside ordinary repository lifecycle writes in GitHub `production` environment state. Repository policy contains no effective authority. Policy hashes and decision IDs are integrity identifiers, not credentials.

The standing delegation grants only `deploy` and `rollback` when both trusted delegation and repository policy allow them. IAM, secrets, environment/settings administration, branch protection and arbitrary infrastructure mutation remain outside Delivery Orchestrator authority.

Changing repository visibility to private on the Free plan, removing main protection or removing required checks makes production fail closed until the independent control-plane state is restored.

## Ubuntu zero-touch transport

GitHub-hosted runners do not join the production ZeroTier network. Ubuntu production transport therefore uses the existing VPS only as an SSH jump host:

```text
GitHub-hosted runner
  -> strict-host-key SSH to VPS
  -> ProxyJump over existing ZeroTier reachability
  -> sea-speed-deploy@10.123.239.102
  -> OpenSSH restrict + forced command
  -> root-owned zero-touch gate
  -> deploy/worker/ubuntu/deploy-authorized.sh
```

The dedicated Worker key cannot request an interactive shell, PTY, port forwarding, X11 or agent forwarding. The root boundary admits only the exact zero-touch gate. The gate validates exact SHA/Issue/artifact digest, proves the SHA is on current main first-parent history, recomputes the deterministic exact Ubuntu artifact digest and then invokes the canonical target transaction.

The VPS jump credential is transport-only and does not become Ubuntu production authority.

## Runtime contours

### VPS
FastAPI, frontend, public nginx/TLS and VPS deployment infrastructure.

### Ubuntu Worker/relay
Shared Worker runtime, Ubuntu service/deployment, private relay, Linux-hosted operations and the Authentik managed blueprint.

### Mixed
`MIXED` means both active contours; exact VPS/Ubuntu flags remain authoritative.

## Evidence and compatibility

Merge is not release; release is not deployment; deployment is not acceptance. New release evidence uses `sea_speed_release_manifest_v3` and typed execution audit. Historical v1/v2 and Windows records remain readable but cannot authorize new execution.
