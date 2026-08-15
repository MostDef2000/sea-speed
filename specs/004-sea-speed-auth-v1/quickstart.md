# Quickstart: Validate Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Parent Issue: #115
- Runtime topology: #122
- Cutover split-layout remediation: #140
- Status: Accepted runtime-security reference

This guide is validation guidance, never production authorization.

## Canonical topology

```text
Internet -> VPS nginx/TLS
  / -> public
  /sea-speed/** -> forward auth -> Ubuntu Worker private Authentik origin
  auth.mostdef.ru -> same private Authentik origin
Ubuntu Worker -> Authentik loopback + PostgreSQL + exact-peer private proxy
Worker M2M -> exact Worker peer -> VPS private listener -> FastAPI
```

## Source checks

Run focused Auth/frontend/nginx tests plus `python scripts/ci/validate_sdd.py` and repository quality gates. Issue #140 remains the durable split-layout materialization/cutover remediation reference.

## Runtime checks

- production API origin health: `http://127.0.0.1:8010/api/health` on VPS;
- `/` remains public;
- `/cams/**` exposes no camera content;
- anonymous `/sea-speed/**` redirects/denies;
- forged identity headers cannot bypass;
- authenticated `/sea-speed/api/session` returns the trusted current username;
- protected Camera 1 HLS advances;
- Worker private M2M remains exact-peer/method/path scoped;
- Authentik private proxy is reachable only from approved VPS peer.

## Fail-closed reference

Issue #122 final acceptance already demonstrated a bounded outage of only `sea-speed-auth-private-proxy.service`: public `/` stayed available, protected Sea Speed failed closed including forged-header requests, the proxy recovered, and normal authentication gating returned. Repeating production failure tests requires a separate current protected authorization; historical PASS evidence is not blanket permission to rerun them.

## Secrets

Never record passwords, cookies, OAuth state/code, TOTP material, tokens, SMTP credentials, populated `.env` values or DB backup contents.
