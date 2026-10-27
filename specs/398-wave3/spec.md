# Spec: #398 wave 3 — mediamtx/deploy-shell cluster raw-source-text conversion (RB/SS/SP)

- Issue: #398
- Specification: specs/398-wave3/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the 8-file
  mediamtx/deploy-shell cluster of that scope (tests-only), per the wave-3 work order
  (base 03c7543).

## Product outcome

The mediamtx regression cluster (8 files) stops verifying deploy-shell and renderer behavior by
reading script sources as raw text and starts verifying it by executing the real thing (RB) or
parsing it structurally (SS: `ast.parse`, `yaml.safe_load`). Raw `assertIn` / byte-position /
loop-text pins become executed twins or structured-shape assertions; STATIC_POLICY pins
(fail-closed shell markers, cross-flow wiring counts, worker-control bans, rollback warnings,
negative-space bans whose textual presence IS the deploy contract) stay verbatim with in-code
justification. Redundant text pins retire only against recorded same-commit executed twins, so
the battery is never weaker. A shell-exec harness (`tests/support/relay_shell.py`) runs the REAL
deploy script bytes under an unprivileged user namespace (root-gated flows execute; systemctl is
a stub on PATH); a two-direction demo (`tests/test_398_wave3_demo.py`) proves the conversion
property on the real camera-relay script.

## User scenarios

- A developer reformats the reader-ip accumulation loop or renames a shell variable in
  `camera-relay.sh`: the converted checks stay green (old loop-text pins would have failed —
  false failure eliminated), except where marker text IS the policy (SP pins deliberately still
  fail).
- A developer breaks the reader-ip forwarding (drops accumulated occurrences) or the
  renderer-gate ordering while leaving the historical marker text in place: the executed twin
  fails (old text pin would have passed — false pass eliminated).
- A future wave touches deploy scripts without behavior change: review attention goes to real
  diffs instead of shell-text churn.

## Scope

- tests/test_mediamtx_systemd_v247_runner.py, tests/test_mediamtx_activate_identity.py,
  tests/test_mediamtx_compatibility_remediation.py, tests/test_mediamtx_multi_reader_ip.py,
  tests/test_mediamtx_preview_relay.py, tests/test_mediamtx_remediate_reader.py,
  tests/test_mediamtx_sanitize_auth.py, tests/test_camera1_live_replacement.py — converted per
  the plan.md mapping table (RB→exec, SS→structured parse, SP verbatim, redundant→retired with
  twins).
- tests/support/relay_shell.py (new, additive) — shell-exec harness (user-namespace root-gated
  flows, systemctl stub, recording renderer, bindable-private-listener helper).
