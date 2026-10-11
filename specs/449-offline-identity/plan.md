# Plan: Productive offline service-identity derivation + #448-review hardening pins

- Issue: #449
- Specification: specs/449-offline-identity/spec.md

## Implementation approach

1. RECON-established facts: `derive_relay_service_identity` (camera-relay.sh
   196-246 at 1ede018) falls back to `systemctl cat` — bus-dependent per the
   RF-001 on-box finding, so the offline branch never fired under chroot;
   the caller (`identity="$(derive_relay_service_identity)" || exit 9` +
   `read -r install_owner install_group install_mode <<< "$identity"`) is
   correct but unpinned; the #448 review flagged the sed captures as
   whitespace-strict (`User=([^[:space:]].*)$`); the existing battery
   executes the extracted function with stubbed systemctl/id via
   `shell_function`.
2. Shell (function only): replace the `systemctl cat` block with a direct
   on-disk read loop over the three standard unit paths (first
   `[[ -f && -r && ! -L ]]` candidate wins), merge `$candidate.d/*.conf`
   drop-ins in lexical glob order with an explicit newline separator (guards
   against last-line/first-line concatenation), parse with
   whitespace-tolerant seds (`[[:space:]]*` after `=` in both captures);
   everything else (show branch, root semantics, id -gn fallback, refusal
   text/rc) byte-unchanged.
3. Battery (extend test_mediamtx_activate_identity.py — one identity
   battery): the harness substitutes the function's unit-path roots with a
   temp tree (longest-root-first replacement so `/usr/lib/...` is not
   corrupted by the `/lib/...` substring; literals asserted first so drift
   fails loudly); the systemctl stub becomes bus-fail-for-everything
   (mirroring real chroot); scenarios re-shaped to on-disk unit files; new
   RED cases + structural pins (no `systemctl cat` in the executable body,
   path order, whitespace captures, caller read-line).
4. Docs: runbook subsection point 2 rewritten (on-disk parse, drop-ins,
   грабля №27, bounded limitations).

## Architecture

- The offline branch becomes a pure filesystem derivation (no bus
  dependency): candidates are tried in fixed standard order, the first
  readable regular non-symlink unit wins, its drop-in directory merges, and
  the existing last-assignment sed parsing runs over the concatenated text —
  the SAME parse code as #447, now fed from disk instead of `systemctl cat`.
- The harness seam (path-root substitution) keeps the production function
  free of test knobs: the real path literals stay in the shell; the test
  asserts them and rewrites them to a temp tree, so a path drift breaks the
  suite loudly instead of silently testing nothing.
- Drop-in merge uses lexical glob order and an explicit newline separator —
  systemd applies drop-ins after the main unit in lexical order, so
  last-assignment-wins is preserved across the concatenation.
- The whitespace tolerance touches ONLY the spacing between `=` and the
  captured value: `[[:space:]]*([^[:space:]].*)$` still requires at least
  one non-space character, so spaces-only values remain "absent" (→ root)
  and trailing-space captures keep failing at `id -gn` (the F3(b)/(c)
  residuals stay recorded, fail-closed).

## Decisions

- D-1: Direct on-disk read instead of any systemctl fallback (`systemctl cat`
  pinned absent from the executable body): the bus dependency was the bug;
  any retained cat path would leave the offline branch unreliable.
- D-2: First-readable-wins over the fixed path order /etc → /lib → /usr/lib
  (the standard systemd unit search order); no configurable search list (no
  knobs in a root-run derivation).
