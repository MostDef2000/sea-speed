# Tasks — Issue #398 wave 5

- Issue: #398
- Specification: specs/398-wave5/spec.md

## Delivery tasks

- T-1: RECON + baseline: cluster 72 passed / 24 subtests on base 7a12da8 (repo 1203 / 2 / 300,
  orchestrator-observed); recon probes (YAML 1.1 parses a bare `on:` key as boolean True —
  trigger_of canon; deploy-ubuntu-worker.yml lines 37-51 COMMENT block carries the
  source-protection markers = key false-green; overlayfs refuses rename() of 0555 dirs;
  iter_strings/trigger_of/steps_of/run_text canon in test_autonomous_execution_policy.py).
  DONE.
- T-2: test_sync_tasks_md_flow.py — 2 raw pins retired (raw wf_text SYNC_PUSH_TOKEN pin +
  positional steps[3] env read) → parsed position-independent twin (push step located
  semantically; env GH_TOKEN + SYNC_PUSH_TOKEN exact values asserted on THAT step); run-text
  pins already parsed-derived (SS keeps); executed tests untouched. DONE (10 passed).
- T-3: test_deploy_freshness.py — NO-CHANGE (recon-verified: all 6 tests already execute
  extracted bash in git fixtures). DONE (6 passed, unchanged).
- T-4: test_github_actions_connector_contract.py — NO-CHANGE (recon-verified: opencode.json
  pins already json-parsed, validate_repo pins already module-executed, 2 prose scans with 0
  HTML comments in the docs). DONE (4 passed, unchanged).
- T-5: test_ubuntu_zero_touch_transport.py — workflow parsed twin + executed
  entrypoint-dispatch gate twin (helpers-only extract; id→sea-speed-deploy stub; sudo records
  argv; malformed fields → generic entrypoint rejection BEFORE validate_request, specific
  messages via _run_function on validate_request) + executed bootstrap/hardening twins
  (verbatim function extraction, readonly paths sed→tmp, stubbed sshd -T lowercase-normalizing
  /systemctl "$*"-recording/getent/usermod/chown) + executed effective_allowusers parser twin
  (multi-row sshd -T stub) + parsed ordering twin (composite walk + verify-before-ProxyJump);
  execute_root internals SS keeps (root+network gated). DONE (23 passed / 6 subtests; CC-1
  orchestrator fix round: 5 diagnosed fixes applied mid-conversion).
- T-6: test_ubuntu_worker_runtime_hash_lock.py — 9 executed twins (LockValidation 1,
  FinalizeRuntime 4, VerifyReadyRuntime 3, DirectiveStrip 1) + parsed iter_strings resolver
  bans (2); 15 kept (executed PipHash 4 + RuntimeIdAndLock 6 NO-CHANGE, two-phase flag
  sets/order + guard-order SS, pip-install-r ban SP, schema-2/committed-lock already parsed);
  overlayfs mv shim (CC-2) + interpreter-visible package probe (CC-4). DONE (24 passed).
- T-7: test_delivery_contract_convergence.py — AST SOURCE_AUTHORIZATIONS twin (set ==
  {"commit approved"}) + executed validate_authorization twin ("commit accepted" → receipt;
  "OUTCOME APPROVED" → ContractError naming both phrases) + json.loads schema-enum twin +
  parsed routing twin (jobs set, needs-evaluate with single-scalar normalization (CC-3),
  uses/secrets/if per contour job); 5 router raw pins superseded by wave-4's parsed twins
  (verified line-by-line); 12 prose/governance tests NO-CHANGE. DONE (14 passed).
- T-8: test_quality_status.py — 5 MainQualityStatusPublisherTests raw pins (21 raw assertions)
  → module-level parsed twins (trigger map equality, job if-conditions quote-normalized,
  permissions strict equality + no uses:, run-identity env wiring exact values, STATE mapping
  ordering if<success<failure); twins take a parsed data dict (demo-reusable); 3 executed
  module tests NO-CHANGE. DONE (8 passed).
