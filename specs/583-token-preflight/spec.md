# Spec: #583 — Repo-owned token pre-flight probe

- Issue: #583
- Spec: specs/583-token-preflight/spec.md
- Plan: specs/583-token-preflight/plan.md
- Tasks: specs/583-token-preflight/tasks.md
- Base: de868bb (branch fix/579-api-dependency-lock-gradual-lint, content-identical to origin/main)
- Authorization: the #583 scope (data/contracts/token-inventory-v1.json +
  scripts/quality/validate_token_preflight.py + .github/workflows/token-preflight.yml +
  quality-integration.yml step/ruff/mypy edits + mypy.ini strict section + this trio +
  docs/operations/TOKEN_PREFLIGHT.md) admitted by the delivery orchestrator; the RED test
  module tests/test_token_preflight.py had 46 tests on the base and now carries 56
  after the peer-review date-matrix additions; it is test-protected.

## Product outcome

GitHub credentials that the sea-speed delivery pipeline depends on are currently
invisible to CI: nothing fails when a token expires or is revoked, and expiry
knowledge lives in chat history and issue comments instead of the repository.
After this change the repo owns a token inventory
(`data/contracts/token-inventory-v1.json`, schema `sea-speed-token-inventory/v1`)
recording every contracted credential identity — kind, expiry status, review
date, probe mode, credential pointer — together with a stdlib-only validator
(`scripts/quality/validate_token_preflight.py`) that (a) runs offline in every
PR/push Quality run to prove the inventory is schema-valid and no expiry or
review date is due, and (b) runs weekly on a schedule (`token-preflight.yml`,
cron `17 9 * * 2` UTC Tuesdays, main only) in probe mode, performing a live
`GET https://api.github.com/zen` with `Authorization: Bearer <credential>` for
every inventory entry marked `probe: api-zen`, writing a sanitized
`GITHUB_STEP_SUMMARY` section, and failing loudly with stable markers
(`EXPIRED`, `EXPIRY-DUE`, `REVIEW-DUE`, `MISSING-CREDENTIAL`,
`INVALID-CREDENTIAL`, `PROBE-UNAUTHORIZED`, `PROBE-FORBIDDEN`,
`PROBE-UNREACHABLE`, `PROBE-SERVER-ERROR`, `PROBE-FAILED`,
`SUMMARY-WRITE-FAILED`) and a final `TOKEN-PREFLIGHT PASS`/`FAIL` line. The
operator runbook (`docs/operations/TOKEN_PREFLIGHT.md`) documents scope,
schedule, alarm ownership, marker interpretation, remediation, limits and the
activation path for future REST-capable credentials.

## User scenarios

- SC-1: a contributor opens a PR — the quality-integration static job runs the
  validator offline (`python scripts/quality/validate_token_preflight.py`); a
  malformed inventory, an expired date, or a date due within 21 days turns the
  PR red with a marker line naming the token, so date drift cannot merge.
- SC-2: the repo owner relies on the weekly scheduled run — every Tuesday
  09:17 UTC the token-preflight workflow runs on main, probes every
  `api-zen` entry's credential against `api.github.com/zen`, and appends a
  sanitized summary section; a revoked credential turns the run red and
  notifies the repo owner.
- SC-3: a credential's env var is unset or blank at probe time — the validator
  reports `MISSING-CREDENTIAL` with zero network requests; a value carrying
  surrounding whitespace or control characters is reported
  `INVALID-CREDENTIAL` and is never normalized or sent.
- SC-4: the API rejects a probed credential — 401 maps to
  `PROBE-UNAUTHORIZED` and 403 to `PROBE-FORBIDDEN`, neither retried; 5xx,
  network and timeout failures retry to 3 total attempts (sleeping 1s then
  2s) before failing; any other status fails without retry; no response body,
  header, raw exception or credential value is ever printed.
- SC-5: an operator wants to check dates locally — they run the validator
  offline (optionally with `--today YYYY-MM-DD`); it never touches the
  network or credential env vars, so it is safe on any machine.
- SC-6: a REST-capable credential becomes available as a repo secret — the
  owner flips its inventory entry to `probe: api-zen` with the env-var
  pointer, adds the matching env mapping to the workflow step, and amends the
  pinned workflow contract test in the same reviewed change (activation path
  documented in the runbook).

## Requirements

