# Plan — Issue #398 wave 3

- Issue: #398
- Specification: specs/398-wave3/spec.md

## Architecture

Follow the wave-1/wave-2 house model: RB (execute the real thing) > SS (structured parse:
`ast.parse` / `yaml.safe_load`) > SP (STATIC_POLICY pins kept verbatim with justification) >
redundant retirement (only with a recorded same-commit executed twin). One new support module
(`tests/support/relay_shell.py`, sibling of `tests/support/frontend_html.py`) reuses the
established executed-twin pattern at the shell layer: the REAL deploy script bytes run under
`unshare --user --map-root-user` (root-gated flows execute against tmp state; systemctl is a
parameterized stub on PATH with a per-service quiet-active model and a restart-failure knob;
a recording renderer serves copy-tree runs; a bindable-private-listener helper replaces the
environment-dependent dead-address probes). Python AST conversions reuse the generic helpers in
`tests/support/worker_source.py` (direct `ast.parse` for the entrypoint module, which the curated
path list does not include). No new frameworks or patterns.

## Decisions

- **Executed twins over listener dead-addresses**: the sandbox egress proxy accepts TCP connects
  to dead RFC1918 addresses, so the historical rc-32 dead-listener branch is NOT deterministic;
  the deterministic replacements are (a) a REAL bound private listener (probed, skipped when no
  RFC1918 address binds) for PASS paths and (b) the systemctl restart-failure knob (rc 30) for
  the failure branch.
- **Stub must CALL `systemctl "$@"`** (defining alone is inert); quiet-active is per-service
  (worker gate needs worker NOT-active while post-restart gates need the relay IS-active — same
  call shape); `SYSTEMCTL_RESTART_FAIL=yes` yields the deterministic rc-30 twin.
- **Protected files inside the user namespace**: files created OUTSIDE the namespace show uid
  65534 inside; the preview inventory root-ownership gate requires planting the inventory with a
  tiny writer script run under the SAME namespace (mapped root).
- **Candidate layouts differ**: cam1 candidate = `$state_root/cam1-mediamtx.candidate.yml`;
  preview candidates = `$state_root/candidates/*` — twins pin the REAL paths, not a shared
  assumption.
- **`verify-reader-auth` failure propagates the renderer's rc 1** (not the shell's 3, which is
  reserved for reader-ip argument validation) — twins pin observed rc, not guessed codes.
- **AST over text for renderer/entrypoint structure**: FunctionDef names and string constants
  carry the contract; `NEEDS_FILE` / `preview-contour` exist only inside docstrings → substring
  semantics via `any()`; `worker_source.worker_source_paths()` does NOT include
  `ubuntu_worker_entrypoint.py` → parse it directly.
- **Renderer mode registration is behavioral**: a registered legacy mode fails argparse with
  "required" (exit 2), an unregistered one with "invalid choice" — probes replace the mode-name
  text pin.

## Site-mapping table (old → replacement)

| # | File | Classification | Action |
|---|------|----------------|--------|
| 1 | tests/test_mediamtx_systemd_v247_runner.py | RB + redundant | both historical root-gated skips → EXECUTED under user namespace; embedded patcher → executed verbatim twin (4 subtest scenarios + round-trip); needle/replacement text pins retired with twin; SP: EXPECTED_CORE_SHA256 digest, sed -i ban, sandbox properties, systemd-run invocation, runtime-scope bans |
| 2 | tests/test_mediamtx_activate_identity.py | RB + redundant | ActivateFlowExecutedTwinTests (7 executed twins: status bare, digest rc 7, worker rc 8, identity rc 9, restart rc 30, full happy path vs real listener, prepare rc 10); contract-class text pins retired with twins; SP: call counts, fallback bans, /usr/lib precedence |
| 3 | tests/test_mediamtx_compatibility_remediation.py | SS + RB | canary contracts → yaml.safe_load on rendered heredoc with script-extracted defaults; parse_loopback_address + canary_listeners_ready executed twins; preserve_failure_log twin extended (all CANARY_FAILURE_* keys, 0600, missing-log, log-sanitization); SP: digest-bound interface literals, systemd-run properties, flow ordering, activation transaction |
| 4 | tests/test_mediamtx_multi_reader_ip.py | RB + redundant | 3 executed prepare twins (repeatable/comma/bad IPs: forwarding, scope evidence, rc 3 fail-closed); accumulation-loop text + ordering pin retired; SP: cross-flow call-site counts, scope-evidence emission pins |
| 5 | tests/test_mediamtx_preview_relay.py | RB + SS + redundant | PreviewRelayExecutedTests (8 twins: copy-tree gates incl. gate-before-root, byte-parity prepare vs direct renderer, multi-IP scope, invalid-address rc 3, inventory 0644/symlink rc 5, real-listener PASS for BOTH shells); renderer structural → AST; 9 legacy modes → executed registration probes; shell text pins retired with twin references; SP: activate-only evidence literals, #452 R8 derivation ban |
| 6 | tests/test_mediamtx_remediate_reader.py | RB + redundant | RemediateShellExecutedTests (3 twins: drifted 2-IP convergence with canonical live-order bytes, byte-identical no-op, verify-before rc 1 fail-closed); dispatch/usage/evidence pins retired; SP: wiring counts (verify==5, CANDIDATE_SHA256==3, MUTATIONS==3), activate reuse, worker bans |
| 7 | tests/test_mediamtx_sanitize_auth.py | RB + redundant | SanitizeShellExecutedTests (3 twins: duplicate prune + sha file, declared-prune passthrough with aggregated DECLARED_PRUNED evidence, fail-closed refusal 2 subtests); loop-text/usage/evidence pins retired; SP: wiring counts, --prune-declared usage, rollback, bans |
| 8 | tests/test_camera1_live_replacement.py | RB + SS + redundant | TranscodeRunExecutedTests (3 twins: fake-ffmpeg run — ffconcat 0600 + file-before-option + argv shape + credentials never in argv + publish target; invalid transport rc 6; bad env rc 6 ×3 subtests); entrypoint text pins → AST (direct parse; string constants incl. docstring-only NEEDS_FILE; real AST negative: no print of input_url); ubuntu scope/message pins retired (F1/F3 twins); VPS pins SP; transcode text pins retired except stale-sweep SP pin |

