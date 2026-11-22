# Spec: #698 — Shared log redaction at real output boundaries

- Issue: #698
- Specification: specs/698-log-redaction/spec.md
- Authorization: wave-4 admission (issue #698), branch
  `agent/wave4-698-log-redaction`, base 67e31272 (current `main`).
- Related: specs/591-audit-stderr-reachability/spec.md (audit content and both
  import modes stay binding), specs/008-worker-rtsp-runtime-resilience/spec.md
  (media credential redaction).

## Product outcome

Sea Speed emits operational logs from four distinct contours — the FastAPI
API process (module-audit records, uvicorn access/traceback, and direct
`sys.stderr` prints), the Ubuntu observed-worker runner (a pipe forwarder for
the worker and its inherited inference stderr), the Ubuntu worker control
agent (its HTTP access line), and the RTSP media diagnostics. Today none of
these boundaries mask credential-shaped VALUES, so an Authorization header,
an `api_key/token` query field, or a digest-shaped secret that reaches a log
line is written verbatim to journald. Issue #698 introduces one stdlib-only
redaction helper and wires it at each *actual* output boundary (not on a
`logging.Filter` alone, because the workers do not use Python logging at all
and the identity logger installs its own handler). After the change a
credential value is replaced by the fixed marker `[REDACTED]` while benign
text — including the authorized-mutation audit fields — is byte-identical, so
the #591 audit trail and #530 semantics are untouched.

## User scenarios

- SC-1: an authorized mutation audit record containing a credential-shaped
  value reaches stderr with the value masked and the
  `user=… role=… action=…` fields intact.
- SC-2: an app-authored `print(..., file=sys.stderr)` diagnostic that embeds
  an exception carrying a token is masked in journald.
- SC-3: a uvicorn access line for `/v1/start?token=…` keeps client address,
  request line and status while masking only the token value; a uvicorn
  exception traceback carrying a credential is masked.
- SC-4: a worker subprocess line containing a token is masked on the
  runner's stdout/stderr, the runner's telemetry counters still update from
  the un-sanitized line, and the binary AI-inference stdout protocol is
  never wrapped.
- SC-5: the worker control agent's rendered access line masks a
  credential-bearing query string without changing auth/response behavior.
- SC-6: a benign log line is written byte-identically; `monkey=banana` is not
  mistaken for a `key=` field.

## Requirements

- R-1: `api/app/log_redaction.py` exists, is stdlib-only (no third-party
  import, no secret environment read, no import of the API application) and
  exposes `redact_log_text`, `RedactingFilter`, `RedactingFormatter` and
  `install_api_redaction`.
- R-2: `redact_log_text` is pure and idempotent, masks VALUES only, uses the
  fixed replacement `[REDACTED]`, and returns text with no credential shape
  byte-identically.
- R-3: labelled values (`Authorization: Bearer …` incl. quoted header-map
  repr; `key=`/`token=` incl. `api_key`, `api-key`, `access_token`; quoted
  values; URL query delimiters `&`/`#`; full credential incl. dots and
  trailing `=` padding) are masked regardless of length; the field boundary
  must not match `monkey=`.
- R-4: the unlabeled free-text heuristic masks a whole hex atom ≥32
  containing a hex letter, or a whole standard/URL-safe base64 atom ≥32 with
  padding or mixed-case+digits; structured audit fields, numeric telemetry
  and known digest fields (e.g. `sha256=<hex>`) are not matched.
- R-5: explicit labels take precedence over heuristic exemptions; an
  unlabeled digest may be masked and an unremarkable unlabeled string may
  survive.
- R-6: `identity.py` attaches `RedactingFilter` to its emitting logger object
  idempotently (marked), keeping the #591 marked stderr handler, INFO level,
  control-character escaping and the `:241-246` audit call unchanged.
- R-7: `main.py`, `passage_mirrors.py` and `analytics.py` import the helper in
  BOTH package (`api.app.*`) and app-dir (bare module) modes; `main.py` calls
  `install_api_redaction()` at import; every direct `sys.stderr` print in
  those modules is wrapped; `store.py` is not touched.
- R-8: `observed-worker-runner.py` resolves `parents[3]/api/app` from its own
  file and sanitizes ONLY the string passed to `target.write` in `forward()`;
  the original line still feeds `record_line`, and newline/stream/flush/order
  are preserved; inference stdout is not wrapped and the RTSP sanitizer is
  retained.
- R-9: `worker-control-agent.py` resolves `parents[3]/api/app` and sanitizes
  the rendered `log_message` before printing; auth and responses are
  unchanged.
- R-10: `api/app/log_redaction.py` is added to the vps and ubuntu-worker
  required inventories (not the archival edge inventory), pinned in
  `validate_exact_artifacts.py`, and mirrored through every
  `deploy/vps/deploy.sh` module touchpoint (targets, release_complete,
  required loop, install-to-release, bootstrap capture, staging, activation).

## Audit: producer -> sink -> protected point

| Producer | Sink | Protection / explicit exclusion |
|---|---|---|
| App-authored API diagnostics (`main.py:406`, `passage_mirrors.py:133,150`, `analytics.py:145,175`) | `sys.stderr` -> journald | Wrapped with `redact_log_text(...)` at the print |
| Identity authorized-mutation audit (`identity.py:241-246`) | `_LOGGER.info` -> marked stderr handler | `RedactingFilter` on the emitting logger object; audit fields preserved |
| Uvicorn access log | `uvicorn.access` handlers (structured `record.args`) | `RedactingFormatter` wrapper; args/status/request line intact |
| Uvicorn error / traceback | `uvicorn.error` handlers | `RedactingFormatter` wrapper; formatter-appended traceback covered |
| Runner worker stdout | `forward()` -> `sys.stdout` | `redact_log_text` on the written string only |
| Runner worker stderr (incl. inherited inference stderr) | `forward()` -> `sys.stderr` | `redact_log_text` on the written string only |
| Worker control service access line (`log_message`) | `print` -> journald (`sea-speed-worker-control`) | `redact_log_text(fmt % args)` before print |
| AI-inference binary IPC stdout (`ubuntu_ai_inference_worker.py:158`) | binary frame protocol | EXCLUDED: binary protocol, not text logging; never wrapped |
| RTSP media diagnostics (`ubuntu_worker_entrypoint.py:280-292`) | worker stderr -> runner forward | Existing `_redact_media_secrets` retained; also passes through `forward()` |
| Persisted outbox `last_error` (`worker_outbox.py`) | SQLite column | EXCLUDED: persisted state, not an output boundary; no rotation/retroactive purge. Its send/accept error prints do pass through `forward()` |
| Direct developer invocations bypassing the runner / unrelated host services | their own stdout/stderr | EXCLUDED: outside the repo-owned output boundaries |
| Historical journals / existing log files | already rotated/persisted | EXCLUDED: no rotation and no retroactive purge in this change |
| Store inventory stderr (`store.py:244`) | `sys.stderr` | EXCLUDED: fixed text + integer count only (no credential) and outside allowed paths |

## Masking contract

- Only credential VALUES are replaced; label text, separators, quotes, URL
  structure and surrounding benign bytes are preserved.
- Replacement marker is the literal `[REDACTED]`.
- Idempotent: masking already-masked text is a no-op (repeat renders do not
  grow brackets).
- Explicit labels take precedence over heuristic exemptions; a value under a
  known credential label is masked regardless of shape or length.
- The unlabeled heuristic is free-text only: whole atoms, never `key=value`
  fragments, so structured audit fields, numeric telemetry and labelled
  digests are not matched. Consequence: an unlabeled digest may be masked
  (acceptable) and an unremarkable unlabeled string may survive (acceptable).
- Exact regexes (from `api/app/log_redaction.py`):
  - Bearer: `(?i)(authorization['\"]?\s*[:=]\s*['\"]?\s*bearer\s+)([^\s'\",;}]+)`
  - Labelled: `(?i)(?<![A-Za-z0-9])(api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|bearer[_-]?token|id[_-]?token|client[_-]?secret|token|password|passwd|pwd|secret|key)(\s*[:=]\s*)(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'&#,;)}\]]+))`
  - Atom: `(?<![A-Za-z0-9+/=_-])([A-Za-z0-9+/=_-]{32,})(?![A-Za-z0-9+/=_-])`
  - Hex: `[0-9a-fA-F]{32,}`; Base64: `[A-Za-z0-9+/_-]+={0,2}`; hex letter: `[A-Fa-f]`

## Acceptance criteria

- AC-001: an identity audit record carrying a Bearer token is written to
  stderr with `[REDACTED]`, and the `user=…. role=…. action=…` audit fields
  are byte-identical to #591 behaviour.
- AC-002: a direct API `sys.stderr` diagnostic carrying a credential is
  masked.
- AC-003: a uvicorn access record keeps client address, request line and
  status code while masking a `token=` query value; a uvicorn exception
  text carrying a credential is masked.
- AC-004: the runner `forward()` masks a token on stdout/stderr, feeds the
  original line to `record_line` (telemetry counters update), preserves
  newline/order, and never wraps the binary inference stdout.
- AC-005: the worker control access line masks a credential-bearing query
  string; auth/response behaviour is unchanged.
- AC-006: `redact_log_text` is idempotent, leaves three benign lines
  byte-identical, does not mask `monkey=banana`, and masks labelled values
  regardless of length.
- AC-007: installing redaction twice (reload / both import modes) attaches no
  second filter and wraps no formatter twice.
- AC-008: vps + ubuntu-worker inventories and `deploy.sh` mirror include
  `api/app/log_redaction.py` (edge archival inventory does not); exact
  artifact build + validate are green.

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** and worker/** ride the normal
  release contours. Runtime acceptance = exact-head CI green, then the lane-A
  VPS probe (trigger a credential-bearing line, observe `[REDACTED]` in
  `journalctl -u sea-speed-api`) and the Ubuntu worker update/progression gate.
- RF-002: logging-only change — no stored data, schema, API or auth behaviour
  changes; the only observable delta is credential values replaced by
  `[REDACTED]` at the output boundaries.

## NFR assessment

- NFR-001 | Area: security auditing | Target: credential-shaped VALUES are masked at every in-scope output boundary while audit fields stay intact | Validation: log_redaction unit scenarios + wired-boundary smoke (identity filter, uvicorn formatter, runner forward, control log_message) | Evidence: observed in this change's verification runs | Status: PASS
- NFR-002 | Area: compatibility | Target: zero change to audit structure, auth/response behaviour, telemetry parsing, binary inference IPC or RTSP redaction | Validation: benign byte-identical checks, telemetry counter smoke, existing suite | Evidence: observed runs recorded in plan.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — a few compiled regex subs per emitted line; install is import-time and idempotent | Validation: code review; module-level compiled patterns, no hot-path new I/O | Evidence: diff inspection | Status: PASS
