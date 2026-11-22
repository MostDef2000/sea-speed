# Feature Specification: #706 — Unified speed-config loader and `.bak` backup

- Feature: 706-speed-config-backup
- Issue: #706
- Status: Implementation landed; tests and CI pending
- Owner outcome: One calibration loader serves both the speed-config GET and POST, and every
  successful speed-config write keeps the immediately previous file as `<name>.bak`.

## Product outcome

Speed-config calibration is the only analytics config family whose GET path and POST path
currently use different rules: GET reads JSON, then applies `setdefault` defaults and returns
whatever is on disk; POST independently parses, finite-checks and range-checks the request
before writing. A stored record is therefore never validated by the same code that produced
it. A single side-effect-free loader removes that divergence, so what the operator reads back
is exactly the shape the writer produced.

The second outcome is operator recovery: after a bad calibration write, the previous
speed-config document must still exist on disk as `<name>.bak` so it can be restored without
inventing values. The backup is an opt-in per-write behaviour, enabled only for speed-config,
and never changes the behaviour of any other JSON write.

### Admitted scope resolution (orchestrator-verified, do not re-litigate)

Issue #706 cites `main.py:919` and `main.py:1027` from base commit `282fe49d` and calls both a
"GET loader". At that commit `:919` is the speed-config POST write and `:1027` is inside the
speed-lines POST; neither line is a GET loader. The "GET loader" premise rests on stale line
numbers. The admitted scope is therefore **speed_config only**, for both camera IDs
(`/api/analytics/{camera_id}/speed-config`) and the `cam1` alias (`/api/cam1/speed-config`).

`speed_lines` is a separate config family: its GET performs migration-on-GET and writes, and it
has a different storage projection (`line_a_norm` / `line_b_norm`, reference dimensions). It is
explicitly out of scope and requires its own admission; this feature must not touch it.

## User scenarios

### Scenario 1 - Read back the shape that was written

Given a stored speed-config file written by a successful POST, when an operator GETs the
speed-config route, then the response is produced by the same loader that validated the POST,
with `ok`/`camera_id` set, numeric `kmh_per_px_s`, and `enabled` normalised against a positive
factor.

### Scenario 2 - Corrupt storage never masquerades as calibration

Given a speed-config file that is not valid JSON or carries an invalid factor, when an operator
GETs the route, then the API answers HTTP 500 `speed-config storage is corrupted` and does not
return a `.bak` document as live calibration.

### Scenario 3 - Invalid request never reaches disk

Given an operator POSTs a non-numeric, non-finite or negative `kmh_per_px_s`, when the handler
runs, then it answers HTTP 400 with the pre-existing detail string and writes nothing.

### Scenario 4 - Previous document survives a write

Given a speed-config file already exists, when a valid POST succeeds, then the exact previous
bytes are published to `<name>.bak` and the primary carries the new document; a subsequent
successful POST replaces the single `.bak` slot with the then-current previous bytes.

### Scenario 5 - First write has no predecessor

Given no speed-config file exists, when the first valid POST succeeds, then the primary is
written and no `.bak` is created (a genuinely absent predecessor is ignored).

### Scenario 6 - Backup failure aborts publication

Given publishing the backup fails for a reason other than an absent predecessor, when a valid
POST runs, then the primary keeps its prior content and no new document is published.

### Scenario 7 - Restore without production mutation

Given a `.bak` document in temporary storage, when the documented restore procedure runs, then
the selected camera's backup is validated by the same loader and published by same-directory
atomic replacement, and a subsequent GET shows the restored document. Acceptance exercises this
only in temporary storage.

## Requirements

- FR-001: There MUST be exactly one side-effect-free loader for the speed-config stored-record
  shape; both the GET handler and the POST handler MUST call it. No second validator may exist.
- FR-002: The loader MUST convert `kmh_per_px_s` to `float`, reject non-finite values, reject
  negative values, and return a new record with `ok=True`, the resolved `camera_id`, the
  normalised `enabled`, the numeric `kmh_per_px_s`, and a preserved-or-null `updated_at`.
- FR-003: The loader MUST preserve compatible extra stored keys and MUST NOT perform filesystem
  access.
- FR-004: Storage defaults (`enabled=False`, `updated_at=None`) MUST remain distinct from POST
  candidate defaults (`enabled=True` before zero-factor handling, `updated_at=now_iso()`).
- FR-005: GET MUST map unreadable/invalid stored content to HTTP 500
  `speed-config storage is corrupted`, and MUST NOT serve a backup as live calibration.
- FR-006: POST MUST validate the candidate through the loader before any filesystem write and
  MUST map loader rejections to HTTP 400 with the exact pre-existing detail strings
  (`kmh_per_px_s must be a number`, `kmh_per_px_s must be a finite number`,
  `kmh_per_px_s must be >= 0`). Invalid requests MUST NOT be turned into 500s.
- FR-007: `write_json_file` MUST accept a keyword-only `backup: bool = False`; only the
  speed-config POST passes `backup=True`.
- FR-008: With `backup=True`, while holding the existing primary-file advisory lock, the
  implementation MUST stage the serialized candidate, publish the exact old primary bytes to
  `<filename>.bak` via the existing atomic byte writer, and only then replace the primary.
- FR-009: Only a genuinely absent predecessor may be ignored; any other backup error MUST abort
  publication and leave the primary untouched.
- FR-010: The first successful write MUST create no backup; each later successful write MUST
  overwrite the single `.bak` slot (no multi-generation history).
- FR-011: The change MUST NOT alter the config JSON format, the response shape, `cam1`
  delegation, the speed-lines family, or any other config family; no new dependencies.
