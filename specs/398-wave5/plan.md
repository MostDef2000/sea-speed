# Plan — Issue #398 wave 5

- Issue: #398
- Specification: specs/398-wave5/spec.md

## Architecture

Follow the wave-1/2/3/4 house model: RB (execute the real thing) > SS (structured parse:
`ast.parse` / `yaml.safe_load` / `json.loads`) > SP (STATIC_POLICY pins kept verbatim with
justification) > NO-CHANGE (recorded rationale) > redundant retirement (only with a recorded
same-commit twin). The wave-5 surface is the workflow-YAML/governance layer: deploy-workflow
contracts assert on `yaml.safe_load`-parsed structure — trigger maps (YAML 1.1 parses a bare
`on:` key as boolean True; the canon `trigger_of` helper handles both), job `if` conditions
(quote-normalized: GitHub expressions treat `'x'` and `"x"` identically), permissions maps by
strict equality, env chains from parsed step env, and run-text literals from PARSED steps
(comment-blind, so the deploy-ubuntu-worker.yml lines 37-51 comment block stops being a false
green). Shell scripts have no AST: the zero-touch gate/bootstrap and hash-lock
finalize/verify/ready paths are extracted VERBATIM by stable anchors and EXECUTED in tmp
fixtures with redirected readonly paths and stubbed binaries (sshd -T lowercases the keyword
like the real sshd; systemctl records `"$*"` one line per call; chown/getent/usermod stubs);
validator vocabulary converges via AST-parsed module constants so template presentation and
validator enforcement cannot drift. No new frameworks or patterns.

## Decisions

- **Executed twins over script text**: assertions read RECORDED behavior (sudo argv, systemctl
  call lines, sshd -T parse results, file modes 0444×5 + 0555 dir, rc + stderr literals), not
  script text — a reformatted script passes, a rewired script fails.
- **Workflow assertions run on PARSED structure** (`yaml.safe_load`, comment-blind): the
  main-quality-status publisher twins pin the ENTIRE trigger map (workflow_run the only
  trigger, exact workflows/types), the job if-condition logic, `permissions ==
  {"statuses": "write"}` with no `uses:` in any job/step, run-identity env wiring by exact
  value, and the conclusion→STATE mapping as ORDERED structure (if < success < failure) — an
  inverted mapping fails where the raw pins passed.
- **Semantic step location**: steps are located by what they do (the `/statuses/` API call;
  the push step by its sync semantics), not by positional index — the retired positional
  `steps[3]` env read was order-fragile.
- **Function extraction with redirected readonly paths**: bootstrap/hardening functions are
  sliced verbatim from the script source (stable anchors), readonly path constants are
  sed-redirected to tmp, and binaries are stubbed on PATH — the real code paths execute without
  privileges or network. `sshd -T` stub lowercases the keyword (real sshd -T normalizes; the
  script matches `allowusers` lowercase); `systemctl` stub records `"$*"` one line per call so
  reload sequences are assertable; `chown` is stubbed (root-only in the sandbox).
- **Entrypoint dispatch executed, not sourced**: sourcing the entrypoint block would
  fail/exit, so the gate twin extracts the helpers (`fail`/`validate_request`) plus the
  entrypoint dispatch block only, stubs `id` → sea-speed-deploy, and records sudo argv;
  malformed protocol fields are rejected by the entrypoint regex with the generic
  "unsupported restricted SSH command" message BEFORE `validate_request` (real behavior) —
  the specific validate_request messages are pinned by executing `validate_request` directly
  via the `_run_function` helper.
- **Failed reload asserts the REAL 4-call sequence**: failed reload pair + rollback restore
  pair (`restore_sshd_hardening` reloads too) — a 2-call stub sequence would be a weaker twin.
