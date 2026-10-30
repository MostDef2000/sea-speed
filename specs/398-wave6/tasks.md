# Tasks — Issue #398 wave 6

- Issue: #398
- Specification: specs/398-wave6/spec.md

## Delivery tasks

- T-1: RECON + baseline: base battery 1227 passed / 2 skipped / 306 subtests on
  0ab0911 (orchestrator-observed); cluster recon (10 files, ~60 sites estimated;
  per-file pin groups inventoried; markdown-scanner gap identified → new
  tests/support/markdown_docs.py; probe iterated to 0 failures against the real
  docs BEFORE writing tests). DONE.
- T-2: test_delivery_resume_contract.py — ~45 sites → per-doc co-section twins
  (truth classes, admission receipts, resume probe, context-loss + negation,
  connector chain, wait-replay + negation, CI-foreground, terminal model), runtime
  truth-section binding, checkpoint-v2 JSON block parsed (json.loads) + schema
  properties/required cross-check, v1 upgrade EXECUTED via real
  upgrade_v1_checkpoint, monotonic fenced reason set EXACT equality + CONTEXT_LOSS
  ban; combined event-driven/wait-replay pins SP-kept with per-doc section twins
  (GATE excluded — carries neither marker). DONE (24 passed; CC-3 negation
  extension).
- T-3: test_delivery_terminal_states.py — ~45 sites → per-doc session-disposition
  twins, runtime fenced blocks EXACT equality, Required status block template,
  WAITING_EXTERNAL placement twins, 6-marker ci-foreground bundle (CC-4 scoping);
  SP keeps: 5 legacy-phrase bans + Final-state ban + combined pins (per-doc twins
  in the resume file, same-commit ledger). DONE (24 passed).
- T-4: test_delivery_todo_contract.py — ~50 sites → per-entrypoint Required-behavior
  twins, Structured todo projection twins (runtime + agent), todo display block
  exact 5-line set, vocabulary co-section twins; SP keeps (agent-file Russian
  routing bans, DELIVERY_POLICY todo-authority placement pin); L96-185
  byte-identical. DONE (9 passed + 19 subtests).
- T-5: test_sea_speed_auth_v1.py — ~30 sites → AUTH_DOC + OPS_DOC section twins
  (preamble issue chains, EXACT fenced blocks, co-sections, fail-closed Phase E,
  96h/30d timing co-sections); SP keep ("External host:" ban); SDD feature docs
  kept verbatim (wave-4 NO-CHANGE precedent, in-code). DONE (21 passed + 10
  subtests).
- T-6: test_camera1_live_replacement.py — 12 pins → 11 co-section/section_titled
  twins + EXACT fenced blocks (relay prepare single block; canonical cam1 source
  EXACT 3-line block); SP keep ("runtime remains `UNKNOWN`" ban). DONE (19 passed +
  6 subtests).
- T-7: test_mediamtx_compatibility_remediation.py — 12 pins → 9 unique groups → 6
  twin groups (blocker classification, provenance, canary contract, final-scope
  bundle, worker non-mutation, rollback prohibition placement); SP keep (rollback
  prohibition + separate-governed-decision caveat). DEMO TARGET. DONE (14 passed).
- T-8: test_camera1_direct_h264_cutover.py — 6 pins → co-section twins + preamble
  topology block with removeprefix("-> ") normalization (CC-5); SP keep
  (stale-identity ban). DONE (7 passed).
- T-9: test_ubuntu_worker_storage_lifecycle_contract.py — 4 pins → preamble UNKNOWN
  + Safety model co-location + --apply-plan unique fenced block. DONE (6 passed).
- T-10: test_ubuntu_worker_observability.py — 4 pins → Runtime boundary + Safe
  inspection 2-line fenced block + Install periodic checks timer ban; SP keep
  (assertNotIn("Grafana") whole-doc absence). DONE (6 passed).
- T-11: test_ubuntu_worker_manual_install.py — single DOC pin SP-kept with one-line
  rationale (data-preservation warning); installer-script pins untouched (out of
  wave-6 scope). DONE (7 passed; diff = 2 added comment lines).
- T-12: Demo tests/test_398_wave6_demo.py — two-direction proof on
  MEDIAMTX_COMPATIBILITY_REMEDIATION.md tmp copies (12 retired pins restated; the
  documented 2/12 prose-form verdict split; both inverted-mutation proofs in-demo).
  DONE (1 passed; pre-write probe 14/14; flip-runs recorded below).
- T-13: Grandfather line (validate_sdd.py "398" set += "398-wave6", one line) + this
  trio + allowed-paths self-check; full battery worker-run per the work order.
  DONE.

## Completion gate

- Cluster `pytest tests/<10 cluster files> tests/test_398_wave6_demo.py -q` green:
  observed 138 passed / 35 subtests in 3.36s (all 10 files converted in place at 0
  count delta; demo +1).
