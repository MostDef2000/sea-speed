# Plan — Issue #398 wave 7

- Issue: #398
- Specification: specs/398-wave7/spec.md

## Architecture

Follow the wave-1..6 house model: RB (execute the real thing) > SS (structured
parse/scan) > SP (STATIC_POLICY pins kept verbatim with justification) >
NO-CHANGE (recorded rationale) > redundant retirement (only with a recorded
same-commit twin). The wave-7 surface is the auth-infra YAML layer: three test
files pinning RENDERED MediaMTX YAML by raw substring. The wave-7 house model
is the PARSED-STRUCTURE TWIN (wave-5 canon extended): `yaml.safe_load` parses
the rendered text and twins assert on the structure —

- reader-rule binding — the cam1/cam1-h264 reader rule block is located in the
  PARSED `authInternalUsers` list by its permissions (action read on the path
  name), not by its marker comment (comments are dropped by `safe_load`); the
  block's `ips` list is asserted with exact order equality (input order is the
  contract);
- security absence bans — the foreign-IP exclusion walks ALL parsed keys AND
  values recursively (`_parsed_strings`), asserting the needle appears in NO
  parsed string (stronger than substring absence on bytes: it covers every
  parsed scalar regardless of rendering format; comment-blind by design —
  comments are not config semantics);
- exact booleans — server toggles assert `assertIs(parsed[key], False)` /
  `assertIs(parsed["rtsp"], True)`, never falsy checks (a `0`/`""`/`None`
  must fail, not pass);
- exact key absence — `apiAddress` absence walks all dict keys at every level
  (`_parsed_yaml_keys`), not substring absence;
- YAML 1.1 scalars — the rendered `sourceOnDemand: no` parses to Python
  `False`; the twin asserts the parsed boolean with `assertIs`, and the
  byte-level `no` spelling stays frozen by the untouched byte oracles.

Byte-level contracts stay with their byte oracles: the golden render test and
the parity oracle (LEGACY_SINGLE_CAMERA_CONFIG exact equality) are NO-CHANGE —
they freeze the bytes ON PURPOSE. pyyaml is already a test-env dependency
(wave 4/5 precedent). No new frameworks or patterns; no tests/support changes
(byte-identical).

## Decisions

- **Parsed-structure twins over anywhere-in-bytes pins**: the rendered YAML is
  a structured artifact; the twin asserts the structure (ips order, boolean
  off-set, key absence) and stops asserting the bytes — the bytes stay frozen
  by the dedicated byte oracles, so nothing is unpinned, but formatting drift
  no longer produces false failures.
- **Security absence walks everything**: the foreign-IP ban (IP_C) is the
  wave's security-critical twin — it recursively walks every parsed key and
  value and asserts the IP appears in NO string (exact-value occurrences and
  embedded substrings inside parsed values both fail). The old
  `assertNotIn(IP_C, rendered)` covered only the rendered bytes; the twin
  covers the parsed semantics and is formatting-insensitive.
- **Strengthening is verified against the real render first**: the 9-key
  off-set was probed from the live renderer CLI and cross-checked against
  LEGACY_SINGLE_CAMERA_CONFIG BEFORE the twin was written (work-order
  requirement); the Unit-3 rule twin asserts the REAL combined rule (reader +
  publisher IPs) — the deviation from the checkpoint sketch is recorded in
  the mapping table, not silently asserted.
- **SP keeps are byte-identity or renderer-ownership contracts**: the
  SINGLE_IP_BLOCK pin IS the byte-identity contract (the test's name says
  byte_identical — a parsed twin cannot distinguish byte-identical from
  structurally-equal output); the preview marker line is a COMMENT (dropped
  by `safe_load`) whose textual presence IS the renderer-ownership contract
  for the bounded sanitize scanner. Both carry in-code justification.
- **The demo asserts the twin's verdict, not a pytest subprocess**: Direction
  A loads the mutated text and asserts the twin function's rejection (the
  self-proving inversion); Direction B asserts the old substring conditions
  hold on the mutated text (the false-green) AND the twin rejects it. All
  mutations land in TemporaryDirectory copies; repo files are never written.
