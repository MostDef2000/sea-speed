# Spec: #398 wave 5 — workflow-YAML/governance cluster raw-source-text conversion (parsed/executed)

- Issue: #398
- Specification: specs/398-wave5/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the 8-file
  workflow-YAML/governance cluster of that scope (tests-only + one recorded validator line),
  per the wave-5 work order (base 7a12da8, the wave-4 merge).

## Product outcome

The workflow-YAML/governance regression cluster (8 files) stops verifying deploy workflows,
worker bootstrap/hardening scripts, runtime lock tooling and governance docs by reading sources
as raw text and starts verifying them by parsing structure (SS: `yaml.safe_load`, `ast.parse`,
`json.loads`) or executing the real thing (RB). Deploy-workflow contracts assert on
`yaml.safe_load`-parsed structure — trigger maps, job if-conditions, permissions maps, env
chains, run-text literals taken from PARSED steps (comment-blind, so comment-only compliance
stops passing; YAML 1.1 parses a bare `on:` key as boolean True, handled by the canon
`trigger_of` helper). The zero-touch transport gate and bootstrap/hardening paths EXECUTE under
stubbed binaries (sshd -T with lowercase keyword normalization, systemctl recording "$*" per
call, stubbed chown/getent/usermod) and verbatim function extraction with redirected readonly
paths; the runtime hash-lock script's finalize/verify/ready paths execute end-to-end against
real fixtures (interpreter-visible package probe; 0444×5 files inside a 0555 dir via the
overlayfs mv shim); validator vocabulary converges via AST-parsed module constants so template
presentation and validator enforcement cannot drift. Pins whose textual presence IS the
contract (prose governance docs, deliberate SP bans) stay verbatim or NO-CHANGE with recorded
rationale. Redundant text pins retire only against recorded same-commit twins, so the battery
is never weaker. A two-direction demo (`tests/test_398_wave5_demo.py`) proves the conversion
property on the real Main Quality status publisher workflow.

## User scenarios

- A developer reformats main-quality-status.yml (quoted trigger key, flow-style lists,
  hex-escaped scalars, single-quoted bash literals, brace-less shell variables): the converted
  checks stay green (old text pins would have failed — false failure eliminated).
- A developer inverts the conclusion→STATE mapping while leaving every historical marker
  verbatim: the parsed fail-closed ordering twin fails (old text pins would have passed —
  false pass eliminated).
- A deploy workflow "complies" via a comment block carrying the required policy markers (the
  deploy-ubuntu-worker.yml lines 37-51 comment false-green): parsed-structure twins never see
  comments, so comment-only compliance fails.
