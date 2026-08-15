# Implementation Plan: Sea Speed Auth v1

- Specification: specs/004-sea-speed-auth-v1/spec.md
- Issue: #115
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Status: Accepted core runtime/security architecture; parent backlog remains open

## Architecture

```text
Internet
 -> VPS nginx/TLS
    -> public /
    -> protected /sea-speed/**
    -> auth.mostdef.ru
         -> ZeroTier/private -> Ubuntu Worker private proxy -> Authentik loopback

Ubuntu Worker
 -> Authentik server/worker + PostgreSQL
 -> Auth private proxy: exact worker private IP, exact VPS peer

Worker M2M (separate flow)
 -> exact Worker peer -> VPS private listener -> loopback FastAPI
```

Camera 1 remains physical camera -> Ubuntu private relay -> VPS H.264 compatibility origin -> protected nginx media path.

## Decisions

### D-001 - Authentik owns identity
No Sea Speed-native auth database/session.

### D-002 - Worker hosts Authentik
Production VPS resource preflight caused Issue #122 relocation; public ingress remains VPS.

### D-003 - Fail closed
Loss of private Authentik dependency never makes `/sea-speed/**` anonymous.

### D-004 - Browser and provider timers are separate
12 hours User Login Stage target vs 96 hours Proxy Provider token validity.

### D-005 - Private M2M is separate
Worker machine-to-machine traffic is exact-peer/method/path scoped and not browser Authentik.

### D-006 - Reproducible nginx boundary
Issue #140 established split-layout materialization while retaining source-controlled, SHA-guarded and fail-closed candidate rendering.

### D-007 - Runtime scope mappings
Production diagnostics proved missing managed scope mappings caused empty username headers; applying system OAuth/proxy scope blueprints and provider defaults restored trusted identity propagation.

## Affected contours

- VPS: public ingress/application release and security boundary when changed.
- Ubuntu Worker/relay: Authentik/private proxy runtime.
- Windows AI Worker: NONE for Auth v1.
- Public interfaces: `/`, protected `/sea-speed/**`, retired `/cams/**`, `auth.mostdef.ru`.

## Validation

Static renderer/blueprint/frontend tests plus exact runtime health, anonymous/forged-header smokes, authenticated browser identity/media acceptance and controlled fail-closed dependency test.

## Rollout and rollback

Production changes were separately exact-SHA authorized and bounded. Rollback is fail-closed; never restore anonymous `/cams/**` as an automatic rollback.

## Runtime feedback

Issue #122 Stage 7 acceptance is PASS and the core Auth v1 architecture above is accepted. Parent Issue #115 remains open as broader audit/backlog; this plan does not change its GitHub state.
