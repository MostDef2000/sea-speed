# Plan — Issue #398 wave 8

- Issue: #398
- Specification: specs/398-wave8/spec.md

## Architecture

Follow the wave-1..7 house model: RB (execute the real thing) > SS
(structured parse/scan) > SP (STATIC_POLICY pins kept verbatim with
justification) > NO-CHANGE (recorded rationale). The wave-8 surface is the
cluster D residual: two workflow-YAML EXTRACTION helpers in
tests/test_deploy_freshness.py that sliced raw workflow text before
EXECUTING the extracted shell (the assertions themselves were already
executed/RB — only the extraction was brittle), plus one unannotated
byte-ban pair in tests/quality/test_quality_architecture.py.

Conversion approach (parsed step lookup semantics):

- `_extract_freshness_run_block`: `yaml.safe_load(source)`, walk `jobs` →
  each job's `steps`, return the `run` of the step whose `id ==
  "freshness"`. The YAML block scalar is already dedented by the parser —
  the manual min-indent stripping is deleted. Clip chomping (`run: |`)
  preserves the single trailing newline, so the returned script is
  byte-identical to the retired line-scan output for the real workflow
  (probed before implementation) and the executed tests stay green
  untouched. Meaningful AssertionErrors kept (adapted messages): no step
  with id 'freshness'; empty/missing run.
- `_extract_sync_staging_command`: parsed walk of ALL jobs → ALL steps'
  run texts; within each run text, scan LINES for
  `re.match(r"git add\b", line.strip())` (word-boundary semantics kept);
  collect the stripped lines; require EXACTLY ONE across the workflow
  (old message shape kept). The invariant is now scoped to executable step
  run texts: comment-only lines never match (they start with `#` after
  strip), and non-run YAML regions are out of scope — the old whole-file
  regex false-failed on a non-executable `git add` mention at line start
  inside a note field (probed: old helper raises, parsed walk unaffected).
- Why SP-keep for the byte bans (test_windows_package_workflow_is_retired):
  byte-absence of the retired Windows fallback markers IS the contract — a
  parsed-structure absence check would be WEAKER (the markers could survive
  in YAML comments, which `yaml.safe_load` drops); the tombstone assertFalse
  (package-worker.yml absence) already covers file absence. Same verdict
  family as the wave-2 STATIC_POLICY keeps at L95/102/110.

## Decisions

- **Extraction hardening, not assertion churn**: both usage sites (L148
  freshness block → executed in the git fixture; L244 staging command →
  executed via shell) and every assertion stay byte-identical — only the
  two module-level helpers change. The tests were already executed twins;
  the brittleness lived in the extraction slice.
- **Unconditional `import yaml`** at module top (wave-5 pattern:
  tests/test_quality_status.py, tests/test_autonomous_execution_policy.py);
  the HAS_YAML/skipUnless guard stays unique to
  tests/quality/test_quality_architecture.py (stdlib-only CI job) and is
  NOT copied into test_deploy_freshness.py.
- **Trailing-newline normalization: none needed**: the real workflow uses
  `run: |` (clip chomping), whose parsed value ends with exactly one
  newline — byte-identical to the old helper's `block + "\n"` (probed
  before implementation). Had the workflow used `|-`/`|+`, normalization
  would go in the HELPER, not the tests (trap checked; not triggered).
- **Demo asserts the real module helpers**: the demo imports
  `_extract_freshness_run_block` from tests.test_deploy_freshness (wave-5
  import pattern) — no mocking — and fails under the retired line-scan
  implementation (the Direction-A equality breaks on the reformatted
  variant). The retired helper is inlined as a verbatim documented copy
  (demo-twin-копия — задокументированный паттерн, дрейфа нет; documented
  like the wave-5 demo mapping row in specs/398-wave5/plan.md) for the
  brittleness direction only.
- **The outside-D residual is inventoried, not converted**: the ~200
  candidate pins in 14 files were never adjudicated by waves 1–7;
  converting them is a material change vs the approved six-field scope →
  recorded as out of scope pending owner decision (wave-9 candidate or
  documented closure).

## Site-mapping table (old → replacement)

