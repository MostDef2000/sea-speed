# Plan — Issue #583 repo-owned token pre-flight probe

- Issue: #583
- Spec: specs/583-token-preflight/spec.md
- Base: de868bb (branch fix/579-api-dependency-lock-gradual-lint, content-identical to origin/main)

## Architecture

Three cooperating pieces plus documentation. (1) Inventory:
`data/contracts/token-inventory-v1.json` is the single repo-owned record of
contracted credential identities under schema `sea-speed-token-inventory/v1`
— name, kind, expiry status, expiry, review date, probe mode, credential
pointer, expected scopes, note. It records facts and pointers only; no
credential value ever enters the repository. (2) Enforcement:
`scripts/quality/validate_token_preflight.py` — a stdlib-only validator in
the proven #579 validator pattern (argparse CLI, `main(argv=None) -> int`,
`raise SystemExit(main())`, repo root from `__file__`) with two modes:
offline (schema + date evaluation, wired into the quality-integration static
job) and `--probe` (reads the credential env var named by an api-zen entry's
pointer and performs one Bearer-authenticated `GET https://api.github.com/zen`
with a no-redirect opener, 10s timeout, bounded retry on transient failures).
Module seams (`load_inventory`, `evaluate_dates`, `fetch_status`,
`probe_token`, `main`) keep the probe transport patchable so the whole
behaviour is testable with zero network. (3) Schedule:
`.github/workflows/token-preflight.yml` runs the probe weekly (cron
`17 9 * * 2` UTC Tuesdays) on main only, with `contents: read`, pinned
actions, no secrets, and a sanitized GITHUB_STEP_SUMMARY section on PASS and
FAIL. The runbook (`docs/operations/TOKEN_PREFLIGHT.md`) carries scope,
schedule, alarm ownership, marker interpretation, remediation, limits and the
activation path.

## Decisions

- **Inventory is pointer-only, never secret-bearing**: the inventory stores
  where a credential lives (env var name or absolute on-box path) and its
  expiry/review metadata — never the value. The validator rejects
  credential-shaped strings (token prefixes, key material, JWT shapes,
  Authorization assignments) in any string field, naming record index and
  field without echoing content, so a pasted secret can never merge.