- **Hash-lock executes end-to-end**: `finalize_runtime`/`verify_python`/`verify_ready_runtime`
  extracted verbatim; fixtures pin an interpreter-visible package (subprocess probe with
  packaging/setuptools/pip/pytest fallback) so importlib.metadata + ABI checks pass against
  real interpreter state; the 0555 runtime dir is created via the overlayfs mv shim (sandbox
  overlayfs refuses rename() of 0555 directories; production ext4 is unaffected).
- **Validator convergence via AST constants**: the templates/PR-template/vocabulary twins read
  validate_sdd.py and validate_change_contract.py PARSED module constants (QUALITY_SPEC/PLAN/
  TASK_MARKERS, RISK_PROFILE_VALUES, QUALITY_VERDICTS, RISK_CATEGORIES, TEST_LEVELS,
  TEST_PRIORITIES) and the function-local `waiver_fields` tuple — a validator-enforced
  artifact missing from a template fails even if the pin list is never updated; `ast.walk`
  literal membership is comment-blind.
- **Pins superseded by earlier waves retire without duplication**: the 5 router raw pins in
  test_delivery_contract_convergence.py are superseded by wave-4's parsed twins in
  test_autonomous_execution_policy.py (verified line-by-line before retirement); the new
  parsed routing twin adds what wave-4 does not pin (jobs set, needs-evaluate gating with the
  single-scalar `needs:` normalization, uses/secrets/if per contour job).