- T-9: test_delivery_quality_layer.py — 3 AST convergence twins (templates vs validate_sdd.py
  PARSED QUALITY_SPEC/PLAN/TASK_MARKERS; PR-template fields vs validate_change_contract.py
  RISK_PROFILE_VALUES/QUALITY_VERDICTS + all 5 waiver fields vs the function-local
  waiver_fields tuple + trigger fields as {"YES","NO"} value-sets + validator literal
  membership; vocabulary vs RISK_CATEGORIES/TEST_LEVELS/TEST_PRIORITIES/QUALITY_VERDICTS
  parsed-set membership); "Separate merge approval" ban SP keep; 3 prose tests NO-CHANGE.
  DONE (6 passed).
- T-10: Demo tests/test_398_wave5_demo.py — two-direction proof on main-quality-status.yml
  tmp copies (17 retired pins restated; Direction A asserts ALL 17 fail individually). DONE
  (1 passed).
- T-11: Grandfather line (validate_sdd.py "398" set += "398-wave5", one line) + this trio +
  allowed-paths self-check; full battery = orchestrator-owned post-trio step. DONE.

## Completion gate

- Cluster `pytest tests/<8 cluster files> tests/test_398_wave5_demo.py -q` green: observed
  95 passed / 30 subtests in 5.14s (baseline 72 / 24 on 7a12da8; identity: 72 + 14
  zero-touch + 7 hash-lock + 1 convergence + 1 demo = 96; subtests 24→30).
- Full battery `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w5/pytest-tmp`: orchestrator-owned post-trio step (base
  battery 1203 passed / 2 skipped / 300 subtests, orchestrator-observed on 7a12da8; expected
  arithmetic 1203 + 23 cluster tests + 0 = 1226 passed / 2 skipped / 306 subtests — to be
  OBSERVED by the orchestrator, not claimed here).
- Demo two-direction proof observed: `python3 -m pytest tests/test_398_wave5_demo.py -q` →
  1 passed (refactor tolerance with all-17-retired-pins-fail AND dead-marker intolerance;
  real-workflow sanity).
- `validate_sdd.py` bare informational run for the trio after the grandfather line (NOT a gate
  at worker level — the orchestrator runs `--event` mode on the fresh commit, which also picks
  up the untracked trio).
- ruff clean on changed files (`ruff check scripts/ci/validate_sdd.py --config
  scripts/quality/ruff.toml` → All checks passed; all 7 test files ruff-clean per focused
  runs).

## Requirements traceability