- FR-012: There MUST be no restore endpoint, no startup auto-restore and no production
  calibration write for acceptance; restore is a documented operator procedure validated in
  temporary storage.

## Acceptance criteria

- AC-001: GET returns a valid stored/default speed-config through the shared loader, with extra stored keys preserved and `ok`/`camera_id`/`updated_at` normalised.
- AC-002: GET maps corrupt JSON or an invalid stored factor to HTTP 500 `speed-config storage is corrupted` and never returns `.bak` content.
- AC-003: POST validates the candidate through the same loader before writing; non-numeric, non-finite and negative `kmh_per_px_s` produce HTTP 400 with the exact legacy detail strings and zero writes.
- AC-004: A successful POST persists the loader output; the first write creates no `.bak`, and each later successful write stores the exact previous bytes in `<name>.bak` in one slot.
- AC-005: A backup publish failure (other than absent predecessor) aborts publication keeping the primary old; a final primary-replace failure leaves the primary old and may leave `.bak` equal to the primary, as documented.
- AC-006: `cam1` alias and every analytics camera ID show identical behaviour, response format and JSON format are unchanged, and no other config family is modified.
- AC-007: The restore procedure is documented and exercised in temporary storage only, with no restore endpoint, no startup auto-restore and no production calibration mutation.

## Loader contract

`_load_speed_config(camera_id: str, record: Dict[str, Any]) -> Dict[str, Any]` in
`api/app/main.py`, placed immediately before `get_analytics_speed_config`.

Input: a dict. Callers own their defaults:

| Caller | `enabled` default | `kmh_per_px_s` default | `updated_at` default |
|---|---|---|---|
| GET (storage) | `False` | `0.0` | `None` |
| POST (candidate) | `True` | `0.0` | `now_iso()` |

Processing (side-effect free, no IO):

1. A non-dict record raises `ValueError("speed-config record must be an object")`.
2. `float(record.get("kmh_per_px_s", 0.0))`; `TypeError`/`ValueError`/`OverflowError` raise
   `ValueError("kmh_per_px_s must be a number")`.
3. Non-finite raises `ValueError("kmh_per_px_s must be a finite number")`.
4. Negative raises `ValueError("kmh_per_px_s must be >= 0")`.
5. Returns `dict(record)` with `ok=True`, `camera_id=camera_id`,
   `enabled = bool(record.get("enabled", False)) and kmh_per_px_s > 0`,
   `kmh_per_px_s` replaced by the float, and `updated_at` preserved or defaulted to `None`.

Error mapping is the caller's, not a second validator: GET wraps read+load in
`store.JSON_READ_ERRORS` (which includes `ValueError`) and answers 500; POST catches the
loader's `ValueError` and answers 400 with `str(exc)`.

## `.bak` transaction failure matrix

`write_json_file(path, data, backup=True)` runs three steps under the primary's `flock`:

| Step | Failure | Primary after | `.bak` after | Publication |
|---|---|---|---|---|
| Stage candidate (temp write) | write error | old, untouched | unchanged | aborted |
| Publish backup (read old + atomic byte write) | `FileNotFoundError` (no predecessor) | old (absent) | none created | proceeds |
| Publish backup | any other error | old, untouched | old/partial slot untouched | aborted |
| Replace primary (`os.replace`) | replace error | old, untouched | may already equal old primary | aborted |

Consequence: primary and `.bak` are two files, not one atomic transaction. The only reachable
non-atomic state is "primary old and `.bak` equal to primary"; no code path promises two
historical generations. A concurrent reader may observe the backup one generation newer than
the primary during the window between the two publishes; this is acceptable for an operator
recovery artifact and is not part of the live read path.

## Compatibility and boundaries

- Stable public interfaces: `GET/POST /api/analytics/{camera_id}/speed-config`,
  `GET/POST /api/cam1/speed-config`, config JSON keys, response JSON keys.
- Out of scope: `speed_lines` (separate family, separate admission), restore endpoint, startup
  auto-restore, multi-generation backup history, any other config family, `tests/**`,
  `worker/**`, `deploy/**`, `.github/**`, `scripts/**`, lockfiles.
- Security constraints: backups contain the same non-secret calibration values as the primary
  and live beside it under the same storage permissions; no new network or secret surface.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: GET of an invalid stored speed-config returns HTTP 500 `speed-config storage is corrupted`; GET of a valid document returns HTTP 200 with the loader shape | Validation: integration test over temp storage, plus runtime manual restore probe | Evidence: TEST-002 planned by the test worker | Status: CONCERNS
- NFR-002 | Area: DATA | Target: after two consecutive successful speed-config writes, `<name>.bak` byte-equals the first primary and the primary equals the second document | Validation: unit test of `write_json_file(..., backup=True)` in temp storage | Evidence: TEST-003 planned by the test worker | Status: CONCERNS
- NFR-003 | Area: OPERABILITY | Target: restore procedure validates the selected backup with the same loader before publishing and leaves GET showing the restored document | Validation: runtime-manual probe in temp storage | Evidence: TEST-004 planned | Status: CONCERNS

## Runtime feedback

- Runtime acceptance: temp-storage probes executed during this implementation (loader round-trip, backup slots, failure matrix); hosted tests owned by the test worker.
- Accepted production behavior: no production calibration write was performed for acceptance.
- Regressions/learning: AST-extraction tests that exec the POST handler in isolation must include `_load_speed_config`; owned by the test worker.
- Follow-up work: open a separate scope for the speed-lines loader (migration-on-GET, different projection).
