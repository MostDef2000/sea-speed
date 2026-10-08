# Plan: Multi-reader-IP support in the canonical MediaMTX config tooling

- Issue: #372
- Specification: specs/372-multi-reader-ip/spec.md

## Implementation approach

1. RECON-established facts: `_reader_rule_lines(path_name, reader_ips: list[str], publisher_ips)`
   already renders `ips: [...]` from a list in input order;
   `ensure_internal_reader_rule` / `verify_internal_reader_rule` already
   normalize `reader_ip: str | list[str]` (list precedent from 3866220/#335
   publisher_ips); `verify_internal_reader_rule` is SUBSET
   (`set(requested) <= block_ips`) and must stay; `ensure_internal_reader_rule`
   compares the whole rendered block exactly (fail-closed, order-sensitive);
   `render_ubuntu_relay`/`render_verify_reader_auth` passed a single
   `args.reader_ip` string validated by `validate_reader_ip` (RFC1918);
   the CLI declared `--reader-ip` as a single required value on
   `ubuntu-relay`/`verify-reader-auth`/`ubuntu-transcode-reader`;
   camera-relay.sh parsed a single `--reader-ip` value, validated it via a
   python heredoc, forwarded it into both renderer invocations, and printed
   the literal `READER_AUTH_SCOPE=cam1-single-rfc1918-peer` in prepare and
   activate; the preview relay never invokes this renderer (#373).
2. Renderer: add `_reader_ip_list` (repeatable + comma-split normalization,
   input-order preserving, duplicate/empty fail-closed) and
   `reader_scope_token` (1 → historical `single-rfc1918-ip`; N →
   `multi-rfc1918-ip-count-N`); switch `--reader-ip` to `action="append"` on
   `ubuntu-relay` and `verify-reader-auth` only; per-IP `validate_reader_ip`
   loop in `render_ubuntu_relay`; list pass-through into
   `ensure_internal_reader_rule` / `verify_internal_reader_rule`; evidence
   line uses the token. Core rule functions unchanged.
3. Shell: `reader_ips=()` array, `--reader-ip` case splits on commas, trims
   whitespace, rejects empty entries and accumulates; required check becomes
   array-non-empty; per-IP validation loop; `reader_ip_args` forwarding
   array expanded into both renderer invocations; `reader_auth_scope()`
   helper prints the deterministic token; `READER_AUTH_SCOPE=%s` printf in
   prepare and activate; usage text updated.
4. Tests: new `tests/test_mediamtx_multi_reader_ip.py` (renderer + CLI +
   shell structural pins) and the one documented anchor re-pin in
   `tests/test_camera1_live_replacement.py` (literal moved inside
   `reader_auth_scope()`; strength preserved).

## Architecture

- The renderer change is a pure input-plumbing widening: the list passes
  through the already-list-capable core (`_reader_rule_lines` joins
  `reader_ips + publisher_ips` in order), so the rendered block shape,
  marker, permissions and insertion point are byte-identical to the
  single-IP path when one IP is requested.
- Fail-closed guarantees are structural, not incidental: the exact-block
  compare in `ensure_internal_reader_rule` includes all IPs and their order,
  so any list/order divergence between the requested and existing rule is a
  ConfigError before `write_candidate`; subset verification remains a set
  containment on the parsed block.
- The shell never edits config bytes: it validates each occurrence
  (RFC1918 heredoc, unchanged) and forwards the accumulated occurrences as
  repeated `--reader-ip` flags; the renderer remains the only writer.

## Decisions

- D-1: Implement on `ubuntu-relay` + `verify-reader-auth` only — the live
  2-IP rule is the cam1 relay path; `ubuntu-transcode-reader` keeps its
  single peer reader (`--reader-ip`) and publisher (`--publisher-ip`)
  semantics and is pinned unchanged by the existing battery.
- D-2: Accept BOTH repeatable flags and one comma-separated value — the
  issue body names either form; the normalizer makes them equivalent, and
  mixed usage stays unambiguous.
- D-3: Preserve exact input order and reject duplicates fail-closed — the
  rendered `ips: [...]` order is the documented, deterministic contract, and
  a silent dedupe/reorder could mask an operator mistake; mismatching
  re-renders stay ConfigError (exact-block compare, order-sensitive).
- D-4: Keep the historical single-IP evidence literals
  (`single-rfc1918-ip`, `cam1-single-rfc1918-peer`) for one reader and
  count-annotate multi-reader (`multi-rfc1918-ip-count-N`,
  `cam1-multi-rfc1918-peer-count-N`) — deterministic tokens, and single-IP
  invocations (and existing evidence parsers) see byte-identical output.
- D-5: Preview stays untouched (#373): the preview relay uses one regex rule
  with a single IP and never invokes this renderer or camera-relay.sh.
- D-6: No production runtime change in this task — activation of a 2-IP
  candidate remains a separate operator-gated transaction.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera-relay.sh` (classified
  UBUNTU_WORKER by the change-control policy), 
  `scripts/operations/mediamtx_path_config.py` (classified CONTROL_PLANE),
  the two focused test files, this SDD trio (+ durable progress file
  outside the repo tree).
- No change to `api/**`, `frontend/**`, `worker/**`, `.github/**`,
  `deploy/vps/**`, preview-relay behavior, watchdog, prepare-runtime.sh,
  update-exact.sh, systemd units.

## Validation

- Full suite on head branch: green (exact counts in the verification
  transcript and tasks.md AC-6).
- New battery verbose: `tests/test_mediamtx_multi_reader_ip.py` green;
  `tests/test_camera1_live_replacement.py` green with the re-pinned anchor.
- `bash -n` on the changed shell file: clean.
- ruff (`scripts/quality/ruff.toml`) on the changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py`: green.

## Runtime feedback

- RF-001: Operator actions expected: 0 on merge — the next operator-scheduled
  worker relay re-render may adopt the repeatable `--reader-ip` form; until
  then the tool change is dormant and single-IP behavior is byte-identical.
- RF-002: Evidence: renderer `reader_scope=multi-rfc1918-ip-count-2`; shell
  `READER_AUTH_SCOPE=cam1-multi-rfc1918-peer-count-2` on 2-IP
  prepare/activate; historical single-reader literals unchanged.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set —
  `deploy/worker/ubuntu/camera-relay.sh` classifies UBUNTU_WORKER,
  `scripts/operations/mediamtx_path_config.py` classifies CONTROL_PLANE;
  `derive_impact` returns UBUNTU_WORKER (observed: `derive_impact(files,
  policy) == "UBUNTU_WORKER"`), matching the 406/407 precedent that the
  Ubuntu Worker contour derives a full risk profile.
- RISK-001 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: an operator who re-applies a live N-IP rule with a different list/order gets a fail-closed ConfigError and no candidate write (exact-block compare, order-sensitive), instead of a silent partial-IP render that would lock out a reader; the input-order contract and repeatable/comma forms are documented in usage text and spec | Validation: executed mismatch matrix (different member, dropped IP, reversed order) with no-candidate assertions and idempotent same-order re-apply pins | Residual risk: LOW — a same-set/different-order re-apply is rejected and must be reissued in the documented order; verify-reader-auth (subset) still allows validating the live rule meanwhile | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: every requested reader IP passes the existing per-IP RFC1918 gate (renderer + shell heredoc) before any write; duplicates and empty input fail closed; no new permission scope is introduced (read-only cam1 rule, marker-scoped) and verify SUBSET semantics are unchanged | Validation: executed per-IP validation negatives (public/loopback/CIDR), duplicate rejection, subset/membership verification on 2-IP rules | Residual risk: LOW — an RFC1918 IP outside the operator's intended peers could be granted if typed twice in the flags; bounded by the exact-block re-apply compare and the reviewed-candidate SHA gate before activate | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: single-IP byte-identity is pinned at three levels (str-vs-list-vs-comma core equivalence, exact historical block bytes, evidence-token literal), so existing wrappers, evidence parsers and single-IP deployments see identical output; other renderer modes untouched | Validation: executed byte-identity pins and the unchanged single-IP battery in test_camera1_live_replacement.py (full suite green) | Residual risk: LOW — byte-identity is pinned on the cam1 profile; an exotic caller relying on argparse internals (e.g. `--reader-ip=x` form) still works via action="append" | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: shell parsing trims whitespace, rejects empty comma entries, fails on missing values, and forwards via a quoted array expansion (`"${reader_ip_args[@]}"`) so IPs cannot word-split; per-IP validation loop precedes any renderer invocation | Validation: `bash -n` gate plus structural pins (established style) covering the array init, comma split, forwarding expansion and its two call sites | Residual risk: LOW — an IP with embedded whitespace is rejected by the per-IP RFC1918 validation before any write | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_two_ip_render_includes_both_ips_in_input_order + test_render_order_follows_input_order_stably (both IPs rendered in input order; same order byte-identical twice; reversed input renders reversed ips line)
- TEST-002 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: test_single_ip_is_byte_identical_to_historical_str_behavior (str vs list vs comma equivalence, exact historical block bytes, scope-token literals) + test_cli_single_flag_matches_historical_output (single-IP CLI stdout token + idempotent str-API re-apply)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_mismatch_reader_ip_list_is_rejected_fail_closed (different member / dropped IP / reversed order / extended list → ConfigError) + test_cli_mismatch_list_is_rejected_and_candidate_untouched (exit 1, exact-block error, no candidate file) + test_duplicate_reader_ips_fail_closed
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_verify_subset_semantics_on_two_ip_live_rule (requested ⊆ existing passes as str/list/mixed; non-member rejected) + test_cli_verify_reader_auth_accepts_repeatable_and_comma_ips (verify mode repeatable/comma green on 2-IP rule, non-member exit 1)
- TEST-005 | Covers: RISK-001 | Level: integration | Priority: P0 | Evidence: test_cli_repeatable_flags_render_both_ips + test_cli_comma_separated_value_renders_both_ips (end-to-end ubuntu-relay CLI renders ips: [A, B] and passes verify_internal_reader_rule with both IPs)
- TEST-006 | Covers: RISK-004 | Level: integration | Priority: P0 | Evidence: test_shell_contracts_forward_all_reader_ip_occurrences (bash -n; array init; comma split; trim/accumulate; quoted array expansion forwarded at both renderer call sites; per-IP validation precedes render; generalized scope evidence) + test_shell_contracts_are_explicit_and_ai_worker_is_not_controlled (re-pinned anchor, strength preserved)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical Issue #372 Outcome Contract scope; allowed paths (renderer, camera-relay.sh, focused tests, SDD trio, progress file) enforced before first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: no new deployment machinery — the tool reaches the host only through a future operator-scheduled relay re-render; camera-relay.sh prepare remains candidate-only
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved | Retry: NO | Rollback: the relay candidate flow preserves a root-only config backup for an explicit rollback decision (automatic rollback intentionally not authorized); a mismatching re-render fails before write_candidate | Evidence: tests/test_mediamtx_multi_reader_ip.py — test_cli_mismatch_list_is_rejected_and_candidate_untouched; camera-relay.sh activate backup flow unchanged
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: rendered candidate verified by verify_internal_reader_rule (all forwarded IPs, subset semantics) in prepare/activate before activation; fail-closed mismatch pinned by executed tests
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new state — candidate + sha file handling unchanged (root-only, 0600)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing candidate/backup temporaries | Retry: NO | Rollback: NONE | Evidence: existing write_candidate temp-file cleanup and relay state-root handling unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: renderer reader_scope token (single-rfc1918-ip / multi-rfc1918-ip-count-N); shell READER_AUTH_SCOPE=cam1-single-rfc1918-peer / cam1-multi-rfc1918-peer-count-N
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the camera-relay.sh root-only backup; a rolled-back single-IP config is again renderable byte-identically by the updated tool | Evidence: unchanged relay backup flow; byte-identity pins