- AC-001 | Task: T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-2, T-5, T-6, T-7, T-8, T-9, T-10 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-10 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-11 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-11 | Evidence: TEST-004, TEST-005 | Coverage: COVERED
- AC-006 | Task: T-11 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → the mapping table in plan.md (all 8 files adjudicated pin-group by
pin-group; every removed assertion has a twin, SP retention, or NO-CHANGE rationale) + the
battery-delta ledger below; R-2 → SP pins kept verbatim carry in-code justification comments
or mapping-table rationale (pip-install-r directive ban; "Separate merge approval" concept
ban; prose governance docs); R-3 → the demo's two-direction proof recorded below; R-4 → no
production file touched (git status limited to tests/**, specs/398-wave5/** + the recorded
validate_sdd.py exception); R-5 → workflow twins parse repo files read-only, executed script
twins run in tmp fixtures with stubbed binaries and redirected readonly paths, the overlayfs
mv shim is sandbox-local; R-6 → battery green with per-file deltas accounted (orchestrator
--event gate after commit).

## Battery-delta ledger (per-file test counts counted from base 7a12da8; identity: 72 + 14 + 7 + 1 + 1 demo = 95 passed; subtests 24→30)

| File | Delta (base→now) | Retired assertions → covering twin (same commit) |
|------|------------------|--------------------------------------------------|
| test_sync_tasks_md_flow.py | 0 (10→10) | 2 raw pins (wf_text SYNC_PUSH_TOKEN, positional steps[3] env read) → parsed position-independent twin (push step located semantically; env GH_TOKEN + SYNC_PUSH_TOKEN exact values on THAT step); run-text pins already parsed-derived (SS keeps); executed tests unchanged |
| test_deploy_freshness.py | 0 (6→6) | NO-CHANGE — recon-verified already executed (freshness run block → bash in git fixture; git-add pathspec → execute); no raw pins remain |
| test_github_actions_connector_contract.py | 0 (4→4) | NO-CHANGE — opencode.json pins already json-parsed; validate_repo pins already module-executed; 2 markdown-scan tests are prose governance docs (0 `<!--` verified) — presence scan is the executable ceiling |
| test_ubuntu_zero_touch_transport.py | +14 (8→23; subtests +6) | workflow text pins → parsed-structure twin (jobs/steps/env) + parsed ordering twin (composite walk + ubuntu step order verify-before-ProxyJump); gate text pins → executed entrypoint-dispatch twin (helpers-only extract fail/validate_request + entrypoint block; id→sea-speed-deploy stub; sudo records argv; malformed protocol fields → generic "unsupported restricted SSH command" BEFORE validate_request — real behavior; specific validate_request messages pinned via _run_function; script's `PATH=` line omitted from extraction, documented); bootstrap/hardening pins → executed twins via verbatim function extraction with redirected readonly paths + stubbed sshd (lowercase -T normalization)/systemctl ("$*" one line per call)/getent/usermod/chown; parser pins → executed effective_allowusers twin (multi-row sshd -T stub); failed-reload twin asserts the REAL 4-call sequence (failed reload pair + rollback restore pair); execute_root internals SS keeps (root+network gated) |
| test_ubuntu_worker_runtime_hash_lock.py | +7 (17→24) | 13 raw pins retired → 9 executed twins: inputs-invalid marker → LockValidationExecutedTests (real script, unpinned lock → rc 3 + exact message + no RUNTIME_CREATED); manifest/verify_python heredoc pins → FinalizeRuntimeExecutedTests (4: runtime_id sha256-v2 formula, manifest fields, 0444×5 + 0555 dir via overlayfs mv shim, cmp parity, re-verify via real verify_python → PASS, lock-hash/graph-drift rc!=0 + exact messages); verify_ready_runtime pins → VerifyReadyRuntimeExecutedTests (3: healthy 0, tampered 1, missing 1); grep -v '^--' pin → DirectiveStripExecutedTests (committed entries survive, poisoned --index-url does not); resolver raw bans (secrets:/deploy-authorized) → parsed iter_strings bans; 15 kept (executed PipHash+RuntimeIdAndLock, SS flag/guard keeps, pip-install-r SP ban, schema-2/committed-lock already parsed) |
| test_delivery_contract_convergence.py | +1 (13→14) | validator byte-exact SOURCE_AUTHORIZATIONS pin → AST twin (_constant_string_set → set == {"commit approved"}); quoted-literal ban → superseded by executed validate_authorization twin ("commit accepted" → receipt; "OUTCOME APPROVED" → ContractError naming both phrases); schema JSON fragment → json.loads twin (authorization_receipt.enum); 5 router raw pins → superseded by wave-4 parsed twins (verified) + NEW parsed routing twin (jobs == {evaluate, deploy-vps, deploy-ubuntu-worker}, needs evaluate with single-scalar normalization, uses ./.github/workflows/<file>, secrets inherit, if conditions); 12 prose/governance tests NO-CHANGE |
| test_quality_status.py | 0 (8→8) | 21 raw assertions across 5 MainQualityStatusPublisherTests → 5 module-level parsed twins (trigger map equality: workflow_run only + exact workflows/types; job if-conditions quote-normalized + HEAD_SHA env exact + 40-hex regex class-order-tolerant; permissions == {"statuses": "write"} + no uses: in any job/step; run-identity env wiring exact values + context value + /statuses/$HEAD_SHA brace-normalized + description identity vars; STATE mapping ordering if<success<failure — inverted mapping fails); 3 executed module tests unchanged |
| test_delivery_quality_layer.py | 0 (6→6) | 28 raw markers across 3 tests → 3 AST convergence twins: templates test vs validate_sdd.py PARSED QUALITY_SPEC/PLAN/TASK_MARKERS (validator-enforced artifact missing from template fails); PR-template fields → template value-sets parsed from "- Field: a / b" lines asserted == RISK_PROFILE_VALUES/QUALITY_VERDICTS + all 5 waiver fields vs function-local waiver_fields tuple + trigger fields {"YES","NO"} value-sets + validator literal membership (ast.walk, comment-blind); vocabulary → RISK_CATEGORIES/TEST_LEVELS/TEST_PRIORITIES/QUALITY_VERDICTS parsed-set membership; "Separate merge approval" ban SP kept; 3 prose tests NO-CHANGE |
| demo tests/test_398_wave5_demo.py | +1 | new two-direction regression demonstration (additive) |

Arithmetic note: per-file deltas are test-count deltas vs the base commit (git-counted);
cluster Σ = +23 (zero-touch +15, hash-lock +7, convergence +1; six files converted in place
or NO-CHANGE at 0 count delta); the demo adds +1; passed total is 72 + 22 + 1 = 95, subtests
24→30 (zero-touch executed bootstrap/gate matrices; per-file baseline subtest splits not
invented — the redistribution is recorded as an observed cluster total). Conversions-in-place
keep counts while replacing text pins with parsed/executed twins — the coverage became
observable without new test names except where an executed twin needed its own case.

## Demo — two-direction proof (observed output)

`python3 -m pytest tests/test_398_wave5_demo.py -q` → **1 passed**:

- Direction A (refactor tolerance): tmp copy of the real main-quality-status.yml rewritten
  behavior-preservingly (quoted trigger key, flow-style lists, `\x20`-escaped watched-workflow
  name, double-quoted GitHub expression literals, `\x2e`-escaped env expression dots — PyYAML
  decodes all to identical values, probe-verified; equivalent regex character-class order
  [a-f0-9]; bash single-quote literals; brace-less `$HEAD_SHA`; python payload CONTEXT
  variable) → the parsed twins PASS; ALL 17 retired text pins FAIL (asserted individually via
  `assertEqual(retired_failed, list(RETIRED_TEXT_PINS))`).
- Direction B (dead-marker intolerance): tmp copy keeping every retired marker byte-for-byte
  but with the conclusion→STATE mapping inverted (success and failure states swapped) →
  retired pins PASS (the false-green), parsed twins FAIL (the ordering assertion: the success
  state must follow the success comparison).
- Sanity: the real workflow satisfies the parsed twins (tmp copies only; .github/ never
  modified).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line = CONTROL_PLANE; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — remaining #398 raw-text clusters outside this 8-file scope stay in the issue backlog
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED (tests-only wave)
- [x] Waivers resolved or current — no waivers

Wave record: all 8 cluster files adjudicated (mapping table in plan.md); battery delta +22
cluster tests (+1 demo; skips unchanged) with recorded twins, no assertion weakened or
skipped; the demo proves the conversion property in both directions on the real
main-quality-status.yml workflow; four course corrections recorded (CC-1 zero-touch
orchestrator fix round — 5 diagnosed fixes incl. the sshd -T lowercase normalization and the
generic-message-before-validate_request entrypoint behavior, CC-2 overlayfs 0555-rename mv
shim, CC-3 single-scalar needs: normalization, CC-4 interpreter-visible package probe);
observed totals 95 passed / 30 subtests (cluster, 9 files) with the full battery as the
orchestrator-owned post-trio step (base 1203 / 2 / 300); validate_sdd.py grandfather entry
`398-wave5` added (one line, orchestrator-recorded exception).