- tests/test_398_wave3_demo.py (new) — two-direction regression demonstration.
- specs/398-wave3/** — this trio.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**
  untouched (wave-1/wave-2 test files also untouched).
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives `398-wave3` in the
  existing `"398"` GRANDFATHERED_PREFIX_COLLISIONS set (staged-wave precedent 396/397/520/537
  and the 398-wave1/wave2 entries) so this trio is admissible; delivery-orchestrator addition,
  documented in plan.md Correct-course and tasks.md ledger. No other scripts/** surface is
  touched.

## Requirements

- R-1: every behavioral assertion carried by a raw text pin is replaced by an executed or
  structured twin per the plan.md mapping table; no assertion is lost without a recorded
  same-commit executed twin (redundancy ledger in tasks.md) or verbatim STATIC_POLICY retention.
- R-2 (SP justification): STATIC_POLICY pins kept verbatim carry an in-code justification comment
  (`398-wave3: SP pin — …`; wave-2 T8b/D-6 precedents; cross-flow wiring counts; worker-control
  and rollback bans).
- R-3: tests/test_398_wave3_demo.py proves both directions on tmp copies of the real script:
  (a) refactor tolerance — behavior-preserving loop-idiom rewrite passes the executed check while
  the retired text pins would fail; (b) dead-marker intolerance — marker text intact with broken
  forwarding FAILS the executed check where the retired pins pass.
- R-4 (tests-only): if any conversion requires a production change → STOP and report; none did.
- R-5: the suite stays deterministic in CI — executed harnesses are offline (systemctl stub,
  recording renderer, tmp fixtures, no network beyond the scripts' own RFC1918 loopback-listener
  probes; dead addresses never relied on); root-gated twins skip gracefully where user namespaces
  are unavailable (same discipline as the historical root-gated skips they replace, and they EXECUTE
  where the sandbox provides `unshare --user --map-root-user`).
- R-6: full battery green with per-file deltas accounted (never weaker); validate_repo and
  validate_sdd green; changed files limited to the allowed set.

## Acceptance criteria

- AC-001: all 8 cluster files adjudicated in the plan.md mapping table (converted / SP-kept /
  retired-with-twin / NO CHANGE) and every converted file's focused run is green.
- AC-002: battery delta vs baseline 1160 passed / 4 skipped / 271 subtests equals cluster per-file
  deltas (F1 +5, F3 +3, F4 +10, F5 +3, F6 +3, F7 +1, F8 +3; F2 0; per-file test counts counted
  from the base commit 03c7543) plus demo +1, with F7's two historical root-gated skips
  additionally EXECUTED — the identity holds: 1160 + 28 + 1 + 2 = 1191 (skipped 4→2), with the
  covering twin recorded in the tasks.md ledger for every removed assertion; observed 1191 passed /
  2 skipped / 294 subtests (after the wave-3 review round: MED-2 field-order twin, MED-3
  root-ownership-gate twin, LOW-6 single-peer scope twin).
- AC-003: tests/test_398_wave3_demo.py passes with both explicit directions (refactor-tolerant
  AND dead-marker-intolerant), inverted-mutation run recorded in tasks.md.
- AC-004: full battery `pytest tests/ -q` green (observed 1191 passed / 2 skipped / 294 subtests
  in 48.79s).
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio; `validate_repo.py` green.
- AC-006: `git status`/diff shows only tests/**, tests/support/**, specs/398-wave3/** plus the
  recorded orchestrator exception (one-line `398-wave3` grandfather entry in
  `scripts/ci/validate_sdd.py`, per Scope above).

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only change; no deploy and no production artifact
  changes. Runtime acceptance = exact-head CI green on the merge PR (the battery, including the
  executed shell twins, runs in CI; user-namespace-unavailable environments skip the root-gated
  twins exactly as the historical root-gated skips did).
- RF-002: after this wave the battery reports 1191 passed / 2 skipped / 294 subtests; every count
  delta vs the wave baseline is recorded in the tasks.md battery-delta ledger (retired assertion →
  covering executed twin, same commit). Subtests grew 271→294 (executed forwarding/transport/
  inventory-gate matrices) — evidence that conversion made coverage observable, not smaller.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (systemctl stub knobs, recording renderer, tmp fixtures, bindable private listener probed with graceful skip; dead RFC1918 addresses never used after the MITM-proxy false-connect finding) | Validation: focused runs repeated across sessions and environments; demo isolates mutations in tmp with cleanup | Evidence: full battery 1191 passed / 2 skipped / 294 subtests | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to an executed twin, a structured equivalent, or a retained verbatim SP pin; formerly skip-only coverage (F7 root-gated steps) becomes executed | Validation: mapping table in plan.md; tasks.md redundancy ledger | Evidence: tests_run tails | Status: PASS
- NFR-003 | Area: performance | Target: battery wall time does not materially regress (48.79s vs 43.24s wave-2 baseline; the executed shell twins add user-namespace spawns and the transcode twins add a fake-ffmpeg run) | Validation: full battery timing comparison vs baseline | Evidence: tests_run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: ONE new support module (tests/support/relay_shell.py) beside the wave-2 harness; house conversion models only (user-namespace exec, systemctl stub, yaml.safe_load, AST helpers from tests/support/worker_source.py) | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
