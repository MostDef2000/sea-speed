# Feature Specification: Sea Speed Auth v1

- Feature: 004-sea-speed-auth-v1
- Issue: #115
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Browser-routing remediation: #146
- Authenticated header UX: #148 / #150
- Status: Core Auth v1 production boundary accepted; parent Issue #115 remains open audit/backlog

## Product outcome

`https://mostdef.ru/` remains public while `/sea-speed/**` UI/API/media is Authentik-protected and fails closed. `/cams/**` exposes no camera content. Authentik/PostgreSQL run on the Ubuntu worker; the VPS remains public nginx/TLS ingress and reaches the exact private worker Authentik origin over ZeroTier/private networking. Worker M2M remains a separate exact-peer/private VPS listener.

## User scenarios

1. Known users enroll through Owner-created single-use invitations; no public registration.
2. Admin/Operator/Viewer use password authentication; Owner additionally requires TOTP.
3. Protected UI/API/media requires authentication; failure of Authentik/private path fails closed while `/` stays public.
4. Camera 1 is available only under protected `/sea-speed/media/cam1/index.m3u8`.
5. Worker infrastructure traffic remains private M2M, not an interactive Authentik browser session.
6. Protected pages receive trusted session identity and preserve provider logout/home navigation behavior.

## Requirements

- Authentik owns identity/session/enrollment/recovery; Sea Speed does not add a native password/session store.
- public registration/access request disabled; invitation is single-use/expiring/fixed-role.
- Owner TOTP is mandatory; normal roles remain password-only in v1.
- HTTPS secure/revocable browser sessions; 12h browser-login target and 96h proxy-provider token remain distinct timers.
- `/sea-speed/**` is authenticated; `/cams/**` retired; forged `X-authentik-*` headers cannot bypass nginx.
- Authentik Docker HTTP is worker-loopback-only; PostgreSQL has no public host port; worker Authentik has no Docker-socket requirement.
- private Authentik proxy is bound to exact worker private IP and exact VPS peer.
- private Worker M2M listener is exact VPS private address / exact Worker peer / exact methods+paths and retains existing Bearer-token writes.
- production cutover/rendering is reproducible and fail-closed.
- secrets, passwords, cookies, TOTP, SMTP and tokens remain outside Git/evidence.

## Acceptance criteria

- anonymous `/` = public; anonymous protected surfaces redirect/deny; `/cams/**` exposes no camera content.
- Owner TOTP and role/invitation behavior accepted for the implemented v1 contour.
- authenticated Camera 1 H.264 playback works under the protected path.
- exact private Worker M2M remains functional and restricted.
- worker-hosted Authentik/private origin remains healthy and source restricted.
- controlled loss of `sea-speed-auth-private-proxy.service` leaves `/` available and makes protected Sea Speed fail closed; restoration returns normal authentication gating.
- trusted username rendering/browser acceptance passed after scope-mapping remediation.

## Compatibility and boundaries

Camera acquisition/relay, AI/detection/tracking/speed/calibration and Worker API token semantics are unchanged. Password-recovery deep acceptance remains a separate/deferred product item unless explicitly required by parent backlog.

## Runtime feedback

- Issue #122 is closed completed.
- Final Stage 7 fail-closed evidence on Issue #122 recorded `FAIL_CLOSED_TEST=PASS`: public `/` stayed 200, protected Sea Speed returned failure during private-auth outage, forged headers did not bypass, and normal 302 gating returned after recovery.
- Authentik system scope mappings were remediated and browser identity acceptance returned the trusted username.
- Core Auth v1 runtime/security boundary is therefore accepted. Parent Issue #115 is still open and must not be represented as closed merely because the deployed boundary passed acceptance.
