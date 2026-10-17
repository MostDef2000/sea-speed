# Plan: #520 — edge vhost renderer codification (PR-2)

- Specification: specs/520-edge-vhost-renderer/spec.md

## Architecture

The renderer keeps its single-module shape: marker constants, block
parsers, snippet builders, `render()`, `verify()`, `main()`. The change adds
a mode axis (`MODE_AUTHENTIK` default / `MODE_BASIC_AUTH`) and one shared
edge-injection primitive instead of forking the renderer:

- `_edge_injection_lines(include)` returns the two-line pair
  (`include <path>;` + `proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;`)
  used by BOTH location snippets, so both contours share one code path.
- `_auth_location_snippet` (authentik) prepends the include and places the
  edge header before the `X-authentik-*` overwrites; the authentik directive
  set is otherwise untouched (byte-compat).
- `_basic_auth_location_snippet` is new: canonical basic-auth pair + include
  + edge header + six blank `X-authentik-*` strips; no `auth_request`, no
  `error_page`, no fallback references.
- Basic-auth marker stripping is scoped to the target host server
  (`_strip_marked_sections_in_server`) because the production nginx source
  hosts several servers; sibling contours must survive a basic-auth
  codification.
- `materialize_sea_speed_includes` gains a marker-span guard: include
  directives inside renderer-managed LOCATION marker spans are never
  expanded or read (the operator edge-secret include lives there).
- `verify()` branches per mode over the same location walk; the authentik
  upstream validator stays active in both modes (fail-closed parameter
  discipline) even though basic-auth never proxies to it.

## Decisions

- D-1 (mode parameter with backward-compatible default): `render`/`verify`
  and the CLI default to `authentik`; every pre-existing invocation —
  including the #115 cutover script's `render/verify/materialize` calls —
  keeps its exact behavior. No default-behavior drift is acceptable in a
  PR whose runtime application is deferred.
- D-2 (canonical basic-auth pair verbatim): realm `"Valery Manager"` and
  `/etc/nginx/.htpasswd_3d` are pinned renderer constants matching the
  recorded live vhost, so verify can reject drift (realm or file) instead
  of silently codifying a different contour.
- D-3 (client identity blanking in basic-auth mode): every
  `/sea-speed/**` location sets the six `X-authentik-*` headers to `""` so a
  basic-auth holder cannot impersonate an Authentik identity at the API —
  this is the edge half of the PR-1 spoofing fix. Authentik mode keeps its
  existing overwrite discipline and gains no duplicate strips.
- D-4 (edge injection as include + header, never a value): the renderer
  references the operator-managed include by validated path (absolute, no
  traversal, no shell/nginx metacharacters) and never defines `$edge_auth`
  itself — no `set $` line may appear in renderer source or output, so no
  secret value can enter the repo through the renderer.
- D-5 (server-scoped stripping): `_strip_marked_sections_in_server` limits
  basic-auth marker removal to the target host server; the documented split
  nginx layout keeps mostdef.ru and 3d.mostdef.ru contours in one file.
- D-6 (materialize marker-span guard): include directives inside
  renderer-managed marker spans are treated as renderer-owned and never
  expanded, so a re-cutover cannot flatten the edge-secret include (and its
  value) into a candidate or artifact.
- D-7 (upstream validation in both modes): the Authentik upstream stays
  validated (loopback/RFC1918 IPv4, port range, no credentials) even in
  basic-auth mode — malformed parameters fail closed regardless of mode,
  keeping parameter discipline uniform.
- D-8 (edge half is PR-2 under a sibling spec dir): the renderer half is its
  own admission with its own trio under `specs/520-edge-vhost-renderer/`;
  the API half remains `specs/520-operator-edge-auth/` (merged PR-1). The
  shared 520 prefix mirrors the staged-wave precedent (396/397) and is
  grandfathered in `validate_sdd.py` by the orchestrator.

## Affected contours

- VPS: `deploy/vps/README.md` puts the PR in the VPS Change Contract class
  (derived impact VPS); no runtime mutation happens from this PR — the
  codified config is applied only through the #520 phase-2 sysadmin
  transaction (полоса C, ИБ-этап, include provisioned before candidate).
- Repo CI: focused suites + full battery + validators on the exact head.
- Ubuntu Worker/relay: none (worker contour untouched; the worker-private
  nginx block is a VPS-side listener codified parametrically as before).

## Validation

- Focused: `python3 -m pytest tests/test_sea_speed_edge_vhost_renderer.py
  tests/test_camera1_direct_h264_cutover.py tests/test_line_crossing.py -q`.
- Full battery: `python3 -m pytest tests/ -q` (orchestrator-owned for this
  unit).
