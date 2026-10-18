# Spec: #530 — server-side role authorization

- Issue: #530
- Reference checkout: 48a143a380c707d0a7b77f4ef189dfe5c3ecbb3d
- Status: IMPLEMENTED — source + tests complete, suite/validators observed green;
  commit/PR and runtime acceptance pending authorization

## Product outcome

Authenticated viewers cannot change objects, preview processes, calibration
or worker execution. Operators can review objects and operate previews.
Admins can perform all browser-facing mutations. Authorization is enforced
by the API; UI hiding is cosmetic.

Owner decision, issue #530 comment 6236142800. Paraphrase: role separation
with owner/admin, operator, and everyone-else = viewer; server-side
enforcement is the security boundary; UI hiding is cosmetic; every denial
gets a negative test; mutations log verified identity. Verbatim (owner chat,
2026-10-18): «по идее нужно разделение ролей типо владелец админ и оператор
с разными возможностями».

## User scenarios

- Viewer (default for unrecognized users): reads, media, live video and
  analytics all work as today; every browser mutation attempt — object
  edit/delete, calibration save, preview start/stop/snapshot commit, worker
  start/stop — returns 403 "Forbidden" with no side effect and a 403 in
  the UI.
- Operator: object review/edit, preview start/stop, snapshot commit work
  unchanged; object delete, all calibration saves and worker control
  return 403.
- Admin/Owner: every existing capability works unchanged; each authorized
  mutation attempt records the verified username, resolved role and a
  static action name in the API log.
- Env override: a username listed in SEA_SPEED_OPERATOR_USERS or
  SEA_SPEED_ADMIN_USERS is elevated without authentik groups; an
  operator-list entry overrides admin group membership; membership in
  both lists resolves admin.
- Groups absent/unrecognized: fail-closed viewer. A live outpost that
  emits an unexpected group format denies mutations instead of granting
  anything.
- Basic-auth contour and direct API access without verified identity:
  existing 403/503 identity failure, untouched by roles; a verified
  identity with no recognized membership resolves viewer.

## Problem statement and inventory correction

Earlier intake described "19 ungated routes" and "object PATCH (4), DELETE
(4)". The checkout contains **15 ungated** browser mutations: two PATCH, two
DELETE, three preview POST and eight calibration POST. Four additional
worker-control POST routes verify identity but do not enforce roles. Total:
19 browser mutations, not 23.

Evidence: api/app/main.py:410-447,554-601,769-922,1002-1009,1023-1075.
The frozen route inventory reconciles to 61 endpoints: 33 GET, 19 browser
mutations and nine M2M POST (tests/test_route_table.py:27-89,138).
The issue comment 6236261157 repeats the incorrect aggregate; this spec
corrects arithmetic, not the owner's capability decision.

## Decision record

The accepted capability policy is:

| Capability | Viewer | Operator | Admin / Owner |
|---|---|---|---|
| Existing reads, media and SSE | Allow | Allow | Allow |
| Preview start/stop/snapshot commit | Deny | Allow | Allow |
| Object PATCH | Deny | Allow | Allow |
| Object DELETE | Deny | Deny | Allow |
| Calibration POST | Deny | Deny | Allow |
| Worker start/stop | Deny | Deny | Allow |

"Allow" preserves existing identity, validation and resource constraints;
it does not guarantee that a resource exists or that a worker is available.

| Exact authentik group | Application role |
|---|---|
| Sea Speed Owner | admin |
| Sea Speed Admin | admin |
| Sea Speed Operator | operator |
| Sea Speed Viewer | viewer |
| No recognized membership | viewer |

Group names are defined in
deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml:10-37.
Owner's authentik superuser/TOTP distinction remains upstream; the app does
not create a fourth role or implement MFA.

## Requirements

- R-1: Verify identity before resolving or enforcing a mutation role.
  Preserve require_operator_identity's strict edge check and existing
  403/503 ordering (api/app/identity.py:99-132).
- R-2: Resolve roles by the normative precedence below; insufficient role
  raises HTTP 403 "Forbidden".
- R-3: Gate every browser mutation listed below before business operations,
  storage access with side effects, process control or outbound mutation.
