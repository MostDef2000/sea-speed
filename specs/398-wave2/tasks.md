# Tasks — Issue #398 wave 2

- Issue: #398
- Specification: specs/398-wave2/spec.md

## Delivery tasks

- T-1: RECON + baseline: 1167 passed / 4 skipped / 262 subtests; validate_sdd + validate_repo green (base 7ff2194).
- T-2: F2 installed-copy refresh — SS conversions (inventory triples, transaction order, command list) + 3 redundant retirements (executed twins in same file). DONE.
- T-3: F3 runtime hash lock — pip invocation parse, guard-order SS, resolver workflow yaml.safe_load, 1 redundant retirement. DONE.
- T-4: F4 quality architecture — workflow yaml.safe_load (real carrier: shared verify action), verifier AST, tombstone executed, caddy-boundary redundant pins retired, SP bans kept. DONE.
- T-5: F5 runtime rebuild — executed 11-sub-check classify matrix replaces the order-mirror pin; 2 redundant retirements; quarantine SP bans kept. DONE.
- T-6: F7 auth privilege boundary — 1 redundant gate-order retirement (executed deploy.sh twins). DONE.
- T-7: F12+F15 — executed legacy-HD twin (704 seed → HD + flags), env-file SS parse, AST string-constants, AST import checks. DONE.
- T-8: F16 — NEW tests/support/frontend_html.py; road watchdog behavioral via node-exec of the page's real inline scripts; SP wiring tests verbatim. DONE.
- T-9: Demo tests/test_398_wave2_demo.py — two-direction proof with inverted mutation. DONE.
- T-10: Full battery + validators + allowed-paths self-check. DONE.

## Completion gate

- Full battery `python3 -m pytest tests/ -q` green: observed 1160 passed / 4 skipped / 271
  subtests (baseline 1167 / 4 / 262; cluster net −8 with recorded twins, demo +1).
- `validate_repo.py` green (784 files); `validate_sdd.py` green for this trio after the
  orchestrator's staged-wave grandfather entry for prefix 398.
- Demo inverted-mutation proof observed: `python3 -m pytest tests/test_398_wave2_demo.py -q` →
  1 passed (refactor tolerance AND dead-marker intolerance; real-page sanity).

## Requirements traceability

- AC-001 | Task: T-1, T-2, T-3, T-4, T-5, T-6, T-7, T-8 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-2, T-3, T-4, T-5, T-6, T-7 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-9 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-10 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-10 | Evidence: TEST-004 | Coverage: COVERED
- AC-006 | Task: T-10 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → mapping table in plan.md (all 16 files adjudicated; every removed
assertion has a twin or SP retention) + the battery-delta ledger below; R-2 → SP pins kept
verbatim carry in-code justification comments (T8b / D-6 / #514 precedents); R-3 → the demo's
inverted-mutation proof recorded below; R-4 → no production file touched (git status limited to
tests/**, tests/support/**, specs/398-wave2/** + the recorded validate_sdd.py exception); R-5 →
executed harnesses offline; PyYAML already CI-pinned (battery jobs) and loudly skipped in the
stdlib-only property-fuzz job; node exec deterministic; R-6 → battery green with per-file deltas
accounted; both validators green.

## Battery-delta ledger (cluster net −8; demo +1; observed 1167→1160, subtests 262→271)

| File | Delta | Retired assertions → covering twin (same commit) |
|------|-------|--------------------------------------------------|
| F2 test_ubuntu_worker_installed_copy_refresh.py | −3 | prior-bytes backup → executed test_install_failure_fails_closed_and_restores_prior_bytes; hash parity → executed test_hash_mismatch_fails_closed_and_restores_prior_bytes; fresh-install idempotency → executed test_fresh_host_installs_every_inventory_entry_from_release |
| F3 test_ubuntu_worker_runtime_hash_lock.py | −1 | runtime-id payload pins → executed test_runtime_id_v2_formula_is_deterministic + test_any_single_byte_change_moves_the_runtime_id; marker pins (graph-empty / PASS runtime_lock_validated) → executed twins in this file + rebuild (c) stdout |
| F5 test_ubuntu_worker_runtime_rebuild.py | −3 | evidence markers → executed scenarios (a)/(b)/(d); healthy-path emissions → executed (c) exact stdout + issue-514 RUNTIME_CREATED; order-mirror structural test → REPLACED by executed 11-kind check=<kind> matrix |
| F7 test_vps_auth_privilege_boundary.py | −1 | deploy-runtime_verified gate order → executed deploy.sh twins in test_vps_deploy_transaction.py (no manifest on pre-gate failure; rolled_back on post-mutation failure; runtime_verified on success; two gate sites) |
| F12 test_detection_runtime_optimization.py | −1 | no-704 literals/flag text → executed test_legacy_resolution_dimensions_are_forced_to_hd (F15, same commit) |
| F15 test_analytics_profiles_configure_drift.py | +1 | new executed legacy-resolution twin (additive) |
| F4, F16 | 0 | converted in place; count unchanged |

Peer-review corrections (adversarial review, 2026-10-27; both verified by orchestrator diff + focused runs):
- F2 required-command gate: initial conversion pinned only `sha256sum ∈ parsed list`; restored to
  full 10-command set equality (order-tolerant) — no assertion narrowed (review finding 1).
- F3 `grep -v '^--'` pin: input argument `"$lock_file_path"` restored to the pin (review finding 2);
  pin is byte-verbatim to origin/main again.
- F12/F15 ledger unchanged (narrowing already recorded via executed legacy-HD twin).

## Demo — inverted-mutation proof (observed output)

`python3 -m pytest tests/test_398_wave2_demo.py -q` → **1 passed**:

- Direction A (refactor tolerance): tmp copy of the real road page with
  `const SESSION_WATCHDOG_MS = 15000;` (reformatted) and internals renamed
  (`loadSessionIdentity` → `refreshTrustedIdentity`) → converted executed check PASSES; the
  retired text pins would fail it (2 of 4 markers gone).
- Direction B (dead-marker intolerance): tmp copy keeping all four retired markers byte-for-byte
  with a `setInterval` interceptor re-cadencing the watchdog 15000→60000 ms → retired pins PASS
  (the false-green), converted executed check FAILS with
  `FAIL: no 15000 ms interval registered (session watchdog missing)`.
- Sanity: the real page satisfies the converted check.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — waves 3+ of #398 remain in the issue backlog; #478 owner-lane items live on the issue; CI-admission findings recorded in the tasks.md ledger
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED with prose risks recorded
- [x] Waivers resolved or current — no waivers

Wave record: all 16 cluster files adjudicated (mapping table in plan.md); battery delta −8 (+1 demo)
with recorded twins, no assertion weakened or skipped; demo proves the conversion property in both
directions; validate_repo.py green; validate_sdd.py green for the trio (staged-wave grandfather
entry for prefix 398 added by the orchestrator).

