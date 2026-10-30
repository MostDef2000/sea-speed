# Tasks — Issue #398 wave 7

- Issue: #398
- Specification: specs/398-wave7/spec.md

## Delivery tasks

- T-1: RECON + baseline: base battery 1228 passed / 2 skipped / 306 subtests on
  ec8e9b4 (orchestrator-observed, wave-6 merge); cluster recon per the wave-7
  checkpoint (21 candidates → 18 NO-CHANGE, 3 files with real raw pins on
  rendered YAML; per-line pin inventory with twin strategy); canonical preview
  render probed live BEFORE implementation (9-key off-set confirmed). DONE.
- T-2: test_mediamtx_multi_reader_ip.py — L77/L91 retired to parsed twins
  (cam1 reader block ips order via `_reader_rule_blocks` on `yaml.safe_load`),
  L78 retired to the recursive parsed-absence twin (`_parsed_strings`, keys +
  values); L102 SP-kept with the byte-identity justification comment;
  executed twins untouched. DONE (15 passed / 7 subtests).
- T-3: test_mediamtx_preview_relay.py (DEMO TARGET) — PreviewProfileContractTests:
  L345/L346/L349 retired to parsed twins (`assertIs(parsed["api"], False)`;
  recursive exact-key walk `_parsed_yaml_keys` for apiAddress absence at every
  level); L362-363 loop + L364 retired to parsed twins STRENGTHENED to the
  FULL 9-key off-set + rtsp `assertIs` True (off-set verified against the live
  probe + LEGACY_SINGLE_CAMERA_CONFIG); L353-354 marker_line SP-kept (comment;
  textual presence IS the renderer-ownership contract); parity oracle,
  verify-rejection tests and shared-rule-parser test untouched. DONE (47
  passed / 11 subtests).
- T-4: test_vps_transcode_to_ubuntu.py — L56-L63 retired to parsed twins
  (cam1-h264 rule block: ips == reader + publisher in renderer order — CC-1
  deviation from the sketch, probe-verified; exact read+publish permission
  list; paths["cam1-h264"] source + `sourceOnDemand` `assertIs` False per YAML
  1.1); L82 retired to the parsed hlsAddress twin; executed verifier L54 kept.
  DONE (6 passed).
- T-5: Demo tests/test_398_wave7_demo.py — two-direction proof on tmp copies
  of the real canonical preview render (Direction A: api mutation → retired
  pin fails + twin rejects, verdict asserted in-demo, class-split trade
  proven; Direction B: srt mutation → all 5 retired pins green + twin
  rejects). DONE (2 passed; flip-runs recorded below).
- T-6: Grandfather line (validate_sdd.py "398" set += "398-wave7", one line) +
  this trio + allowed-paths self-check; full battery worker-run per the work
  order. DONE.
- T-7: ruff clean on every changed file; validate_sdd informational run clean
  for the trio. DONE.

## Completion gate

- Cluster `pytest tests/test_mediamtx_multi_reader_ip.py
  tests/test_mediamtx_preview_relay.py tests/test_vps_transcode_to_ubuntu.py
  tests/test_398_wave7_demo.py -q` green: observed 70 passed / 18 subtests
  (all 3 files converted in place at 0 count delta; demo +2).
- Full battery `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w7/pytest-tmp tests/ -q`: OBSERVED 1230 passed
  / 2 skipped / 306 subtests in 72.77s (base 1228 / 2 / 306
  orchestrator-observed on ec8e9b4; identity 1228 + 2 demo methods = 1230;
  subtests unchanged).