- `python3 scripts/ci/validate_sdd.py` (repository + event mode with the PR
  body and exact changed-file set); `python3 scripts/ci/validate_repo.py`;
  `python3 scripts/ci/validate_change_contract.py --event <event.json>`.
- Cross-check: every AC in tasks.md traceability maps to at least one TEST
  row and every TEST row is referenced by at least one AC.
- PR Change Contract: exact eight-file match; impact VPS; Risk profile
  REQUIRED (security, HARDENING); no issue-closing reference in the PR; CI
  green on the exact head before merge.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: basic-auth mode blanks the full client X-authentik-* set in every Sea Speed location and forbids auth_request; the edge include + edge header are mandatory in both modes and verify() rejects any candidate missing them | Validation: fail-matrix tests (missing include/header/strip, auth_request forbidden, mode mixing) + golden byte-configs | Residual risk: runtime enforcement is proven only after the phase-2 sysadmin tx applies the rendered config (deferred by design to the sysadmin lane) | Owner: delivery-orchestrator | Status: OPEN
- RISK-002 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the edge secret lives only in an operator-managed VPS include outside the repo; the renderer validates the include path (absolute, no traversal/metacharacters), never emits a `set $` line, and materialize never expands renderer-managed includes | Validation: secret-absence pins (source + both goldens) and materialize guard test with a planted edge snippet | Residual risk: none known in repo scope | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: basic-auth marker stripping is scoped to the target host server, and the byte-compat authentik mode is pinned by an unchanged regression suite plus an authentik golden | Validation: server-scoped strip test; camera1 direct-h264 cutover suite green unmodified | Residual risk: none known | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: mode defaults keep pre-existing CLI/API behavior byte-wise; the CLI round-trip is tested for both modes with explicit defaults | Validation: authentik golden + CLI both-modes test + idempotence test | Residual risk: none known | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: nginx include of a missing file fails closed at nginx -t/reload, so the edge header cannot be silently dropped; provisioning order documented in docs + deploy README; rollback is the pre-tx vhost backup + reload | Validation: docs runbook #520 section, deploy/vps/README.md note, plan.md deployment transaction audit (TX-002..TX-004, TX-008) | Residual risk: an out-of-order phase-2 application fails nginx -t — fail-closed and recoverable by provisioning the include | Owner: delivery-orchestrator | Status: OPEN
- RISK-006 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the basic-auth codification documents the live legacy contour verbatim without migrating it; forward-auth migration remains an explicit owner decision recorded out of scope | Validation: spec out-of-scope + docs #520 section | Residual risk: the legacy basic-auth browser surface remains until the owner decides the migration | Owner: delivery-orchestrator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: R-1, R-2, AC-001, AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_edge_vhost_renderer.py::test_basic_auth_golden_byte_config, ::test_authentik_golden_byte_config — pinned byte-exact goldens for both modes
- TEST-002 | Covers: R-1, R-2, R-3, AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: ::test_edge_injection_present_in_every_sea_speed_location_in_both_modes, ::test_basic_auth_mode_strips_client_authentik_headers_in_every_location, ::test_authentik_mode_keeps_auth_request_and_avoids_duplicate_blank_strips
- TEST-003 | Covers: R-1, AC-001 | Level: unit | Priority: P0 | Evidence: ::test_render_is_idempotent_for_both_modes, ::test_basic_auth_render_leaves_server_level_directives_and_other_servers_untouched — idempotence and split-layout safety
- TEST-004 | Covers: R-3, AC-003 | Level: unit | Priority: P0 | Evidence: ::test_verify_fail_matrix_missing_edge_injection_both_modes, ::test_verify_fail_matrix_missing_edge_include_both_modes, ::test_verify_fail_matrix_missing_strip_in_basic_auth_mode, ::test_verify_fail_matrix_missing_basic_auth_pair, ::test_verify_fail_matrix_auth_request_forbidden_in_basic_auth_mode, ::test_verify_rejects_mode_mixing
- TEST-005 | Covers: R-4, AC-004 | Level: unit | Priority: P0 | Evidence: ::test_worker_private_block_matches_recorded_live_facts; tests/test_line_crossing.py WORKER_PRIVATE_ENDPOINTS pin (endpoint/method surface unchanged)
- TEST-006 | Covers: R-5, AC-005 | Level: unit | Priority: P0 | Evidence: ::test_edge_auth_include_path_is_a_parameter (custom path renders+verifies; relative/space paths rejected), ::test_rendered_output_never_contains_secret_literals (source + goldens: no secret literal, no set $edge_auth, no set $ assignment)
- TEST-007 | Covers: R-6, AC-005 | Level: unit | Priority: P1 | Evidence: ::test_materialize_never_expands_or_reads_the_edge_secret_include — planted edge snippet in the include root, materialized output byte-identical and snippet unread
- TEST-008 | Covers: R-7, AC-006 | Level: integration | Priority: P1 | Evidence: ::test_cli_render_and_verify_both_modes — subprocess CLI render+verify with --mode/--edge-auth-include for both contours
- TEST-009 | Covers: R-2, R-7, AC-002, AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_camera1_direct_h264_cutover.py renderer suite (7 tests) green unmodified — authentik-mode regression and idempotence on the existing contour
- TEST-010 | Covers: AC-007 | Level: runtime-manual | Priority: P1 | Evidence: phase-2 sysadmin tx probes on #520 — nginx -t PASS, browser basic-auth flow on 3d.mostdef.ru, authentik flow on mostdef.ru, edge header present at the API, forged X-authentik-* blanked, worker-private listener unchanged

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

