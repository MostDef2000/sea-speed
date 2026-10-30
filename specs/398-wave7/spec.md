# Spec: #398 wave 7 — auth-infra YAML cluster F (parsed-structure twins on rendered YAML)

- Issue: #398
- Specification: specs/398-wave7/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the
  auth-infra YAML cluster F of that scope (tests-only + one recorded validator
  line), per the wave-7 work order (base ec8e9b4, the wave-6 merge).

## Product outcome

The three auth-infra regression files that still pin RENDERED MediaMTX YAML by
raw substring (tests/test_mediamtx_multi_reader_ip.py,
tests/test_mediamtx_preview_relay.py, tests/test_vps_transcode_to_ubuntu.py)
stop verifying renderer output by matching text anywhere in the rendered bytes
and start verifying it by asserting on the PARSED structure
(`yaml.safe_load`): reader-rule IP lists (order preserved), the foreign-IP
exclusion (recursive walk over every parsed key/value), the preview profile's
server off-set (strengthened to the FULL 9-key off-set + rtsp on, each an
exact boolean via `assertIs`), the api-less contract (exact `False` + no
`apiAddress` key at any level), and the transcode publisher path (source,
`sourceOnDemand` as exact `False` per YAML 1.1). A render that drifts in
formatting (quoting, spacing, key order) no longer produces false failures; a
render that drifts in STRUCTURE (a server toggled on, a foreign IP granted, an
api address introduced) fails the parsed twin where the old substring pins
either failed noisily on bytes or — for the 5-key loop — passed silently (the
false green removed: `srt: yes` passed every old pin). Pins whose textual
presence IS the contract stay verbatim SP with recorded rationale (the
byte-identity block, the preview marker comment line). A two-direction demo
(`tests/test_398_wave7_demo.py`) proves the conversion property on tmp copies
of the real canonical preview render: the twin carries the retired api pins'
protection (Direction A) and adds protection the old pins lacked (Direction
B), with the formatting-sensitivity trade documented and proven.

## User scenarios

- A developer reformats the rendered YAML (single quotes, reordered keys,
  extra whitespace between tokens): the parsed twins stay green where the old
  substring pins failed on bytes — false failure eliminated, bounded to the
  formatting-sensitive pins (the demo proves the `api:  false` double-space
  case explicitly).
- A future renderer change toggles an unused preview server on (`srt: yes`)
  while leaving every retired substring needle intact: the strengthened
  9-key off-set twin fails where the old 5-key loop passed — the false green
  removed (Direction B of the demo).
- A drift grants the foreign reader IP (IP_C) anywhere in the parsed config —
  as a rule ips entry, a key, or embedded in any string value: the recursive
  parsed-absence twin fails; the old substring ban only covered the exact
  rendered bytes.
- A future wave touches the renderer's YAML emission without structural
  change: review attention goes to real diffs instead of byte churn.

## Scope

- tests/test_mediamtx_multi_reader_ip.py, tests/test_mediamtx_preview_relay.py,
  tests/test_vps_transcode_to_ubuntu.py — adjudicated per the plan.md mapping
  table (parsed-structure twins, SP verbatim keeps, NO-CHANGE with rationale);
  executed twins (verify_internal_reader_rule, idempotency, _reader_ip_list,
  scope tokens, parity oracle, verify-rejection tests, shared-rule-parser test)
  untouched.
- tests/test_398_wave7_demo.py (new) — two-direction regression demonstration
  on tmp copies only (the renderer CLI runs for real; repo files never
  modified).