- Full battery `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w6/pytest-tmp`: OBSERVED 1228 passed / 2 skipped /
  306 subtests in 72.25s (base 1227 / 2 / 306 orchestrator-observed on 0ab0911;
  identity 1227 + 1 demo = 1228; subtests unchanged).
- Demo two-direction proof observed: `python3 -m pytest tests/test_398_wave6_demo.py
  -q` → 1 passed (sanity + Direction A + inv-A + Direction B + inv-B +
  repo-doc-unchanged).
- `validate_sdd.py` bare informational run for the trio after the grandfather line
  (NOT a gate at worker level — the orchestrator runs `--event` mode on the fresh
  commit, which also picks up the untracked trio); the intermediate duplicate-prefix
  error before the trio landed was the expected strict-set-equality state; clean
  once specs/398-wave6/ exists.
- ruff clean on changed files (`ruff check --config scripts/quality/ruff.toml` on
  the 10 converted files + scanner + demo + validate_sdd.py → All checks passed).

## Requirements traceability

- AC-001 | Task: T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10, T-11 | Evidence:
  TEST-001 | Coverage: COVERED
- AC-002 | Task: T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10, T-11, T-12 |
  Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-12 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-13 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-13 | Evidence: TEST-004, TEST-005 | Coverage: COVERED