- R-4: Preserve read access, M2M ingestion, route names and success payloads,
  except for the additive /api/session role field.
- R-5: Record verified identity for each authorized mutation attempt.
  Never log raw identity headers, groups, edge secrets or request payloads.
- R-6: Every denied matrix cell and identity failure branch has a negative
  test proving no mutation occurs.

## Normative role resolution

Role resolution receives the username returned by require_operator_identity,
not a raw client username.

1. If username is in SEA_SPEED_ADMIN_USERS, resolve admin.
2. Else if username is in SEA_SPEED_OPERATOR_USERS, resolve operator.
3. Else parse X-Authentik-Groups and resolve the highest recognized role:
   Owner/Admin > Operator > Viewer.
4. Otherwise resolve viewer.

Both env lists default empty. Parse on whitespace or comma, discard empty
tokens and compare usernames exactly and case-sensitively after identity's
existing outer trim. Membership in both lists resolves admin.

An operator-list match overrides an admin group: the env override tier is
authoritative, not additive. A username absent from both lists falls through
to groups.

For the comma-separated header contract, split only on commas, trim each
token's surrounding whitespace, discard empty tokens, and perform exact
case-sensitive whole-group matching. Do not split group names on spaces,
recognize substrings, decode JSON or guess alternative delimiters. Unknown
tokens grant nothing. Absent, blank or wholly unrecognized groups resolve
viewer when no env override matches.

Live outpost emission/format is unverified. A different format must fail
closed, not trigger permissive parsing.

## Route-to-role contract

References below are api/app/main.py at the reference checkout.
Every table row is an independently tested HTTP route.

| Method and path | Handler | Minimum role | Lines |
|---|---|---|---|
| PATCH /api/cam1/objects/{object_id} | patch_cam1_object | operator | 554-556 |
| PATCH /api/objects/{object_id} | patch_object | operator | 1002-1004 |
| DELETE /api/cam1/objects/{object_id} | delete_cam1_object | admin | 559-561 |
| DELETE /api/objects/{object_id} | delete_object | admin | 1007-1009 |
| POST /api/cameras/{camera_id}/snapshot/commit | commit_camera_snapshot | operator | 410-422 |
| POST /api/cameras/{camera_id}/preview/start | start_camera_preview | operator | 432-440 |
| POST /api/cameras/preview/stop | stop_camera_preview | operator | 443-447 |
| POST /api/cam1/roi | post_cam1_roi | admin | 569-571 |
| POST /api/cam1/speed-config | post_cam1_speed_config | admin | 579-581 |
| POST /api/cam1/speed-lines | post_cam1_speed_lines | admin | 589-591 |
| POST /api/cam1/crossing-line | post_cam1_crossing_line | admin | 599-601 |
| POST /api/analytics/{camera_id}/roi | post_analytics_roi | admin | 769-794 |
| POST /api/analytics/{camera_id}/speed-config | post_analytics_speed_config | admin | 813-826 |
| POST /api/analytics/{camera_id}/speed-lines | post_analytics_speed_lines | admin | 876-912 |
| POST /api/analytics/{camera_id}/crossing-line | api_post_crossing_line | admin | 920-922 |
| POST /api/worker/control/start | start_worker_control | admin | 1023-1031 |
| POST /api/worker/control/stop | stop_worker_control | admin | 1034-1042 |
| POST /api/worker/control/road1/start | start_road_worker_control | admin | 1056-1064 |
| POST /api/worker/control/road1/stop | stop_road_worker_control | admin | 1067-1075 |

Read surface: all 33 GET routes in tests/test_route_table.py:30-62 retain
their current access rules. This includes camera reads
(main.py:386-407,425-429), cam1/analytics state/events/passages/objects and
calibration reads (450-998), worker status (1012-1020,1045-1053), session
(1078-1084), live data/SSE (1106-1123,1143-1159) and health (1161-1164).
The /media mount remains unchanged (365). SSE routes are included in the
33 GET count, not additional endpoints.

Worker-status GETs and /api/session retain their existing identity check,
but impose no role minimum. "Reads for all roles" does not remove those
checks or upstream authentication.

