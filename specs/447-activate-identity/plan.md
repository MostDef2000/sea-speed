# Plan: Activate service-identity derivation must fail closed

- Issue: #447
- Specification: specs/447-activate-identity/spec.md

## Implementation approach

1. RECON-established facts: the activate block derived identity at
   camera-relay.sh lines 420-434 with `service_user="$(systemctl show -p
   User --value ... || true)"` and `[[ -z "$service_user" || "$service_user"
   == "root" ]]` → silent root:root 0600 — empty (bus failure under chroot)
   and explicit root were conflated (the #447 fail-open). The derivation
   already sat before the backup; exit code 9 is the identity-failure code;
   the test suite has an established extractable-function + inline-stub
   `systemctl` pattern (`shell_function` helper in
   tests/test_mediamtx_compatibility_remediation.py).
2. Shell: add `derive_relay_service_identity()` (stdout `owner group mode`,
   stderr ERROR + return 1 on failure): (1) `systemctl show -p User/-p Group
   --value` — non-empty User is definitive (root → `root root 0600`;
   non-root → Group from show, else `id -gn`, else refuse → `root <group>
   0640`); (2) empty User → `systemctl cat "$service_name"` — parse the
   LAST `User=`/`Group=` via sed + tail (systemd override semantics;
   absent/empty User = root); (3) cat empty/unavailable → the explicit
   refusal ERROR + return 1. Replace the silent-fallback block with the
   fail-closed caller (`identity="$(derive_relay_service_identity)" ||
   exit 9`, `read -r install_owner install_group install_mode`) plus the
   `INSTALL_OWNER=<owner>:<group>` / `MODE=<mode>` evidence lines, keeping
   the derivation before the backup (documented: backup is itself a
   state-dir mutation).
3. Tests: new battery `tests/test_mediamtx_activate_identity.py` — 8
   execution cases over the extracted function with inline `systemctl`/`id`
   stubs (show non-root, show root, chroot show-fail → unit file, unit
   without User=, unit without Group= + id stub, drop-in override
   last-wins, both fail, group unresolvable) and 3 structural pins
   (fail-closed markers + old fallback absent; derivation precedes
   backup/install; activate discipline counts unchanged).
4. Docs: brief "Relay service identity derivation" subsection in
   docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md (incident one-liner,
   derivation order, fail-closed contract, evidence lines).

## Architecture

- The derivation is a pure decision function over two bounded sources
  (`systemctl show`, `systemctl cat`) with no mutation; the caller wires it
  into the existing gate sequence so refusal happens before ANY state-dir
  write. The old inline block's decision table (non-root → 0640 with
  `id -gn` group fallback, root → 0600) is preserved exactly for definitive
  answers; only the AMBIGUOUS empty-User case changes from silent-0600 to
  unit-file-derivation-then-refuse.
- `systemctl cat` is offline-safe (reads the unit file from disk, works
  under docker-chroot where the bus is unavailable) — the authoritative
  fallback per the issue. Last-assignment parsing matches systemd override
  semantics for drop-ins.
- The function is extractable (blank-line separated, `name() {` … `\n}\n\n`)
  so the existing structural-battery pattern can execute it with stubs —
  no new test infrastructure.
- Renderer invocation counts are untouched (the derivation adds no renderer
  calls), so all existing forwarding/digest pins hold without edits (AC-3).

## Decisions

- D-1: Empty `User=` from `systemctl show` is NEVER treated as root: empty
  conflates "unit runs as root" with "bus unreachable" — the incident root
  cause. Non-empty answers stay definitive.
- D-2: The unit file (`systemctl cat`) is the single fallback source (no
  on-disk path guessing): it is exactly what systemd would load (main unit +
  drop-ins, last assignment wins) and is readable under chroot.
- D-3: Both derivations fail → exit 9 BEFORE the backup: backup creation is
  a mutation of the state root; the safest ordering is zero writes before
  the identity is known. (The identity block already sat before the backup;
  the caller keeps that position and documents it.)
- D-4: `User=root` semantics unchanged (root:root 0600 even if a Group= is
  set): bounded preservation of current behavior; the incident class is the
  AMBIGUOUS empty case, not the explicit-root case.
- D-5: Evidence lines print BEFORE the backup/install (not after the
  install): if a later restart step fails, the transcript still shows the
  intended ownership for the post-mortem (exactly what the 2026-10-10
  incident lacked).
- D-6: New battery file named by domain (`test_mediamtx_activate_identity.py`)
  following the established stubbing pattern instead of growing the VPS
  remediation battery (different script under test).
