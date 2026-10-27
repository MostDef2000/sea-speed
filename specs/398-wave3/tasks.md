# Tasks — Issue #398 wave 3

- Issue: #398
- Specification: specs/398-wave3/spec.md

## Delivery tasks

- T-1: RECON + baseline: 1160 passed / 4 skipped / 271 subtests; validate_sdd + validate_repo green (base 03c7543); capability recon (unshare userns, systemctl-stub semantics, MITM false-connect finding for dead RFC1918 addresses). DONE.
- T-2: F7 v247 runner — both historical root-gated skips EXECUTED under the user namespace; embedded patcher → executed verbatim twin (4 subtest scenarios + round-trip); needle pins retired with twin; SP kept. DONE.
- T-3: F1 activate identity — ActivateFlowExecutedTwinTests (7 executed twins incl. full happy path vs a real bound listener and the rc-30 restart-failure branch); contract-class text pins retired with twins; shared bindable_private_listener() moved into the harness. DONE.
- T-4: F2 compat remediation — yaml.safe_load canary contracts (defaults extracted from the script), parse_loopback_address + canary_listeners_ready executed twins, preserve_failure_log twin extended (classifications, 0600, missing-log, log sanitization); SP keeps annotated. DONE.
- T-5: F3 multi reader ip — 3 executed prepare twins (repeatable/comma/bad IPs); accumulation-loop text + ordering pin retired; SP cross-flow counts kept. DONE.
- T-6: F4 preview relay — PreviewRelayExecutedTests (copy-tree gate twins incl. gate-before-root; byte-parity prepare; inventory gates; real-listener PASS for both shells); renderer structural → AST; legacy modes → executed registration probes; shell text pins retired; SP activate-only evidence + R8 ban. DONE.
- T-7: F5 remediate reader — 3 executed shell twins (convergence with canonical live-order bytes, byte-identical no-op, verify-before fail-closed rc 1); dispatch/usage/evidence pins retired; SP counts + bans. DONE.
- T-8: F6 sanitize auth — 3 executed shell twins (duplicate prune + sha file; declared prune with aggregated DECLARED_PRUNED evidence; fail-closed refusal); loop-text/usage/evidence pins retired; SP counts + usage kept. DONE.
- T-9: F8 camera1 live replacement — TranscodeRunExecutedTests (fake-ffmpeg run: ffconcat 0600 + file-before-option + argv shape + credentials never in argv; invalid-transport and bad-env fail-closed); entrypoint pins → AST (direct parse); ubuntu scope/message pins retired with twins; VPS + stale-sweep SP kept. DONE.
- T-10: tests/support/relay_shell.py — shell-exec harness (user-namespace root-gated flows, parameterized systemctl stub, recording renderer fixed to key on the renderer path, bindable-private-listener helper). DONE.
- T-11: Demo tests/test_398_wave3_demo.py — two-direction proof with inverted mutation. DONE.
- T-12: Full battery + validators + allowed-paths self-check. DONE.
- T-13: Adversarial-review fix round (MED-1..MED-5, LOW-5..LOW-7): preview digest-evidence twin,
  root-ownership-gate twin, single-peer scope twin, distinct-identity field-order twin with
  fail-closed install, unshare-skip guards, transport-default assertions, fresh not-ready ports,
  ledger corrections. DONE.

## Completion gate

- Full battery `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w3/pytest-tmp` green: observed 1191 passed / 2 skipped /
  294 subtests in 48.79s (baseline 1160 / 4 / 271; the identity holds:
  1160 + 28 cluster tests + 1 demo + 2 executed former skips = 1191, skipped 4→2; subtests +23).
- Focused post-review run green: F1+F4+F8+F2 → 104 passed / 17 subtests in 8.20s
  (F1 24, F4 47, F8 19, F2 14).
- `validate_sdd.py` green for this trio after the staged-wave grandfather entry `398-wave3`;
  `validate_repo.py` green (observed in the pre-review session; trio files only gained
  observed-number corrections since).