- Demo two-direction proof observed: `python3 -m pytest
  tests/test_398_wave7_demo.py -q` → 2 passed (Direction A + Direction B, all
  inversions asserted in-demo on the twin's verdict).
- `validate_sdd.py` bare informational run for the trio after the grandfather
  line (NOT a gate at worker level — the orchestrator runs `--event` mode on
  the fresh commit, which also picks up the untracked trio); the intermediate
  duplicate-prefix error before the trio landed was the expected
  strict-set-equality state; clean once specs/398-wave7/ exists.
- ruff clean on changed files (`ruff check --config scripts/quality/ruff.toml`
  on the 3 converted files + the demo + validate_sdd.py → All checks passed).

## Requirements traceability

- AC-001 | Task: T-2, T-3, T-4 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-2, T-3, T-4, T-5 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-5 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-6 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-6, T-7 | Evidence: TEST-004, TEST-005 | Coverage: COVERED
- AC-006 | Task: T-6 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → the mapping table in plan.md (all 3 files adjudicated
pin by pin; every removed assertion has a twin, SP retention, or NO-CHANGE
rationale; security properties same-or-stronger) + the battery-delta ledger
below; R-2 → SP pins kept verbatim carry in-code justification comments;
R-3 → the 9-key off-set and the Unit-3 rule twin verified against live probes
before implementation (deviation recorded); R-4 → the demo's two-direction
proof with in-demo inversions and recorded flip-runs below; R-5 → no
production file touched (git status limited to tests/**, specs/398-wave7/** +
the recorded validate_sdd.py exception); R-6 → twins parse in-memory rendered
text via pyyaml, the demo mutates tmp copies only; R-7 → battery green with
per-file deltas accounted (orchestrator --event gate after commit).

## Battery-delta ledger (base ec8e9b4 = wave-6 merge; identity: 1228 + 2 demo methods = 1230 passed / 2 skipped / 306 subtests, OBSERVED)

| File | Delta (base→now) | Retired assertions → covering twin (same commit) |
|------|------------------|--------------------------------------------------|
| test_mediamtx_multi_reader_ip.py | 0 (15→15; subtests 7) | L77/L91 ips-order pins → parsed twins (cam1 reader block ips exact-order equality via `_reader_rule_blocks` on `yaml.safe_load`); L78 foreign-IP ban → recursive parsed-absence twin (`_parsed_strings` over ALL keys+values — same-or-stronger); L102 SINGLE_IP_BLOCK SP-kept (byte-identity IS the contract, in-code justification); executed twins (verify/idempotency/_reader_ip_list/scope tokens) and CLI-boundary pins NO-CHANGE (rationale in the mapping table) |
| test_mediamtx_preview_relay.py | 0 (47→47; subtests 11) | L345/L346/L349 api pins → parsed twins (`assertIs(parsed["api"], False)`; recursive exact-key apiAddress absence); L362-363 5-key loop + L364 rtsp pin → parsed twins STRENGTHENED to the FULL 9-key off-set + rtsp `assertIs` True (probe-verified); L353-354 marker_line SP-kept (comment; renderer-ownership contract); golden render + parity oracle + verify-rejection + shared-rule-parser NO-CHANGE (byte freeze / executed) |
| test_vps_transcode_to_ubuntu.py | 0 (6→6) | L56 vacuous ips pin + L57 vacuous read pin + L58 weak publish pin → parsed twins (cam1-h264 rule block: ips == reader+publisher renderer order — CC-1 deviation recorded; exact read+publish permission list); L61/L62/L63 path pins → parsed twins (paths["cam1-h264"] existence, source == "publisher", `sourceOnDemand` `assertIs` False per YAML 1.1); L82 hlsAddress pin → parsed twin; executed verifier L54 kept |
| demo tests/test_398_wave7_demo.py | +2 (new file: test_direction_a_twin_carries_the_retired_api_pins_protection, test_direction_b_twin_adds_protection_the_retired_pins_lacked) | new two-direction regression demonstration (additive; CC-2 records the +2 vs the checkpoint's "+1" estimate) |

Arithmetic note: all 3 files converted IN PLACE at 0 test-count delta
(git-counted test methods base==now per file — only assertion lines and
module-level helpers changed; battery identity 1228 + 2 = 1230 observed,
subtests 306→306) — the coverage became structure-sensitive without new test
names in the 3 files: the same assertions now fail on structural drift (and
stop failing on formatting drift) where the old pins matched bytes.

## Demo — two-direction proof (observed output)

`python3 -m pytest tests/test_398_wave7_demo.py -q` → **2 passed**:

- Direction A (test_direction_a_twin_carries_the_retired_api_pins_protection):
  the canonical render (real renderer CLI, one-camera inventory, tmp only)
  satisfies the parsed twin AND all 5 retired pins (sanity); the tmp-copy
  mutation `api: false` → `api: yes` makes the retired `api: yes` ban FAIL
  (the old pin caught this drift too) and the parsed twin REJECT with exactly
  `['server-off twin: api must be exactly False, got True']` — the inversion
  is asserted in-demo on the twin's verdict (no pytest subprocess). The
  documented class-split trade is proven in the same method: the
  formatting-only drift `api:  false` (double space) FAILS the retired
  `api: false\n` byte pin while PASSING the parsed twin (the boolean value is
  unchanged; the byte-level contract stays with the untouched parity oracle).
- Direction B (test_direction_b_twin_adds_protection_the_retired_pins_lacked):
  the tmp-copy mutation `srt: false` → `srt: yes` passes ALL 5 retired-pin
  equivalents on the mutated text (asserted pin by pin — srt was unpinned by
  the old 5-key loop; the api pins do not mention srt; rtsp is untouched) —
  the old false-green — while the parsed twin REJECTS with exactly
  `['server-off twin: srt must be exactly False, got True']` via the
  strengthened FULL 9-key off-set; the canonical render passes the twin (the
  verdict is mutation-sensitive, not a constant).
- Manual flip-run evidence (mutation OFF → inverted verdict → restore):
  - FLIP-A (`mutated = canonical` in Direction A): focused pytest RED —
    `AssertionError: True is not false` at the retired-pin assertion (the
    Direction-A chain holds only under the mutation; the twin's verdict
    inverts to PASS on the unmutated bytes). Direction B stayed green
    (1 failed / 1 passed).
  - FLIP-B (`mutated = canonical` in Direction B): focused pytest RED —
    `Second list contains 1 additional elements. First extra element 0:
    'server-off twin: srt must be exactly False, got True'` at the
    twin-rejection assertion (the twin's verdict inverts to PASS; the
    retired-pin assertions stayed green in the flip run — the false-green
    story holds). Direction A stayed green (1 failed / 1 passed).
  - Both restores: `cmp` → RESTORED_BYTE_IDENTICAL → focused pytest green
    (2 passed).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line = CONTROL_PLANE; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — remaining #398 raw-text sites outside this 3-file scope stay in the issue backlog (waves 1-6 NO-CHANGE records stand)
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED (tests-only wave)
- [x] Waivers resolved or current — no waivers

Wave record: all 3 cluster files adjudicated (mapping table in plan.md);
battery delta +2 (demo only; all conversions in place; skips and subtests
unchanged) with recorded twins, no assertion weakened or skipped; security
properties same-or-stronger (recursive parsed-absence for the foreign IP,
`assertIs` exact booleans, exact key absence at every level); the demo proves
the conversion property in both directions on tmp copies of the real canonical
preview render with the class-split trade proven in-demo and both flip-runs
recorded; two course corrections recorded (CC-1 Unit-3 rule-twin deviation —
probe-verified, CC-2 demo method count +2 vs the "+1" estimate — observed per
the work order); observed totals 70 passed / 18 subtests (cluster, 4 files)
and 1230 passed / 2 skipped / 306 subtests (full battery, worker-observed;
base 1228 / 2 / 306); validate_sdd.py grandfather entry `398-wave7` added
(one line, orchestrator-recorded exception).
