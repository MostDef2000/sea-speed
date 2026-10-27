# Plan — Issue #398 wave 2

- Issue: #398
- Specification: specs/398-wave2/spec.md

## Architecture

Follow the wave-1 house model: RB (execute the real thing) > SS (structured parse:
`ast.parse` / `yaml.safe_load` / JSON / env-file) > SP (STATIC_POLICY pins kept verbatim with
justification) > redundant retirement (only with a recorded same-commit executed twin). One new
support module (`tests/support/frontend_html.py`, sibling of `tests/support/frontend_node.py`)
reuses the established node-exec pattern; Python AST conversions reuse the generic helpers in
`tests/support/worker_source.py`. No new frameworks or patterns.

## Decisions

- **Comment-only verifier anchors**: the deploy workflow files reference the verifier scripts only
  in comments; the real carrier of the exact-release verify chain is the shared composite action
  `.github/actions/verify-exact-release/action.yml` — structured order/flag asserts point there.
- **YAML 1.1 `on:`**: `yaml.safe_load` parses a bare `on:` key as boolean `True`; trigger reads go
  through `workflow.get(True, workflow.get("on", {}))`.
- **Transaction-stage anchors**: tolerant order checks anchor on failure linkage
  (`abort_activation` / `;then`) — bare command regexes match helper-function internals.
- **Behavioral identification over names**: the frontend harness identifies the watchdog by cadence
  and re-fetch behavior, never by function name (names are implementation details a pure refactor
  may change).
- **`string_constants` returns full constants** — substring membership via `any()`.
- **Legacy 704 seed is a deliberate test fixture** (documented in-test), not a config value.

## Site-mapping table (old → replacement)

| # | File | Classification | Action |
|---|------|----------------|--------|
| 1 | tests/test_vps_deploy_transaction.py | RB-clean | NO CHANGE (executes real deploy.sh; reads feed parsers) |
| 2 | tests/test_ubuntu_worker_installed_copy_refresh.py | SS + redundant | inventory array → structured (src,dst,mode) triple set; transaction order → tolerant regex anchors; sha256sum list → parsed; −3 retired (twins: executed refresh-failure/restore, hash-mismatch/restore, fresh-host-install); SP never-delete ban verbatim |
| 3 | tests/test_ubuntu_worker_runtime_hash_lock.py | SS + redundant | pip download/install → normalized invocation parse with flag sets + order; guard order → tolerant positions (SP "inputs are invalid" kept — no executed twin); −1 retired (runtime-id payload → executed formula + byte-flip twins); resolver workflow → yaml.safe_load; secrets:/deploy-authorized bans verbatim |
| 4 | tests/quality/test_quality_architecture.py | SS + RB + redundant | workflow admission → yaml.safe_load (job env dict, environment, require_allow, step names); verify-chain order → shared action; verify_source_protection.py → AST; tombstone → EXECUTED rc 2; caddy-boundary presence/order pins retired (executed deploy.sh twins in file 1), 5 SP bans verbatim |
| 5 | tests/test_ubuntu_worker_runtime_rebuild.py | RB + redundant | order-mirror structural test REPLACED by executed 11-sub-check matrix (check=<kind> for every verify_ready_runtime sub-check; fixture extended with 5 failing kinds); −2 retired (evidence markers → executed a/b/d; healthy path → executed (c) + issue-514 RUNTIME_CREATED); quarantine keeps 2 SP never-delete bans verbatim; root gate / verify order / stage order / #514 anti-dup pin verbatim SP |
| 6 | tests/test_ubuntu_worker_exact_updater.py | SP (T8b) | NO CHANGE (deploy transaction contract; abort wiring has no executed twin; documented sentinels) |
| 7 | tests/test_vps_auth_privilege_boundary.py | redundant | −1 retired (deploy-runtime_verified gate → executed deploy.sh twins: no manifest on pre-gate failure, rolled_back on post-mutation failure, runtime_verified on success, two gate sites); rest RB/SP-clean |
| 8 | tests/test_road_event_delivery.py | RB/SS-clean | NO CHANGE (AST-executes real post_analytics_event) |
| 9 | tests/test_api_state_transaction.py | RB-clean | NO CHANGE (fully behavioral) |
| 10 | tests/test_ubuntu_worker_shared_runtime.py | SP/SS (T8b-style) | NO CHANGE (json.load parses, executed --runtime-id-only, transaction markers) |
| 11 | tests/test_validate_sdd.py | SS-clean | NO CHANGE (reads feed mutation workflows; executes real validator) |
| 12 | tests/test_detection_runtime_optimization.py | SS + redundant | −1 retired (no-704 literals/flag text → executed legacy-resolution twin in file 15); road env example → structured KEY=VALUE parse; observed telemetry → AST string constants |
| 13 | tests/test_roi_normalization.py | SP (D-6/T8b analogy) | NO CHANGE (frontend wiring tags + deploy.sh migration markers are the contract) |
| 14 | tests/test_mediamtx_remediate_reader.py | SP (established style) | NO CHANGE (documented shell contract class; systemctl bans are policy) |
| 15 | tests/test_analytics_profiles_configure_drift.py | RB + AST | +1 executed legacy-HD twin (real configure run, 704×576 seed → HD + flags in water and road read-backs); `import analytics_profiles` pin → AST import check; SP absence pins + SystemExit/ERROR verbatim |
| 16 | tests/test_auth_session_frontend_contract.py | RB | NEW tests/support/frontend_html.py; road watchdog behavioral (15 s interval re-fetches identity, same-origin, population, identity-loss redirect); 3 wiring/SP tests verbatim |

