# Sea Speed Auth v1 operations

Original Issue: #115  
Runtime topology revision: #122  
Split nginx cutover remediation: #140  
Browser auth routing remediation: #146  
Session retention revision: #231

Sea Speed Auth v1 replaces the legacy browser Basic Auth/public camera contour with self-hosted Authentik Forward Auth. Issue #122 relocated Authentik and PostgreSQL from the undersized public VPS to the commissioned Ubuntu worker. Issue #140 makes the final cutover compatible with the production `mostdef.ru` split nginx layout. Issue #146 corrects the canonical-host and Forward Auth callback routing discovered during authenticated browser acceptance. Issue #231 extends the managed Sea Speed browser session to 30 days without changing roles, Owner TOTP, Forward Auth routing or analytics behavior. Runtime execution follows the current standing-production-delegation policy; this runbook does not itself grant runtime authority.

## Final browser boundary

```text
https://mostdef.ru/                         public
https://www.mostdef.ru/**                   308 -> https://mostdef.ru/**
https://mostdef.ru/cams                     404/410
https://mostdef.ru/cams/**                  404/410
https://mostdef.ru/sea-speed/**             Authentik required
https://mostdef.ru/outpost.goauthentik.io/** Authentik outpost, no recursive auth
https://auth.mostdef.ru/                    Authentik login/admin via VPS HTTPS
```

Camera 1 browser playback remains:

```text
https://mostdef.ru/sea-speed/media/cam1/index.m3u8
```

The camera source, Ubuntu relay, Ubuntu Worker H.264 transcode publishing `cam1-h264`, VPS MediaMTX sourcing `cam1-h264` and serving HLS at `127.0.0.1:18889/cam1/`, and AI-independent live behavior do not change. Issue #335 relocates the transcode from the VPS to the Ubuntu Worker but preserves the authenticated browser path and the `cam1-h264` reader-auth boundary (VPS read + Ubuntu publish).

## Identity runtime topology

```text
Internet
  -> VPS 82.146.37.153 nginx/TLS
       -> auth.mostdef.ru
       -> /outpost.goauthentik.io/**
       -> auth_request for /sea-speed/**
            |
            | ZeroTier/private HTTP
            v
       Ubuntu worker sea-speed-worker
            -> source-restricted private proxy
                 -> 127.0.0.1:9000
                      -> Authentik server

Ubuntu worker Docker Compose:
  PostgreSQL 16       -> no host port
  Authentik server    -> host publish 127.0.0.1:9000 only
  Authentik worker    -> no Docker socket mount
```

The worker private Authentik proxy binds one literal private/ZeroTier IPv4 and accepts only the exact VPS private peer. Public browser access to Authentik remains through VPS HTTPS only. The original `deploy/vps/authentik/**` Compose placement is superseded for production; the blueprint remains the canonical identity-policy source copied into the worker runtime.

The worker stage helper remains:

```bash
sudo deploy/worker/ubuntu/authentik/stage.sh stage \
  --bind-ip <worker-zerotier-ip> \
  --vps-peer <vps-zerotier-ip> \
  --env-file <protected-runtime-env-file>
```

Secrets stay in the protected worker env file. Successful staging exposes a non-secret `AUTHENTIK_PRIVATE_ORIGIN=http://<worker-private-ip>:19000`; never record the env contents.

## Current proven identity checkpoint

Before Issue #140 final cutover work, the following integration contour has already been proven:

- Authentik `2026.5.6` and PostgreSQL are healthy on `sea-speed-worker`;
- Authentik Docker HTTP is worker-loopback-only and the VPS reaches it through the source-restricted private path;
- `https://auth.mostdef.ru` is healthy through VPS TLS;
- Owner login requires TOTP and succeeds with valid TOTP;
- Sea Speed provider/application/policy/outpost are attached for Forward Auth;
- Viewer single-use invitation enrollment and password-only login work;
- disabling the Viewer and revoking sessions stops the active session;
- SMTP test delivery works and a real invitation email is delivered.

Password-recovery deep acceptance is deferred/non-blocking by current operator decision and may be verified later if required. Do not reinterpret that deferral as removal of the product requirement.

### Session/token timing

