# 470 — Plan

Specification: specs/470-water-envelope-hardening/spec.md

## Architecture

Single-module change in `api/app/live_feeds.py` (introduced by #396 wave 6): the water
validator's size check is wrapped in the same try/except pattern as the road validator.
No new modules, no seam changes, no route changes, no deploy manifest change (no new
files). Tests follow the established importlib pattern (no httpx/TestClient in the repo
test suite; the app boots against /opt state).

## Decisions

- D-1: guard scope is `except Exception` matching the road block byte-for-byte (TypeError
  and ValueError both caught) — parity over narrowness; wording "invalid json" identical.
- D-2: tests exercise the validators directly via importlib (test_camera1_live_replacement
  pattern), not route-level posting: repo tests are deliberately import-free of the app
  boot; the staying route bodies delegate their entire failure path to the validators
  (main.py:1073/:1111), so validator coverage is route-failure coverage.
- D-3: RED-first protocol — tests written and observed failing (water: TypeError from set
  at live_feeds.py:168 → 500) before the fix was applied.
- D-4: SSE generator `_json.dumps(env, ...)` at live_feeds.py:118/:189 stays unguarded:
  not reachable today (only validator-gated serializable envelopes are appended; server
  enrichment fields `_live_seq` int / `_received_at` str are serializable), pre-existing on
  both domains, outside this fix's parity scope — recorded as a residual in review and on
  the issue evidence.

## Affected contours

- VPS application code: `api/app/live_feeds.py` (behavior-visible only for malformed
  payloads: 500 → 400). Deploy manifest: unchanged. Frontend/worker/contracts: none.

## Validation

- RED-first: `python3 -m unittest tests.test_live_envelope_validators -v` — road ok, water
  ERROR (TypeError) before fix; 2/2 OK after.
- Battery: full suite Ran 910 OK (skipped=4) — delta exactly +2, zero other drift;
  validate_repo (674 files); validate_sdd; ruff; route table 61==61 (fingerprint untouched);
  focused neighbor run (new file + test_api_contract + test_393) 28 OK.
- Independent adversarial peer review: APPROVE (unanimous; static RED-first verification
  from base file + code-path trace; no test asserts 500 anywhere; scope guard exact).

## Runtime feedback

Post-deploy: health gate + authenticated route probe via the deploy workflow; behavior
change visible only as 400 instead of 500 for malformed water live payloads.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: byte-identical guard to the battle-tested road block; RED-first tests pin both validators | Validation: full battery 910/4 + peer review APPROVE | Residual risk: none beyond pre-existing generator-dumps latent (D-4, unreachable) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: no manifest change (no new files); deploy plumbing untouched; automatic rollback on failed gate | Validation: deploy-transaction suite green (23 tests) | Residual risk: standard band-A deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002 (both validators return 400 on non-serializable payload) | Level: unit | Priority: P0 | Evidence: tests/test_live_envelope_validators.py 2/2 OK; RED-first water case observed failing pre-fix
- TEST-002 | Covers: AC-005 (no regression) | Level: unit | Priority: P0 | Evidence: full battery Ran 910 OK (skipped=4); delta exactly +2
- TEST-003 | Covers: AC-002/AC-004 (route failure path delegation unchanged) | Level: unit | Priority: P1 | Evidence: focused neighbor run (test_api_contract + test_393 + new file) 28 OK

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: no repo change | Retry: on blocker resolution | Rollback: not applicable | Evidence: issue #470 + owner tails directive 2026-10-13
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: RED-first evidence recorded; fix withheld | Retry: after test repair | Rollback: not applicable | Evidence: water test observed failing (TypeError -> 500) before fix applied
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: uncommitted working tree | Retry: re-run extraction script | Rollback: git checkout of touched files | Evidence: single bounded commit 0248b13 on sdd/470-water-envelope-hardening
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: commit exists; merge withheld | Retry: fix and re-run battery | Rollback: not applicable | Evidence: battery 910/4; validate_repo 674; validate_sdd; ruff; route 61==61; peer review APPROVE
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: branch unmerged | Retry: after CI repair (empty commit; never --failed rerun) | Rollback: delete remote branch | Evidence: exact-green-head squash merge to main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: cosmetic only | Retry: manual | Rollback: not applicable | Evidence: branch cleanup post-merge
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deploy evidence gap on #470 | Retry: post-deploy comment | Rollback: not applicable | Evidence: deploy run URL + probe output recorded on #470
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous release re-activated | Retry: not applicable | Rollback: re-dispatch previous release SHA (owner confirmation) | Evidence: deploy-vps.yml content-guarded activation blocks; no manifest change this PR