- **NO-CHANGE records stand from earlier waves**: the CLI-boundary and
  shell-flow substring pins (they pin the subprocess/shell boundary bytes and
  sit next to executed verification), the wave-3 shell-contract SP pins, the
  byte-freeze oracles, and all executed twins (verify_internal_reader_rule,
  idempotency, _reader_ip_list, scope tokens, verify-rejection tests,
  shared-rule-parser test, watchdog tests).

## Site-mapping table (old → replacement)

| File | Retired pin (group) | Kind | Twin / where it lives |
|------|---------------------|------|-----------------------|
| test_mediamtx_multi_reader_ip.py | L77 `assertIn(f'ips: ["{IP_A}", "{IP_B}"]', rendered)` (ips order) | SS | parsed twin: `_reader_rule_blocks(yaml.safe_load(rendered), "cam1")` — exactly 1 block, `ips == [IP_A, IP_B]` (order preserved) |
| test_mediamtx_multi_reader_ip.py | L78 `assertNotIn(IP_C, rendered)` (SECURITY foreign-IP exclusion) | SS | parsed twin: recursive walk `_parsed_strings(parsed)` over ALL parsed keys+values — no parsed string contains IP_C (stronger on parsed scalars); the byte-level ban `assertNotIn(IP_C, rendered)` is RETAINED alongside the parsed twin as defense in depth (yaml.safe_load drops comments, so a foreign IP mentioned only in a comment would pass the parsed twin — the byte pin keeps that surface covered; strictly same-or-stronger now) |
| test_mediamtx_multi_reader_ip.py | L91 `assertIn(f'ips: ["{IP_B}", "{IP_A}"]', flipped)` (flipped order) | SS | parsed twin: flipped block `ips == [IP_B, IP_A]` |
| test_mediamtx_multi_reader_ip.py | L102 `assertIn(SINGLE_IP_BLOCK, str_rendered)` | SP | KEPT verbatim with in-code justification: the pin IS the byte-identity contract (test name: byte_identical_to_historical_str_behavior); a parsed twin cannot distinguish byte-identical from structurally-equal output |
| test_mediamtx_multi_reader_ip.py | executed twins L79 verify_internal_reader_rule, L81-84 idempotency assertEqual, L97 list==str, L100-101 _reader_ip_list, L103-105 scope tokens | NO-CHANGE | executed twins already present; untouched |
| test_mediamtx_multi_reader_ip.py | CLI-boundary substring pins L170/L178 (ips line on subprocess output), L186 (SINGLE_IP_BLOCK on CLI output), L290-291/L303 (ips line + IP_C ban on shell-flow candidate) | NO-CHANGE | they pin the CLI/shell BOUNDARY bytes (subprocess output, not the renderer-core API); L172/L292 execute verify_internal_reader_rule on the same bytes; the renderer-core behavior they reflect is twin-covered at the renderer level this wave (same-commit coverage ledger) |
| test_mediamtx_multi_reader_ip.py | wave-3 SP pins L331-335 (forwarding count, verify-reader-auth, scope-evidence literals) | NO-CHANGE | wave-3 SP records with in-code rationale stand; shell text, not rendered YAML |
| test_mediamtx_preview_relay.py | L345 `assertNotIn("api: yes", config)` | SS | parsed twin: `assertIs(parsed["api"], False)` (exact boolean — stronger than a substring ban: also rejects `api: 1`, `api: "yes"` parsed truthy) |
| test_mediamtx_preview_relay.py | L346 `assertNotIn("apiAddress", config)` | SS | parsed twin: `"apiAddress" not in _parsed_yaml_keys(parsed)` — exact key absence at EVERY level (recursive), not substring absence |
| test_mediamtx_preview_relay.py | L349 `assertIn("api: false\n", config)` | SS | same parsed twin as L345 (the group collapses to one exact-boolean twin; the byte presence pin is subsumed — `assertIs(False)` implies the key exists and is off) |
| test_mediamtx_preview_relay.py | L353-354 marker_line `assertIn(f"  {PREVIEW_MARKER}\n", config)` | SP | KEPT verbatim with in-code justification: the marker is a COMMENT (`yaml.safe_load` drops comments); its textual presence IS the renderer-ownership contract (the bounded sanitize scanner marks the rule renderer-owned by this exact line) |
| test_mediamtx_preview_relay.py | L362-363 loop `assertIn(f"{key}: false\n")` for api/metrics/pprof/playback/moq | SS | parsed twin STRENGTHENED to the FULL 9-key off-set: `assertIs(parsed[key], False)` for rtmp/hls/webrtc/srt/api/metrics/pprof/playback/moq (off-set VERIFIED against the live renderer probe + LEGACY_SINGLE_CAMERA_CONFIG before implementation — the old loop covered only 5 of 9; recorded strengthening per R-3) |
| test_mediamtx_preview_relay.py | L364 `assertIn("rtsp: true\n", config)` | SS | parsed twin: `assertIs(parsed["rtsp"], True)` |
| test_mediamtx_preview_relay.py | golden render L153-194 + parity oracle L225-233 (LEGACY_SINGLE_CAMERA_CONFIG exact equality, marker-line replace) | NO-CHANGE | byte-freeze oracles — exact-byte equality IS the contract (#442/#522 D-3); untouched |
| test_mediamtx_preview_relay.py | (byte-level guard note, peer review) | NO-CHANGE | after the parsed-twin conversion the LEGACY_SINGLE_CAMERA_CONFIG parity oracle remains the ONLY byte-level guard for the off-key formatting (the parsed twins assert values, not bytes) — its integrity is load-bearing; it stays byte-identical |
| test_mediamtx_preview_relay.py | verify-rejection tests L296-338 (drifted ips, missing marker, drifted action, drifted path pattern) | NO-CHANGE | behavioral/executed twins (real verify-preview-auth CLI runs); untouched |
| test_mediamtx_preview_relay.py | shared-rule-parser test L366-375 (`_parse_rule_block` on splitlines) | NO-CHANGE | executed twin; untouched |
| test_mediamtx_preview_relay.py | wave-3 shell-contract pins (L869-872 wiring pins, L915-918 SP evidence/ban pins) | NO-CHANGE | wave-3 records with in-code rationale stand; shell text, not rendered YAML |
| test_vps_transcode_to_ubuntu.py | L56 `assertIn("ips:", text)` (vacuous) | SS | parsed twin: the cam1-h264 rule block (located by read-permission on cam1-h264 in parsed authInternalUsers) — exactly 1 block, `ips == ["82.146.37.153", "10.123.239.102"]` |
| test_vps_transcode_to_ubuntu.py | L57 `assertIn("read", text)` (vacuous: matched "reader") + L58 `assertIn("publish", text)` (weak) | SS | parsed twin: the rule block's `permissions == [{action: read, path: cam1-h264}, {action: publish, path: cam1-h264}]` (exact list — stronger than inclusion) |
| test_vps_transcode_to_ubuntu.py | L61 `assertIn("cam1-h264:", text)` | SS | parsed twin: `"cam1-h264" in parsed["paths"]` |
| test_vps_transcode_to_ubuntu.py | L62 `assertIn('source: "publisher"', text)` | SS | parsed twin: `parsed["paths"]["cam1-h264"]["source"] == "publisher"` |
| test_vps_transcode_to_ubuntu.py | L63 `assertIn("sourceOnDemand: no", text)` | SS | parsed twin: `assertIs(parsed["paths"]["cam1-h264"]["sourceOnDemand"], False)` (YAML 1.1: `no` parses to False; exact boolean, not falsy) |
| test_vps_transcode_to_ubuntu.py | L82 `assertIn('hlsAddress: ":18889"', text)` | SS | parsed twin: `parsed["hlsAddress"] == ":18889"` |
| test_vps_transcode_to_ubuntu.py | L54 executed verifier `verify_internal_reader_rule(text, ...)` | NO-CHANGE | executed twin already present; kept |
| test_vps_transcode_to_ubuntu.py | DEVIATION record: the checkpoint sketch listed the rule twin as `ips == ["82.146.37.153"]` (reader only) | SS | the REAL render carries reader + publisher IPs in renderer order (`_reader_rule_lines`: reader first, publisher appended) — the twin asserts what IS true (verified by live probe before implementation); recorded here per the work-order rule |
| tests/test_398_wave7_demo.py | (new) two-direction demo | SS | Direction A: api mutation → retired L345 pin fails + parsed twin rejects (verdict asserted in-demo) + class-split trade proven (`api:  false` double-space fails the retired byte pin, passes the twin); Direction B: srt mutation → ALL 5 retired pins green (asserted pin by pin) + parsed twin rejects; tmp copies only |

## Affected contours

- Tests only: the 3 converted test files, the new demo, this trio — plus the
  recorded one-line grandfather entry in scripts/ci/validate_sdd.py.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, .github/**,
  nginx/**, docs/**, contracts/**, tests/support/** (byte-identical), and all
  wave-1..wave-6 test files (byte-identical).

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in
  the session checkpoint /tmp/opencode/398-w7/checkpoint.md: multi_reader_ip
  15 passed / 7 subtests, preview_relay 47 passed / 11 subtests,
  vps_transcode 6 passed, demo 2 passed).
- Cluster: `pytest` over the 4 files (3 cluster + demo) → 70 passed / 18
  subtests (all 3 files converted in place at 0 count delta; demo +2).
- Full battery: worker-run per the wave-7 work order (`python3 -m pytest -p
  no:cacheprovider --basetemp=/tmp/opencode/398-w7/pytest-tmp tests/ -q`) →
  OBSERVED 1230 passed / 2 skipped / 306 subtests in 72.77s (base 1228 / 2 /
  306 on ec8e9b4, orchestrator-observed; identity 1228 + 2 demo methods).
- `python3 scripts/ci/validate_sdd.py` → informational bare run for the trio
  after the grandfather line (NOT a gate here — the orchestrator runs
  `--event` mode on the fresh commit); expected clean once specs/398-wave7/
  exists (strict set equality at validate_prefix_uniqueness).
- ruff: `python3 -m ruff check --config scripts/quality/ruff.toml` clean on
  every changed file.
- Allowed-paths check: `git status` shows only the 3 cluster test files + the
  demo, specs/398-wave7/** plus the recorded validate_sdd.py exception.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE change (tests + one
  validator line); runtime acceptance = exact-head CI green on the merge PR.
- RF-002: post-wave cluster reports 70 / 18 (counts flat vs base + demo 2);
  all deltas recorded in the tasks.md battery-delta ledger (retired assertion
  → covering twin, same commit); the coverage became structure-sensitive
  without new test names in the 3 files.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every mapping-table action's focused run green (multi_reader_ip 15 passed / 7 subtests, preview_relay 47 passed / 11 subtests, vps_transcode 6 passed); NO-CHANGE records recon-documented
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: cluster 70 passed / 18 subtests (3 files at 0 delta + demo +2); battery-delta ledger in tasks.md maps every retired assertion to its recorded twin; full battery observed 1230 passed / 2 skipped / 306 subtests
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave7_demo.py green — 2 passed (Direction A twin-rejection + retired-pin failure + proven class-split trade; Direction B all-retired-pins-green + twin rejection); both inversions asserted in-demo on the twin's verdict; manual flip-runs recorded in tasks.md
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: full battery 1230 passed / 2 skipped / 306 subtests in 72.77s observed (base 1228 / 2 / 306 on ec8e9b4); validate_sdd green after the grandfather line
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git status shows only declared paths + the recorded validate_sdd.py grandfather-entry exception

## Correct-course check

Course correction CC-1 — Unit-3 rule-twin deviation from the checkpoint sketch
(the sketch listed the parsed twin as `ips == ["82.146.37.153"]`, reader only;
the live render probe showed the combined rule carries reader + publisher IPs
in renderer order — `_reader_rule_lines` appends publisher_ips):

- Trigger: NONE
- Issue impact: NONE — the admitted tests-only scope is unchanged.
- Specification impact: R-3 records the deviation explicitly; the twin asserts
  what IS true (reader + publisher, renderer order) instead of the sketch.
- Plan impact: mapping-table DEVIATION row records the probe finding.
- Tasks impact: T-4 evidence records the probe; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — the probe-first discipline (verify the real render before
  writing the twin) is the wave-7 canon and matches the work-order
  instruction for the Unit-2 off-set.

Course correction CC-2 — demo method count (the checkpoint's battery
expectation said "+1 demo → 1229"; the work order requires each direction to
be a separate test method, so the demo contributes +2 and the observed battery
is 1230):

- Trigger: NONE
- Issue impact: NONE — same admitted scope; the demo file was already in scope.
- Specification impact: AC-002/AC-004 record the observed identity
  1228 + 2 = 1230.
- Plan impact: Validation section records the observed battery.
- Tasks impact: battery-delta ledger records the +2 with the method names.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — future demo waves state the method count explicitly.
