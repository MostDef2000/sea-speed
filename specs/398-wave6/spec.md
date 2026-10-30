# Spec: #398 wave 6 — governance-docs cluster raw-source-text conversion (section-scoped text twins)

- Issue: #398
- Specification: specs/398-wave6/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the
  governance-docs cluster of that scope (tests-only + one recorded validator line),
  per the wave-6 work order (base 0ab0911, the wave-5 merge).

## Product outcome

The governance-doc regression cluster (10 files) stops verifying runbooks, operator
docs, agent instructions and delivery contracts by reading them as raw text anywhere
in the file and starts verifying them by asserting on parsed document structure (SS:
section-scoped twins via the new stdlib scanner `tests/support/markdown_docs.py` —
fence-aware ATX sections, case-insensitive co-location, `section_titled` heading
binding, fenced-block extraction — plus `json.loads` for the embedded checkpoint-v2
schema block and an executed `upgrade_v1_checkpoint` twin). A marker that drifts
into an unrelated section now fails the placement contract instead of passing
file-wide; a doc that keeps every historical marker but breaks the placement
contract fails where the old pins passed (the false green removed). Pins whose
textual presence IS the contract (literal policy bans, data-preservation warnings,
prose SDD docs) stay verbatim SP or NO-CHANGE with recorded rationale. A
two-direction demo (`tests/test_398_wave6_demo.py`) proves the conversion property
on the real MediaMTX compatibility-remediation runbook, with the wave-6-specific
verdict classes documented (see R-3).

## User scenarios

- A developer rewords a runbook's prose around a pinned contract (lowercase prose
  references, sentence joins): the section-scoped twins stay green where they anchor
  on headings/case-insensitive co-location (old text pins would have failed — false
  failure eliminated, bounded to the 2 prose-form pins; see R-3).
- A developer moves a contract sentence into an unrelated section while leaving every
  historical marker verbatim: the co-location twin fails (old text pins would have
  passed — false pass eliminated).
- A doc drops one half of a paired ban (rollback prohibition without the
  separate-governed-decision caveat): the placement twin fails even though every
  retired marker is still present somewhere in the file.
