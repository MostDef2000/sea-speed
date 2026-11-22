# Implementation Plan: #706 — Unified speed-config loader and `.bak` backup

- Specification: specs/706-speed-config-backup/spec.md
- Issue: #706
- Status: Implemented (tests owned by the test worker)

## Architecture

One side-effect-free loader in `api/app/main.py`, `_load_speed_config(camera_id, record)`,
placed immediately before `get_analytics_speed_config`, converts and validates the stored-record
shape and returns the response/persisted document. GET reads JSON (or the storage default) and
passes it to the loader; POST builds a candidate with its own defaults and `updated_at`, passes
it to the loader before any write, then persists the result. The conversion, finite check and
non-negative check move from POST into the loader, so there is exactly one validator.

`api/app/store.py::write_json_file` gains a keyword-only `backup: bool = False`. With backup
enabled and while holding the existing primary-file `flock`, it stages the serialized candidate,
reads the exact old primary bytes, publishes them to `<filename>.bak` through the existing
`atomic_write_bytes` helper, then performs the existing `os.replace` of the primary. Only the
speed-config POST passes `backup=True`.

The change touches no other config family. `speed_lines` keeps its migration-on-GET and its
different projection untouched, per the admitted-scope resolution recorded in spec.md.

## Decisions

### D-001 - Loader raises ValueError; callers own the HTTP mapping

- Decision: the loader raises `ValueError` with the exact legacy detail strings. GET wraps
  read+load in `store.JSON_READ_ERRORS` (which already includes `ValueError`) and answers 500
  `speed-config storage is corrupted`; POST catches the loader's `ValueError` and answers 400
  with `str(exc)`.
- Reason: one loader serves both paths without a second validator, while each caller keeps its
  existing contract (storage corruption is 500, bad request is 400).
- Alternatives rejected: a loader raising `HTTPException` directly cannot distinguish request
  from disk origin and would turn bad disk content into 400 or bad requests into 500; a boolean
  origin flag would leak transport concerns into the loader.

### D-002 - Callers supply defaults, loader normalises

- Decision: GET passes the storage default (`enabled=False`, `updated_at=None`); POST passes a
  candidate (`enabled=True` from the request default, `updated_at=now_iso()`). The loader applies
  `enabled = bool(record.get("enabled", False)) and kmh_per_px_s > 0`.
- Reason: preserves the existing distinction between storage defaults and request defaults while
  keeping zero-factor handling in one place.
- Alternatives rejected: putting POST defaults inside the loader would make GET read storage
  records with request defaults and change read-back of `enabled`.

### D-003 - Backup before primary replace, same lock, single slot

- Decision: under the primary's `flock`, stage candidate, publish old bytes to `.bak` via
  `atomic_write_bytes`, then `os.replace` the primary. Ignore only `FileNotFoundError`; any other
  backup error aborts before the primary is replaced.
- Reason: the `.bak` always equals the immediately previous primary; the primary is never
  published unless its predecessor was safely captured.
- Alternatives rejected: renaming the primary away (leaves a window with no primary and breaks
  atomic replace semantics); two independent `write_json_file` calls from main.py (no shared
  lock, race between primary and backup); renaming the old primary to `.bak` via `os.replace`
  instead of byte-copying (still valid, but byte-copy reuses the existing fsync'd helper and
  keeps the old primary readable until the final replace).

## Affected contours

- Repository: `api/app/main.py` (loader + GET/POST wiring), `api/app/store.py` (opt-in backup),
  `specs/706-speed-config-backup/{spec,plan,tasks}.md`.
- VPS: NONE — no deploy, service, or config-file change; `.bak` appears beside the existing
  calibration file at runtime.
- Ubuntu worker/relay: NONE — worker reads the same GET contract.
- Windows worker/AI: NONE.
- Public interfaces: response shape and config JSON format unchanged; only a new sibling
  `<name>.bak` file appears after a successful speed-config write.

## Validation

- Static/CI: `python3 -m py_compile api/app/main.py api/app/store.py`;
  `python3 -m ruff check --config scripts/quality/ruff.toml api/app/main.py api/app/store.py`;
  `python3 scripts/ci/validate_sdd.py`.
- Integration: existing suite (`pytest --ignore=tests/quality`) with the test worker's updated
  speed-config/RBAC harnesses; the worker's new loader and backup tests.
- Runtime acceptance: temp-storage probes only — loader round-trip, two-write backup slot,
  default-off no-backup, backup-failure abort, simulated final-replace failure, restore probe.
  No production calibration write.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: backup publish happens under the primary's flock and before primary replace; only an absent predecessor is ignored; byte-identical previous document | Validation: TEST-003 backup matrix in temp storage | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: single shared loader removes GET/POST divergence; exact legacy 400 strings preserved; GET keeps the 500 storage contract | Validation: TEST-001/TEST-002 loader and endpoint tests | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: restore is documented and exercised only in temp storage; no endpoint or startup auto-restore | Validation: TEST-004 runtime-manual temp-storage restore probe | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-003, AC-006 | Level: unit | Priority: P0 | Evidence: tests to be added by the test worker (loader contract: defaults, extras, zero-factor, invalid values)
- TEST-002 | Covers: AC-001, AC-002, AC-003, AC-006 | Level: integration | Priority: P0 | Evidence: tests to be added by the test worker (GET/POST over temp storage for cam1/road1, 500/400 mapping, cam1 alias)
- TEST-003 | Covers: AC-004, AC-005 | Level: unit | Priority: P0 | Evidence: tests to be added by the test worker (`write_json_file(..., backup=True)` matrix in temp storage)
- TEST-004 | Covers: AC-007 | Level: runtime-manual | Priority: P1 | Evidence: documented restore probe in temporary storage; no production write

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: speed_lines loader is out of scope and needs its own admission (migration-on-GET and different projection).

## Deployment transaction audit

Not applicable: this change ships application code only, mutates no deployment/release surface,
and declares no runtime deployment REQUIRED.

## Rollout and rollback

- Rollout: normal application deploy; no migration; the first post-deploy speed-config write
  creates the first `.bak`.
- Rollback: revert the application commit; existing calibration files and any `.bak` remain
  valid JSON and are readable by the prior code.

## Runtime feedback

- Actual architecture after acceptance: loader + opt-in backup as planned.
- Differences from plan: NONE YET
- Deferred cleanup: pre-existing `tests/quality` collection errors are unrelated to this change.