| File | Site | Verdict | Twin / rationale |
|------|------|---------|------------------|
| tests/test_deploy_freshness.py | `_extract_freshness_run_block` (L58–81 line-scan: `id: freshness` anchor, `run: \|` scan, `^      - name:` terminator, manual dedent) | CONVERT | parsed step lookup: `yaml.safe_load` → jobs → steps → `id == "freshness"` → `step["run"]`; the parser dedents the block scalar; clip chomping keeps the trailing newline (byte-identical, probed); adapted AssertionErrors; wave-8 conversion comment in-code |
| tests/test_deploy_freshness.py | `_extract_sync_staging_command` (L228–232 whole-file regex `(?m)^\s*(git add\b.*)$`) | CONVERT | parsed walk ALL jobs → ALL steps' run texts, line scan `re.match(r"git add\b", line.strip())`, exactly-one invariant with the old message shape; comment-only lines and non-run regions no longer match (strictly stronger scoping); wave-8 conversion comment in-code |
| tests/test_deploy_freshness.py | usage sites L148/L244, all test methods, env overrides L31–36, FreshnessFixture, module docstring | NO-CHANGE | executed assertions and fixtures byte-identical; docstring says "extract" (not "regex") — stays accurate unchanged |
| tests/quality/test_quality_architecture.py | L205–206 raw assertNotIn (`windows_worker_required`, `windows-worker-fallback`) in test_windows_package_workflow_is_retired | SP-KEEP + annotation | STATIC_POLICY comment added above the pair (byte-absence IS the contract; parsed-absence would let markers survive in comments; tombstone covers file absence); assertions and the L203 tombstone assertFalse byte-identical; L61–63 raw reads + L95/102/110 already adjudicated wave 2 |
| tests/test_398_wave8_demo.py | (new) one-test two-direction demo | SS | Direction A reformat-equivalence (comment insertion + steps reindent + step reorder → identical extraction, equal to expected script bytes); Direction B old-approach brittleness (verbatim retired line-scan copy raises or returns different bytes on the same reformat); imports the real module helpers |

## Outside-D residual inventory (NOT converted; wave-9 candidate or documented closure — owner decision)