Legacy calibration GETs normalize and write old representations
(main.py:741-751,843-857). Preserve these maintenance effects; this feature
does not promise side-effect-free GETs or alter calibration values supplied
by users through reads.

The nine worker ingestion POST routes retain require_auth and carry no
identity-header requirement: cam1 state/events/passages/crossings/live;
analytics state/events/crossings; road1 live
(main.py:473-517,604-609,624-720,925-938,1089-1104,1127-1141).

## Session contract

GET /api/session returns exactly:

{"ok": true, "username": "<verified, trimmed username>",
 "role": "admin|operator|viewer"}

The role value is one of the three literals, not the pipe-separated string.
No groups, override source or other claims are exposed. Current shape:
api/app/main.py:1078-1084.

## Security notes

Strict edge mode is confirmed live on the production API (verified
2026-10-18 during #520 phase 3; see #520 records). Do not remove or modify
transitional mode in this feature.

The renderer forwards upstream groups in authentik mode and blanks identity
fields in basic-auth mode
(scripts/operations/nginx_sea_speed_auth.py:294-308).
Basic-auth therefore cannot elevate roles: absent identity fails the existing
identity check, normally 503 with a valid edge secret; a verified identity
with blank groups and no override resolves viewer and receives 403 on
mutations. Do not mislabel all these cases as role-denial 403.

Current worker mutations expose requested_by, but the identity primitive
does not log successful mutations (identity.py:99-132; main.py:1023-1075).
New gates must add explicit mutation-attempt audit records using only the
verified username, resolved role and a static action name. An authorized
attempt record is not a claim that the downstream mutation succeeded.

## Non-goals

- Transitional-mode removal.
- Frontend redesign or role-aware hiding; /api/session enables a cosmetic
  follow-up, not an authorization mechanism.
- Authentik blueprint, group membership, nginx or renderer changes.
- Worker ingestion, outbound worker protocol or token changes.
- Read/media access redesign or GET normalization refactoring.
- Schema changes, migrations, new routers, middleware or Depends.
- Live env-list administration or logging infrastructure/retention changes.

## Acceptance criteria

- AC-001: All three roles behave as specified on all 19 browser mutations.
- AC-002: Identity-first ordering, env precedence and exact group parsing
  are covered by positive and negative tests.
- AC-003: Every denial prevents storage/process/network mutation.
- AC-004: Session exact shape, identity import seams, route fingerprint,
  existing reads and M2M contracts remain covered.
- AC-005: Authorized mutation attempts record verified identity without
  secrets or raw header/payload material.
- AC-006: Full suite and SDD/repository validators pass; runtime acceptance
  proves role behavior through the existing trusted edge.

## NFR assessment

- NFR-001 | Area: security | Target: no denied browser mutation reaches a business side effect; unknown claims grant no privilege; insufficient role is 403 "Forbidden" after identity verification | Validation: per-route denial/side-effect tests, identity-first ordering pins | Evidence: test_sea_speed_rbac.py 19x3 matrix green; full suite 1097 passed @ worktree 2026-10-18 | Status: PASS
- NFR-002 | Area: compatibility | Target: 61 unchanged method/path/handler entries; unchanged M2M and read policy; only session role is additive | Validation: route and contract suites | Evidence: test_route_table fingerprint and test_api_contract green in same run | Status: PASS
- NFR-003 | Area: maintainability | Target: one resolver and one role guard, layered on existing identity verification; no Depends, no new routers or middleware | Validation: import/wiring tests and independent review | Evidence: import/wiring tests green; review 9/9 checklist PASS | Status: PASS
- NFR-004 | Area: auditability | Target: every authorized mutation attempt has verified-user attribution without secret/header/payload leakage | Validation: captured audit records, including calibration alias forwarding | Evidence: audit capture tests incl. alias forwarding green | Status: PASS

## Runtime feedback

Missing groups may make legitimate users viewers. This is a safe denial,
not justification to relax parsing or trust client headers. Validate live
group emission and representative memberships before accepting rollout.
A rollback restores the prior authorization weakness and must be recorded
as a security regression, not a neutral feature rollback.