- A future wave touches docs/** or contracts/** prose without structural change:
  review attention goes to real diffs instead of text churn.

## Scope

- tests/test_delivery_resume_contract.py, tests/test_delivery_terminal_states.py,
  tests/test_delivery_todo_contract.py, tests/test_sea_speed_auth_v1.py,
  tests/test_camera1_live_replacement.py,
  tests/test_mediamtx_compatibility_remediation.py,
  tests/test_camera1_direct_h264_cutover.py,
  tests/test_ubuntu_worker_storage_lifecycle_contract.py,
  tests/test_ubuntu_worker_observability.py,
  tests/test_ubuntu_worker_manual_install.py — adjudicated per the plan.md mapping
  table (SS section-scoped twins, SP verbatim bans, NO-CHANGE with rationale).
- tests/support/markdown_docs.py (new) — shared stdlib markdown structure scanner
  (sections / section_containing / section_titled / fenced_blocks), fence-aware;
  justified by 3+ sharing files.
- tests/test_398_wave6_demo.py (new) — two-direction regression demonstration.
- specs/398-wave6/** — this trio.
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives `398-wave6`
  in the existing `"398"` GRANDFATHERED_PREFIX_COLLISIONS set (staged-wave precedent
  396/397/520/537 and the 398-wave1..wave5 entries) so this trio is admissible;
  delivery-orchestrator addition, documented in plan.md Correct-course and tasks.md
  ledger. ONE line; no other scripts/** surface is touched.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**,
  nginx/**, docs/**, contracts/** untouched (wave-1..wave-5 test files also
  untouched, byte-identical).
- Out of scope (NO-CHANGE, rationale in the mapping table / checkpoint): the wave-5
  NO-CHANGE prose-scan records (test_delivery_contract_convergence.py,
  test_delivery_quality_layer.py, test_github_actions_connector_contract.py — prose
  IS the contract; reopening = churn); test_camera_preview_gallery.py SDD/QUICKSTART
  prose (wave-4 record stands); SDD feature docs in test_sea_speed_auth_v1.py
  (wave-4 precedent, kept verbatim in-code); installer-script pins in
  test_ubuntu_worker_manual_install.py (they pin the INSTALLER, not docs).
- Change classification: tests-only + 1 validator line = CONTROL_PLANE
  (contracts/runtime/RELEASE_READINESS_GATE.md) — authorized source lifecycle and
  PR/post-merge Quality only; runtime deployment NOT REQUIRED. Risk profile: NOT
  REQUIRED (tests-only wave).

## Requirements

- R-1: every behavioral assertion carried by a raw anywhere-in-file text pin is
  replaced by a section-scoped structural twin per the plan.md mapping table; no
  assertion is lost without a recorded same-commit twin (redundancy ledger in
  tasks.md) or verbatim SP retention.
- R-2 (SP justification): STATIC_POLICY pins kept verbatim carry an in-code
  justification comment or a mapping-table rationale (legacy-phrase bans; no-Grafana
  absence ban; "External host:" ban; data-preservation warning; rollback-prohibition
  placement twin; prose SDD docs NO-CHANGE — the text IS the artifact).
- R-3 (demo, with the recorded wave-6 verdict-class deviation):
  tests/test_398_wave6_demo.py proves both directions on tmp copies of the real
  MediaMTX runbook: (a) refactor tolerance — a meaning-preserving rewording passes
  every section-scoped twin; the retired pins split into two verdict classes — the
  10 "vocabulary" pins carry the contract identifiers the twins match on, so they
  fail only under refactors that ALTER those identifiers (including case drift,
  which the twins enforce exact-case for the gate/policy tokens "MoQ",
  "CONFIRM_NEW_CAMERA", "one OpenCode rollout scope") and exactly the 2
  "prose-form" pins fail under editorial rewording the twins tolerate (deviation
  from the wave-4/5 "every pin fails" letter, flagged to the orchestrator, recorded
  in Correct-course CC-1); (b) dead-marker
  intolerance — all 12 markers verbatim with six placement breaks FAILS all six
  twin groups where the retired pins pass (the false green). Both directions carry
  in-demo inverted-mutation proofs (flipping one mutation inverts the verdict).
- R-4 (tests-only): if any conversion requires a production change → STOP and
  report; none did.
- R-5: the suite stays deterministic in CI — twins parse repo files read-only via
  the stdlib scanner (no new dependencies); executed twins run in tmp fixtures; the
  demo mutates tmp copies only; no network.
- R-6: full battery green with per-file deltas accounted (never weaker);
  validate_sdd green for the trio after the recorded grandfather line; changed files
  limited to the allowed set.

## Acceptance criteria

- AC-001: all 10 cluster files adjudicated in the plan.md mapping table (converted /
  SP-kept / NO-CHANGE) and every converted file's focused run is green. → TEST-001
- AC-002: cluster delta vs the base battery equals the per-file deltas (all 10 files
  converted in place at 0 count delta; demo +1) — the identity holds: 1227 + 1 =
  1228 passed / 2 skipped / 306 subtests, observed. → TEST-002
- AC-003: tests/test_398_wave6_demo.py passes with both explicit directions
  (refactor-tolerant with the documented 2/12 prose-form verdict split AND
  dead-marker-intolerant with all six twin groups failing), both inverted-mutation
  proofs asserted in-demo, and the flip-run evidence recorded in tasks.md. →
  TEST-003
- AC-004: full battery `pytest tests/ -q` green on top of the base 1227 passed /
  2 skipped / 306 subtests (base 0ab0911, orchestrator-observed) with the AC-002
  deltas applied — worker-observed this wave: 1228 passed / 2 skipped / 306
  subtests in 72.25s. → TEST-004
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio (after the
  recorded grandfather line; bare informational run clean once specs/398-wave6/
  exists). → TEST-004, TEST-005
- AC-006: `git status`/diff shows only tests/** (the 10 converted files, the new
  scanner, the demo), specs/398-wave6/** plus the recorded orchestrator exception
  (one-line `398-wave6` grandfather entry in `scripts/ci/validate_sdd.py`, per
  Scope above). → TEST-005

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only + one validator line
  (CONTROL_PLANE); no deploy and no production artifact changes. Runtime acceptance
  = exact-head CI green on the merge PR (the battery, including the executed
  upgrade twin and the demo, runs in CI; the scanner is stdlib-only and offline).
- RF-002: after this wave the cluster reports 138 passed / 35 subtests (10 files at
  0 count delta + demo 1); every count delta vs the base battery is recorded in the
  tasks.md battery-delta ledger (retired assertion → covering twin, same commit).
  Counts stayed flat — the coverage became placement-sensitive without new test
  names: the same assertions now fail on section drift where the old pins passed
  file-wide.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (read-only parsing of repo files via the stdlib scanner; tmp-copy demo; no network; no new dependencies) | Validation: focused runs repeated across sessions; demo isolates mutations in tmp copies | Evidence: cluster 138 passed / 35 subtests in 3.36s | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to a section-scoped twin, a retained verbatim SP pin, or a recorded NO-CHANGE rationale | Validation: mapping table in plan.md; tasks.md battery-delta ledger | Evidence: ledger rows + focused run tails | Status: PASS
- NFR-003 | Area: performance | Target: cluster wall time stays bounded (3.36s for 138 tests incl. the executed upgrade twin and the demo) | Validation: cluster timing observation | Evidence: cluster run tail | Status: PASS
- NFR-004 | Area: maintainability | Target: house conversion models only (the shared markdown_docs.py scanner canon: fence-aware ATX sections, case-insensitive co-location with disambiguating co-markers, section_titled heading binding, fenced-block EXACT-equality twins, json.loads for embedded schema blocks) — no new framework/pattern invented | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