- A future wave touches .github/workflows/** or worker deploy scripts without behavior change:
  review attention goes to real diffs instead of text churn.

## Scope

- tests/test_sync_tasks_md_flow.py, tests/test_deploy_freshness.py,
  tests/test_github_actions_connector_contract.py, tests/test_ubuntu_zero_touch_transport.py,
  tests/test_ubuntu_worker_runtime_hash_lock.py, tests/test_delivery_contract_convergence.py,
  tests/test_quality_status.py, tests/test_delivery_quality_layer.py — adjudicated per the
  plan.md mapping table (RB→exec, SS→structured parse, SP verbatim, redundant→retired with
  twins, NO-CHANGE with rationale).
- tests/test_398_wave5_demo.py (new) — two-direction regression demonstration.
- specs/398-wave5/** — this trio.
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives `398-wave5` in the
  existing `"398"` GRANDFATHERED_PREFIX_COLLISIONS set (staged-wave precedent 396/397/520/537
  and the 398-wave1/wave2/wave3/wave4 entries) so this trio is admissible; delivery-orchestrator
  addition, documented in plan.md Correct-course and tasks.md ledger. ONE line; no other
  scripts/** surface is touched.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**
  untouched (wave-1/wave-2/wave-3/wave-4 test files also untouched, including tests/support/).
- Out of scope (NO-CHANGE, rationale in the mapping table): tests/test_deploy_freshness.py and
  tests/test_github_actions_connector_contract.py — recon-verified already executed/parsed (no
  raw pins to retire); prose governance scans are the executable ceiling for markdown docs
  (the text IS the artifact).
- Change classification: tests-only + 1 validator line = CONTROL_PLANE
  (contracts/runtime/RELEASE_READINESS_GATE.md) — authorized source lifecycle and PR/post-merge
  Quality only; runtime deployment NOT REQUIRED. Risk profile: NOT REQUIRED (tests-only wave).

## Requirements

- R-1: every behavioral assertion carried by a raw text pin is replaced by an executed or
  structured twin per the plan.md mapping table; no assertion is lost without a recorded
  same-commit executed twin (redundancy ledger in tasks.md) or verbatim SP retention.
- R-2 (SP justification): STATIC_POLICY pins kept verbatim carry an in-code justification
  comment or a mapping-table rationale (pip-install-r directive ban; "Separate merge approval"
  concept ban; prose governance docs as NO-CHANGE — the text IS the artifact).
- R-3: tests/test_398_wave5_demo.py proves both directions on tmp copies of the real
  main-quality-status.yml: (a) refactor tolerance — a behavior-preserving reformat passes the
  parsed twins while ALL 17 retired text pins fail individually; (b) dead-marker intolerance —
  markers verbatim with an inverted STATE mapping FAILS the parsed twins where the retired
  pins pass.
- R-4 (tests-only): if any conversion requires a production change → STOP and report; none did.
- R-5: the suite stays deterministic in CI — workflow twins parse repo files read-only;
  executed script twins run in tmp fixtures with stubbed binaries (sshd/systemctl/chown/
  getent/usermod) and redirected readonly paths; the overlayfs 0555-rename mv shim is a
  sandbox-only fallback that is a plain rename on production ext4; no network.
- R-6: full battery green with per-file deltas accounted (never weaker); validate_sdd and
  validate_repo green; changed files limited to the allowed set.

## Acceptance criteria

- AC-001: all 8 cluster files adjudicated in the plan.md mapping table (converted / SP-kept /
  retired-with-twin / NO-CHANGE) and every converted file's focused run is green. → TEST-001
- AC-002: cluster delta vs baseline 72 passed / 24 subtests (base 7a12da8) equals the per-file
  deltas (zero-touch +14, hash-lock +7, convergence +1, demo +1; the other files at 0 count
  delta) — the identity holds: 72 + 14 + 7 + 1 + 1 = 95 passed / 30 subtests — with the
  covering twin recorded in the tasks.md ledger for every retired assertion. → TEST-002
- AC-003: tests/test_398_wave5_demo.py passes with both explicit directions (refactor-tolerant
  AND dead-marker-intolerant), the all-17-retired-pins-fail assertion recorded in tasks.md. →
  TEST-003
- AC-004: full battery `pytest tests/ -q` green on top of the base 1203 passed / 2 skipped /
  300 subtests (base 7a12da8, orchestrator-observed) with the AC-002 deltas applied — the
  full-battery run is the delivery-orchestrator's post-trio step; worker-observed evidence is
  the per-file focused runs plus the observed cluster run (95 passed / 30 subtests in 5.14s).
  → TEST-004
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio (after the recorded
  grandfather line); `validate_repo.py` green. → TEST-004, TEST-005
- AC-006: `git status`/diff shows only tests/** (the 7 converted/new cluster files),
  specs/398-wave5/** plus the recorded orchestrator exception (one-line `398-wave5` grandfather
  entry in `scripts/ci/validate_sdd.py`, per Scope above). → TEST-005

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only + one validator line (CONTROL_PLANE); no
  deploy and no production artifact changes. Runtime acceptance = exact-head CI green on the
  merge PR (the battery, including the executed script twins, runs in CI; the overlayfs mv
  shim degrades to a plain rename on production ext4; stubbed-binary twins need no privileges).
- RF-002: after this wave the cluster reports 95 passed / 30 subtests (baseline 72 / 24); every
  count delta vs the wave baseline is recorded in the tasks.md battery-delta ledger (retired
  assertion → covering executed twin, same commit). Subtests grew 24→30 (executed
  bootstrap/gate matrices) — evidence that conversion made coverage observable, not smaller.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (read-only parsing of repo files; tmp fixtures with stubbed binaries and redirected readonly paths; no network; root-gated internals stay SS-keeps) | Validation: focused runs repeated across sessions; demo isolates mutations in tmp copies | Evidence: cluster 95 passed / 30 subtests in 5.14s | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to an executed twin, a structured equivalent, a retained verbatim SP pin, or a recorded NO-CHANGE rationale | Validation: mapping table in plan.md; tasks.md battery-delta ledger | Evidence: ledger rows + focused run tails | Status: PASS
- NFR-003 | Area: performance | Target: cluster wall time stays bounded (5.14s for 95 tests incl. executed script twins vs 2.29s text-only baseline) — executed coverage costs bounded subprocess spawns per scenario | Validation: cluster timing comparison vs baseline | Evidence: tests_run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: house conversion models only (yaml.safe_load + trigger_of/steps_of/run_text canon, worker_source AST helpers, verbatim function extraction with redirected readonly paths, stubbed-binaries exec, AST constant convergence) — no new framework/pattern invented | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
