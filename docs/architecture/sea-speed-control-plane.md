# Sea Speed Control Plane

Version: 2.1.0
Status: Active

## Overview

GitHub `main` is the source of truth. Sea Speed has two active production runtime contours: VPS and Ubuntu Worker/relay. The delivery control plane is repository-centric and uses one persistent orchestration context.

Windows Worker is retired as a production/runtime component. Existing Windows scripts/documentation are deprecated non-production local/archive tooling. Historical Windows Issue/PR/release/deployment evidence remains immutable/readable audit history.

## Control layers

1. GitHub Issues: canonical backlog, authorization and audit history.
2. Task Intake: read-only evidence/task-shaping lens.
3. SDD: product intent, architecture, bounded tasks and runtime feedback.
4. Canonical governance/runtime contracts.
5. **Sea Speed Delivery Orchestrator**: scope lock, implementation coordination, PR/CI, merge, runtime continuation and terminal evidence.
6. Domain/release contracts: optional review lenses/checklists; no mandatory autonomous handoff.
7. GitHub Connector: repository lifecycle transport.
8. Runtime execution: protected VPS/Ubuntu workflow or operator-owned target shell under separate production authorization.

## Repository control flow

```text
User request
-> Delivery Orchestrator recovers main / Issue / evidence
-> optional read-only Task Intake lens
-> Outcome Contract + visible Implementation Scope Check
-> OUTCOME APPROVED
-> fresh branch + implementation
-> optional review lenses
-> integrity gate
-> PR Validation + Quality integration
-> expected-head merge
-> post-merge exact-main verification
-> separate production envelope when an active runtime contour applies
-> runtime acceptance
-> terminal Issue evidence
```

## Runtime contours

### VPS

API, frontend, public nginx/TLS and VPS deployment infrastructure when changed.

### Ubuntu Worker/relay

Shared Worker runtime, Ubuntu-specific Worker service/deployment, private relay and Linux-hosted operations when changed.

### Mixed

`MIXED` means both VPS and Ubuntu Worker/relay apply; the exact two deployment flags remain authoritative.

### Retired Windows tooling

`worker/*.ps1`, `worker/*.cmd`, `worker/windows/**`, `worker/README.txt`, and `worker/UPDATE.md` may remain for historical/local use but do not create a production contour, packaging workflow, release, deployment action or acceptance requirement. Generic Python portability is distinct from a supported runtime target.

## Remote execution boundary

Operator-owned control stations may establish SSH/ZeroTier transport, but transport does not grant source or production authorization. Root/sudo/password/TOTP/credential boundaries stay local to the operator/trusted UI. Repository-owned deployment logic executes target-local from exact approved source when safe.

## Compatibility and evidence

Merge is not release; release is not deployment; deployment is not acceptance. Runtime identity, rollback and product evidence are verified independently for each applicable active contour.

Modern production authorization fingerprints bind VPS/Ubuntu runtime fields only. Historical immutable PRs containing legacy Windows fields retain their old fingerprint shape when read by compatibility logic. Historical Windows manifests remain readable but cannot reactivate a Windows production target.