- D-7: `check_auth_environment_override` is out of scope: it reads systemd
  Environment (auth-override detection for prepare gates), not service
  identity, and its empty-answer behavior (skip the override check) has no
  ownership consequence (AC-3 keeps prepare untouched).

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera-relay.sh` (UBUNTU_WORKER
  per the change-control policy), the new test battery, the docs runbook,
  this SDD trio (+ durable progress file outside the repo tree).
- No change to `scripts/operations/mediamtx_path_config.py` (zero renderer
  diff), prepare/sanitize/remediate blocks, activate install/restart/probe
  sequence, `deploy/vps/**`, `.github/**`, systemd units, other test
  batteries.

## Validation

- RED: the new battery fails 10/11 on base 80bcb0e (all 8 derivation
  execution cases + 2 structural pins; exact names in the delivery
  transcript and tasks.md AC-4) and passes 11/11 on the branch; the counts
  guard passes on base by construction.
- Full suite on head branch: green (exact counts in the verification
  transcript).
- Byte-identity: seven-mode fixed-input harness run on base 80bcb0e
  (byte-id-base-447) and on the branch (byte-id-head-447); the output
  directories must diff empty (shell-only change — trivially equal, still
  executed).
- `bash -n deploy/worker/ubuntu/camera-relay.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on the new test file: clean.
- `python3 scripts/ci/validate_sdd.py --event <pr-event.json>`: green
  (base 80bcb0e, head = branch tip).

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box verification
  transaction (dry activate or equivalent derived-owner check on the real
  box, confirming root:mediamtx 0640; no config change expected);
  orchestrator records the runtime acceptance.
- RF-002: Evidence: `INSTALL_OWNER=<owner>:<group>` + `MODE=<mode>` before
  the install lines; refusal `ERROR relay service identity could not be
  derived (systemctl unavailable and unit file unreadable); refusing to
  install with guessed ownership` (stderr, exit 9, no backup/install);
  `ERROR cannot resolve relay service group` (stderr, exit 9) when a
  non-root user's group is unresolvable.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set — `deploy/worker/ubuntu/camera-relay.sh`
  classifies UBUNTU_WORKER (runtime contours {UBUNTU_WORKER}) with an
  install-mutation behavior change, matching the Outcome Contract on issue
  #447. Security impact is declared LOW in the PR body (auth-surface-adjacent
  shell hardening in the fail-closed direction; matching RISK-001's LOW
  residual).
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the derivation is a two-source whitelist (bus answer non-empty, else unit file) with refusal on ambiguity BEFORE any mutation; the old silent fallback markers are pinned absent; `User=root` semantics preserved so no legitimate root unit changes behavior; group resolution refuses instead of guessing | Validation: executed derivation table (8 stubbed-systemctl cases incl. both-fail and group-unresolvable) + structural pins (refusal precedes backup/install, old block absent, bash -n) | Residual risk: LOW — a unit file readable but MALFORMED (no parseable User=) is treated as a root unit (systemd's own default), which preserves the pre-incident install mode for genuine root units | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: refusal now happens BEFORE the backup, so a failed derivation leaves the state root and live config byte-untouched (cleaner than the old post-backup failures); the refusal text tells the operator exactly which two sources failed; INSTALL_OWNER/MODE evidence makes the derived identity reviewable before every install | Validation: ordering pin (derivation index < backup index < install index) + execution refusal cases + INSTALL_OWNER/MODE structural pins | Residual risk: LOW — an operator on a box with neither bus nor unit file must fix the environment before activating; that is the intended fail-closed outcome | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the change is shell-only (zero renderer diff — byte-identity holds trivially), the derivation is an extractable pure decision function executed against stubs in tests, and every existing shell pin count (verify-reader-auth == 5, CANDIDATE_SHA256 == 3, MUTATIONS == 3) is asserted unchanged | Validation: seven-mode byte-identity harness diff empty + full pytest suite green + bash -n | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_show_user_mediamtx_derives_group_from_show + test_show_explicit_root_keeps_root_root_0600 + test_chroot_show_unavailable_falls_back_to_unit_file + test_chroot_unit_without_user_means_root + test_chroot_unit_group_missing_resolves_via_id + test_unit_file_override_last_assignment_wins (extracted function, stubbed systemctl/id)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_both_derivations_fail_closed (rc 1, explicit refusal ERROR, no IDENTITY output) + test_unit_file_group_unresolvable_fails_closed (rc 1, cannot-resolve-group ERROR)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_identity_derivation_precedes_any_mutation (derivation < backup < install) + test_shell_is_valid_and_contracts_fail_closed_derivation (refusal text, INSTALL_OWNER/MODE evidence lines, old silent-fallback markers absent, bash -n)
- TEST-004 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: test_activate_flow_unchanged_pins_hold (verify-reader-auth == 5, CANDIDATE_SHA256 == 3, MUTATIONS == 3, --expected-sha256, restart + no-auto-rollback markers)
- TEST-005 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base 80bcb0e vs branch, empty diff) + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #447 Outcome Contract; allowed paths (camera-relay.sh, new test battery, docs runbook, SDD trio, progress file) enforced before first write; GH007 author identity set before any commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: the identity derivation (with its fail-closed refusal) now runs BEFORE the root-only backup — both derivations failing leaves the state root and live config byte-untouched; the existing digest/mode/worker-stopped gates are unchanged and still precede the derivation
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved at the printed BACKUP path; install ownership now evidenced (INSTALL_OWNER/MODE) before the install | Retry: NO | Rollback: the unchanged activate flow preserves a root-only timestamped backup for an explicit rollback decision; automatic rollback is intentionally not authorized | Evidence: camera-relay.sh activate backup/install/restart sequence unchanged except the evidenced ownership variables
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: unchanged verify-before pair (reader auth on CANDIDATE + candidate mode/digest gates) and post-install restart/is-active/private-listener probes; the derivation adds a new pre-mutation verification stage with exit 9
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state beyond the existing candidate/sha-file/backup set; the derivation function writes nothing and keeps no state
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing temporaries | Retry: NO | Rollback: NONE | Evidence: a failed derivation creates no backup file churn (refusal precedes backup) — the pre-fix behavior could leave a fresh backup after a wrong-ownership install; the new ordering strictly reduces partial state
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: INSTALL_OWNER=<owner>:<group> + MODE=<mode> before the install lines; refusal ERROR lines on stderr with exit 9; unchanged BACKUP=/CANDIDATE_SHA256-style activation evidence
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the unchanged camera-relay.sh root-only timestamped backup (explicit operator decision); a refused derivation never reaches the install step so there is nothing to roll back | Evidence: unchanged activate fault paths (exit 30/31/32 with BACKUP printed; "automatic rollback is not authorized")
