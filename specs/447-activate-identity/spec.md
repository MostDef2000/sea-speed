# Spec: Activate service-identity derivation must fail closed

- Issue: #447
- Specification: specs/447-activate-identity/spec.md

## Product outcome

During the 2026-10-10 on-box activate under docker-chroot (the #436/#444
retry transaction), `systemctl show -p User` returned empty ("Failed to
connect to system scope bus") and `camera-relay.sh activate` silently fell
back to root:root 0600 instead of the service's root:mediamtx 0640. mediamtx
crash-looped on the freshly installed config (`open /etc/mediamtx/
mediamtx.yml: permission denied`) for ~100 s until the operator hand-fixed
ownership to exactly what the script had intended. The no-auto-rollback
contract held (ERROR + BACKUP emitted), but the permission derivation
FAILED OPEN: an ambiguous `systemctl show` answer (bus failure) was treated
as "unit runs as root".

This change makes the derivation fail closed and chroot-safe:

1. A new extractable `derive_relay_service_identity` function in
   `camera-relay.sh` derives the install identity in two bounded steps:
   `systemctl show` (definitive ONLY when `User=` is non-empty), then the
   unit file via `systemctl cat` (offline-safe under chroot; the LAST
   `User=`/`Group=` assignment wins per systemd override semantics; `User=`
   absent or empty means root). If BOTH fail, activate refuses with an
   explicit error BEFORE any mutation — before the backup and before the
   install — so a wrong guess can never be silently installed.
2. The activate step evidences the derived identity on the success path
   (`INSTALL_OWNER=<owner>:<group>` and `MODE=<mode>`) so a wrong derivation
   is visible in the transcript even if a later step fails.
3. Everything else is unchanged: digest binding, candidate mode gate,
   verify-before, worker-stopped gate, root-only timestamped backup, atomic
   install, restart, private-listener probe, "automatic rollback is not
   authorized"; prepare/sanitize/remediate and the renderer are untouched.

## User scenarios

- US-1: On a healthy box (system bus reachable), activate derives
  `User=mediamtx` from `systemctl show` and installs root:mediamtx 0640 —
  behavior identical to before for definitive answers.
- US-2: Under docker-chroot (the incident): `systemctl show` fails/returns
  empty; the unit file on disk carries `User=mediamtx`/`Group=mediamtx`;
  activate derives root:mediamtx 0640 from the unit file and the transcript
  shows `INSTALL_OWNER=root:mediamtx` + `MODE=0640` before the install.
- US-3: Both derivations fail (no bus AND no readable unit file): activate
  prints the explicit refusal error and exits nonzero BEFORE creating the
  backup or touching the config — no partial install with wrong ownership.
- US-4: A unit genuinely running as root (explicit `User=root` or no `User=`
  in a readable unit file) keeps the root:root 0600 install — same outcome
  as before, now derived from a definitive source.
- US-5: A non-root unit whose group cannot be resolved anywhere: activate
  refuses (exit 9, `ERROR cannot resolve relay service group`) rather than
  guessing.

## Scope

- `deploy/worker/ubuntu/camera-relay.sh`: new `derive_relay_service_identity`
  function (placed with the other extractable helpers, blank-line separated
  for test extraction); the activate block replaces the silent-fallback
  derivation with the fail-closed caller + `INSTALL_OWNER`/`MODE` evidence.
  No other block changes; renderer invocation counts unchanged.
- `tests/test_mediamtx_activate_identity.py`: new RED-first battery (8
  derivation execution cases with stubbed `systemctl`/`id` following the
  established `shell_function` + inline-stub pattern, 3 structural contract
  tests).
- `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: brief
  "Relay service identity derivation" subsection (derivation order, chroot
  note, fail-closed contract, evidence lines).
- This SDD trio and the durable progress file.
- Out of scope: `check_auth_environment_override` (reads systemd Environment,
  not service identity — untouched per AC-3), the renderer
  (`scripts/operations/mediamtx_path_config.py` — zero changes), the
  prepare/sanitize/remediate flows, the activate install/restart/probe
  sequence itself, automatic rollback, `deploy/vps/**`.

## Requirements

- R-1: activate NEVER silently falls back when `systemctl show` returns
  empty/unavailable: the identity is re-derived from the unit file
  (`systemctl cat`), and if BOTH derivations fail activate exits nonzero
  with the explicit refusal error BEFORE the backup and install.
- R-2: The install path evidences the derived ownership and mode
  (`INSTALL_OWNER=<owner>:<group>`, `MODE=<mode>`) before the install.
- R-3: Definitive-answer semantics are preserved: explicit non-root
  `User=` → root:<group> 0640 (group from show, else `id -gn`, else refuse);
  explicit `User=root` or a readable unit without `User=` → root:root 0600.
- R-4: The rest of the activate flow is unchanged (expected-sha256 binding,
  root-only timestamped backup, atomic install, restart, listener probe, no
  auto-rollback); prepare/sanitize/remediate untouched; existing shell pin
  counts hold (verify-reader-auth == 5, CANDIDATE_SHA256 == 3,
  MUTATIONS == 3).

## Acceptance criteria

- AC-1: activate (and any step deriving service identity) NEVER silently
  falls back when `systemctl show` returns empty/unavailable: it derives
  `User=`/`Group=` from the unit file (`systemctl cat`), and if BOTH
  derivations fail it fails closed with an explicit error BEFORE any file
  install (no partial install with wrong ownership).
- AC-2: the install step evidences expected ownership/mode in its output
  (`INSTALL_OWNER=root:mediamtx MODE=0640` shape) so a wrong derivation is
  visible in the transcript.
- AC-3: activate flow otherwise unchanged (expected-sha256 binding, root-only
  timestamped backup, atomic install, restart, probe, no auto-rollback);
  prepare/sanitize/remediate untouched; shell pins updated only where counts
  change, with documented reasons (none change).
- AC-4: RED-first tests (unit-file derivation path; systemctl-unavailable →
  fail-closed before install), full suite green; SDD trio with deployment
  transaction audit.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box verification
  transaction (a dry activate or equivalent check confirming derived owner
  == root:mediamtx on the real box; no config change expected — perms are
  already correct), recorded in the #447 runtime acceptance by the
  orchestrator.
- RF-002: Evidence: on the success path `INSTALL_OWNER=<owner>:<group>` +
  `MODE=<mode>` immediately before the install lines; on the failure path
  `ERROR relay service identity could not be derived (systemctl unavailable
  and unit file unreadable); refusing to install with guessed ownership` on
  stderr with exit 9 and NO backup/install churn; group-resolution failures
  keep `ERROR cannot resolve relay service group` (exit 9).

## NFR assessment

- NFR-001 | Area: security/reliability | Target: the activate permission derivation fails closed on ambiguity — an empty `systemctl show` answer is treated as "unknown" (never as "unit runs as root"), the unit-file fallback is the authoritative offline source, and both derivations failing refuse the transaction before any state-dir or config mutation; a non-root unit without a resolvable group also refuses rather than guessing | Validation: executed derivation table (show definitive non-root, show explicit root, chroot show-failure → unit file, unit without User= → root, unit without Group= → id -gn, drop-in last-assignment-wins, both fail → rc 1 + no IDENTITY output, group unresolvable → rc 1) plus structural pins (refusal precedes backup and install, old silent-fallback markers absent) | Evidence: tests/test_mediamtx_activate_identity.py — all ActivateIdentityDerivationTests cases + test_identity_derivation_precedes_any_mutation + test_shell_is_valid_and_contracts_fail_closed_derivation | Status: PASS
- NFR-002 | Area: operations | Target: the derivation is visible and bounded: `INSTALL_OWNER`/`MODE` evidence on the install path, explicit refusal error text, exit code 9 preserved for identity failures, and the digest/backup/restart/no-auto-rollback discipline byte-unchanged | Validation: structural contract pins (INSTALL_OWNER/MODE lines, refusal message, verify-reader-auth == 5, CANDIDATE_SHA256 == 3, MUTATIONS == 3, --expected-sha256, "automatic rollback is not authorized", systemctl restart) + bash -n | Evidence: tests/test_mediamtx_activate_identity.py — ActivateIdentityContractTests | Status: PASS
- NFR-003 | Area: compatibility | Target: zero renderer changes and no new renderer invocations — every existing renderer mode keeps byte-identical output; prepare/sanitize/remediate flows untouched; the one behavior change is scoped to the activate identity derivation | Validation: seven-mode fixed-input byte-identity harness diffed base vs head (empty diff trivially — shell-only change) + full pytest suite green | Evidence: byte-identity harness transcript (byte-id-base-447 vs head, diff empty) | Status: PASS