The phase-2 VPS edge transaction (sysadmin lane, полоса C, ИБ-этап) that
applies this PR's rendered configuration after merge: provision the
operator-managed edge include, render candidates from the exact merged head,
apply and verify both vhost contours. The repo PR itself performs no on-box
mutation; this audit pins the deferred transaction's stages.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no on-box action; live vhosts keep running the current hand-maintained config | Retry: after fresh sysadmin handoff acceptance (полоса C, ИБ-этап checklist complete) | Rollback: not applicable (no mutation) | Evidence: exact 40-hex SHA of the merged PR-2 head on origin/main + green CI on that SHA + phase-2 handoff accepted on #520
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Mutation detail: operator-managed edge include provisioned (root-owned, mode 0600, outside the repo) and live vhost files backed up with digests; rendered candidates produced by the renderer CLI from the merged head and checked with nginx -t before any activation | Failure disposition: CONDITIONAL | State after failure: include file present but unreferenced (inert) and live config untouched on nginx -t failure; backup and digests recorded | Retry: yes, after root-cause read (fix include mode/owner or candidate defect) | Rollback: remove the inert include file; no config change to revert | Evidence: tx log with include path/mode, backup digests, nginx -t PASS output
- TX-003 | Stage: MUTATION | Mutation: YES | Mutation detail: rendered candidates replace the managed vhost contours (mostdef.ru authentik + 3d.mostdef.ru basic-auth + worker-private block) and nginx is reloaded | Failure disposition: CONDITIONAL | State after failure: nginx reload fails closed on an invalid candidate — previous config stays active; a half-applied file state is prevented by the nginx -t gate in TX-002 | Retry: one bounded retry after root-cause read | Rollback: restore the TX-002 vhost backup and reload (digest-bound) | Evidence: tx log with applied digests and reload output
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: new config active but not accepted; rollback (TX-008) executed before handoff closes | Retry: after remediation and fresh probes | Rollback: as TX-008 | Evidence: probes on #520 — nginx -t PASS; browser basic-auth flow on 3d.mostdef.ru; authentik flow on mostdef.ru; X-Sea-Speed-Edge-Auth present at the API on Sea Speed routes; forged client X-authentik-* blanked; worker-private listener probes unchanged
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: applied config remains active; the recorded authoritative digest state is completed before the handoff closes (no silent drift) | Retry: yes, recording-only | Rollback: as TX-008 if the recorded state contradicts the probed state | Evidence: applied digest triple (mostdef.ru, 3d.mostdef.ru, worker-private) + include file pointer recorded in the tx log and on #520
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: runtime correct; candidate/backup temp files may linger and are cleaned next session; the secret exists only as the include file (never copied into candidates, logs or evidence) | Retry: next sysadmin session | Rollback: not applicable (cleanup only) | Evidence: tx log listing removed temp files; secret-pointer-only rule confirmed
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime correct; evidence gap closes on the next session | Retry: yes | Rollback: not applicable | Evidence: #520 phase-2 comment with probe outputs and digests; JOURNAL entry after the tx
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: pre-transaction vhost backups restored and reloaded; probes re-run; live state back to the previous digests | Retry: one bounded retry, then hold for owner decision | Rollback: digest-bound restore from the TX-002 backup via the sysadmin lane (standing rollback contract) | Evidence: rollback probe results on #520 (rollback ready_not_used unless triggered)

## Runtime feedback

- Fail-closed ordering: the rendered include references the operator secret
  file, so applying a candidate before provisioning the include fails at
  `nginx -t`/reload — the hazard is fail-closed, never a silent header drop.
  Phase 2 (this PR's config) stays before phase 3 (API env + deploy, PR-1
  scope) per the #520 rollout order.
- Mode discipline: `verify` rejects cross-mode configs, so a future re-render
  with the wrong mode cannot pass verification against a live basic-auth or
  authentik contour; the prefixed-outpost rejection holds in both modes.
- The basic-auth contour stays legacy by design; its forward-auth migration
  is an owner decision outside this admission.