- **Probe mode is opt-in per token (`probe: none` vs `probe: api-zen`)**:
  today's three identities are all `probe: none` for cause — the worker
  quality-read token lives only on the box (CI cannot read the host file; its
  liveness signal is the on-box GET /zen command), the connector token has no
  verified storage location, and SYNC_PR_TOKEN is proven 401 over REST while
  git push works (issue #558), so a REST probe would be permanently red. The
  probe machinery ships fully tested so activation is a one-entry flip plus a
  workflow env mapping (documented in the runbook).
- **Offline default, probe behind an explicit flag**: the same binary serves
  the PR gate (offline: schema + dates, zero network, zero env reads) and the
  scheduled probe. `--today` exists for deterministic date testing and is a
  usage error combined with `--probe` (probe mode always evaluates today's
  UTC date).
- **Fail-closed transport**: redirects are refused via a custom handler (a
  followed redirect would forward the Bearer credential), the response is
  always closed (ResourceWarning discipline), 401/403 fail without retry,
  5xx/network/timeout retry to 3 attempts total (1s then 2s), and bodies,
  headers, raw exceptions and credential values are never printed.
- **Summary is sanitized and always written in probe mode**: on PASS and FAIL
  the step summary carries markers, the UTC evaluation date, the 21-day
  threshold, the coverage note and the runbook link; an unwritable summary
  path fails closed (SUMMARY-WRITE-FAILED + exit 1) rather than silently
  dropping the operator-facing evidence.
- **Gradual strict tier continues**: the new validator joins
  validate_api_dependency_lock.py in the ruff strict invocation and gets its
  own `strict = True` mypy section — one more module under the #579 protocol,
  never mass-enabled.

## Affected contours

- CONTROL_PLANE — .github/workflows/token-preflight.yml (new scheduled job),
  .github/workflows/quality-integration.yml (offline step + ruff/mypy
  listings), scripts/quality/validate_token_preflight.py,
  scripts/quality/mypy.ini, data/contracts/token-inventory-v1.json: all
  classified CONTROL_PLANE by data/contracts/change-control-policy-v1.json.
- VPS — NOT affected: api/**, frontend/**, deploy/vps/** untouched.
- Ubuntu worker/relay — NOT affected: worker/** and deploy/worker/** are
  untouched (the worker token is only *described* in the inventory; its
  liveness signal remains the on-box check).
- specs/** and docs/** are documentation contours.

## Validation

- RED-first: tests/test_token_preflight.py carried 46 tests on the base
  (test-protected) and failed 12 + errored 33 there (observed,
  /tmp/opencode/583/red-evidence.txt); those 46 must pass on the delivered
  tree without edits. After peer review the module carries 56 tests (46
  original + 10 date-matrix/aggregation/stream-routing tests).
- Focused suite: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_token_preflight.py' -v` — OBSERVED "Ran 56 tests ... OK",
  zero skips (re-observed on the delivered tree during reconciliation).
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'` — OBSERVED "Ran 1331 tests ... OK (skipped=17)".
- Gates: validate_workflow_policy.py, validate_repo.py,
  validate_contracts.py, validate_quality_contracts.py, validate_sdd.py all
  exit 0; base ruff clean; ruff strict over both validators clean; mypy
  strict over the module clean (mypy 1.18.2, matching the CI pin, was
  scratch-installed to /tmp/opencode/toolcache/mypy on the delivery host and
  OBSERVED "Success: no issues found in 1 source file" for the new module;
  CI remains the standing mypy oracle; the module is fully annotated
  regardless).
- Validator: `python3 scripts/quality/validate_token_preflight.py --today
  2026-11-03` exits 0 on the committed inventory (offline, PASS line).

## Runtime feedback

- CI is the runtime for this change. The offline step runs in every PR/push
  Quality run; the scheduled probe runs weekly on main. With the current
  inventory the scheduled run performs no network I/O; a future api-zen
  activation adds exactly one authenticated GET per entry (bounded retries).
  A red scheduled run is the alarm: it fails the job, notifies the repo owner
  through GitHub's failed-scheduled-run notifications, and writes the
  sanitized step summary. The validator performs no repository write and no
  host mutation; the only artifact it produces is the step summary section.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: the inventory is pointer-only (env names and absolute paths, never values); the validator rejects credential-shaped strings in any field without echoing content; probe output prints markers and env var names only; the workflow references no secrets; tests assert a runtime-built synthetic credential never appears in stdout, stderr or the summary | Validation: leak assertions in the probe/summary unit tests plus the workflow no-secrets test, all observed green | Residual risk: a future api-zen activation introduces a secrets. env mapping by design; that change deliberately amends the pinned workflow test in the same reviewed PR (activation path documented in the runbook) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: the dead-man risk of scheduled monitoring — GitHub disables workflow schedules after 60 days without repo activity, so the probe can stop silently; the runbook mandates a monthly calendar check that the latest scheduled run is recent, documents alarm ownership (repo owner) and requires the owner to confirm actual notification delivery once (a red run alone is not proof of alerting) | Validation: runbook sections reviewed against the workflow schedule; workflow_dispatch available for manual verification | Residual risk: if the monthly calendar check is skipped, coverage silently lapses until the next manual interaction (accepted; documented in the runbook limits section) | Owner: repo owner | Status: ACCEPTED
- RISK-003 | Category: TECH | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: probe:none entries have no live CI coverage by design; the coverage matrix in the runbook states exactly what each signal covers (expiry-only, push-failure surfacing, on-box probe) so absence of a red probe is never mistaken for proof of liveness; UNKNOWN-EXPIRY warns non-failingly so the gap stays visible in every run | Validation: coverage matrix reviewed against the inventory; UNKNOWN-EXPIRY marker pinned by the date-evaluation contract | Residual risk: a revoked probe:none token is detected only by its out-of-band signal (e.g. sync-merged-tasks push failures), which may lag the revocation | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: date boundaries (EXPIRED / EXPIRY-DUE at 21 days / REVIEW-DUE incl. overdue / UNKNOWN-EXPIRY) are pinned by unit and subprocess tests with --today fixtures; strict YYYY-MM-DD parsing rejects malformed dates fail-closed | Validation: the earlier "focused suite date tests observed green" claim predated the date tests (peer-review finding) and is superseded by the observed state — the date matrix is pinned by 10 added tests (TokenPreflightDateMatrixSubprocessTests: 8 subprocess --today boundary tests incl. the inclusive day-21 upper bounds; TokenPreflightAggregationUnitTests: an expired-date failure does not suppress the probe finding; TokenPreflightStreamRoutingUnitTests: EXPIRED routes to stderr while UNKNOWN-EXPIRY and NOT-PROBED stay on stdout); focused suite OBSERVED "Ran 56 tests ... OK" and full battery OBSERVED "Ran 1331 tests ... OK (skipped=17)"; mutation bite-proof: the inclusive-boundary test fails against a mutated <= -> < copy (evidence: /tmp/opencode/583/mutation-check/) | Residual risk: none identified beyond the accepted unknown-expiry warning semantics | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: committed inventory contract — file exists, schema + root keys, exactly the three contracted identities with exact field values | Level: unit | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightInventoryTests
- TEST-002 | Covers: offline CLI surface via subprocess — valid inventory PASS/exit 0, default inventory PASS, malformed inventory FAIL/exit 1, --today+--probe usage error exit 2 with a usage message | Level: integration | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightValidatorOfflineSubprocessTests
- TEST-003 | Covers: offline mode purity — fetch_status never called, credential env var never read | Level: unit | Priority: P0 | Evidence: tests/test_token_preflight.py::test_offline_never_calls_fetch_status_or_reads_credential_env
- TEST-004 | Covers: probe mode — PROBE-OK, PROBE-UNAUTHORIZED/PROBE-FORBIDDEN no-retry, 5xx and network retry (3 attempts, sleeps 1s then 2s), MISSING-CREDENTIAL (unset/whitespace, zero requests), INVALID-CREDENTIAL (no normalization, no send), NOT-PROBED for probe:none, no credential leakage | Level: unit | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightProbeUnitTests
- TEST-005 | Covers: GITHUB_STEP_SUMMARY written on PASS and FAIL with the runbook link; unwritable path -> SUMMARY-WRITE-FAILED + exit 1 | Level: unit | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightSummaryUnitTests
- TEST-006 | Covers: fetch_status transport — exact URL/Bearer/User-Agent/timeout, redirect rejection via a custom handler, response closure, 401/500 statuses, network error never 200 | Level: unit | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightTransportTests
- TEST-007 | Covers: workflow structure (token-preflight.yml) and quality-integration.yml edits via yaml.safe_load; mypy.ini strict section | Level: integration | Priority: P0 | Evidence: tests/test_token_preflight.py TokenPreflightWorkflowTests + TokenPreflightQualityIntegrationTests + TokenPreflightMypyTests
- TEST-008 | Covers: generic workflow policy accepts every workflow including the new one | Level: integration | Priority: P0 | Evidence: tests/test_token_preflight.py::TokenPreflightWorkflowPolicyTests + observed validate_workflow_policy.py exit 0
- TEST-009 | Covers: no regression — full repository battery stays green with the new module and workflow | Level: integration | Priority: P0 | Evidence: discover battery exact counts in the completion gate

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none required — the admitted scope was implemented as specified;
  the RED suite turned GREEN without any test edit and no production learning,
  architecture pivot or material scope change surfaced during implementation.