- **SP keeps**: the pip-install-r directive ban (the ban's textual presence IS the contract);
  the "Separate merge approval" concept ban; prose governance docs NO-CHANGE (the text IS the
  artifact; verified 0 HTML comments in all 8 scanned docs — presence scan is the executable
  ceiling).
- **NO-CHANGE**: test_deploy_freshness.py (all 6 tests already execute extracted bash in git
  fixtures); test_github_actions_connector_contract.py (opencode.json pins already
  json-parsed, validate_repo pins already module-executed, 2 prose scans); executed module
  tests (verify_quality_status, PipHash, RuntimeIdAndLock); wave-2 normalized-extraction keeps
  in the hash-lock structural tests.

## Site-mapping table (old → replacement)

| File | Retired pin (group) | Kind | Twin / where it lives |
|------|---------------------|------|-----------------------|
| test_sync_tasks_md_flow.py | raw wf_text SYNC_PUSH_TOKEN pin + positional steps[3] env read (2 raw pins) | SS | parsed position-independent twin: push step located semantically, env GH_TOKEN + SYNC_PUSH_TOKEN exact values asserted on THAT step (`WorkflowStructuralPinTests`); run-text pins already parsed-derived (SS keeps); executed tests untouched |
| test_deploy_freshness.py | (no raw pins — recon-verified) | NO-CHANGE | all 6 tests already executed (freshness run block → bash in git fixture; git-add pathspec → execute) |
| test_github_actions_connector_contract.py | (no raw pins — recon-verified) | NO-CHANGE | opencode.json pins already json-parsed; validate_repo pins already module-executed; 2 markdown-scan tests are prose governance docs (0 `<!--` verified) — presence scan is the executable ceiling |
| test_ubuntu_zero_touch_transport.py | workflow text pins (connector usage, delegation env, step order) | SS | parsed-structure twin (workflow jobs/steps/env) + parsed ordering twin (composite walk + ubuntu step order verify-before-ProxyJump) |
| test_ubuntu_zero_touch_transport.py | gate text pins (restricted-command dispatch, fail/validate_request wiring) | RB | executed entrypoint-dispatch twin (helpers-only extract + entrypoint block; id→sea-speed-deploy stub; sudo records argv; PATH stub dir; script's `PATH=` line omitted from extraction — documented) in `ZeroTouchGateExecutedTests`; malformed fields → generic entrypoint rejection before validate_request; specific messages via `_run_function` on validate_request; execute_root internals stay SS (root+network gated) |
| test_ubuntu_zero_touch_transport.py | bootstrap/hardening text pins (sshd hardening, reload/rollback, allowusers parse) | RB | executed twins via verbatim function extraction with redirected readonly paths (SSHD_HARDENING_PATH etc. sed→tmp) + stubbed sshd/systemctl/getent/usermod; parser twin executes effective_allowusers against a multi-row `sshd -T` stub (lowercase-normalized); failed-reload twin asserts the real 4-call sequence |
| test_ubuntu_worker_runtime_hash_lock.py | inputs-invalid marker pin | RB | `LockValidationExecutedTests`: real script, fixture minus runtime-lock.json → rc 3 + "ERROR runtime lock inputs are invalid" + refusing + no RUNTIME_CREATED |
| test_ubuntu_worker_runtime_hash_lock.py | verify_python/manifest message pins (heredoc L231-341) | RB | `FinalizeRuntimeExecutedTests` (4 tests): real finalize_runtime end-to-end — runtime_id sha256-v2 formula, manifest fields, 0444×5 + 0555 dir (overlayfs mv shim), cmp parity, re-verify via real verify_python → PASS; lock-hash/graph-drift twins → rc!=0 + exact messages |
| test_ubuntu_worker_runtime_hash_lock.py | verify_ready_runtime pins | RB | `VerifyReadyRuntimeExecutedTests` (3 tests): healthy staged fixture → 0; tampered lock copy → 1; missing staged lock copy → 1 |
| test_ubuntu_worker_runtime_hash_lock.py | `grep -v '^--'` directive-strip pin | RB | `DirectiveStripExecutedTests`: real extracted line — committed lock entries survive, poisoned --index-url directive does not |
| test_ubuntu_worker_runtime_hash_lock.py | resolver raw bans (secrets:/deploy-authorized) | SS | parsed iter_strings bans (no "secrets"/"deploy-authorized" in any parsed key/value) |
| test_ubuntu_worker_runtime_hash_lock.py | two-phase flag sets/order, pip-install-r ban, guard order, schema-2/committed-lock | SS/SP kept | 15 kept: executed PipHash(4)+RuntimeIdAndLock(6) NO-CHANGE; flag sets/order + guard-order SS; pip-install-r ban SP (textual presence IS the contract); schema-2/committed-lock already parsed |
| test_delivery_contract_convergence.py | validator byte-exact SOURCE_AUTHORIZATIONS pin + quoted-literal ban + schema JSON fragment | RB+SS | AST twin (`_constant_string_set` → set == {"commit approved"}); executed `validate_authorization` twin ("commit accepted" → receipt; "OUTCOME APPROVED" → ContractError naming both phrases); json.loads twin (authorization_receipt.enum) |
| test_delivery_contract_convergence.py | 5 router raw pins (trigger ban, PRODUCTION APPROVED, Execution-Intent, delegation env, verify_source_protection) | SS | superseded by wave-4 parsed twins in test_autonomous_execution_policy.py (verified) + NEW parsed routing twin (jobs == {evaluate, deploy-vps, deploy-ubuntu-worker}; needs evaluate with single-scalar normalization; uses ./.github/workflows/<file>; secrets inherit; if conditions) |
| test_delivery_contract_convergence.py | 12 prose/governance scans | NO-CHANGE | markdown scans (wave-2 canon) — the text IS the artifact |
| test_quality_status.py | 21 raw assertions across 5 MainQualityStatusPublisherTests (trigger, if-conditions, permissions slice + 6 forbidden substrings + no uses, context/identity literals, STATE mapping) | SS | 5 module-level parsed twins (trigger map equality; if-conditions quote-normalized + HEAD_SHA env + 40-hex regex class-order-tolerant; permissions strict equality + no uses; env wiring exact values + context/statuses literals; STATE mapping ordering if<success<failure) — demo-reusable; 3 executed module tests NO-CHANGE |
| test_delivery_quality_layer.py | templates marker pins (6 raw markers) | SS | convergence twin vs validate_sdd.py PARSED QUALITY_SPEC/PLAN/TASK_MARKERS; "Separate merge approval" ban SP keep |
| test_delivery_quality_layer.py | PR-template field line pins (7 raw lines) | SS | template value-sets parsed from `- Field: a / b` lines asserted == validator AST constants RISK_PROFILE_VALUES / QUALITY_VERDICTS; ALL 5 waiver fields vs the function-local waiver_fields tuple; 2 trigger fields as {"YES","NO"} value-sets + validator literal membership |
| test_delivery_quality_layer.py | vocabulary marker pins (11 raw markers) | SS | AST parsed-set membership (RISK_CATEGORIES/TEST_LEVELS/TEST_PRIORITIES/QUALITY_VERDICTS) + field names in ast.walk string literals (comment-blind) |
| test_delivery_quality_layer.py | hard_gates / role+contours / stage-C prose tests | NO-CHANGE | prose governance docs — the text IS the artifact |
| test_398_wave5_demo.py | (new) two-direction demo | RB+SS | parsed-twin contract on main-quality-status.yml tmp copies; 17 retired pins restated; directions recorded in tasks.md |
| tests/test_validate_sdd.py | (out of wave-5 scope) | NO-CHANGE | validate_sdd pins the validator itself — the validator's source text IS the artifact under test (SS by design); not part of the admitted 8-file cluster |

## Affected contours

- Tests only: the 7 converted/new test files (sync, zero-touch, hash-lock, convergence,
  quality_status, quality_layer, demo), this trio — plus the recorded one-line grandfather
  entry in scripts/ci/validate_sdd.py.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**, and all
  wave-1/wave-2/wave-3/wave-4 test files (byte-identical, including tests/support/).

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in the session
  checkpoint /tmp/opencode/398-w5/checkpoint.md: sync 10, zero-touch 23/6, hash-lock 24,
  convergence 14, quality_status 8, quality_layer 6, demo 1).
- Cluster: `pytest` over the 9 files (8 cluster + demo) → 95 passed / 30 subtests in 5.14s
  (baseline 72 / 24 on 7a12da8).
- Full battery: orchestrator-owned post-trio step (`python3 -m pytest tests/ -q -p
  no:cacheprovider --basetemp=/tmp/opencode/398-w5/pytest-tmp`); base battery 1203 passed /
  2 skipped / 300 subtests (orchestrator-observed on 7a12da8); expected arithmetic +23 tests
  (zero-touch +15, hash-lock +7, convergence +1, demo +1) and +6 subtests (24→30) — to be
  OBSERVED by the orchestrator, not claimed here.
- `python3 scripts/ci/validate_sdd.py` → informational bare run for the trio after the
  grandfather line (NOT a gate here — the orchestrator runs `--event` mode on the fresh
  commit); `validate_repo.py` unchanged-behavior read-only.
- ruff: `python3 -m ruff check --config scripts/quality/ruff.toml` clean on every changed file.
- Allowed-paths check: `git status` shows only the 7 cluster test files + demo,
  specs/398-wave5/** plus the recorded validate_sdd.py exception.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE change (tests + one validator line);
  runtime acceptance = exact-head CI green on the merge PR.
- RF-002: post-wave cluster reports 95 / 30 (baseline 72 / 24); all deltas recorded in the
  tasks.md battery-delta ledger (retired assertion → covering executed twin, same commit);
  full battery is the orchestrator's post-trio step.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every mapping-table action's focused run green (sync 10, zero-touch 23/6, hash-lock 24, convergence 14, quality_status 8, quality_layer 6); NO-CHANGE files recon-documented
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: cluster 72/24 → 95/30 (incl. demo +1); battery-delta ledger in tasks.md maps every retired assertion to its recorded twin
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave5_demo.py — both directions with the all-17-retired-pins-fail assertion (Direction A) and the inverted-STATE-mutation run (Direction B fails the ordering twin)
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: full battery orchestrator-owned post-trio (base 1203 / 2 / 300); validate_sdd informational run green for the trio (orchestrator --event gate after commit)
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git status shows only declared paths + the recorded validate_sdd.py grandfather-entry exception

## Correct-course check

Course correction CC-1 — zero-touch orchestrator fix round (the worker hit the output limit
mid-conversion of test_ubuntu_zero_touch_transport.py; the orchestrator applied the worker's
5 diagnosed fixes — f-string missing closing quote in the SSHD_HARDENING_PATH header line,
SSHD_STUB -T branch lowercasing the keyword via awk (real sshd -T normalizes), systemctl stub
recording "$*" one line per call, failed-reload twin asserting the REAL 4-call sequence
(failed reload pair + rollback restore pair), and malformed protocol fields rejected by the
entrypoint regex with the generic message BEFORE validate_request via the new _run_function
helpers-only extract):

- Trigger: NONE
- Issue impact: NONE — the admitted 8-file tests-only scope is unchanged; the incident was
  execution-level (mid-file handoff), not a scope event.
- Specification impact: NONE — no requirement changed; the stub-fidelity semantics are
  recorded in Scope/plan (sshd -T lowercase normalization, systemctl "$*" records, 4-call
  reload sequence, generic-message-before-validate_request).
- Plan impact: recorded here and in the Decisions bullets (entrypoint dispatch executed via
  helpers-only extract; failed-reload 4-call sequence).
- Tasks impact: T-4 evidence notes the orchestrator-applied fixes; per-file counts unchanged
  (23 passed / 6 subtests).
- Authorization impact: NONE — same admitted scope; the test file was already in scope.
- Follow-up: none — conversion completed and verified in the same wave; lesson recorded in
  the checkpoint.

Course correction CC-2 — overlayfs 0555-rename quirk (the sandbox overlayfs refuses rename()
of a 0555 directory, so finalize_runtime's chmod-0555-then-mv sequence failed in the sandbox
although production ext4 behaves correctly; the harness mv shim does chmod u+w → REAL
`command mv` → chmod 0555 dst):

- Trigger: NONE
- Issue impact: NONE — sandbox-environment accommodation inside the admitted tests-only scope;
  no test weakened (the real `command mv` still executes).
- Specification impact: NONE — determinism requirement (R-5) unchanged; the shim is
  sandbox-local and a no-op difference on production ext4.
- Plan impact: Architecture records the mv shim; Decisions hash-lock bullet notes it.
- Tasks impact: T-5 harness note; FinalizeRuntime twins green.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — shim documented in the test module and the checkpoint; do not remove.

Course correction CC-3 — single-scalar `needs:` normalization (YAML parses a single
`needs: evaluate` as the STRING "evaluate", not a list; the routing twin's needs-evaluate
assertion normalizes scalars to a list before comparing — the wave-4 canon hit the same
class of YAML 1.1 quirk as the bare `on:` → True key):

- Trigger: NONE
- Issue impact: NONE — twin-fidelity fix; no assertion weakened.
- Specification impact: NONE — R-1 twin fidelity improved (the twin accepts the real
  workflow's scalar form without weakening the gating assertion).
- Plan impact: Decisions routing bullet records the normalization.
- Tasks impact: T-6 note; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — quirk documented in the trio and the checkpoint.

Course correction CC-4 — interpreter-visible package probe (the hash-lock finalize/verify
fixtures must pin a package that verify_python's importlib.metadata + ABI checks accept
against the REAL interpreter; the fixture probes installed distributions via subprocess
with a packaging/setuptools/pip/pytest fallback instead of hardcoding a name that may not
exist in a given environment):

- Trigger: NONE
- Issue impact: NONE — fixture-authoring discipline recorded for future scenario authors.
- Specification impact: NONE — determinism requirement unchanged (probe is offline, subprocess-local).
- Plan impact: Decisions hash-lock bullet records the probe.
- Tasks impact: T-5 fixture note; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — probe documented in the test module and the checkpoint.