The canonical Authentik User Login Stage browser session is **30 days** for both `sea-speed-authentication-login` and `sea-speed-enrollment-login`. `remember_me_offset` and `remember_device` remain `seconds=0`, so no separate remember-me/device extension is introduced. The Sea Speed Proxy Provider access-token validity remains intentionally **96 hours**. These are separate timers; the provider token setting does not redefine the browser login-stage session contract.

## Issue #231 - bounded 30-day session reconciliation

Production Authentik runs on the Ubuntu Worker, while the canonical identity blueprint remains `deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml`. Change-control therefore classifies this specific blueprint subtree as `UBUNTU_WORKER` before the generic `deploy/vps/**` rule.

The canonical Ubuntu target transaction detects an Authentik-blueprint-only exact merge diff and runs:

```text
deploy/worker/ubuntu/authentik/reconcile-blueprint.sh
```

The reconcile transaction is deliberately narrower than a full Authentik stage/restage:

- it requires the exact source blueprint to contain exactly two `session_duration: days=30` values;
- it preserves Owner TOTP, role and password-policy markers;
- it writes through the existing mounted blueprint path at `/opt/sea-speed-auth/blueprints/sea-speed-auth-v1.yaml`;
- it does not run `docker compose pull`, restart PostgreSQL, restart Authentik containers, or touch Water/Road services;
- the already-running Authentik worker observes the blueprint file modification and applies the managed instance;
- acceptance queries the Authentik worker ORM for exactly `sea-speed-authentication-login` and `sea-speed-enrollment-login`, requiring `days=30`, `seconds=0`, `seconds=0` for duration/remember-me/remember-device;
- if the expected runtime values do not appear, the previous blueprint bytes are restored and the previous two-stage runtime values must be observed again before the transaction reports a bounded rollback.

The protected GitHub Actions Ubuntu workflow evaluates standing production delegation with `--require-allow` before runtime transport. The target transaction does not consume the retired per-release authorization verifier. If restricted zero-touch Ubuntu SSH is unavailable, the workflow emits the exact one-command fallback only after policy allow; that operator-local root/sudo execution is transport, not a new production-approval step.

## Issue #146 - Canonical host and Forward Auth callback routing

Authenticated browser acceptance after the first nginx activation proved two routing defects that are corrected by Issue #146:

1. `www.mostdef.ru` must not enter Forward Auth as a separate application host. The canonical TLS server redirects `www.mostdef.ru` to `https://mostdef.ru$request_uri` with HTTP 308 before protected location handling.
2. The Authentik Proxy Provider **External host** must be the application origin only:

```text
External host: https://mostdef.ru
```

The Sea Speed Application launch URL remains path-scoped and separate:

```text
Launch URL: https://mostdef.ru/sea-speed/
```

Do not configure the Proxy Provider External host as `https://mostdef.ru/sea-speed/`. A path-bearing External host can make Authentik emit callback URLs under `/sea-speed/outpost.goauthentik.io/**`; that path is intentionally protected by `/sea-speed/**` and therefore creates recursive authentication. The only unauthenticated callback/start contour is root `/outpost.goauthentik.io/**` on canonical `mostdef.ru`.

Issue #146 does not add nginx buffer tuning: production evidence did not show `upstream sent too big header`. It also does not change the worker Authentik private origin, worker M2M listener, Camera 1 media path, or `/cams/**` retirement. Its historical production authorization record remains audit evidence only; current runtime mutations use standing production policy evaluation.

## Machine-to-machine worker contour remains separate

The Sea Speed worker must not use interactive browser authentication. The final nginx candidate creates a private-only listener on the VPS, bound to the VPS private address and restricted to the exact worker peer.

Only these methods and paths exist on that listener:

```text
POST /api/cam1/state
POST /api/cam1/events
GET  /api/cam1/roi
GET  /api/cam1/speed-config
GET  /api/cam1/speed-lines
```

No generic `/api/` proxy is created. The existing `SEA_SPEED_API_TOKEN` remains required for state/event writes and must not appear in chat, argv, Issue comments or logs.

At final cutover change only the worker runtime URLs:

```text
SEA_SPEED_API_URL=http://<vps-private-ip>:<port>/api/cam1/state
SEA_SPEED_EVENT_API_URL=http://<vps-private-ip>:<port>/api/cam1/events
SEA_SPEED_ROI_URL=http://<vps-private-ip>:<port>/api/cam1/roi
SEA_SPEED_SPEED_CONFIG_URL=http://<vps-private-ip>:<port>/api/cam1/speed-config
SEA_SPEED_SPEED_LINES_URL=http://<vps-private-ip>:<port>/api/cam1/speed-lines
```

