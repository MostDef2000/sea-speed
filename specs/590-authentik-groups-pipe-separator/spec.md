# Spec: #590 — X-Authentik-Groups must parse both pipe and comma separators

- Issue: #590
- Specification: specs/590-authentik-groups-pipe-separator/spec.md
- Authorization: the #590 scope (one parsing line in `api/app/identity.py`,
  the new pipe-format test pins in `tests/test_sea_speed_rbac.py` and this
  trio) admitted by the delivery orchestrator; owner authorization
  `commit approved` (2026-11-01, production incident). Base dc1e9f7
  (branch fix/590-authentik-groups-pipe-separator).

## Product outcome

Every authenticated dashboard user resolves the role the #530 model intends,
regardless of how the authentik proxy outpost joins group values into the
`X-Authentik-Groups` header. Verified production evidence (journalctl -u
caddy on lifesim, 2026-11-01): the outpost joins multiple group values into
ONE header with `|` (`"X-Authentik-Groups":["authentik Admins|Sea Speed
Owner"]`), while duplicate headers are joined with `,`. `resolve_role()` split
on commas only, so the single pipe-joined token never matched a recognized
group name and every user resolved to `viewer` — all mutation endpoints
(minimum=operator/admin) returned 403 since the #530 role gates first ran in
production (2026-10-22; zero successful `POST /api/cam1/roi`). After the fix
the header is split on both separators; every other matching semantic is
unchanged: tokens trimmed, exact case-sensitive whole-token match, unknown
tokens grant nothing, highest recognized role wins, absent/blank resolves
viewer, env lists (ADMIN_USERS/OPERATOR_USERS) remain authoritative and
checked first.

## User scenarios

- SC-1: the owner (akadmin, member of `authentik Admins` and
  `Sea Speed Owner`) opens the dashboard behind the production outpost — the
  pipe-joined header resolves `admin`, so worker control, ROI save/clear and
  every other operator/admin mutation succeed instead of 403.
- SC-2: a user whose pipe-joined groups contain only unrecognized tokens
  (e.g. `authentik Admins|garbage`) still resolves `viewer` — fail-closed is
  preserved, unknown tokens grant nothing.
- SC-3: a deployment (or proxy) that delivers duplicate headers joined with
  `,` behaves exactly as before — comma-separated tokens match as before,
  byte-for-byte.
- SC-4: a header mixing both separators resolves the highest recognized role
  across all tokens.
- SC-5: env-list users (ADMIN_USERS/OPERATOR_USERS) keep their authoritative
  resolution, checked before group matching, exactly as documented.

## Acceptance criteria

- AC-001: `resolve_role("akadmin", "authentik Admins|Sea Speed Owner")`
  returns `admin` (production pipe format; this assertion fails on base
  dc1e9f7).
- AC-002: pipe-joined groups resolve the highest recognized role across the
  pipe (`Sea Speed Operator|Sea Speed Viewer` → `operator`; this assertion
  fails on base).
- AC-003: mixed separators resolve correctly
  (`Sea Speed Admin,Sea Speed Operator|Sea Speed Viewer` → `admin`).
- AC-004: fail-closed semantics are intact: unknown pipe tokens grant
  nothing, absent/blank groups resolve `viewer`, matching stays exact
  case-sensitive whole-token, env lists stay authoritative and checked first.
- AC-005: existing comma-format behavior is unchanged (all pre-existing
  resolver tests pass untouched); full battery, ruff and validate_sdd stay
  green with the battery delta accounted.

## Requirements

- R-1: `api/app/identity.py` `resolve_role()` splits `x_authentik_groups` on
  both `|` and `,` (implemented as `.replace("|", ",").split(",")` — see
  plan.md Decisions for why not `re.split`); no other logic change.
- R-2: the `resolve_role` docstring and the constants comment block document
  both separators and why (outpost joins with `|`, duplicate headers join
  with `,`).
- R-3: `tests/test_sea_speed_rbac.py` gains production-format pins in
  `ResolverSemanticsTests` (pipe format → admin, highest-wins across pipe,
  mixed separators, fail-closed with unknown pipe tokens); no existing test
  is modified, weakened or removed.
- R-4: the SDD trio
  `specs/590-authentik-groups-pipe-separator/{spec,plan,tasks}.md` is
  created; no other files change.

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, lane-A
  deploy on the merged main SHA, then the production probe: owner-triggered
  mutations (`POST /api/worker/control/stop`, `POST /api/cam1/roi`) return
  200 in the API journal; GPU worker traffic unaffected.
- RF-002: strictly widening fix for the pipe format only — every previously
  working comma-format input behaves identically; the only behavior change is
  that pipe-joined recognized groups now grant their role instead of
  resolving viewer (which was the incident).

## NFR assessment

- NFR-001 | Area: correctness / authorization | Target: pipe-joined production group headers resolve the highest recognized role; fail-closed preserved (unknown tokens grant nothing, absent/blank → viewer, env lists authoritative) | Validation: tests/test_sea_speed_rbac.py ResolverSemanticsTests — 4 new cases, the two pipe-only-reachable ones observed failing on base dc1e9f7 | Evidence: focused pytest runs (implementer + independent peer in separate scratch worktrees) recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero behavior change for comma-format headers and env-list resolution | Validation: all pre-existing resolver tests pass untouched; peer fuzz 20,027 cases proved `replace("|", ",").split(",")` ≡ `re.split(r"[|,]", …)` token-for-token (0 mismatches) | Evidence: peer verification record in plan.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one string replace + split per request on a short header | Validation: code review; no loops or I/O added | Evidence: diff inspection | Status: PASS
