# Sea Speed Control Plane

Version: 2.0.0
Status: Active

## Overview

GitHub `main` is the source of truth. Sea Speed has three independent production runtime contours: VPS, Ubuntu Worker/relay and Windows AI Worker. The delivery control plane is repository-centric and uses one persistent orchestration context.

## Control layers

1. GitHub Issues: canonical backlog, authorization and audit history.
2. Task Intake: read-only evidence/task-shaping lens.
3. SDD: product intent, architecture, bounded tasks and runtime feedback.
4. Canonical governance/runtime contracts.
5. **Sea Speed Delivery Orchestrator**: scope lock, implementation coordination, PR/CI, merge, runtime continuation and terminal evidence.
6. Domain/release contracts: optional review lenses/checklists; no mandatory autonomous handoff.
7. GitHub Connector: repository lifecycle transport.
8. Runtime execution: operator-owned target shell / trusted UI under separate production authorization.

## Repository control flow

```text
User request
-> Delivery Orchestrator recovers main / Issue / evidence
-> optional read-only Task Intake lens
-> Outcome Contract + Implementation Scope Check
-> OUTCOME APPROVED
-> fresh branch + implementation
-> optional domain/release review lenses
-> integrity gate
-> PR Validation + Quality integration
-> expected-head merge
-> post-merge exact-main verification
-> separate production envelope when a runtime contour applies
-> runtime acceptance
-> terminal Issue evidence
```

Historical `HANDOFF_VALIDATED` / `CORE_RELEASE_INTEGRATING` states and Project Manager/Core Release agent language may appear in older audit evidence. New tasks do not emit those ownership-transfer states.

## Runtime contours

### VPS
API, frontend, public nginx/TLS and VPS deployment infrastructure when changed.

### Ubuntu Worker/relay
Ubuntu-specific worker service/deployment, private relay and Linux-hosted operations when changed.

### Windows AI Worker
Windows-specific worker packaging/scripts/runtime when changed.

### Shared Worker
Shared `worker/**` runtime source normally affects Ubuntu + Windows unless a more-specific rule applies. `MIXED` summarizes; exact flags remain authoritative.

## Remote execution boundary

The operator-owned Windows control station may establish SSH/ZeroTier transport, but transport does not grant source or production authorization. Root/sudo/password/TOTP/credential boundaries stay local to the operator/trusted UI. Repository-owned deployment logic executes target-local from exact approved source when safe.

## Compatibility and evidence

Merge is not release; release is not deployment; deployment is not acceptance. Runtime identity, rollback and product evidence are verified independently for each applicable contour. Historical decision records remain immutable; DR-004 records the active ownership convergence.
