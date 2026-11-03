# Token pre-flight runbook

Status: Active

Operational runbook for the repo-owned token pre-flight probe (issue #583):
the inventory `data/contracts/token-inventory-v1.json`, the validator
`scripts/quality/validate_token_preflight.py`, the weekly workflow
`.github/workflows/token-preflight.yml`, and the offline Quality-gate step in
`.github/workflows/quality-integration.yml`.

## Scope and inventory

The inventory is the single repo-owned record of GitHub credentials the
delivery pipeline depends on. It stores metadata only — kind, expiry status,
review date, probe mode, and a credential *pointer* (an env var name or an
absolute on-box path). No credential value is ever stored in the repository.

Coverage matrix (the three contracted identities):

| Token | Kind | Expiry | Probe | CI coverage | Out-of-band signal |
|---|---|---|---|---|---|
| `sea-speed-worker-quality-read` | classic | no-expiry, semi-annual review (next 2027-04-14) | none | date/review tracking only | on-box `GET /zen` liveness command documented in INFRASTRUCTURE.md; the token lives only at `/etc/sea-speed/github-read-token`, which CI cannot read |
| `sea-speed-opencode-connector` | classic | 2026-12-31 | none | expiry tracking only | owner calendar rotation reminder due by 2026-12-24; storage location unverified — confirm during rotation |
| `SYNC_PR_TOKEN` | fine-grained (inferred) | unknown | none | none from CI | revocation is loudly surfaced by sync-merged-tasks push failures; expiry lookup is an owner lane |

`github.token` (the workflow-provided token) is deliberately excluded: it is
ephemeral, rotation-free, and scoped per run — it cannot expire in a way this
probe could detect, and it is not an operator-managed credential.

## Schedule and manual execution

- Scheduled: cron `17 9 * * 2` — every Tuesday 09:17 UTC — via
  `.github/workflows/token-preflight.yml`, guarded to `refs/heads/main` only
  (the job is skipped on every other ref).
- Manual run: GitHub UI → Actions → "Token pre-flight" → "Run workflow"
  (workflow_dispatch). The dispatch path also executes only when the ref is
  `main` because of the job-level `if` guard.
- The scheduled run executes
  `python scripts/quality/validate_token_preflight.py --probe`: schema and
  date evaluation for every entry, plus a live `GET https://api.github.com/zen`
  probe for every entry marked `probe: api-zen` (none today — see Activation
  path below).
- Local offline check (no network, no credential env reads):
  `python scripts/quality/validate_token_preflight.py --today YYYY-MM-DD`.

## Alarm ownership

The repo owner owns the alarm. A failing scheduled run surfaces three ways:

1. GitHub's failed-scheduled-run notification email to the repo owner
   (watch/failure-notification settings for the repository);
2. the red run on the Actions tab;
3. the sanitized `## Token pre-flight` section appended to the run's step
   summary (markers + UTC date + threshold + runbook link; never credential
   values).

## Notification setup and acceptance

A red run alone is NOT proof of alerting. The owner must confirm, at least
once after activation, that the failed scheduled run actually produced a
notification they received (email/watch settings). Acceptance procedure:
after merge, dispatch the workflow once on main with a deliberately failing
input (or wait for a real failure), and verify the owner-visible notification
arrives. Until that confirmation exists, assume the alarm is unproven.

## Marker interpretation

Every finding line is `<MARKER>: <token-name> <short safe detail>`; errors go
to stderr, info/warnings to stdout; the final line is exactly
`TOKEN-PREFLIGHT PASS` or `TOKEN-PREFLIGHT FAIL` (exit 0/1; 2 = usage error).

- `OK` — dates are valid and outside the 21-day warning window.
- `EXPIRED` — expiry date is in the past (failing).
- `EXPIRY-DUE` — expiry falls within the next 21 days (failing).
- `REVIEW-DUE` — review date is due within 21 days or overdue (failing).
- `UNKNOWN-EXPIRY` — expiry is unknown; non-failing warning until the owner
  completes the expiry lookup (SYNC_PR_TOKEN today).
- `NOT-PROBED` — entry has `probe: none`; coverage is documented, not live.
- `PROBE-OK` — the /zen probe returned 200.
- `PROBE-UNAUTHORIZED` — 401; the credential is revoked or wrong. No retry.
- `PROBE-FORBIDDEN` — 403 (missing scope or blocked). No retry.
- `PROBE-UNREACHABLE` — network/timeout failure persisted across 3 attempts.
- `PROBE-SERVER-ERROR` — 5xx persisted across 3 attempts (sleeps 1s then 2s).
- `PROBE-FAILED` — any other unexpected status (incl. a refused redirect).
- `MISSING-CREDENTIAL` — the env var named by the pointer is unset/blank;
  zero requests were made.
- `INVALID-CREDENTIAL` — the value carries surrounding whitespace or control
  characters; it is never normalized or sent.
- `SCHEMA-ERROR` — the inventory violates the schema (naming record index and
  field, never content).
- `SUMMARY-WRITE-FAILED` — GITHUB_STEP_SUMMARY could not be written (exit 1).

REST-401-vs-push discrepancy (issue #558): `SYNC_PR_TOKEN` is proven to
return `401 Bad credentials` on REST/GraphQL calls while the same secret
successfully authenticates `git push` (see the sync-merged-tasks.yml comments
and live run 40281552508). A 401 from a REST probe against that credential is
therefore NOT evidence of revocation — this discrepancy is exactly why the
entry is `probe: none`; its revocation signal is the sync workflow's push
failures instead.

## Remediation

1. Rotate or review the credential locally (owner lane; credentials never
   enter chat, issues, or the repository).
2. Update the secret in GitHub settings (or the on-box file for host-only
   credentials), keeping the storage location in sync with the inventory
   pointer.
3. Update the inventory via a PR — pointer-only changes: new expiry/review
   dates, corrected pointer, note. Never paste credential values.
4. Re-run: dispatch the token-preflight workflow (or rely on the next
   scheduled run) and confirm the marker clears.

## Limits and dead-man risk

- No unattended rotation: the probe never rotates, replaces, or updates
  credentials; rotation is always a human step.
- No scope verification: the probe proves liveness (a 200 from /zen), not
  that `expected_scopes` are still granted.
- No host token live check: CI cannot read `/etc/sea-speed/github-read-token`;
  the worker token's liveness is only observable on the box.
- Dead-man risk: GitHub disables workflow schedules after 60 days without
  repository activity. Keep a monthly calendar reminder to check that the
  latest "Token pre-flight" scheduled run is recent; if the schedule was
  disabled, re-enable it and run a dispatch to verify end-to-end.

## Rollback

Revert the change (workflow + validator + inventory + Quality-gate wiring).
Restoring an older inventory file does NOT restore a revoked or expired
token — credential state lives outside the repository; rollback only restores
the monitoring itself.

## Activation path for REST-capable credentials

When a credential that is REST-capable becomes available as a repo secret,
activate live probing for it in one reviewed change:

1. Flip its inventory entry to `"probe": "api-zen"` and set
   `credential_pointer` to the env var name the validator should read
   (uppercase pattern, never `GITHUB_TOKEN`/`GH_TOKEN`).
2. Add the matching env mapping to the probe step in
   `.github/workflows/token-preflight.yml`
   (`env: <NAME>: ${{ secrets.<SECRET> }}`).
3. Amend the pinned workflow contract test
   (tests/test_token_preflight.py currently forbids `secrets.` references in
   token-preflight.yml) in the same change — the test suite is the
   consistency enforcement point between the inventory's probe modes and the
   workflow's env mappings, so the activation is deliberately a reviewed
   contract change, never a drive-by edit.
4. Confirm the first probe run is green and that a revoked-credential drill
   (optional, with a throwaway credential) surfaces PROBE-UNAUTHORIZED.
