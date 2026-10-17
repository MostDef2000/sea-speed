# Spec: #520 — edge vhost renderer codification (PR-2)

- Issue: #520

Design + phase plan: issue comment 6217745201. This spec is the PR-2
admission of #520 — the edge half (vhost contour codification in the nginx
renderer), per design comment item 2. The app-layer half (operator identity
edge-secret enforcement at the API) already shipped as PR-1
(`specs/520-operator-edge-auth/`, merged as `0a5d755`). Rollout phases 2-3
(edge include provisioning + rendered candidate application, then API env +
deploy) are sysadmin lanes (полоса C, ИБ-этап), not repo scope; issue closure
follows runtime acceptance after those phases, so this PR leaves #520 open.

## Product outcome

The nginx renderer (`scripts/operations/nginx_sea_speed_auth.py`) codifies
only the canonical Authentik Forward Auth contour (`mostdef.ru`). The
single-vhost basic-auth browser-front reference shape (auth_basic
"Valery Manager" + `/etc/nginx/.htpasswd_3d`, no `auth_request`) and its
exact-peer worker-private listener existed only as hand-maintained VPS
config built from recorded facts, and the #520 edge-secret pair — an
operator-managed include defining `$edge_auth` plus the
`X-Sea-Speed-Edge-Auth` header injection the PR-1 API strict mode depends
on — is codified nowhere. After this change the renderer codifies BOTH
contours with the edge injection built in: mode `authentik` (default;
previous output preserved byte-wise with two additive edge lines
per `/sea-speed/**` location) and mode `basic-auth` (the canonical
single-vhost basic-auth reference contour built from recorded facts:
canonical basic-auth pair, full client `X-authentik-*` blanking, no
`auth_request`, no embedded outpost/global/fallback blocks, server-level
directives untouched). The renderer still never contains, emits or reads a
secret value: the edge include stays an operator-managed VPS file referenced
by path only.

Live-state note (2026-10-18, owner confirmation, #520 comments
6235122283/6235163257): the live `3d.mostdef.ru` vhost is a separate, active
project — basic-auth in front of a worker-host FastAPI on port 8000, with no
`/sea-speed/**` locations (FastAPI returns 404 on those paths). It is OUT of
renderer scope and MUST NOT be codified or re-rendered; during #520 phase 2
the drift was discovered and the renderer refused it by design
(inject-never-create, fail-closed), which was correct. The `basic-auth`
renderer mode is a generic capability; the golden pins the canonical
reference shape built from recorded facts, not a live-vhost claim.

## User scenarios

- Cutover operator, authentik contour: `render`/`verify` invocations without
  new flags keep producing the #140/#115 contour; every `/sea-speed/**`
  location additionally carries `include /etc/nginx/snippets/sea-speed-edge-auth.conf;`
  and `proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;` inside the
  renderer-managed marker block. Existing suites stay green unmodified.
- Cutover operator, basic-auth contour: `--mode basic-auth` renders the
  canonical single-vhost basic-auth reference shape (built from recorded
  facts) — canonical `auth_basic "Valery Manager";` +
  `auth_basic_user_file /etc/nginx/.htpasswd_3d;` in every `/sea-speed/**`
  location, client `X-authentik-*` blanked to `""`, the same edge injection,
  no `auth_request` machinery, HSTS and other server-level directives and
  sibling servers untouched; the worker-private listener stays parameterized
  (listen/peer/API origin derived from the `/sea-speed/api/` proxy_pass).
- Re-cutover/materialize: include directives inside renderer-managed marker
  spans — including the operator edge-secret include — are never expanded or
  read, so re-running the cutover cannot flatten the secret into a candidate.
- API strict mode (after phases 2-3): nginx injects `X-Sea-Speed-Edge-Auth`
  on every `/sea-speed/**` location in both contours and basic-auth clients
  cannot spoof `X-authentik-*`; the PR-1 API accepts operator identity only
  with the matching secret.

## Scope

In scope (PR-2 renderer admission):

- `scripts/operations/nginx_sea_speed_auth.py`: renderer modes
  (`authentik` default / `basic-auth`), basic-auth location snippet with
  client identity stripping, shared edge injection lines (include +
  `proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;`), server-scoped
  marker stripping for the basic-auth flow, edge include path validation,
  materialize marker-span guard, CLI `--mode` / `--edge-auth-include`.
- `tests/test_sea_speed_edge_vhost_renderer.py`: goldens for both modes,
  edge-injection pins, fail matrix, secret-absence pins, materialize guard,
  CLI test, recorded-live-facts worker-private pin.
- `docs/operations/SEA_SPEED_AUTH_V1.md`: issue #520 section (edge
  injection, client identity stripping, phase-2 ordering).
