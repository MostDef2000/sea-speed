# Spec: #591 — Authorized-mutation audit line must reach stderr/journald under default startup

- Issue: #591
- Specification: specs/591-audit-stderr-reachability/spec.md
- Authorization: wave-1 admission (owner instruction 2026-11-08: continue
  execution per the last approved plan; the same formula was previously
  accepted as valid continuation authorization in #576 gen11); scope A of
  wave 1 (#591 + #587 + #589 + #576 closure); base 0d2763ac (branch
  fix/591-audit-stderr-reachability).

## Product outcome

require_role() emits the audit record "authorized mutation attempt:
user=… role=… action=…" (api/app/identity.py, _LOGGER.info), but the app
configures no logging anywhere and production runs uvicorn 0.54.0 in app-dir
mode, whose default logging leaves the root logger unconfigured — the INFO
record is dropped by lastResort before reaching any handler, so the audit
trail promised by spec #530 does not exist in journald (verified on prod:
0 `journalctl -u sea-speed-api -g "authorized mutation attempt"` hits since
22.10). After the fix: the identity module wires a dedicated stderr handler
on its own logger object at module init and raises that logger's level to
INFO, so every authorized-mutation audit record reaches stderr (→ journald
under the sea-speed-api unit) in both import modes, without touching the
root logger or any other module's logging. Alias delegation may still emit
two records per user-facing mutation — that is spec #530 D-4 semantics,
explicitly out of scope here.

## User scenarios

- SC-1: an authorized actor performs a mutation (e.g. POST /api/cam1/roi) —
  the audit line "authorized mutation attempt: user=<name> role=<role>
  action=<action>" appears on the API process stderr and therefore in
  `journalctl -u sea-speed-api`, in the production uvicorn app-dir import
  mode.
- SC-2: the same holds when the app is imported in package mode
  (`api.app.main`) — the logger name differs between modes and the wiring
  must not depend on it.
- SC-3: repeated app initialization / module reloads (dev reload, test
  harnesses) never attach a second handler — one audit record per guard
  emission, no duplication.
- SC-4: nothing else changes: root logger stays unconfigured, no other
  logger gains handlers, denial-path logging and the alias double-record
  semantics (#530 D-4) are byte-identical.

## Requirements

- R-1: api/app/identity.py attaches a logging.StreamHandler(sys.stderr) to
  the module logger OBJECT (never by hard-coded name) at module init.
- R-2: the same logger's level is set to INFO (a handler alone is
  insufficient: with an unconfigured root the effective level is WARNING and
  the record is dropped before any handler is consulted).
- R-3: attachment is idempotent — a marked-handler presence check on the
  logger object keeps repeated module init / importlib.reload() from
  duplicating handlers (the Logger singleton survives reloads).
- R-4: no logging.basicConfig, no dictConfig, no changes to any other
  module's logging; the module-level wiring stays outside the AST-extracted
  guard functions (tests/test_sea_speed_rbac.py extracts them into a stub
  namespace).
- R-5: tests/test_591_audit_stderr_reachability.py proves stderr
  reachability in real subprocesses (default startup, no logging config) for
  both import modes and pins reload idempotence relatively (post-reload
  count == single-init baseline), with no caplog/assertLogs and no mocks.

## Acceptance criteria

- AC-001: under default startup (no logging configuration), an authorized
  mutation attempt emits "authorized mutation attempt: user=… role=…
  action=…" on stderr in the production app-dir import mode; on base
  0d2763ac the test fails (line absent) — RED authenticity recorded.
- AC-002: same for the package import mode.
- AC-003: after repeated app init (identity and main reloaded), the audit
  line count equals the single-init baseline (no handler duplication).
- AC-004: full battery green with the fix (1382 tests, skipped=2), ruff
  clean, validate_sdd green; no committed test regressed.

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, then
  the lane-A deploy probe: trigger one authorized mutation and observe
  `journalctl -u sea-speed-api -g "authorized mutation attempt"` returning
  the record (0 hits today).
- RF-002: logging-only change — no stored data, schema, or API behavior
  changes; the only observable delta is the audit line now present on
  stderr/journald.

## NFR assessment

- NFR-001 | Area: security auditing | Target: every authorized-mutation audit record is observable in journald under default production startup | Validation: tests/test_591_audit_stderr_reachability.py (4 tests, real subprocesses, stderr capture; RED on base verified in both directions) | Evidence: focused run + base-stash differential recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero change to root logging, other modules' logging, denial paths, alias double-record semantics (#530 D-4) and AST extraction of guards | Validation: full battery 1382 OK incl. tests/test_sea_speed_rbac.py (30 OK); ruff clean | Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one handler attach at import, one stderr write per audit record | Validation: code review; the presence check runs once at module init, no hot-path additions | Evidence: diff inspection (+20 lines, module init only) | Status: PASS
