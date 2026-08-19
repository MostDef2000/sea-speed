# Sea Speed Control Plane

Version: 2.2.0
Status: Active

## Overview

GitHub `main` is the source of truth. Sea Speed has two active production runtime contours: VPS and Ubuntu Worker/relay. The Delivery Orchestrator owns one task context from source intake through acceptance, while production execution authority is a separately administered standing delegation.

Windows Worker is retired from production. Historical Windows evidence remains immutable/readable audit history.

## Control layers

1. GitHub Issues: canonical backlog, source authorization and task history.
2. Task Intake: read-only task shaping.
3. SDD: product intent, architecture, bounded tasks and runtime feedback.
4. Canonical governance/runtime contracts.
5. Sea Speed Delivery Orchestrator: scope lock, source implementation, PR/CI, merge, policy-driven runtime continuation and terminal evidence.
6. GitHub Connector: repository lifecycle transport.
7. Trusted GitHub `production` environment state: independently administered standing production delegation.
8. Repository production policy: deterministic constraint/evaluation layer that can narrow but not widen trusted delegation.
9. Protected VPS/Ubuntu workflows and target transactions.

## Source flow

```text
User request
-> current-main recovery
-> Outcome Contract + visible Scope
-> OUTCOME APPROVED
-> fresh branch + SDD/source
-> integrity + PR/CI
-> exact-green merge
-> exact-main Quality
```

`OUTCOME APPROVED` remains source authority only.

## Runtime flow

```text
successful Quality integration gate for push/main
-> exact merged Issue/PR/Change Contract resolution
-> trusted standing delegation + repository policy
-> typed allow/deny decision
-> applicable protected VPS/Ubuntu workflow
-> independent policy re-check before transport
-> exact artifact/release v3
-> runtime transaction + verification
-> typed execution audit
```

Issue/PR/comment/README/repository prose is not a runtime authority input. Historical `PRODUCTION APPROVED`, authorization fingerprints, execution-intent text and `DEPLOY VPS` comments remain audit-only.

## Trust boundary

The effective delegation lives outside ordinary repository lifecycle writes in GitHub `production` environment state. Repository policy contains no effective authority. Policy hashes and decision IDs are integrity identifiers, not credentials.

The standing delegation grants only `deploy` and `rollback` when both trusted delegation and repository policy allow them. IAM, secrets, environment/settings administration, branch protection and arbitrary infrastructure mutation remain outside Delivery Orchestrator authority.

Standing delegation administration is a human settings operation. Autonomous operation requires no per-run environment reviewer prompt; otherwise the environment reviewer would recreate per-release approval.

## Runtime contours

### VPS
FastAPI, frontend, public nginx/TLS and VPS deployment infrastructure.

### Ubuntu Worker/relay
Shared Worker runtime, Ubuntu service/deployment, private relay and Linux-hosted operations.

### Mixed
`MIXED` means both active contours; exact VPS/Ubuntu flags remain authoritative.

## Evidence and compatibility

Merge is not release; release is not deployment; deployment is not acceptance. New release evidence uses `sea_speed_release_manifest_v3` and typed execution audit. Historical v1/v2 and Windows records remain readable but cannot authorize or create a new Windows runtime path.
