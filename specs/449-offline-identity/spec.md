# Spec: Productive offline service-identity derivation + #448-review hardening pins

- Issue: #449
- Specification: specs/449-offline-identity/spec.md

## Product outcome

#447 made the activate service-identity derivation fail closed. The RF-001
on-box verification then found the offline premise was wrong: `systemctl cat`
is ALSO bus-dependent ("Failed to connect to system scope bus via local
transport", rc 1) even when the unit file is readable on disk. Under
docker-chroot the #447 fallback never fired: activate refused fail-closed
(exit 9 before backup/install — SAFE, but never productively derived), so
every chroot transaction needs the operator instead of deriving
root:mediamtx 0640 from the unit file that IS readable.

This change makes the offline branch productive and folds in the #448
peer-review hardening:

1. The offline branch parses the ON-DISK unit file directly: first readable
   regular non-symlink candidate among `/etc/systemd/system/<unit>`,
   `/lib/systemd/system/<unit>`, `/usr/lib/systemd/system/<unit>` (first
   wins), then the drop-in directory next to it (`<unit>.d/*.conf`, lexical
   order) merged, and the LAST `User=`/`Group=` assignment wins (systemd
   override semantics — now across main unit + drop-ins).
2. Fail-closed is preserved unchanged: neither derivation readable → the
   explicit `ERROR relay service identity could not be derived (systemctl
   unavailable and unit file unreadable); refusing to install with guessed
   ownership` + exit 9 BEFORE backup/install.
3. #448 hardening: (a) the caller's exact field order
   (`read -r install_owner install_group install_mode <<< "$identity"`) is
   structurally pinned; (b) the sed captures tolerate optional whitespace
   after `=` (`User= mediamtx` hand-edit edge — the incident direction).
4. The executable body no longer calls `systemctl cat` at all (structural
   negative pin): the bus-dependent call was the #449 bug.

## User scenarios

- US-1 (the #449 productivity goal): under docker-chroot with a readable
  `/etc/systemd/system/sea-speed-stream.service` saying `User=mediamtx`,
  activate derives root:mediamtx 0640 and proceeds — no operator
  hand-derivation needed.
- US-2: no bus AND no readable unit file anywhere → the #447 refusal
  (exit 9, before backup/install) — unchanged.
- US-3: a hand-edited unit with `User= mediamtx` / `Group= mediamtx`
  (whitespace after `=`) derives non-root instead of silently degrading to
  root:root 0600 (the incident direction).
- US-4: a drop-in override (`<unit>.d/override.conf`) that reassigns
  User/Group wins over the main unit (last assignment).
- US-5: a symlinked unit file is REFUSED (fail-closed; never followed) —
  the operator sees the explicit error, never a guessed ownership.
- US-6: `/etc` candidate wins over `/lib`/`/usr/lib` when several exist;
  a missing `/etc` unit falls through to the next candidate.

## Scope

- `deploy/worker/ubuntu/camera-relay.sh`: ONLY the
  `derive_relay_service_identity` function (offline branch + sed captures +
  docstring); the caller and every other byte untouched.
- `tests/test_mediamtx_activate_identity.py`: the battery is EXTENDED (one
  identity battery — documented decision); unit-file scenarios are re-shaped
  to the on-disk parse (systemctl stub now fails for EVERYTHING, mirroring
  real chroot; the harness substitutes the function's unit-path roots with a
  temp tree, asserting the path literals first); new cases: on-disk parse
  (the exact RF-001 chroot shape), /etc precedence, /lib fall-through,
  on-disk drop-in last-wins, whitespace tolerance, symlink refusal,
  no-`systemctl cat` pin, unit-path-order pin, whitespace-capture pin,
  caller `read -r` field-order pin.
- `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: the identity-
  derivation subsection updated (on-disk parse, грабля №27, bounded
  limitations).
- SDD trio `specs/449-offline-identity/` and the durable progress file.
- OUT of scope: the renderer (`scripts/operations/mediamtx_path_config.py` —
  zero changes), every other camera-relay.sh block, camera-preview-relay.sh,
  the renderer test batteries, specs/447-activate-identity/plan.md D-3
  wording reconciliation (issue #449 F1 marks it "may ride"; outside this
  unit's allowed paths — recorded as deferred work), the other RFC1918
  copies, everything on the #442 do-not-merge list.

## Requirements

- R-1 (AC-1 productivity): with `systemctl show` failing, a readable regular
  non-symlink unit file at one of the three standard paths yields the
  identity from its content (root:mediamtx 0640 for User=mediamtx) — the
  offline branch never depends on `systemctl cat`.
- R-2 (AC-2 fail-closed): show failing AND no readable candidate → the
  explicit #447 ERROR + rc 1 (caller exits 9 before backup/install).
- R-3 (AC-3a): the caller's `read -r install_owner install_group install_mode
  <<< "$identity"` line is pinned exactly (field-swap regression protection).
- R-4 (AC-3b): the User=/Group= captures tolerate optional whitespace after
  `=`; spaces-only values still parse as absent (→ root); trailing-space
  captures still fail at `id -gn` (F3(b)/(c) residual, recorded, fail-closed
  direction).
- R-5: the drop-in directory next to the found unit merges in lexical order
  with last-assignment-wins; drop-ins from OTHER roots are not modeled
  (bounded, documented); symlinked unit files are refused (bounded,
  documented).
- R-6: the 8-case #447 behavioral battery keeps its semantics (updated to
  the on-disk shape); renderer invocation counts and the activate evidence
  contract are untouched; renderer byte-identity holds (7-mode harness).

## Acceptance criteria

- AC-1: the offline branch parses the ON-DISK unit file directly (standard
  paths in order; first readable wins) — under chroot with a readable unit
  this yields root:mediamtx 0640 instead of refusal.
- AC-2: neither derivation readable → explicit ERROR + exit 9 BEFORE
  backup/install — unchanged from #447.
- AC-3: #448-review hardening: caller `read -r` field order pinned; sed
  whitespace-after-`=` tolerance in both captures (RED-first case).
- AC-4: RED-first tests; full suite green; SDD trio; runbook note updated
  (systemctl cat is bus-dependent — грабля №27).

## Runtime feedback

- RF-001: Operator actions expected: 1 (on-box verification of the
  productive offline path under chroot; no config mutation expected —
  confirm the derived INSTALL_OWNER=root:mediamtx MODE=0640 appears in the
  activate transcript with the bus unavailable).
- RF-002: Evidence: the same #447 evidence set (`INSTALL_OWNER=`/`MODE=`
  before the install; the explicit refusal ERROR with exit 9 when nothing is
  readable; `ERROR cannot resolve relay service group` for an unresolvable
  non-root group). New offline evidence: the derivation succeeds without any
  bus (no systemctl call needed for the fallback branch).

## NFR assessment

- NFR-001 | Area: security | Target: the fail-closed direction is preserved while the offline branch becomes productive: the refusal path, its exact error text, exit 9, and the before-backup/install ordering are unchanged; new inputs (on-disk unit file, drop-ins) are validated (regular non-symlink readable; drop-ins lexical) and the parse stays last-assignment-wins with value semantics unchanged (whitespace tolerance is only MORE permissive on spacing, never on values: spaces-only still means absent→root, trailing-space captures still fail closed at id -gn) | Validation: executed offline table (readable unit → 0640; no-user → root 0600; no-group + id → 0640; drop-in last-wins; /etc precedence; /lib fall-through; symlink refusal; both-fail refusal; unresolvable-group refusal; whitespace tolerance) | Evidence: tests/test_mediamtx_activate_identity.py — ActivateIdentityDerivationTests (12 cases) | Status: PASS
- NFR-002 | Area: reliability/operations | Target: the #449 productivity goal — activate under docker-chroot derives the identity from the readable on-disk unit file instead of refusing, removing the operator hand-derivation step from every chroot transaction; the #448 F2 field-order pin closes the suite-invisible regression class; грабля №27 is recorded in the runbook | Validation: the exact RF-001 chroot-shape test (show AND cat fail, unit readable → root:mediamtx 0640) + caller read-line pin + runbook subsection | Evidence: tests/test_mediamtx_activate_identity.py + docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md | Status: PASS
- NFR-003 | Area: compatibility | Target: zero renderer changes and no new renderer invocations — the 7 legacy harness modes stay byte-identical; the caller region (evidence lines, exit codes, mutation ordering) is byte-untouched; the 8-case #447 battery keeps its semantics re-shaped to the on-disk parse | Validation: 7-mode fixed-input harness diff base 1ede018 vs head (empty) + structural pins (counts unchanged, INSTALL_OWNER/MODE evidence, derivation-before-mutation) + bash -n | Evidence: harness transcript + ActivateIdentityContractTests | Status: PASS