- R-1: `data/contracts/token-inventory-v1.json` — schema
  `sea-speed-token-inventory/v1`; exactly three contracted token identities
  (sea-speed-worker-quality-read: classic/no-expiry/review 2027-04-14/probe
  none/on-box pointer; sea-speed-opencode-connector:
  classic/dated 2026-12-31/probe none; SYNC_PR_TOKEN:
  fine-grained/unknown expiry/probe none/REST proven 401 with working git
  push per issue #558); every record carries exactly the nine contracted
  keys.
- R-2: `scripts/quality/validate_token_preflight.py` — stdlib-only argparse
  CLI (`main(argv=None) -> int` + `raise SystemExit(main())`), `--inventory`
  (default data/contracts/token-inventory-v1.json), `--today YYYY-MM-DD`,
  `--probe`; `--today` + `--probe` is a usage error (exit 2);
  `WARNING_DAYS = 21`. Offline mode: schema validation (exact root/token key
  sets, name pattern + uniqueness, enum fields, strict date fields,
  dated/no-expiry cross-field rules, api-zen env-pointer rules, probe-none
  pointer rules, scope list rules, note bounds, duplicate JSON keys and
  duplicate names rejected, credential-shaped strings rejected naming record
  index + field without echoing content) plus date evaluation (expiry in the
  past -> EXPIRED; expiry within 21 days -> EXPIRY-DUE; review date due
  within 21 days or overdue -> REVIEW-DUE; unknown expiry -> WARN
  UNKNOWN-EXPIRY, non-failing; else OK). Probe mode: missing/empty env ->
  MISSING-CREDENTIAL (zero requests); whitespace/control-contaminated value
  -> INVALID-CREDENTIAL (zero requests); GET
  https://api.github.com/zen with Bearer header, fixed User-Agent, 10s
  timeout, redirects disabled, TLS verified; 200 -> PROBE-OK; 401 ->
  PROBE-UNAUTHORIZED no retry; 403 -> PROBE-FORBIDDEN no retry; 5xx/network/
  timeout -> 3 attempts total with 1s then 2s sleeps; other statuses fail
  without retry; probe: none entries report NOT-PROBED; date failures do not
  suppress probes. Output: one `<MARKER>: <token-name> <short safe detail>`
  line per finding (errors to stderr, info/warn to stdout), final line
  exactly `TOKEN-PREFLIGHT PASS` or `TOKEN-PREFLIGHT FAIL`, exit 0/1/2. In
  probe mode a sanitized `## Token pre-flight` section is appended to
  GITHUB_STEP_SUMMARY on PASS and FAIL; an unwritable summary path is
  `SUMMARY-WRITE-FAILED` + exit 1.
- R-3: `.github/workflows/token-preflight.yml` — weekly schedule
  (`17 9 * * 2`) + workflow_dispatch, top-level `permissions: contents: read`,
  single `preflight` job guarded to `github.ref == 'refs/heads/main'`,
  ubuntu-latest, 5-minute timeout, pinned checkout with
  persist-credentials: false, pinned setup-python 3.14, running
  `python scripts/quality/validate_token_preflight.py --probe`; the file
  references no `secrets.` anywhere (today's inventory is all probe: none, so
  the probe step needs no secret mapping).
- R-4: quality-integration.yml (static-contract-security) gains an offline
  step "Validate token inventory and dates" between "Validate repository and
  canonical contracts" and "Validate JSON and Python syntax"; the ruff strict
  invocation and the mypy invocation both list the new validator module;
  everything else stays unchanged (validate_workflow_policy.py markers keep
  passing).
- R-5: `scripts/quality/mypy.ini` gains a
  `[mypy-scripts.quality.validate_token_preflight]` section with
  `strict = True` (gradual strict protocol, one module).
- R-6: `specs/583-token-preflight/{spec,plan,tasks}.md` and
  `docs/operations/TOKEN_PREFLIGHT.md` exist and satisfy
  scripts/ci/validate_sdd.py; the runbook documents scope, schedule, alarm
  ownership, notification acceptance, marker interpretation (including the
  REST-401-vs-push discrepancy), remediation, limits/dead-man risk, rollback
  and the api-zen activation path.

## Acceptance criteria

- AC-001: `data/contracts/token-inventory-v1.json` exists, parses, has root
  keys exactly {schema, tokens} with schema `sea-speed-token-inventory/v1`,
  and contains exactly the three contracted identities with the contracted
  field values (tests test_inventory_*).
- AC-002: the validator's offline CLI surface holds: a valid inventory with
  `--today` exits 0 with `TOKEN-PREFLIGHT PASS`; the committed default
  inventory exits 0 PASS; a wrong-schema inventory exits 1 with
  `TOKEN-PREFLIGHT FAIL`; `--today` + `--probe` exits 2 with a usage-error
  message on stderr (subprocess tests).
- AC-003: offline mode never calls fetch_status and never reads the
  credential env var (recorded-env-access unit test).
- AC-004: probe mode maps statuses and retries correctly — 200 PROBE-OK;
  401 PROBE-UNAUTHORIZED and 403 PROBE-FORBIDDEN with no retry; 5xx and
  network errors retry to 3 attempts total sleeping 1s then 2s; missing or
  whitespace-only credentials fail MISSING-CREDENTIAL with zero requests;
  whitespace-surrounded credentials fail INVALID-CREDENTIAL without being
  normalized or sent; probe: none entries are NOT-PROBED and never probed;
  synthetic credentials never leak into stdout, stderr or the summary
  (probe unit tests).
- AC-005: in probe mode GITHUB_STEP_SUMMARY receives a `## Token pre-flight`
  section (with the runbook link) on PASS and FAIL; an unwritable summary
  path yields SUMMARY-WRITE-FAILED and exit 1 (summary unit tests).
- AC-006: fetch_status performs exactly one GET
  https://api.github.com/zen with the Bearer credential header, a fixed
  User-Agent and the 10s timeout; redirects are rejected via a custom
  no-redirect opener handler (one request, 3xx surfaced as a status, no
  credential forwarding); the response is closed; 401/500 surface as
  statuses; network errors are never reported as 200 (transport tests).
- AC-007: token-preflight.yml exists with name "Token pre-flight", cron
  `17 9 * * 2` + workflow_dispatch, `permissions: {contents: read}`, a single
  main-guarded job (ubuntu-latest, 5-minute timeout), pinned checkout with
  persist-credentials: false, pinned setup-python 3.14, the exact probe run
  command, and no `secrets.` reference anywhere (workflow tests).
- AC-008: quality-integration.yml contains the offline step "Validate token
  inventory and dates" positioned between "Validate repository and canonical
  contracts" and "Validate JSON and Python syntax", and both the ruff strict
  invocation and the mypy invocation list the new validator module (quality
  integration tests).
- AC-009: mypy.ini contains a `[mypy-scripts.quality.validate_token_preflight]`
  section with `strict = True` (mypy test).
- AC-010: the SDD trio and the runbook exist with their key markers, and the
  generic workflow policy accepts every workflow including the new one
  (SDD + policy tests).

## Runtime feedback

- No runtime code path changes: api/**, worker/**, deploy/** and frontend/**
  are untouched. The change is CONTROL_PLANE (workflows, scripts/quality,
  data/contracts) plus documentation. The scheduled workflow runs
  `--probe` on main only: with today's all-`probe: none` inventory it makes
  zero network requests and reads no secrets; when an api-zen entry is
  activated later, its probe performs exactly one authenticated GET (plus
  bounded retries on transient failures) with the credential supplied via the
  workflow env mapping. Failure modes are fail-closed: an invalid inventory or
  a failing probe turns the scheduled run red and the Quality gate red; the
  validator never mutates state, never writes outside GITHUB_STEP_SUMMARY,
  and never prints credential material. Rollback is `git revert` of the
  change; restoring an older inventory does not restore a revoked token.

## NFR assessment

- NFR-001 | Area: secret hygiene | Target: zero credential values (synthetic or real) in stdout, stderr, or the step summary; zero secrets. references in token-preflight.yml | Validation: synthetic-credential leak assertions across stdout/stderr/summary plus the workflow no-secrets test | Evidence: tests/test_token_preflight.py probe/summary/workflow tests observed green | Status: PASS
- NFR-002 | Area: offline determinism | Target: offline mode performs zero network requests and zero credential env reads | Validation: unit test recording os.getenv/os.environ.get access with fetch_status mocked to fail on any call | Evidence: test_offline_never_calls_fetch_status_or_reads_credential_env observed OK | Status: PASS
- NFR-003 | Area: observability | Target: every finding carries a stable `<MARKER>: <token-name>` prefix and the run ends with exactly TOKEN-PREFLIGHT PASS or TOKEN-PREFLIGHT FAIL | Validation: subprocess tests assert exact markers and exit codes | Evidence: offline subprocess tests observed OK | Status: PASS
- NFR-004 | Area: maintainability | Target: stdlib-only validator held to mypy strict + ruff strict (gradual tier), base ruff gate and full battery unchanged and green | Validation: ruff strict + mypy strict runs over the module; base ruff + battery in the completion gate | Evidence: completion-gate observed outputs | Status: PASS
- NFR-005 | Area: CI cost | Target: scheduled job completes well inside its 5-minute timeout; zero network requests with the current all-probe:none inventory; at most 3 requests per api-zen entry (retry budget 1s+2s) | Validation: workflow timeout-minutes: 5 pinned by test; retry counts pinned by unit tests | Evidence: TokenPreflightWorkflowTests + retry unit tests observed OK | Status: PASS