- specs/398-wave7/** — this trio.
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives
  `398-wave7` in the existing `"398"` GRANDFATHERED_PREFIX_COLLISIONS set
  (staged-wave precedent 396/397/520/537 and the 398-wave1..wave6 entries) so
  this trio is admissible; delivery-orchestrator addition, documented in
  plan.md Correct-course and tasks.md ledger. ONE line; no other scripts/**
  surface is touched.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**,
  nginx/**, docs/**, contracts/** untouched; tests/support/** byte-identical;
  wave-1..wave-6 test files untouched.
- Out of scope (NO-CHANGE, rationale in the mapping table / checkpoint): the
  CLI-boundary and shell-flow substring pins in
  test_mediamtx_multi_reader_ip.py (they pin the subprocess/shell BOUNDARY
  bytes, are adjacent to executed verification, and several are already
  wave-3 SP keeps with in-code rationale); the byte-freeze oracles (golden
  render, parity oracle) whose exact-byte equality IS the contract; the
  wave-3 shell-contract SP pins in test_mediamtx_preview_relay.py.
- Change classification: tests-only + 1 validator line = CONTROL_PLANE
  (contracts/runtime/RELEASE_READINESS_GATE.md) — authorized source lifecycle
  and PR/post-merge Quality only; runtime deployment NOT REQUIRED. Risk
  profile: NOT REQUIRED (tests-only wave).

## Requirements

- R-1: every raw substring pin on RENDERED YAML output identified by the
  wave-7 RECON (checkpoint /tmp/opencode/398-w7/checkpoint.md) is replaced by
  a parsed-structure twin per the plan.md mapping table (one deliberate
  carve-out: the foreign-IP byte-level ban is RETAINED alongside its parsed
  twin — yaml.safe_load drops comments, so the byte pin keeps non-parsed
  surfaces such as comments covered; strictly same-or-stronger); no assertion
  is lost without a recorded same-commit twin or verbatim SP retention;
  security properties are same-or-stronger (recursive parsed-absence for the
  foreign IP; `assertIs` exact booleans, never falsy checks; exact key
  absence, never substring absence).
- R-2 (SP justification): pins kept verbatim carry an in-code justification
  comment or a mapping-table rationale — the SINGLE_IP_BLOCK byte-identity
  pin (byte-identity backwards-compat IS the contract under test) and the
  preview marker line (a comment; `yaml.safe_load` drops comments; textual
  presence IS the renderer-ownership contract for the sanitize scanner).
- R-3 (recorded strengthening, verified against the real render): the preview
  off-set twin asserts the FULL 9-key off-set
  (rtmp/hls/webrtc/srt/api/metrics/pprof/playback/moq all exactly `False`) +
  `rtsp` exactly `True` — verified against the live canonical render and the
  LEGACY_SINGLE_CAMERA_CONFIG parity oracle before implementation (the old
  loop covered only 5 of the 9); the Unit-3 rule twin asserts the REAL
  combined rule (reader + publisher IPs in renderer order — a recorded
  deviation from the checkpoint sketch, which listed the reader IP only).
- R-4 (demo): tests/test_398_wave7_demo.py proves both directions on tmp
  copies of the real canonical preview render: (a) Direction A — the
  `api: false -> api: yes` mutation makes the parsed twin REJECT (asserted
  in-demo on the twin's verdict, no pytest subprocess) while the retired
  `api: yes` ban fails on the same bytes (the twin carries the old
  protection); (b) Direction B — the `srt: false -> srt: yes` mutation passes
  ALL retired-pin equivalents (asserted pin by pin on the mutated bytes) while
  the parsed twin rejects it (the twin adds protection). The documented
  formatting-sensitivity trade is proven in-demo (`api:  false` double-space
  fails the retired byte pin, passes the twin). Manual flip-run evidence
  recorded in tasks.md.
- R-5 (tests-only): if any conversion requires a production change → STOP and
  report; none did.
- R-6: the suite stays deterministic in CI — twins parse in-memory rendered
  text via pyyaml (already a test-env dependency; wave 4/5 precedent); the
  demo mutates tmp copies only; no network.
- R-7: full battery green with per-file deltas accounted (never weaker);
  validate_sdd green for the trio after the recorded grandfather line; changed
  files limited to the allowed set.

## Acceptance criteria

- AC-001: all 3 cluster files adjudicated in the plan.md mapping table
  (converted / SP-kept / NO-CHANGE) and every converted file's focused run is
  green. → TEST-001
- AC-002: cluster delta vs the base battery equals the per-file deltas (all 3
  files converted in place at 0 count delta; demo +2 methods) — the identity
  holds: 1228 + 2 = 1230 passed / 2 skipped / 306 subtests, observed. →
  TEST-002
- AC-003: tests/test_398_wave7_demo.py passes with both explicit directions
  (Direction A twin-rejection + retired-pin failure on the api mutation and
  the proven class-split trade; Direction B all-retired-pins-green false-green
  + twin rejection on the srt mutation), both inversions asserted in-demo on
  the twin's verdict, and the manual flip-run evidence recorded in tasks.md. →
  TEST-003
- AC-004: full battery `pytest tests/ -q` green on top of the base 1228 passed
  / 2 skipped / 306 subtests (base ec8e9b4, orchestrator-observed) with the
  AC-002 deltas applied — worker-observed this wave: 1230 passed / 2 skipped /
  306 subtests in 72.77s. → TEST-004
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio (after the
  recorded grandfather line; bare informational run clean once
  specs/398-wave7/ exists). → TEST-004, TEST-005
- AC-006: `git status`/diff shows only tests/** (the 3 converted files, the
  demo), specs/398-wave7/** plus the recorded orchestrator exception (one-line
  `398-wave7` grandfather entry in `scripts/ci/validate_sdd.py`, per Scope
  above). → TEST-005

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only + one validator line
  (CONTROL_PLANE); no deploy and no production artifact changes. Runtime
  acceptance = exact-head CI green on the merge PR (the battery, including the
  demo, runs in CI; pyyaml is already available in the CI test env).
- RF-002: after this wave the cluster reports 70 passed / 18 subtests (3 files
  at 0 count delta + demo 2); every count delta vs the base battery is
  recorded in the tasks.md battery-delta ledger (retired assertion → covering
  twin, same commit). Counts stayed flat — the coverage became
  structure-sensitive without new test names in the 3 files: the same
  assertions now fail on structural drift (and STOP failing on formatting
  drift) where the old pins matched bytes.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (in-memory parsing of renderer output via pyyaml; tmp-copy demo; no network; no new dependencies) | Validation: focused runs repeated across sessions; demo isolates mutations in TemporaryDirectory copies | Evidence: cluster 70 passed / 18 subtests in ~6s | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to a parsed-structure twin, a retained verbatim SP pin, or a recorded NO-CHANGE rationale; security properties same-or-stronger (recursive absence, assertIs booleans, exact key absence) | Validation: mapping table in plan.md; tasks.md battery-delta ledger | Evidence: ledger rows + focused run tails | Status: PASS
- NFR-003 | Area: performance | Target: cluster wall time stays bounded (~6s for 70 tests incl. the subprocess-rendering demo) | Validation: cluster timing observation | Evidence: focused run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: house conversion models only (the wave-5/7 canon: yaml.safe_load parsed-structure twins, comment-blind, formatting-insensitive; assertIs exact booleans; recursive value/key walks for absence bans; byte-freeze oracles stay for byte contracts) — no new framework/pattern invented | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
