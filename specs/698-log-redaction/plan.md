# Plan — Issue #698 shared log redaction

- Issue: #698
- Specification: specs/698-log-redaction/spec.md

## Architecture

One stdlib-only module, `api/app/log_redaction.py`, is the single source of
the masking rules. It is deliberately free of third-party imports, secret
environment reads and any import of the API application, so the two Ubuntu
scripts (which run under a different interpreter and never import the API)
can load the exact same implementation.

Redaction is applied at the *actual output boundaries*, not only inside a
`logging.Filter`, because the worker contour does not use Python logging and
`identity.py` installs its own marked stderr handler (#591) that a root
filter would miss.

- `redact_log_text(text)` — the pure transform.
- `RedactingFilter` — on the identity logger: renders `getMessage()`,
  sanitizes in place, clears `args`, and pre-renders/sanitizes `exc_text`, so
  `assertLogs`-style captures see masked text.
- `RedactingFormatter` — wraps uvicorn.access/uvicorn.error formatters; the
  inner formatter runs first so the structured `record.args` dict, status
  code, request line and appended traceback are all covered without clearing
  args (clearing would break `AccessFormatter`).
- `install_api_redaction()` — idempotent (marked filter + marked formatter),
  attaches to any already-imported identity logger object and wraps the
  uvicorn handlers without changing levels, handler identity or propagation.

Import seam: `main.py` imports the helper in the existing package/app-dir
try/except idiom and calls `install_api_redaction()` at module init.
`identity.py`, `passage_mirrors.py` and `analytics.py` import the helper
through the same dual idiom; the worker scripts resolve
`Path(__file__).resolve().parents[3] / "api" / "app"` (release root `source/`
or repo root) from their own file location, independent of cwd.

## Decisions

- **Boundary-level text sanitization, not a logging-only filter**: the
  workers print to stdout/stderr and do not use `logging`; a filter would
  protect nothing there.
- **Formatter wrapper for uvicorn**: `uvicorn.access.AccessFormatter`
  consumes `record.args` as a structured dict, so a message-only filter that
  clears `args` would break it; the wrapper redacts after the inner format.
- **`RedactingFilter` renders then clears args on the identity logger**: this
  keeps `assertLogs` captures sanitized and is safe because `identity` logs
  simple `%s` arguments.
- **Sanitize only the written string in `forward()`**: the original line
  still feeds `record_line`, so numeric/prefix telemetry parsing
  (`inference_ms=`, `effective_fps=`, `dropped=`, outbox fields) is byte-for-
  byte unchanged. Newline, stream, flush and ordering are preserved.
- **Do not wrap inference stdout**: `ubuntu_ai_inference_worker.py` speaks a
  binary frame protocol on stdout; wrapping it would corrupt IPC.
- **Keep the RTSP sanitizer**: `_redact_media_secrets` (#008) is retained;
  its output additionally passes through `forward()`.
- **Idempotence by markers on the live objects**: the Logger singleton and
  handler formatters survive `importlib.reload`, so markers
  (`_sea_speed_698_redacting_filter`, `_sea_speed_698_redacting_formatter`)
  prevent duplicate filters/double-wrapping across reloads and both import
  modes.
- **Fixed marker `[REDACTED]`**: one stable token, idempotent re-runs.
- **`store.py` untouched**: its `:244` stderr line is a fixed string plus an
  integer count with no credential, and the file is outside scope.

## Affected contours

- API (VPS release contour): `api/app/log_redaction.py` (new),
  `api/app/identity.py`, `api/app/main.py`, `api/app/passage_mirrors.py`,
  `api/app/analytics.py`.
- Ubuntu Worker/relay: `deploy/worker/ubuntu/observed-worker-runner.py`,
  `deploy/worker/ubuntu/worker-control-agent.py`.
- Packaging / deploy plumbing: `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`, `deploy/vps/deploy.sh`.
- SDD: this trio. Tests are owned by a separate test worker; `tests/**` is
  not touched here.

## Validation

- `python3 -m py_compile` on every changed `.py` file.
- `ruff check --config scripts/quality/ruff.toml` on changed Python files.
- `bash -n deploy/vps/deploy.sh`; direct convergence check
  (`deploy_app_module_targets` vs vps required `api/app` modules = 10/10).
- `python3 scripts/quality/build_exact_artifacts.py` +
  `validate_exact_artifacts.py` in a temp output dir.
- Focused smokes: identity filter masks a Bearer value while preserving audit
  fields; uvicorn AccessFormatter keeps client/status/request line and masks
  `token=`; runner `forward()` masks output while telemetry counters update;
  control `log_message` masks a query token.
- Existing test suite; two known EXPECTED failures belong to the test worker
  (see Risks).

## Runtime feedback

- RF-001: no operator action; acceptance is exact-head CI green, then lane-A
  VPS probe (`journalctl -u sea-speed-api` shows `[REDACTED]`) and the Ubuntu
  worker update/progression gate.
- RF-002: logging-only; no schema, storage or API/auth behaviour change.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: mask at every in-scope boundary incl. quoted/URL forms; explicit labels win over heuristic exemptions; idempotent marker prevents bracket growth | Validation: log_redaction scenarios + wired-boundary smokes | Residual risk: a novel credential shape outside the labelled set and not digest-like may survive the heuristic | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: sanitize only the written string in forward(); leave record_line, binary IPC and RTSP sanitizer untouched; formatter wrapper preserves structured args | Validation: telemetry-counter smoke + existing observability/operator tests | Residual risk: an over-broad heuristic could mask a benign long token | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: mirror the new module through every deploy.sh site and both release inventories, pinned by the existing convergence validator; rides the normal release contour with rollback | Validation: build+validate exact artifacts; deploy.sh syntax | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: tests owned by test worker — pure pattern/idempotence/benign-byte-identical cases
- TEST-002 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: identity logger filter preserves audit fields and masks Bearer
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: uvicorn.access AccessFormatter keeps client/status/request line and masks token query
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: runner forward masks stdout/stderr, record_line parses original, binary IPC untouched
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P1 | Evidence: control log_message masks query token, auth/response unchanged
- TEST-006 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: build+validate exact artifacts; convergence 10/10
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P1 | Evidence: double install / reload adds no second filter, wraps no formatter twice
- TEST-008 | Covers: AC-002 | Level: integration | Priority: P1 | Evidence: wrapped direct stderr print masks credential

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source change; scope unadmitted | Retry: after fresh admission | Rollback: not required | Evidence: admitted issue #698 scope and this SDD
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: live release unchanged | Retry: after fixing release_complete/download_release inputs | Rollback: not required | Evidence: release_complete/download_release required-file checks incl. api/app/log_redaction.py
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next files, live untouched until activation | Retry: re-run deploy after correcting payload | Rollback: previous release already captured | Evidence: install-to-release and .next staging of log_redaction.py
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: activation aborted, previous release restored | Retry: after health/auth probes pass | Rollback: previous exact release | Evidence: post-activation health/protected-boundary probes
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: current-release marker not advanced | Retry: resume from verification | Rollback: previous release pointer | Evidence: current-release/previous-release state files
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deploy still valid, temp files may remain | Retry: harmless | Rollback: not required | Evidence: temp/archive cleanup
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deploy valid, evidence incomplete | Retry: regenerate evidence | Rollback: not required | Evidence: deployment manifest and journald probe
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous exact release active | Retry: redeploy candidate after fix | Rollback: previous release restored | Evidence: rollback path activates captured previous release