## Affected contours

- Tests only: the 8 listed test files, tests/support/ (one new module), the demo test, this trio.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, scripts/** (except the recorded
  one-line grandfather entry), .github/**, nginx/**, and all wave-1/wave-2 test files.

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in the session
  checkpoint /tmp/opencode/398-w3/checkpoint.md: F7 7 passed/4 subtests, F1 23 passed, F2 14
  passed, F3 15 passed/7 subtests, F4 45 passed/11 subtests, F5 21 passed, F6 43 passed/2
  subtests, F8 19 passed/6 subtests, demo 1 passed).
- Full battery: `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w3/pytest-tmp` → 1188 passed / 2 skipped / 294 subtests in 50.46s
  (baseline 1160 / 4 / 271; cluster net +26 tests + demo +1; F7's 2 skips → executed; subtests +23).
- `python3 scripts/ci/validate_sdd.py` → green for the trio after the staged-wave grandfather
  entry `398-wave3`; `validate_repo.py` → green.
- Allowed-paths check: `git status` shows only tests/**, tests/support/**, specs/398-wave3/**
  plus the recorded validate_sdd.py exception.

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only change; runtime acceptance = exact-head CI
  green on the merge PR.
- RF-002: post-wave battery reports 1188 / 2 / 294; all deltas recorded in the tasks.md
  battery-delta ledger (retired assertion → covering executed twin, same commit).

## Risk profile

- Risk profile: NOT REQUIRED
- Executed harnesses are offline and deterministic (systemctl stub, recording renderer, tmp
  fixtures, probed real listener with graceful skip); root-gated twins skip gracefully where user
  namespaces are unavailable — the same environments skipped them before, and they now EXECUTE
  where the sandbox provides unshare.
- Battery may only shrink by the redundancy ledger; every retirement cites its twin.
- Risk that a converted check becomes tautological is countered by the demo's inverted-mutation
  proof (dead-marker direction fails the executed check) and by the byte-parity twin (shell
  candidates must equal direct renderer output).

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every mapping-table action's focused run green (F1 23, F2 14, F3 15/7, F4 45/11, F5 21, F6 43/2, F7 7/4, F8 19/6); SP pins byte-verbatim with in-code justifications
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: battery 1160/4/271 → 1188/2/294; battery-delta ledger in tasks.md maps every retired assertion to its recorded executed twin
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave3_demo.py — both directions with recorded inverted-mutation run (broken-forwarding direction fails the executed check)
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: full battery 1188 passed / 2 skipped / 294 subtests in 50.46s; validate_sdd + validate_repo green
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git status shows only declared paths + the recorded validate_sdd.py grandfather-entry exception

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none — no production learning, no pivot, no material scope change. Session-level
  environment notes (overlay-disk pressure → fixed pytest basetemp; MITM proxy false-connects to
  dead RFC1918 addresses; systemctl-stub semantics) are recorded in the session checkpoint and in
  the harness docstrings, not as scope changes.
