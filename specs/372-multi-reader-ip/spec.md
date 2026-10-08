# Spec: Multi-reader-IP support in the canonical MediaMTX config tooling

- Issue: #372
- Specification: specs/372-multi-reader-ip/spec.md

## Product outcome

The live Ubuntu worker cam1 reader rule legitimately contains TWO VPS reader
IPs (`10.123.239.101`, `10.123.239.102`) in `ips: [...]`. The canonical
tool's CLI accepted a single `--reader-ip` and compared the whole reader
block exactly (`ensure_internal_reader_rule` / `_reader_rule_lines`), so any
2-IP deployment could not be remediated through the canonical bounded tool —
`camera-relay.sh prepare` failed with `existing Sea Speed reader
authorization rule does not match the requested rule` before writing the
candidate (blocked #362 remediation), pushing operators back to manual config
edits that drift away from the canonical tool's expected shape.

The renderer core already accepts `reader_ip: str | list[str]` (introduced
with 3866220/#335 for the transcode publisher `publisher_ips`) and
`verify_internal_reader_rule` already carries SUBSET semantics
(requested ⊆ existing) — the gap was purely CLI/shell. This change closes it:

1. `scripts/operations/mediamtx_path_config.py`: `--reader-ip` on
   `ubuntu-relay` and `verify-reader-auth` becomes repeatable
   (`action="append"`) and additionally accepts one comma-separated value; a
   normalizer (`_reader_ip_list`) preserves the exact input order (stable
   documented order for the rendered `ips: [...]`), rejects duplicates and
   empty lists fail-closed, and both render modes validate every IP with the
   existing per-IP RFC1918 gate. The RENDERED/VERIFIED evidence line carries
   a deterministic count-annotated scope token (`single-rfc1918-ip` for one
   IP — the historical literal — `multi-rfc1918-ip-count-N` otherwise).
2. `deploy/worker/ubuntu/camera-relay.sh`: `--reader-ip` is repeatable and
   comma-separated; every occurrence is validated (per-IP RFC1918) and all
   occurrences are forwarded to the renderer; the `READER_AUTH_SCOPE`
   evidence is generalized deterministically
   (`cam1-single-rfc1918-peer` for one reader — historical literal —
   `cam1-multi-rfc1918-peer-count-N` otherwise).
3. Fail-closed semantics are preserved exactly: `ensure_internal_reader_rule`
   still compares the whole rendered block (including ALL reader IPs and
   their order), so a re-render with a different IP list/order is a
   ConfigError before any candidate write; `verify_internal_reader_rule`
   keeps SUBSET semantics (requested ⊆ existing) unchanged.
4. Single-IP CLI invocations produce byte-identical output to the current
   behavior (rendered block bytes, idempotent re-apply, scope token).

Note (#373 research honored): the preview relay uses one regex rule with a
single IP and never invokes this renderer — preview tooling is untouched.

## User scenarios

- US-1: The operator re-applies the live 2-IP worker deployment
  (`camera-relay.sh prepare --reader-ip 10.123.239.101 --reader-ip
  10.123.239.102`): the candidate renders `ips: ["10.123.239.101",
  "10.123.239.102"]` and `prepare` succeeds — the #362 manual-edit
  workaround is no longer required.
- US-2: The operator passes the two IPs as one comma-separated value:
  identical rendered candidate to US-1.
- US-3: `activate` verifies `verify-reader-auth` with all forwarded IPs and
  subset semantics: a requested single IP that is a member of the 2-IP live
  rule verifies; a non-member IP fails closed.
- US-4: A re-render over an existing 2-IP rule with a different IP list
  (different member, dropped IP, or different order) fails closed with
  ConfigError and writes no candidate.
- US-5: A single-IP deployment re-runs the tool exactly as before: the
  rendered reader block and the evidence line are byte-identical to the
  historical behavior.

## Scope

- `scripts/operations/mediamtx_path_config.py`: `_reader_ip_list`
  normalizer, `reader_scope_token` evidence helper, `--reader-ip`
  `action="append"` on `ubuntu-relay`/`verify-reader-auth`, list pass-through
  and per-IP validation in `render_ubuntu_relay`/`render_verify_reader_auth`.
  Core rule functions (`ensure_internal_reader_rule`,
  `_reader_rule_lines`, `verify_internal_reader_rule`) already accept
  `str | list[str]` and are NOT changed; `ubuntu-transcode-reader` stays
  single-IP.
- `deploy/worker/ubuntu/camera-relay.sh`: `reader_ips` array parsing
  (repeatable + comma-split + trim + empty-entry rejection), per-IP
  validation loop, `reader_ip_args` forwarding array into both renderer
  invocations, generalized `READER_AUTH_SCOPE` evidence, usage text.
- `tests/test_mediamtx_multi_reader_ip.py` (new): renderer two-IP render,
  order stability, single-IP byte-identical pins, mismatch rejection,
  subset-verify on a 2-IP rule, duplicate rejection, CLI repeatable/comma
  paths, CLI fail-closed mismatch, camera-relay.sh forwarding structural
  pins.
- `tests/test_camera1_live_replacement.py`: one documented anchor update in
  `test_shell_contracts_are_explicit_and_ai_worker_is_not_controlled` — the
  `READER_AUTH_SCOPE=cam1-single-rfc1918-peer` literal moved inside the
  `reader_auth_scope()` helper, so the pin is re-pointed at the preserved
  literal plus the generalized printf (strength preserved, no assertion
  weakened).
- This SDD trio and the durable progress file.
- Out of scope: preview-relay tooling (#373 keeps its single-IP regex rule
  untouched), `prepare-runtime.sh`, `update-exact.sh`, `api/**`,
  `deploy/vps/**`, `.github/**`, watchdog, all other scripts, production
  runtime config changes (activation is a separate human-gated transaction).

## Requirements

- R-1: `--reader-ip` on `ubuntu-relay` and `verify-reader-auth` accepts
  repeated flags and one comma-separated value; the rendered
  `ips: [...]` contains ALL requested reader IPs in the exact input order.
- R-2: Every requested reader IP is validated by the existing RFC1918 gate
  (`validate_reader_ip` in `ubuntu-relay`, shell heredoc in
  camera-relay.sh) before any candidate is written; duplicates and empty
  reader-IP input fail closed.
- R-3: The fail-closed exact-block mismatch semantics are preserved:
  re-rendering over an existing rule with a different IP list or order is a
  ConfigError and no candidate is written.
- R-4: `verify_internal_reader_rule` keeps SUBSET semantics (requested ⊆
  existing) unchanged, including on 2-IP live rules.
- R-5: Single-IP CLI invocations produce byte-identical output to the
  current behavior (rendered block bytes, idempotent re-apply, scope token
  literal), and the RENDERED/VERIFIED evidence carries a deterministic
  count-annotated scope token for multi-IP invocations.
- R-6: camera-relay.sh forwards all `--reader-ip` occurrences to both the
  prepare render and the activate verify-reader-auth invocations, and the
  `READER_AUTH_SCOPE` evidence generalizes deterministically
  (`cam1-single-rfc1918-peer` / `cam1-multi-rfc1918-peer-count-N`).

## Acceptance criteria

- AC-1: A two-IP `ubuntu-relay` render (repeatable or comma-separated)
  produces a candidate whose cam1 reader rule is
  `ips: ["10.123.239.101", "10.123.239.102"]` and passes
  `verify_internal_reader_rule` with both IPs.
- AC-2: `verify-reader-auth` accepts a requested single IP and the full
  requested list against a 2-IP live rule (subset), and rejects a
  non-member IP.
- AC-3: A single-IP CLI invocation renders the historically byte-identical
  reader block (`ips: ["10.123.239.101"]`), re-applies idempotently through
  the str API, and prints `reader_scope=single-rfc1918-ip`.
- AC-4: Re-rendering over an existing 2-IP rule with a different IP list or
  order exits non-zero with the exact-block mismatch error and the candidate
  is not written; duplicate `--reader-ip` input fails closed.
- AC-5: Rendering the same input order twice is byte-identical; reversing
  the input order renders the reversed `ips: [...]` line (order stability).
- AC-6: Full pytest suite green; `bash -n` clean on camera-relay.sh; ruff
  clean on changed Python files; `validate_sdd.py` green.

## Runtime feedback

- RF-001: Operator actions expected: 0 on merge — no production runtime
  change until a follow-up operator-scheduled re-render of the worker relay
  uses the repeatable flags; the tool change is dormant until then.
- RF-002: Evidence: renderer `reader_scope=multi-rfc1918-ip-count-2` token
  and shell `READER_AUTH_SCOPE=cam1-multi-rfc1918-peer-count-2` on a 2-IP
  prepare/activate; historical `single-rfc1918-ip` /
  `cam1-single-rfc1918-peer` literals unchanged for one reader.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: any N-IP (including the live 2-IP) worker deployment can be remediated through the canonical bounded tool instead of manual edits that drift the config away from the canonical shape (issue #372 blocked-#362 class closed) | Validation: executed two-IP renders (repeatable + comma-separated CLI) with candidate verification via verify_internal_reader_rule, idempotent re-apply pins | Evidence: tests/test_mediamtx_multi_reader_ip.py — test_two_ip_render_includes_both_ips_in_input_order, test_cli_repeatable_flags_render_both_ips, test_cli_comma_separated_value_renders_both_ips | Status: PASS
- NFR-002 | Area: security | Target: no over-grant and no validation gap: every reader IP passes the existing RFC1918 gate per-IP before any write, duplicates fail closed, and the fail-closed exact-block mismatch semantics (all IPs, order-sensitive) plus verify SUBSET semantics are preserved | Validation: executed mismatch/subset/duplicate/negative-IP scenarios on 2-IP rules and CLI fail-closed render attempts with no candidate write | Evidence: tests/test_mediamtx_multi_reader_ip.py — test_mismatch_reader_ip_list_is_rejected_fail_closed, test_verify_subset_semantics_on_two_ip_live_rule, test_duplicate_reader_ips_fail_closed, test_cli_mismatch_list_is_rejected_and_candidate_untouched | Status: PASS
- NFR-003 | Area: compatibility | Target: single-IP CLI output is byte-identical to the historical behavior (rendered block bytes, idempotent str-API re-apply, `single-rfc1918-ip` / `cam1-single-rfc1918-peer` literals); every other renderer mode (ubuntu-transcode-reader, vps-switch, vps-cleanup, vps-set-hls-address) untouched; preview-relay tooling untouched (#373) | Validation: executed str-vs-list-vs-comma equivalence pins plus exact historical block-byte pins and unchanged other-mode battery (full suite green) | Evidence: tests/test_mediamtx_multi_reader_ip.py — test_single_ip_is_byte_identical_to_historical_str_behavior, test_cli_single_flag_matches_historical_output; tests/test_camera1_live_replacement.py (unchanged pins, updated shell anchor only) | Status: PASS
- NFR-004 | Area: maintainability | Target: the shell forwarding is deterministic and inspectable — repeatable/comma parsing with explicit empty-entry rejection, per-IP validation loop ordered before any renderer call, and generalized evidence that keeps the deterministic single-reader literal | Validation: structural pins in the established style plus `bash -n` syntax gate | Evidence: tests/test_mediamtx_multi_reader_ip.py — test_shell_contracts_forward_all_reader_ip_occurrences; test_camera1_live_replacement.py — test_shell_contracts_are_explicit_and_ai_worker_is_not_controlled (re-pinned anchor) | Status: PASS

## Deviations from the work order

- None in scope. The allowed anchor update in
  `tests/test_camera1_live_replacement.py` was required by the documented
  re-pin discipline: the `READER_AUTH_SCOPE=cam1-single-rfc1918-peer`
  literal moved inside `reader_auth_scope()`; the pin was re-pointed at the
  preserved literal plus the generalized printf with equal-or-stronger
  strength.