- AC-006 | Task: T-13 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → the mapping table in plan.md (all 10 files adjudicated
pin-group by pin-group; every removed assertion has a twin, SP retention, or
NO-CHANGE rationale) + the battery-delta ledger below; R-2 → SP pins kept verbatim
carry in-code justification comments or mapping-table rationale; R-3 → the demo's
two-direction proof with the documented verdict-class split recorded below; R-4 →
no production file touched (git status limited to tests/**, specs/398-wave6/** +
the recorded validate_sdd.py exception); R-5 → twins parse repo files read-only via
the stdlib scanner, the demo mutates tmp copies only; R-6 → battery green with
per-file deltas accounted (orchestrator --event gate after commit).

## Battery-delta ledger (base 0ab0911 = wave-5 merge; identity: 1227 + 1 demo = 1228 passed / 2 skipped / 306 subtests, OBSERVED)

| File | Delta (base→now) | Retired assertions → covering twin (same commit) |
|------|------------------|--------------------------------------------------|
| test_delivery_resume_contract.py | 0 (24→24) | ~45 sites → per-doc co-section twins + runtime truth-section binding + checkpoint-v2 json.loads schema cross-check + EXECUTED upgrade_v1_checkpoint twin + EXACT fenced reason-set equality + CONTEXT_LOSS ban; combined event-driven/wait-replay pins SP-kept with per-doc section twins (GATE excluded, carries neither marker) |
| test_delivery_terminal_states.py | 0 (24→24) | ~45 sites → per-doc session-disposition section twins + runtime fenced blocks EXACT equality + Required status block template + WAITING_EXTERNAL placement twins + 6-marker ci-foreground bundle; SP keeps: 5 legacy-phrase bans, Final-state ban, combined pins (per-doc twins in resume file, same-commit ledger) |
| test_delivery_todo_contract.py | 0 (9→9; subtests 19) | ~50 sites → per-entrypoint Required-behavior twins + Structured todo projection twins + todo display block exact 5-line set + vocabulary co-section twins; SP keeps (Russian routing bans, todo-authority placement); L96-185 byte-identical |
| test_sea_speed_auth_v1.py | 0 (21→21; subtests 10) | ~30 sites → AUTH_DOC/OPS_DOC section twins (preamble issue chains, EXACT fenced blocks, co-sections, fail-closed Phase E, timing co-sections); SP keep (External host ban); SDD feature docs verbatim (wave-4 NO-CHANGE precedent) |
| test_camera1_live_replacement.py | 0 (19→19; subtests 6) | 12 pins → 11 co-section/section_titled twins + EXACT fenced blocks (relay prepare single block; canonical cam1 source EXACT 3-line block) + retirement section BODY rule twin (gated cleanup flow prepare-cleanup→activate-cleanup with --confirmed-public-hls precondition + refuse-unless-canonical guard removing only `cam1-new` — peer review F2); SP keep (UNKNOWN ban) |
| test_mediamtx_compatibility_remediation.py | 0 (14→14) | 12 pins → 9 unique groups → 6 twin groups (blocker classification, provenance, canary contract, final-scope bundle, worker non-mutation, rollback prohibition placement) — the demo surface; case-significant tokens ("MoQ", "CONFIRM_NEW_CAMERA", "one OpenCode rollout scope") enforced EXACT-CASE against the raw section text (peer review F1 — preserves the old case-sensitive pins' strength) |
| test_camera1_direct_h264_cutover.py | 0 (7→7) | 6 pins → co-section twins + preamble topology block with removeprefix("-> ") normalization (CC-5); SP keep (stale-identity ban) |
| test_ubuntu_worker_storage_lifecycle_contract.py | 0 (6→6) | 4 pins → preamble UNKNOWN + Safety model co-location (never-deletes + does-not-read-worker.env) + --apply-plan unique fenced block |
| test_ubuntu_worker_observability.py | 0 (6→6) | 4 pins → Runtime boundary + Safe inspection 2-line fenced block + Install periodic checks timer ban; SP keep (assertNotIn("Grafana") whole-doc absence) |
| test_ubuntu_worker_manual_install.py | 0 (7→7) | 1 DOC pin SP-kept (data-preservation warning — textual presence IS the contract, no executable validator); installer-script pins untouched (out of scope) |
| tests/support/markdown_docs.py | +0 (new file, no tests) | shared stdlib scanner (sections/section_containing/section_titled/fenced_blocks) — fence-aware, case-insensitive, first-match documented |
| demo tests/test_398_wave6_demo.py | +1 | new two-direction regression demonstration (additive) |

Arithmetic note: all 10 files converted IN PLACE at 0 test-count delta (git-counted
test methods base==now per file; battery identity 1227 + 1 demo = 1228 observed,
subtests 306→306) — the coverage became placement-sensitive without new test names:
the same 137 assertions now fail on section drift where the old pins passed
file-wide. Subtest splits (todo 19, auth_v1 10, camera1_live 6) are unchanged from
base (observed focused runs).

## Demo — two-direction proof (observed output)

`python3 -m pytest tests/test_398_wave6_demo.py -q` → **1 passed**:

- Sanity: the real runbook satisfies all six section-scoped twin groups and all 12
  retired pins (tmp copies only; docs/ never modified; repo-doc-unchanged asserted).
- Direction A (refactor tolerance): tmp copy rewritten meaning-preservingly (the two
  lowercase "loopback-only compatibility canary" prose references reworded to
  "compatibility trial"; the rollback prohibition joined into the preceding sentence)
  → all six twins PASS; EXACTLY the 2 prose-form pins FAIL
  (`assertEqual(pin_failed, list(PROSE_FORM_PINS))` → ['loopback-only compatibility
  canary', 'Automatic rollback remains prohibited']). The other 10 vocabulary pins
  are the twins' own needles — twin-pass logically implies pin-pass (documented
  deviation from the wave-4/5 "every pin fails" letter, flagged to the orchestrator;
  Correct-course CC-1).
- Direction B (dead-marker intolerance): tmp copy keeping ALL 12 markers verbatim
  but breaking placement six ways (classification clause out of "Why this exists";
  checksums sentence out of "Candidate provenance"; canary proof item out of the
  canary section; confirmation-gate step out of the scope list; worker non-mutation
  sentence split from the unit name; rollback caveat separated from the prohibition)
  → all 12 retired pins PASS (the false-green), ALL SIX twin groups FAIL.
- Inverted-mutation proofs (in-demo asserts + recorded manual flip-runs):
  - Direction A flip (rollback_rewrite=False): `E AssertionError: Lists differ:
    ['loopback-only compatibility canary'] != ['loopback-only compatibility canary',
    'Automatic rollback remains prohibited']` — the rollback pin's verdict inverts
    to PASS.
  - Direction B flip (split_rollback=False): `E AssertionError: Lists differ:
    [...-non-mutation-co-location'] != [...-non-mutation-co-location',
    'rollback-prohibition-co-location']` — the rollback twin's verdict inverts to
    PASS.
  - Both flip-runs: sed flip → focused pytest RED with the inverted verdict →
    restore → RESTORED_BYTE_IDENTICAL → focused pytest green (1 passed).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line = CONTROL_PLANE; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — remaining #398 raw-text sites outside this 10-file scope stay in the issue backlog (wave-5 NO-CHANGE records stand)
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED (tests-only wave)
- [x] Waivers resolved or current — no waivers

Wave record: all 10 cluster files adjudicated (mapping table in plan.md); battery
delta +1 (demo only; all conversions in place; skips and subtests unchanged) with
recorded twins, no assertion weakened or skipped; the demo proves the conversion
property in both directions on the real MediaMTX compatibility-remediation runbook
with the wave-6 verdict-class split documented and both inverted-mutation proofs
recorded; five course corrections recorded (CC-1 Direction-A verdict classes —
flagged deviation, CC-2 checkpoint append-only canon after the clobbering incident,
CC-3 wait-replay negation extension, CC-4 terminal bundle scoping, CC-5 cutover
topology normalization); observed totals 138 passed / 35 subtests (cluster, 11
files) and 1228 passed / 2 skipped / 306 subtests (full battery, worker-observed;
base 1227 / 2 / 306); validate_sdd.py grandfather entry `398-wave6` added (one
line, orchestrator-recorded exception).