Hosting Authentik on the same physical worker does not merge identity and M2M security contours.

## Issue #140 - production split nginx layout

The production `mostdef.ru` TLS site may keep Sea Speed locations in direct snippets such as:

```nginx
include /etc/nginx/snippets/sea-speed-api.conf;
include /etc/nginx/snippets/sea-speed-page.conf;
```

The root site does not need to contain literal `/sea-speed/**` locations before cutover. `sea-speed-auth-cutover.sh` now identifies the exact TLS `mostdef.ru` root site through the Auth renderer source check and, during candidate rendering, materializes only direct regular `/etc/nginx/snippets/sea-speed-*.conf` includes.

The materialization safety envelope is strict:

- only direct absolute `sea-speed-*.conf` files under `/etc/nginx/snippets/` are expanded;
- wildcard Sea Speed includes fail closed;
- a materialized Sea Speed snippet containing another `include` fails closed;
- symlink, missing, non-regular or out-of-root Sea Speed snippets fail closed;
- non-Sea-Speed includes, including unrelated certificate/Let’s Encrypt includes, remain literal and unchanged;
- active nginx and the original snippet files are not edited during `prepare`.

The materialized temporary source is passed to the existing Camera 1 renderer first and then the Auth v1 renderer. The resulting flattened candidate is what receives the SHA-256 review. During `activate`, materialization/rendering repeats from current source; any relevant source drift changes the SHA and blocks activation through `--expected-sha256`.

After successful activation the root `mostdef.ru` site is the flattened reviewed candidate. The old Sea Speed snippet files remain on disk but are no longer referenced by that root site. Issue #140 does not delete them.

## Preconditions for remaining production work

Before any new runtime mutation require all of the following:

1. The applicable source is merged to current `main` with exact-main Quality green.
2. The new exact full 40-character `main` SHA is identified and remains the current main tip for autonomous routing.
3. The independently administered `production` standing delegation is enabled and the repository policy evaluator returns `allow` for the exact Issue/PR/source-derived contour.
4. Current private Authentik health and public `auth.mostdef.ru` readiness remain good when the operation depends on them.
5. The applicable repository-owned transaction validates its exact target topology before mutation.
6. `SEA_SPEED_API_TOKEN` and other secrets remain available only through protected runtime channels.

No Issue comment, SDD text or per-release approval string grants production authority under the current model.

## Phase A - Prepare the exact nginx candidate

Use the current policy-allowed exact source and current private addresses. Shape:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh prepare \
  --authentik-upstream http://<worker-private-ip>:19000 \
  --worker-private-listen <vps-private-ip>:18080 \
  --worker-private-peer <worker-private-ip>