## Affected contours

- Tests only: the 8 listed test files, tests/support/ (one new module), the demo test, this trio.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, scripts/**, .github/**, nginx/**,
  and the five wave-1 protected test files.

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in the session
  checkpoint /tmp/opencode/398-w2/checkpoint.md).
- Full battery: `python3 -m pytest tests/ -q` → 1160 passed / 4 skipped / 271 subtests in 43.24s
  (baseline 1167 / 4 / 262; cluster net −8 with recorded twins + demo +1; subtests +9).
- `python3 scripts/ci/validate_repo.py` → green, 784 files. `validate_sdd.py` → green for the
  trio after the orchestrator's staged-wave grandfather entry for prefix 398.
- Allowed-paths check: `git status` shows only tests/**, tests/support/**, specs/398-wave2/**.

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only change; runtime acceptance = exact-head CI
  green on the merge PR.
- RF-002: post-wave battery reports 1160 / 4 / 271; all deltas recorded in the tasks.md
  battery-delta ledger (retired assertion → covering executed twin, same commit).

## Risk profile

- Risk profile: NOT REQUIRED
- Executed harnesses are offline and deterministic (node stub DOM, tmp fixtures, no network); the
  executed classify matrix reuses the existing PIP/PY3/CHOWN stub harness — no new flake surface.
- Battery may only shrink by the redundancy ledger; every retirement cites its twin.
- Risk that a converted check becomes tautological is countered by the demo's inverted-mutation
  proof (dead-marker direction fails the converted check).

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every mapping-table action's focused run green (F2 14, F3 17, F4 8, F5 14 with 11 executed sub-checks, F7 15, F12+F15 18, F16 node-exec); SP pins byte-verbatim (peer-review enumeration, findings 1-2 corrected)
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: battery 1167/4/262 → 1160/4/271; battery-delta ledger in tasks.md maps every retired assertion to its recorded executed twin
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave2_demo.py — both directions with recorded inverted-mutation run (dead-marker direction fails the converted check)
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: full battery 1160 passed / 4 skipped / 271 subtests; validate_sdd + validate_repo green (CI-mode --event re-run after CI findings)
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git status shows only declared paths + the recorded validate_sdd.py grandfather-entry exception

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none — no production learning, no pivot, no material scope change (the two CI-admission fixes — NFR line-wrapping and the yaml guard for the stdlib-only property-fuzz job — stayed inside the wave-2 allowed paths and are recorded in the tasks.md ledger).