- Demo inverted-mutation proof observed: `python3 -m pytest tests/test_398_wave3_demo.py -q` →
  1 passed (refactor tolerance AND dead-marker intolerance; real-script sanity).

## Requirements traceability

- AC-001 | Task: T-1, T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-11 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-12 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-12 | Evidence: TEST-004 | Coverage: COVERED
- AC-006 | Task: T-12 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → mapping table in plan.md (all 8 files adjudicated; every removed
assertion has a twin or SP retention) + the battery-delta ledger below; R-2 → SP pins kept
verbatim carry in-code justification comments (`398-wave3: SP pin — …`; T8b / D-6 / cross-flow
count precedents); R-3 → the demo's inverted-mutation proof recorded below; R-4 → no production
file touched (git status limited to tests/**, tests/support/**, specs/398-wave3/** + the recorded
validate_sdd.py exception); R-5 → executed harnesses offline (systemctl stub, recording renderer,
probed real listener with graceful skip; dead RFC1918 addresses never relied on after the
MITM-proxy false-connect finding); root-gated twins skip gracefully where user namespaces are
unavailable — the same environments skipped them before, and they now execute where unshare is
available; R-6 → battery green with per-file deltas accounted; both validators green.

## Battery-delta ledger (per-file test counts counted from base 03c7543; identity: 1160 + Σ28 + 1 demo + 2 executed former skips = 1191 passed, skips 4→2; subtests 271→294)

| File | Delta (base→now) | Retired assertions → covering twin (same commit) |
|------|------------------|--------------------------------------------------|
| F7 test_mediamtx_systemd_v247_runner.py | +1 (6→7; both former root-gated skips EXECUTED: passed 4→7) | historical root-gated skips → executed user-namespace twins (patch-step and verify steps run for real); needle/replacement text pins → executed verbatim patcher twin with 4 subtest scenarios + round-trip identity |
| F1 test_mediamtx_activate_identity.py | +5 (19→24) | read -r field-order, whitespace-regex, derivation-order, rollback, --expected-sha256, exit-9/error/INSTALL_OWNER existence pins → executed twins (status/digest rc 7/worker rc 8/identity rc 9/restart rc 30/full happy path vs real listener/prepare rc 10); 398-wave3 review MED-2: the #448 F2 caller field-order pin → test_activate_field_order_distinct_identity_fails_closed_at_install (distinct identity fields "root nogroup 0640" → order-sensitive INSTALL_OWNER/MODE evidence, install fails closed on the unmapped group before any mv); happy path byte-compares shell flow against a real bound private listener |
| F2 test_mediamtx_compatibility_remediation.py | 0 | loopback-only/minimal-surface/v120 text pins → yaml.safe_load semantic asserts on the rendered canary heredoc (defaults extracted from the script); sleep/kill-0 polling ban → executed canary_listeners_ready twin; classifier string pins → executed preserve_failure_log twin (all CANARY_FAILURE_* keys, 0600, missing-log, raw-log sanitization); count unchanged (conversions in place); 398-wave3 review LOW-7: the not-ready sub-run uses freshly bound-then-closed ports |
| F3 test_mediamtx_multi_reader_ip.py | +3 | reader-ip accumulation loop text + validate-before-render ordering pin → executed prepare twins (repeatable/comma forwarding with live-order candidates + scope evidence; bad IPs rc 3 fail-closed) |
| F4 test_mediamtx_preview_relay.py | +10 | check-address-in-both-shells text pin → executed real-listener PASS probe for both shells; repo-root/gate-ordering/multi-ip-loop/scope-emission pins → executed copy-tree + byte-parity + invalid-address + inventory-gate twins; 398-wave3 review MED-1: retired CONFIG_SHA256/UNIT_SHA256/SANITIZED_CATALOG_SHA256 printf pins → parity twin asserts all three digests present AND equal to the sha256 of the candidate bytes; review MED-3: camera-preview-relay.sh:207 root-ownership branch → executed real-gate-line twin (stat stubbed both directions: uid 0 passes, non-zero uid exits 5 — planting a real non-root-owned file is impossible in the single-uid namespace, choice recorded in-test); review LOW-6: single-peer scope token executed through the real prepare flow (one reader IP); renderer structural pins → AST + executed legacy-mode registration probes; SP: activate-only evidence literals + #452 R8 derivation ban |
| F5 test_mediamtx_remediate_reader.py | +3 | remediate dispatch/usage/evidence pins + verify-before/after wiring pins → executed twins (drifted 2-IP convergence with canonical live-order bytes; byte-identical no-op; verify-before fail-closed rc 1) |
| F6 test_mediamtx_sanitize_auth.py | +3 | sanitize dispatch/usage/SANITIZED_FOREIGN_AUTH emission pins + declared_prune loop text + DECLARED_PRUNED emission pin → executed twins (duplicate prune + sha-file digest; declared prune with per-declaration evidence; fail-closed refusal ×2 subtests) |
| F8 test_camera1_live_replacement.py | +3 | transcode text pins (-f concat, protocol whitelist, chmod 0600, -i "$HLS_URL" ban, file-before-option) → executed fake-ffmpeg run twin (argv shape + ffconcat 0600 content order + credentials absent from every argv element + publish target); entrypoint text pins → AST constants + real negative (no print of input_url); 398-wave3 review MED-5: the udp transport DEFAULT is behavioral — asserted with CAMERA1_RTSP_TRANSPORT absent AND empty-string (a udp→tcp default change fails); ubuntu scope/message pins → F1/F3 executed twins; SP: worker wiring/bans, VPS pins, stale-input sweep |
| demo tests/test_398_wave3_demo.py | +1 | new two-direction regression demonstration (additive) |

Arithmetic note: per-file deltas are test-count deltas vs the base commit (git-counted);
cluster Σ = +28 (F1 5, F3 3, F4 10, F5 3, F6 3, F7 1, F8 3, F2 0); the demo adds +1; F7's two
formerly-skipped tests are among the counted tests but move skipped→passed, so the passed total
is 1160 + 28 + 1 + 2 = 1191 and skipped drops 4→2. (Pre-review round the deltas were F1 +4,
F3 +3, F4 +8, F7 +1 — the review round added F1 +1, F4 +2.)

## Demo — inverted-mutation proof (observed output)

`python3 -m pytest tests/test_398_wave3_demo.py -q` → **1 passed**:

- Direction A (refactor tolerance): tmp copy of the real camera-relay.sh with the accumulation
  idioms rewritten behavior-preservingly (`IFS=',' read -ra … <<<"$2"` fused; indexed assignment
  instead of `+=`; two-string forwarding pair `reader_ip_args+=("--reader-ip" "$reader_ip")`) →
  the executed forwarding check PASSES (the recording renderer receives BOTH reader IPs in input
  order); the retired text pins would fail it (all 3 markers gone).
- Direction B (dead-marker intolerance): tmp copy keeping all three retired markers byte-for-byte
  with a truncation interceptor right after the (verbatim) forwarding loop
  (`reader_ip_args=("${reader_ip_args[0]}" "${reader_ip_args[1]}")`) → retired pins PASS (the
  false-green), executed check FAILS (the second reader IP never reaches the renderer).
- Sanity: the real script satisfies the executed check (copy-tree, recording renderer — no repo
  mutation).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — waves 4+ of #398 remain in the issue backlog (raw-text clusters outside this 8-file scope)
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED with prose risks recorded
- [x] Waivers resolved or current — no waivers

Wave record: all 8 cluster files adjudicated (mapping table in plan.md); battery delta +28
cluster tests (+1 demo; skips 4→2 via executed former skips) with recorded twins, no assertion
weakened or skipped; the demo proves the conversion property in both directions on the real
deploy shell; T-13 adversarial-review fix round (MED-1..MED-5, LOW-5..LOW-7) closed with
executed twins and ledger corrections; observed totals 1191 passed / 2 skipped / 294 subtests;
validate_sdd.py green for the trio (staged-wave grandfather entry `398-wave3` added by the
orchestrator).