```

`prepare` must:

- prove private worker Authentik and public `auth.mostdef.ru` health;
- prove the Camera 1 local H.264 origin;
- discover the exact TLS `mostdef.ru` root site even when Sea Speed lives in direct snippets;
- materialize only approved `sea-speed-*.conf` snippets into temporary input;
- render Camera 1 under `/sea-speed/media/cam1/`;
- apply Authentik Forward Auth to every materialized `/sea-speed/**` location;
- canonicalize `www.mostdef.ru` to `https://mostdef.ru$request_uri` before Forward Auth;
- route only root `/outpost.goauthentik.io/**` to the exact private worker Authentik origin without recursive auth;
- retire `/cams/**`;
- create the exact-peer/method/path private M2M listener;
- verify Camera/Auth output;
- write only `/var/lib/sea-speed-auth-v1/candidate.nginx.conf` mode `0600` and print `CANDIDATE_SHA256`;
- print `NGINX_RELOADED=NO` and leave active nginx unchanged.

Review the candidate SHA and diff. The candidate is a flattened root-site configuration by design.

## Phase B - Prepare worker M2M URLs

Before activation, prepare the five `SEA_SPEED_*_URL` values for the private VPS listener. Keep the existing `SEA_SPEED_API_TOKEN` unchanged and private. Do not yet point the worker at browser-facing `https://mostdef.ru/sea-speed/**` URLs; those are intentionally interactive-session protected.

## Phase C - Activate the exact candidate

Use the same Authentik/M2M addresses and exact candidate digest returned by `prepare`:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh activate \
  --authentik-upstream http://<worker-private-ip>:19000 \
  --worker-private-listen <vps-private-ip>:18080 \
  --worker-private-peer <worker-private-ip> \
  --expected-sha256 <prepare-sha256>
```

Activation must:

- re-materialize/re-render and reject any SHA mismatch;
- write a root-only backup of the original root nginx site;
- install only the reviewed flattened candidate;
- run `nginx -t`;
- reload only nginx;
- never automatically restore the old public `/cams/**` contour;
- require public `/ -> 200`, `www` canonical redirect, `/cams/** -> 404/410`, anonymous `/sea-speed/** -> 302/401/403`, protected Camera 1 -> 302/401/403 and embedded root outpost ping -> 204.

For #146 remediation, the live Sea Speed Proxy Provider External host is exactly `https://mostdef.ru`; the Application launch URL remains `https://mostdef.ru/sea-speed/`.

Immediately apply any still-pending prepared worker M2M URL update and restart only the applicable Sea Speed worker service. If the worker M2M cutover is already proven, do not repeat it merely for an unrelated Authentik session change.

## Phase D - Primary integration acceptance

Anonymous Internet:

```text
/                                      -> 200
www.mostdef.ru/**                      -> 308 canonical mostdef.ru
/cams/                                 -> 404/410
/cams/hls/cam1/index.m3u8              -> 404/410
/sea-speed/                            -> Authentik redirect/deny
/sea-speed/api/health                  -> Authentik redirect/deny
/sea-speed/media/cam1/index.m3u8       -> Authentik redirect/deny
/outpost.goauthentik.io/ping           -> 204
```

Authenticated browser:

- Owner still requires TOTP;
- Viewer/Admin/Operator password login semantics remain unchanged;
- login callback stays under root `/outpost.goauthentik.io/**`, never `/sea-speed/outpost.goauthentik.io/**`;
- `/sea-speed/`, Cameras, Objects and expected API operations load;
- Camera 1 H.264 playlist/video advances through `/sea-speed/media/cam1/index.m3u8`;
- crafted client `X-authentik-*` headers do not bypass or control identity;
- a newly created Sea Speed login session is governed by the 30-day User Login Stage duration;
- explicit Logout still terminates the active session.

Worker M2M from the exact approved peer:

- GET ROI/speed-config/speed-lines works;
- Bearer-authenticated POST state/events works with the existing token;
- wrong methods, unrelated paths and unrelated peers remain denied/absent.

Direct-origin checks from an untrusted Internet host must show no direct access to FastAPI, MediaMTX, H.264 loopback server, Authentik PostgreSQL, worker Authentik loopback HTTP, worker private Authentik proxy or Ubuntu camera relay.

## Phase E - Controlled fail-closed dependency test

After normal acceptance passes, interrupt only the worker Authentik private dependency inside an explicitly applicable runtime test envelope:

1. verify `/sea-speed/**` becomes unavailable/denied and never anonymous;
2. verify public `/` remains available;
3. restore the worker Authentik private path;
4. verify authenticated Sea Speed recovers.

Do not stop camera relay or the Sea Speed worker application for this test.

## Failure and rollback posture

The safe failure posture is a closed/unavailable private Sea Speed surface, not anonymous access.

For the #231 blueprint-only transaction, failed runtime verification restores the pre-change blueprint bytes and requires the pre-change login-stage runtime values to reappear before reporting `AUTHENTIK_BLUEPRINT_ROLLBACK=PASS`. It does not restart Water/Road services or PostgreSQL.

For historical nginx/provider cutover failures:

1. stop further rollout steps and preserve sanitized evidence;
2. do not automatically restore `/cams/**`;
3. do not move Authentik back to the undersized VPS;
4. retain the root-only nginx backup path printed by activation;
5. route any requested runtime rollback through the current standing-delegation rollback policy and repository-owned rollback transaction;
6. restore matching nginx and worker M2M runtime URLs together when that historical topology rollback is actually required, then re-run the large integration checks.

Never disclose Authentik secrets, SMTP passwords, TOTP seeds/codes, invitation/recovery links, `SEA_SPEED_API_TOKEN`, camera credentials, SSH private keys, Authorization headers, OAuth callback codes, or OAuth state values in #231/#146/#140/#122/#115 evidence.