- D-3: Symlinked unit files are REFUSED (not followed): consistent with the
  renderer's regular-non-symlink input discipline; the failure direction is
  refusal, never a guessed ownership; the on-box verification confirms the
  real unit is a regular file (RF-001: "unit file exists readable under
  chroot").
- D-4: Drop-ins merge ONLY from the directory next to the found unit
  (systemd also merges /etc drop-ins over /lib units — not modeled; the
  live unit lives in /etc per RF-001). Bounded, documented in SDD + runbook;
  the last-assignment semantics WITHIN the modeled set are preserved.
- D-5: Drop-in content is appended with an explicit newline separator:
  command substitution strips trailing newlines, so naive concatenation
  could fuse the main unit's last line with a drop-in's first line and
  corrupt the parse.
- D-6: The battery is EXTENDED in test_mediamtx_activate_identity.py rather
  than a new file: one identity battery keeps the #447 semantics and the
  #449 re-shape reviewable as a single diff; the harness seam is documented
  in the module docstring.
- D-7: The harness substitutes path roots longest-first: `/lib/systemd/
  system` is a substring of `/usr/lib/systemd/system`, so dict-order
  replacement would corrupt the third literal (caught by the literal
  assertions during the RED cycle).
- D-8: F1 (specs/447-activate-identity/plan.md D-3 wording) is deferred, not
  fixed here: outside this unit's allowed paths; the issue marks it "may
  ride" (non-gating); recorded in tasks.md deferred work.
- D-9: The `#448 F2` pin asserts the exact caller line
  (`read -r install_owner install_group install_mode <<< "$identity"`)
  rather than a stubbed end-to-end activate run: the caller region is
  three lines, the extraction harness already covers the function, and an
  end-to-end stubbed activate would need a much heavier harness for the
  same guarantee (the issue offers either; the pin is the bounded choice).

## Affected contours

- UBUNTU_WORKER: `deploy/worker/ubuntu/camera-relay.sh` (one function), the
  identity battery, the runbook subsection, this SDD trio (+ durable
  progress file outside the repo tree).
- No change to: the renderer, every other camera-relay.sh block, the
  preview shell, other test batteries, `deploy/vps/**`, `.github/**`.

## Validation

- RED: the extended battery fails 15/19 on base 1ede018 with the FINAL test
  file cmp-verified on red-base-449 (exact names in the delivery transcript
  and tasks.md); 4 structural pins pass by construction.
- Full suite on the head branch: green (exact counts in the verification
  transcript); the #442-era batteries stay green.
- Byte-identity: seven-mode fixed-input harness on base 1ede018
  (byte-id-base-449) and on the branch; diff must be EMPTY (renderer
  untouched).
- `bash -n` camera-relay.sh; ruff on the battery; `python3
  scripts/ci/validate_sdd.py --event <pr-event.json>` green (base 1ede018,
  head = branch tip).

## Runtime feedback

- RF-001: Operator actions expected: 1 (on-box verification of the
  productive offline path under chroot; no config mutation expected);
  orchestrator records the runtime acceptance.
- RF-002: Evidence: INSTALL_OWNER/MODE lines before the install; the
  refusal ERROR + exit 9 when nothing is readable; the derivation now
  succeeds with no bus.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from scripts/ci/validate_change_contract.py classify_file/derive_impact — the change refines the fail-closed shell derivation on the worker relay script (UBUNTU_WORKER) with new input parsing (on-disk unit file + drop-ins), matching the Outcome Contract on issue #449 (operator scope update 6098207117). Security impact declared LOW in the PR body (fail-closed refinement; no auth topology change).
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the offline drop-in handling is a bounded subset of systemd semantics (only the directory next to the found unit; lexical order; documented in SDD + runbook) — a drop-in living at a different root is NOT silently ignored for ownership purposes because the parse still covers the main unit, and the residual is recorded; the refusal path is byte-unchanged for unreadable inputs | Validation: on-disk drop-in last-wins test + refusal tests + runbook limitation text | Residual risk: LOW — a unit whose User= comes ONLY from a foreign-root drop-in would derive root:root 0600 (systemd's default for an absent User), which is the safe direction and matches pre-#447 behavior for genuine root units | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the parse stays last-assignment-wins with UNCHANGED value semantics: whitespace tolerance only widens spacing acceptance (at least one non-space still required; spaces-only = absent → root; trailing-space captures still fail at id -gn — F3(b)/(c) residuals recorded); the on-disk input is gated (regular, non-symlink, readable) before parsing | Validation: whitespace-tolerance test + spaces-only-unit root-derivation semantics via the no-user case + symlink refusal test | Residual risk: LOW — exotic unit syntax (quoted values, multi-line continuations) is unmodeled and parses as absent (→ root 0600, safe direction) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: test fixtures materialize unit files at runtime in TemporaryDirectory trees (no committed fixture content beyond the scenario strings already in the battery); the harness seam asserts the real path literals before substituting them, so path drift fails loudly | Validation: ruff + the RED run with the cmp-verified final file | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the productive offline path is exactly the RF-001 chroot shape (show AND cat fail, unit readable) and is exercised as its own regression case; the operator verification transaction (RF-001) confirms it on the real box with no config mutation; the runbook records грабля №27 so the bus-dependency lesson survives | Validation: test_chroot_show_and_cat_fail_parses_on_disk_unit_file + runbook subsection + the planned on-box verification | Residual risk: LOW — an on-box unit at a non-standard path (--unit= style) is out of scope and still refuses fail-closed | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-004 | Level: unit | Priority: P0 | Evidence: test_chroot_show_and_cat_fail_parses_on_disk_unit_file (the exact RF-001 shape → root:mediamtx 0640) + test_chroot_on_disk_unit_without_user_means_root + test_chroot_on_disk_unit_group_missing_resolves_via_id + test_offline_unit_path_precedence_etc_wins + test_offline_unit_path_precedence_falls_through_to_lib
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_offline_drop_in_directory_last_assignment_wins + test_offline_symlinked_unit_is_refused + test_both_derivations_fail_closed (refusal text + rc 1) + test_unit_file_group_unresolvable_fails_closed
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_offline_whitespace_after_equals_is_tolerated + test_whitespace_tolerant_captures_are_pinned (structural) + test_show_explicit_root_keeps_root_root_0600 (root semantics unchanged)
- TEST-004 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: test_offline_branch_does_not_call_systemctl_cat + test_offline_branch_reads_standard_unit_paths_in_order + test_caller_read_field_order_is_pinned + test_shell_is_valid_and_contracts_fail_closed_derivation + test_identity_derivation_precedes_any_mutation + test_activate_flow_unchanged_pins_hold
- TEST-005 | Covers: NFR-003 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base 1ede018 vs head, empty diff) + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #449 Outcome Contract + scope-update comment 6098207117; allowed paths (camera-relay.sh function, identity battery, runbook subsection, SDD trio, progress file) enforced before first write; GH007 author identity verified before commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: the identity derivation (now productive offline) still runs BEFORE the root-only backup; both derivations failing leaves the state root and live config byte-untouched (unchanged from #447)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved at the printed BACKUP path; ownership now derived productively offline when the unit file is readable | Retry: NO | Rollback: the unchanged activate flow retains the root-only timestamped backup for an explicit rollback decision; automatic rollback is not authorized | Evidence: camera-relay.sh activate sequence byte-unchanged (caller untouched)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: unchanged verify-before pair and post-install restart/probes; the derivation adds the on-disk source as a new offline input with the same refusal discipline
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state; the function writes nothing and keeps no state
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing temporaries | Retry: NO | Rollback: NONE | Evidence: the on-disk read opens no temp files and leaves no churn; a refused derivation still precedes the backup (zero partial state)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: unchanged INSTALL_OWNER/MODE evidence lines; the offline derivation is visible through the same transcript lines (no new evidence format)
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the unchanged root-only timestamped backup (explicit operator decision); a refused derivation never reaches the install step | Evidence: unchanged activate fault paths (exit 30/31/32; "automatic rollback is not authorized")
