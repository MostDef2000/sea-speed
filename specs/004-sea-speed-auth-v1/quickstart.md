# Quickstart: Validate Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Issue: #115

This is an acceptance guide, not production authorization. Do not mutate production until an exact merged `main` SHA has a separate `PRODUCTION APPROVED` envelope.

## Source checks

```bash
python -m unittest tests.test_sea_speed_auth_v1
python -m unittest tests.test_frontend_contract
python -m unittest tests.test_camera1_direct_h264_cutover
python -m unittest tests.test_camera1_live_replacement
python scripts/ci/validate_sdd.py
python scripts/ci/validate_repo.py
```

The full PR must also pass the repository aggregate quality gate.

## Anonymous acceptance

Expected externally:

```text
GET /                                      -> 200
GET /cams                                  -> 404/410
GET /cams/                                 -> 404/410
GET /cams/hls/cam1/index.m3u8              -> 404/410
GET /sea-speed/                             -> authentication redirect/deny
GET /sea-speed/api/health                   -> authentication redirect/deny
GET /sea-speed/cameras/                     -> authentication redirect/deny
GET /sea-speed/objects/                     -> authentication redirect/deny
GET /sea-speed/media/cam1/index.m3u8        -> authentication redirect/deny
GET /outpost.goauthentik.io/...             -> Authentik outpost, no recursive auth
```

A request that supplies forged `X-authentik-username`, `X-authentik-email`, `X-authentik-groups` or related headers must not gain access or control the upstream identity.

## Identity acceptance

1. Owner creates a role-specific invitation with fixed `username=email`, `email=email`, fixed display name, `single_use=true`, and expiry no later than 24 hours.
2. Invitee follows the link and can set only the password fields supplied by the flow.
3. The invitation cannot be reused.
4. Admin/Operator/Viewer can sign in from a second device with email and password.
5. Owner password-only login is rejected; password plus valid TOTP succeeds.
6. Password recovery sends a one-time email recovery path and does not remove Owner TOTP.
7. Disabling a user and revoking sessions prevents continued Sea Speed access.

## Media acceptance

After authenticated login:

```text
/sea-speed/media/cam1/index.m3u8
```

must show advancing Camera 1 H.264 video. The private camera source, Ubuntu relay, VPS H.264 compatibility process and AI-independent live behavior must remain unchanged.

## Network acceptance

From an untrusted Internet host verify that FastAPI origin ports, MediaMTX, the Camera 1 loopback HLS origin, Authentik PostgreSQL and private relay services are not directly reachable. Public ingress remains nginx HTTPS for `mostdef.ru` and `auth.mostdef.ru`.

## Failure posture

If Authentik/outpost is unavailable, private Sea Speed may become unavailable but must not become anonymous. Do not automatically restore the retired `/cams/**` camera route.