| File | Residual (count / site) | Verdict | Notes (verification status) |
|------|-------------------------|---------|------------------------------|
| tests/test_ubuntu_worker_deploy_authorized.py | ~37 | RESIDUAL — verified raw | setUp self.source = SCRIPT.read_text() + assertIn on deploy-authorized.sh shell contract (L16, 23–28 spot-verified) |
| tests/test_vps_nginx_zerotier_startup.py | ~32 | RESIDUAL — verified raw | HELPER/DROPIN raw pins on shell scripts (L127–135 spot-verified: FIXED_ADDRESS/MAX_ATTEMPTS/INTERVAL_SECONDS) |
| tests/test_camera1_h264_freshness_watchdog.py | ~18 | RESIDUAL — heuristic count | per-file verification pending |
| tests/test_393_control_token_separation.py | ~23 | RESIDUAL — verified raw (outside #398 waves; #396 marker) | systemd unit source pins L204–212+ |
| tests/test_ubuntu_worker_ai_supervision.py | ~17 | RESIDUAL — verified raw | L21–34 |
| tests/test_ubuntu_worker_rollback.py | ~13 | RESIDUAL — heuristic count | — |
| tests/test_water_recall_ubuntu_ipc.py | ~14 | RESIDUAL — heuristic count | — |
| tests/test_ubuntu_authentik_blueprint_reconcile.py | ~11 | RESIDUAL — verified raw | shell script pins L107–118 |
| tests/test_vps_deploy_origin_health.py | ~9 | RESIDUAL — heuristic count | — |
| tests/test_sea_speed_auth_cutover_local_ip.py | ~6 | RESIDUAL — heuristic count | — |
| tests/test_ubuntu_worker_compatibility.py | ~5 | RESIDUAL — heuristic count | — |
| tests/test_worker_outbox_delivery.py | 4 | SP-CLASS (documented in-file) | fail-closed installer/artifact list membership; docstring declares "source-text pins" deliberately (L1143–1147) |
| tests/quality/test_exact_artifact_convergence.py | 2 | TO-VERIFY (wave 9) | L77–78 pins on validator source; convergence markdown pins are the executable ceiling (waves 5/6 canon) |
| tests/test_sea_speed_auth_v1.py | ~20 (compose/stage subset, L372–395) | PARTIAL RESIDUAL — verified | compose.yml pins (image tag count, loopback bind, no docker.sock, no :latest) convertible to yaml.safe_load; stage.sh pins are shell-contract SP-class; wave-6 annotations cover doc sections only (L495/515/552) |

## Adjudicated NO-CHANGE (verified 2026-10-30, not residual)

| File | Residual (count / site) | Verdict | Notes |
|------|-------------------------|---------|-------|
| tests/test_ubuntu_worker_exact_updater.py | ~39 | ADJUDICATED wave 2 | mapping row 6: SP T8b, NO CHANGE — deploy transaction contract, documented sentinels |
| tests/test_sea_speed_rbac.py; tests/test_auth_session_identity.py; tests/test_worker_{roi,live,tracking,transport,crossings}_module.py | — | NO-CHANGE-PARSED | ast.parse SS twins |
| tests/test_github_actions_connector_contract.py | — | ADJUDICATED wave 5 | json-parsed / module-executed / prose ceiling |
| tests/test_mediamtx_activate_identity.py | ~51 heuristic | NO-CHANGE-EXECUTED | pins on result.stdout of executed script — heuristic false positive |
| tests/test_camera_preview_gallery.py; tests/test_frontend_contract.py | — | ADJUDICATED wave 4 | — |
| tests/test_auth_logout_contract.py; blueprint reconcile YAML tests | — | NO-CHANGE-PARSED | BlueprintLoader yaml.load |
| tests/test_delivery_contract_convergence.py | — | NO-CHANGE | markdown prose ceiling (wave 5) + parsed router twin |
| tests/test_sea_speed_auth_v1.py nginx/renderer sections | — | NO-CHANGE-EXECUTED | rendered output via executed renderer |

## Affected contours

- Tests only: tests/test_deploy_freshness.py (helper bodies + import),
  tests/quality/test_quality_architecture.py (annotation comment), the new
  demo, this trio — plus the recorded one-line grandfather entry in
  scripts/ci/validate_sdd.py.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, .github/**,
  nginx/**, docs/**, contracts/**, tests/support/** (byte-identical), and
  all wave-1..wave-7 test files except the two adjudicated above
  (byte-identical).

## Validation

- Focused: `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w8/pytest-tmp tests/test_deploy_freshness.py
  tests/quality/test_quality_architecture.py tests/test_398_wave8_demo.py
  -q` → OBSERVED 15 passed in 1.30s (6 freshness + 8 architecture + 1 demo).
- Full battery: `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w8/pytest-tmp tests/ -q` → OBSERVED 1231
  passed / 2 skipped / 306 subtests in 77.08s (base 1230 / 2 / 306 on
  4bde0e6, orchestrator-provided baseline; identity 1230 + 1 demo method).
- Mutation evidence (tmp copies under /tmp/opencode/398-w8/mutations/, never
  in-repo; env-override runs): (a) comment line in the freshness run region
  → 6 passed (parsed run text identical to the real workflow, probed);
  (b) steps list reindented → 6 passed (run text identical, probed);
  (c) second `git add` inside a run block → 1 failed with exactly
  `AssertionError: expected exactly one git add staging command in sync
  workflow, got ["git add -- ':(glob)specs/*/tasks.md'", "git add --
  ':(glob)specs/*/plan.md'"]`; (d) `#`-comment containing `git add` →
  1 passed. CC-1 records the probed correction to the work order's (d)
  parenthetical.
- `python3 scripts/ci/validate_sdd.py` → PASS with the trio + the
  `398-wave8` grandfather line.
- ruff: `python3 -m ruff check --config scripts/quality/ruff.toml` clean on
  every changed file.
- Allowed-paths check: `git status` shows only the two adjudicated test
  files, the demo, specs/398-wave8/** and scripts/ci/validate_sdd.py.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE change (tests + one
  validator line); runtime acceptance = exact-head CI green on the merge PR.
- RF-002: post-wave cluster 15 passed (counts flat vs base + demo 1); the
  battery-delta ledger in tasks.md records the +1 with the demo method name;
  both converted helpers are module-level functions (0 test-count delta in
  the two converted files).

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: focused run over the two cluster files + demo → 15 passed; the plan.md mapping table adjudicates both files (CONVERT / SP-KEEP + annotation)
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: full battery OBSERVED 1231 passed / 2 skipped / 306 subtests in 77.08s (base 1230 / 2 / 306 on 4bde0e6; identity 1230 + 1 demo method); tasks.md ledger maps each converted/annotated site to its twin/rationale
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: the outside-D inventory table in plan.md is complete (14 residual rows + 8 adjudicated NO-CHANGE rows) with per-file verdict class and honest verification markers ("verified raw" vs "heuristic count" vs adjudicated)

## Correct-course check

Course correction CC-1 — the work order's mutation-(d) parenthetical ("old
regex would have matched it") is imprecise for `#`-prefixed YAML comments:

- Trigger: NONE
- Issue impact: NONE — same admitted scope; the mutation was run as specified.
- Specification impact: none — the helpers and demo are unaffected.
- Plan impact: the Validation section records the probed reality: the old
  regex was already blind to `#`-prefixed comment lines (the `#` breaks the
  `^\s*git add` anchor); its real weakness was the whole-file scan scope —
  a non-executable `git add` mention at line start inside a note field made
  the old helper RAISE the exactly-one AssertionError (false failure on
  harmless documentation), while the parsed step-run walk is unaffected
  (both probed this session).
- Tasks impact: T-5 evidence records the probe; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — findings recorded honestly per the work order
  ("note this in findings").