- `deploy/vps/README.md`: edge-secret pair provisioning note (include file
  provisioned BEFORE any rendered candidate is applied; nginx fails closed
  when the include is missing).
- `scripts/ci/validate_sdd.py`: the `"520"` entry in
  `GRANDFATHERED_PREFIX_COLLISIONS` grandfathers the staged PR-1/PR-2 spec
  dirs sharing the #520 issue prefix (orchestrator-owned change, mirrors the
  396/397 staged-wave precedent).
- `specs/520-edge-vhost-renderer/{spec,plan,tasks}.md`: this trio.

Out of scope: basic-auth → Authentik forward-auth migration (owner model
decision); applying any rendered config to the VPS (phase-2 sysadmin
transaction, полоса C, ИБ-этап); phase-3 API env + deploy (PR-1 scope);
api/**, worker/**, frontend/** code; Authentik blueprints; secrets or secret
values anywhere in the repo; changing any pinned directive of the authentik
contour; worker contour code beyond the already-parameterized worker-private
block shape.

## Requirements

- R-1: basic-auth mode renders the canonical single-vhost basic-auth
  reference contour (built from recorded facts; not a claim about any live
  vhost): every
  `/sea-speed/**` location gets the canonical `auth_basic "Valery Manager";`
  + `auth_basic_user_file /etc/nginx/.htpasswd_3d;` pair inside a
  renderer-managed marker block, plus the edge injection; no `auth_request`,
  no global/outpost/fallback/cams blocks; server-level directives and other
  servers in the same source file are untouched; rendering is idempotent.
- R-2: authentik mode (default) is byte-compatible with the previous
  renderer except the two additive edge lines per `/sea-speed/**` location;
  all previously pinned directives (global block, www redirect, outpost
  proxy, fallback block, per-location auth_request + `X-authentik-*`
  forwarding, cams retirement) are retained.
- R-3: `verify()` is mode-aware: both modes require the edge include and
  edge header in every Sea Speed location; basic-auth mode additionally
  requires the canonical pair and all six blank strips and forbids
  `auth_request`; mode mixing is rejected; a prefixed
  `/sea-speed/outpost.goauthentik.io` location is rejected in both modes.
- R-4: the worker-private ingress block is codified for both contours and
  pinned to the recorded live facts (listen `10.123.239.101:18080`, exact
  peer allow `10.123.239.102`, deny all, `limit_except` per endpoint,
  `Authorization` passthrough, loopback API origin derived parametrically
  from the `/sea-speed/api/` proxy_pass); browser worker-control endpoints
  are never exposed on private worker ingress.
- R-5: the edge include path is a validated renderer parameter
  (`--edge-auth-include`, absolute, no traversal, no shell/nginx
  metacharacters); renderer source and output never contain a secret value,
  a `set $edge_auth` literal or any `set $` assignment.
- R-6: snippet materialization never expands or reads include directives
  inside renderer-managed marker spans, so the operator edge-secret include
  cannot be flattened into a candidate or artifact.
- R-7: CLI parity — `render`, `verify` gain `--mode` and
  `--edge-auth-include` with backward-compatible defaults; all pre-existing
  CLI invocations (including the #115 cutover script) keep working
  unchanged.
- R-8: repository documentation states the edge pair (env
  `SEA_SPEED_EDGE_AUTH_SECRET` + nginx include), the provisioning order
  (include before candidate; nginx fails closed on a missing include) and
  the phase-2-before-phase-3 rollout order with полоса C/ИБ-этап routing.

## Acceptance criteria

- AC-001: basic-auth mode golden — `render(mode="basic-auth")` over the recorded basic-auth reference source shape produces the pinned byte-exact config (canonical pair + edge injection + six blank `X-authentik-*` strips per location, worker-private block per recorded live facts), is idempotent, and leaves server-level directives (HSTS) and sibling servers' renderer blocks untouched. The golden pins the canonical reference contour built from recorded facts; the live `3d.mostdef.ru` vhost is a separate, active project, out of renderer scope (drift discovered during #520 phase 2, fail-closed refusal was correct).
- AC-002: authentik golden — default-mode render produces the pinned byte-exact config with the two additive edge lines inside each `/sea-speed/**` marker block; the camera1 direct-h264 cutover suite passes unmodified.
- AC-003: verify fail matrix — verify rejects, in both modes, a missing edge include and a missing edge header per Sea Speed location; in basic-auth mode additionally a missing blank strip, a missing/drifted basic-auth pair and any `auth_request` usage; `verify` rejects cross-mode configs (basic-auth config verified as authentik and vice versa).
- AC-004: worker-private pin — the rendered block matches the recorded live facts (listen/peer/loopback origin), exposes only the pinned endpoint list with per-endpoint `limit_except`, never exposes browser worker-control endpoints, and is verifiable in both modes.
- AC-005: edge-secret discipline — the include path is a validated parameter (custom path renders and verifies; relative or space-bearing paths fail), renderer source and goldens contain no secret literal, no `set $edge_auth` and no `set $` assignment, and materialize over a tree containing a planted edge-secret snippet returns the config unchanged without reading the snippet.
- AC-006: delivery hygiene — docs runbook gains the #520 edge-injection/stripping/phase-ordering section, deploy/vps/README.md gains the provisioning note, the CLI round-trip passes for both modes, existing regression suites (camera1 cutover, line-crossing endpoint pin) stay green, and the PR Change Contract matches the exact eight-file set with no issue-closing reference and no on-box action in repo scope.
- AC-007: runtime-manual acceptance — after the phase-2 sysadmin transaction provisions the edge include and applies the rendered candidates on the VPS: `nginx -t` passes; browser basic-auth flow through `3d.mostdef.ru` works; authentik flow through `mostdef.ru` works; the API receives `X-Sea-Speed-Edge-Auth` on Sea Speed routes; a forged client `X-authentik-*` header is blanked at the edge; the worker-private listener behavior is unchanged. Evidence on #520 via the sysadmin session.

## NFR assessment

- NFR-001 | Area: security | Target: every `/sea-speed/**` location in both modes injects the edge header (include + `proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;`) and basic-auth mode blanks the full client `X-authentik-*` set with no `auth_request`; `verify()` rejects any candidate missing these protections; renderer source and output never contain, read or emit a secret value | Validation: golden byte-configs both modes; fail-matrix tests (missing include/header/strip/pair, auth_request forbidden, mode mixing); secret-absence pins | Evidence: tests/test_sea_speed_edge_vhost_renderer.py | Status: PASS
- NFR-002 | Area: compatibility | Target: authentik mode (default) output stays byte-identical to the pre-change renderer apart from the two additive edge lines inside renderer-managed marker blocks; CLI defaults preserve every pre-existing invocation including the #115 cutover script | Validation: authentik golden test; camera1 direct-h264 cutover suite unmodified and green; CLI round-trip test with explicit defaults | Evidence: tests/test_camera1_direct_h264_cutover.py; tests/test_sea_speed_edge_vhost_renderer.py::test_authentik_golden_byte_config, ::test_cli_render_and_verify_both_modes | Status: PASS
- NFR-003 | Area: maintainability | Target: one shared edge-injection line pair and one mode selector serve both contours (no duplicated directive sets); marker stripping in basic-auth mode is scoped to the target host server so the split nginx layout cannot lose sibling contours | Validation: golden byte-configs for both modes from one renderer; server-scoped strip test with a mostdef.ru contour in the same source file | Evidence: tests/test_sea_speed_edge_vhost_renderer.py::test_basic_auth_render_leaves_server_level_directives_and_other_servers_untouched | Status: PASS
- NFR-004 | Area: operations | Target: the phase-2 provisioning hazard (rendered include referencing a not-yet-provisioned secret file) fails closed at `nginx -t`/reload instead of silently dropping the edge header, and the provisioning order + rollback are documented | Validation: docs runbook #520 section + deploy/vps/README.md note + plan.md deployment transaction audit | Evidence: docs/operations/SEA_SPEED_AUTH_V1.md; deploy/vps/README.md; specs/520-edge-vhost-renderer/plan.md | Status: PASS

## Runtime feedback

- The rendered config references the operator-managed edge include
  (`/etc/nginx/snippets/sea-speed-edge-auth.conf` by default); nginx fails
  closed (`nginx -t` and reload) when the file is missing, so a missing
  secret can never silently drop the edge header. The include must be
  provisioned (root-owned, mode 0600, outside the repo) BEFORE the rendered
  candidate is applied — phase 2 (edge) before phase 3 (API env + deploy),
  per the #520 rollout order; setting the API secret first fails browser
  operator routes closed (403) until the order is corrected.
- Any application of the basic-auth reference-shape render is done through
  the sysadmin lane (полоса C, ИБ-этап), not the normal code deploy; the
  live `3d.mostdef.ru` vhost is a separate, active project, out of renderer
  scope, and is never a render target (see the live-state note under Product
  outcome). Rollback on
  the VPS: restore the pre-transaction vhost backup and reload (plan.md
  TX-008); the repo rollback target is reverting this PR's commit.
- The renderer never learns the secret value; rotating the secret is an
  on-box include-file edit plus the matching API env change — no re-render
  and no repo change.
