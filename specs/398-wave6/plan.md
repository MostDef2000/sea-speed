# Plan — Issue #398 wave 6

- Issue: #398
- Specification: specs/398-wave6/spec.md

## Architecture

Follow the wave-1..5 house model: RB (execute the real thing) > SS (structured
parse/scan) > SP (STATIC_POLICY pins kept verbatim with justification) > NO-CHANGE
(recorded rationale) > redundant retirement (only with a recorded same-commit twin).
The wave-6 surface is the governance-docs layer: runbooks, operator docs, delivery
contracts, agent instructions. These docs have no YAML/AST — the wave-6 house model
is the SECTION-SCOPED TEXT TWIN: a shared stdlib scanner
(`tests/support/markdown_docs.py`) splits a document into fence-aware ATX sections
(headings inside ```/~~~ fences never split sections, so embedded templates, JSON
examples and command blocks keep their placement), and twins assert on:

- co-location — `section_containing(*markers)` returns the first section whose
  heading+body contains EVERY marker, case-insensitively, so a marker that drifts
  into an unrelated section fails instead of passing file-wide;
- heading binding — `section_titled(*fragments)` pins content to the RIGHT section
  (case-insensitive heading match only);
- embedded structure — `fenced_blocks(body)` extracts fenced blocks for EXACT
  line-list equality (command templates, config blocks, status-block templates);
  `json.loads` parses the embedded checkpoint-v2 schema block; the real
  `upgrade_v1_checkpoint` validator EXECUTES against a tmp copy (RB where a
  validator enforces the doc).

Scanner gotchas recorded in-code and in the checkpoint: first-match semantics mean a
co-location twin must always carry a disambiguating co-marker (the AGENTS.md
wait-replay first match is "Mandatory operating rules", not the wait section); the
RELEASE_READINESS_GATE.md bundle section carries neither churn marker, so the
combined pin stays verbatim with a per-doc section twin for the other 5 contracts.
No new frameworks or patterns; the scanner lives in tests/support/ (3+ files share
it).

## Decisions

- **Section-scoped text twins over anywhere-in-file pins**: the doc IS a prose
  artifact, so the twin keeps the textual needle but binds it to a section —
  placement drift fails, pure rewording of non-contract prose passes.
- **Case-insensitivity is part of the canon** (scanner-lowered needles and
  haystacks): heading-cased prose references do not keep a lowercase pin alive, and
  the twins do not depend on sentence-initial capitalization — exactly what bounds
  Direction A of the demo to the 2 prose-form pins (CC-1). Exception (peer review
  F1): case-significant contract tokens ("MoQ", "CONFIRM_NEW_CAMERA", "one
  OpenCode rollout scope") are enforced EXACT-CASE against the raw section text in
  the owning test, preserving the old case-sensitive pins' strength.
- **Fenced-block EXACT equality for embedded templates**: relay prepare commands,
  canonical source blocks, M2M worker URLs, terminal-state and status-block
  templates assert as exact line lists — reordering or editing a line fails.
- **json.loads for the checkpoint-v2 schema block**: the doc embeds a JSON schema;
  the twin parses it and cross-checks properties/required, and the real
  `upgrade_v1_checkpoint` validator executes against a tmp copy (RB where a
  validator enforces the doc).
- **SP keeps are negative contracts or literal policy wording**: 5 legacy terminal
  phrases, "Final state:" runtime ban, no-Grafana whole-doc absence,
  "External host:" ban, "runtime remains `UNKNOWN`" bans, stale-identity ban,
  data-preservation warning, rollback-prohibition placement twin (prohibition +
  separate-governed-decision caveat — dropping either half fails), combined pins
  whose per-doc twins live in a sibling file (same-commit coverage ledger).
- **NO-CHANGE records stand from earlier waves**: wave-5 prose-scan files, wave-4
  SDD feature docs (auth_v1 keeps its SDD spec/plan/tasks/quickstart pins verbatim
  with the wave-4 rationale in-code), installer-script pins in manual_install (they
  pin the INSTALLER, not docs), the already-parsed todo block L96-185
  (byte-identical).
- **Demo verdict classes are documented, not forced**: wave-6 twins are text anchors
  matching on the retired pin strings (case-insensitive, gate/policy tokens
  exact-case), so the vocabulary pins fail only under refactors that alter the
  contract identifiers themselves while the 2 prose-form pins fail under editorial
  rewording the twins tolerate; the demo asserts per-class verdicts instead of
  dishonestly mangling identifiers (CC-1, flagged to the orchestrator).

## Site-mapping table (old → replacement)

| File | Retired pin (group) | Kind | Twin / where it lives |
|------|---------------------|------|-----------------------|
| test_delivery_resume_contract.py | truth-classes, admission receipts, checkpoint-v2 fields, resume-probe, context-loss, monotonic reasons, connector chain, event-driven CI, wait-replay, terminal-model pins (~45 sites across AGENTS.md + 5 contracts + PM_BOOTSTRAP + control-plane doc) | SS+RB+SP | per-doc co-section twins (truth classes; receipt + cannot-create strong form; resume probe + PM_BOOTSTRAP Required-behavior scope; context-loss + DISCUSSION + negation; connector chain + fresh-read exception; wait-replay nonterminal + replay-with-negation (CC-3); CI-foreground bundle; terminal model), runtime truth-section binding, checkpoint-v2 JSON block parsed (json.loads) + schema properties/required cross-check, v1 upgrade EXECUTED via real upgrade_v1_checkpoint, monotonic fenced reason set EXACT equality + CONTEXT_LOSS ban; combined event-driven/wait-replay pins SP-kept with per-doc section twins (GATE excluded — carries neither marker) |
| test_delivery_terminal_states.py | terminal vocabulary, legacy-state bans, blocker/wait semantics, CI behavior pins (~45 sites across 6 contracts) | SS+SP | per-doc session-disposition section twins (3 states + terminal interaction + `FAILED` literal + BLOCKED/human bundles), runtime fenced blocks EXACT equality ({DONE,BLOCKED,HUMAN DECISION REQUIRED}; {ACTIVE,WAITING_EXTERNAL,TERMINAL}), Required status block single fenced template, WAITING_EXTERNAL per-doc co-sections + runtime literals placement-pinned, 6-marker ci-foreground bundle (CC-4 scoping); SP keeps: 5 legacy-phrase bans (combined NotIn), Final-state ban, combined no-background/checkpoint-update/context-loss pins (per-doc twins in resume file, same-commit ledger) |
| test_delivery_todo_contract.py | todo fields, model lines, role markers, forbidden fallback pins (~50 sites; L96-185 already parsed) | SS+SP | per-entrypoint Required-behavior section twins, Structured todo projection section twins (runtime + agent), todo display block exact 5-line set, ACTIVE/WAITING_EXTERNAL/BLOCKED vocabulary co-section twins; SP keeps: agent-file Russian routing bans, DELIVERY_POLICY todo-authority placement pin; L96-185 byte-identical |
| test_sea_speed_auth_v1.py | issue links, topology, deploy commands/URLs, auth vocabulary pins (~30 sites) | SS+SP | AUTH_DOC preamble #115/#122 binding + Topology socat/range co-location + superseded/must-not-stage deprecation co-section; OPS_DOC preamble full issue chain #115/#122/#140/#146, #146 External host + Launch URL EXACT single-line fenced blocks, stage command block, AUTHENTIK_PRIVATE_ORIGIN + SEA_SPEED_API_TOKEN co-sections, M2M worker-URL EXACT 5-line block, fail-closed Phase E section_titled + never-anonymous, cutover/conf co-sections, 96h/30d timing co-section; SP keep: "External host: https://mostdef.ru/sea-speed/" ban; SDD feature docs kept verbatim (wave-4 NO-CHANGE precedent, in-code) |
| test_camera1_live_replacement.py | 12 doc pins (migration history, protected path, relay boundary, rollback authority, UNKNOWN ban) | SS+SP | co-section twins: Issue #115+superseded; protected path+Authentik-protected; /cams/hls ban+must-not-be-recreated; cam2+identity; worker-independence+AI-worker-stop; ZeroTier peer+read (Security model); relay prepare = single fenced block; canonical cam1 source EXACT 3-line block; section_titled retire+cam1-new + body rule (gated cleanup flow + refuse-unless-canonical guard); cutover activation boundary; explicit-rollback+do-not-restore co-section; SP keep: "runtime remains `UNKNOWN`" ban |
| test_mediamtx_compatibility_remediation.py | 12 doc pins → 9 unique groups (DEMO TARGET) | SS+SP | blocker classification co-section [Why this exists]; provenance co-section [Candidate provenance]; canary section_titled + contract (127.0.0.1:18954 + MoQ+disabled + sandboxed proof in-section); scope section_titled bundle (rollout scope + CONFIRM_NEW_CAMERA + cam1-new + /cams/hls + Basic Auth + human visual acceptance); worker non-mutation co-section [Production binary activation]; rollback prohibition SP placement twin (+ separate governed decision — dropping either half fails); demo proves both directions |
| test_camera1_direct_h264_cutover.py | 6 doc pins (issue, route/upstream, tool, standalone, stale-identity ban) | SS+SP | Issue #115+supersedes co-section; preamble fenced topology block (topology[-2:] normalized via removeprefix("-> ") — CC-5); cutover.sh+only-production-activation-path co-section; standalone+deliberately-retired co-section; SP keep: stale-identity ban |
| test_ubuntu_worker_storage_lifecycle_contract.py | 4 doc pins (UNKNOWN runtime, secret boundary, auto-delete, --apply-plan) | SS | preamble (sections[0]) states "Runtime remains `UNKNOWN`"; Safety model section co-locates never-deletes + does-not-read-worker.env; --apply-plan = unique fenced command block in "Apply an approved plan" section |
| test_ubuntu_worker_observability.py | 4 doc pins (UNKNOWN state, journalctl, timer, no-Grafana) | SS+SP | Runtime boundary section carries "Runtime remains `UNKNOWN`"; journalctl unique 2-line fenced block in "Safe inspection"; timer ban in "Install periodic checks"; SP keep: assertNotIn("Grafana") whole-doc absence IS the enforcement |
| test_ubuntu_worker_manual_install.py | 1 doc pin (data-preservation warning) | SP | kept verbatim with one-line rationale (textual presence IS the contract, no executable validator); installer-script pins untouched (out of wave-6 scope) |
| tests/support/markdown_docs.py | (new) | SS | shared stdlib scanner: sections / section_containing / section_titled / fenced_blocks — fence-aware, case-insensitive, first-match (documented) |
| tests/test_398_wave6_demo.py | (new) two-direction demo | SS | section-scoped twin contract on MEDIAMTX_COMPATIBILITY_REMEDIATION.md tmp copies; 12 retired pins restated; verdict classes + inverted mutations recorded in tasks.md |

## Affected contours

- Tests only: the 10 converted test files, the new tests/support/markdown_docs.py,
  the demo, this trio — plus the recorded one-line grandfather entry in
  scripts/ci/validate_sdd.py.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**,
  docs/**, contracts/**, and all wave-1..wave-5 test files (byte-identical).

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in the
  session checkpoint /tmp/opencode/398-w6/checkpoint.md: resume 24, terminal 24,
  todo 9+19, auth_v1 21+10, camera1_live 19+6, mediamtx 14, cutover 7,
  storage_lifecycle 6, observability 6, manual_install 7, demo 1).
- Cluster: `pytest` over the 11 files (10 cluster + demo) → 138 passed / 35 subtests
  in 3.36s (all 10 files converted in place at 0 count delta; demo +1).
- Full battery: worker-run per the wave-6 work order (`python3 -m pytest tests/ -q
  -p no:cacheprovider --basetemp=/tmp/opencode/398-w6/pytest-tmp`) → OBSERVED 1228
  passed / 2 skipped / 306 subtests in 72.25s (base 1227 / 2 / 306 on 0ab0911,
  orchestrator-observed; identity 1227 + 1 demo).
- `python3 scripts/ci/validate_sdd.py` → informational bare run for the trio after
  the grandfather line (NOT a gate here — the orchestrator runs `--event` mode on
  the fresh commit); expected clean once specs/398-wave6/ exists (strict set
  equality at validate_prefix_uniqueness).
- ruff: `python3 -m ruff check --config scripts/quality/ruff.toml` clean on every
  changed file.
- Allowed-paths check: `git status` shows only the 10 cluster test files + scanner +
  demo, specs/398-wave6/** plus the recorded validate_sdd.py exception.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE change (tests + one validator
  line); runtime acceptance = exact-head CI green on the merge PR.
- RF-002: post-wave cluster reports 138 / 35 (counts flat vs base + demo 1); all
  deltas recorded in the tasks.md battery-delta ledger (retired assertion → covering
  twin, same commit); the coverage became placement-sensitive without new test names.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every
  mapping-table action's focused run green (resume 24, terminal 24, todo 9+19,
  auth_v1 21+10, camera1_live 19+6, mediamtx 14, cutover 7, storage 6,
  observability 6, manual 7); NO-CHANGE records recon-documented
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: cluster
  138/35 (10 files at 0 delta + demo +1); battery-delta ledger in tasks.md maps
  every retired assertion to its recorded twin; full battery observed 1228/2/306
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence:
  tests/test_398_wave6_demo.py — both directions with the documented 2/12
  prose-form verdict split (Direction A) and the six-placement-break run (Direction
  B fails all six twin groups), plus both in-demo inverted-mutation proofs and the
  recorded manual flip-runs
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence:
  full battery observed 1228 passed / 2 skipped / 306 subtests in 72.25s (base
  1227/2/306); validate_sdd informational run clean for the trio (orchestrator
  --event gate after commit)
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git
  status shows only declared paths + the recorded validate_sdd.py grandfather-entry
  exception

## Correct-course check

Course correction CC-1 — Direction-A verdict classes (the wave-4/5 demo letter says
"a semantically-equivalent refactor fails EVERY retired pin"; wave-6 twins are
section-scoped TEXT anchors matching on the retired pin strings — case-insensitive
per the scanner, with the gate/policy tokens enforced EXACT-CASE against the raw
section text after peer review F1 — so the 10 vocabulary pins fail only under
refactors that alter the contract identifiers themselves; the letter is
unsatisfiable for an identifier-preserving refactor without dishonestly mangling
identifiers the contract itself matches on):

- Trigger: NONE (design-level fact discovered in demo recon, pre-implementation).
- Issue impact: NONE — the admitted tests-only scope is unchanged; the demo file was
  already in scope.
- Specification impact: R-3 restated for wave-6 reality: Direction A asserts
  twins-pass + EXACTLY the 2 prose-form pins fail (lowercase canary prose refs —
  twin anchored on the case-insensitive heading; sentence-initial rollback capital —
  twin matches case-insensitively); the vocabulary pins fail only under refactors
  that alter the contract identifiers (case drift now enforced exact-case for
  "MoQ", "CONFIRM_NEW_CAMERA", "one OpenCode rollout scope"); the 10/2 class split
  is documented in the demo module docstring. Direction B unchanged (full spec).
- Plan impact: recorded here and in the Decisions (verdict classes documented, not
  forced).
- Tasks impact: T-12 evidence records the class split + probe + flip-runs; demo
  count unchanged (1 passed).
- Authorization impact: NONE — same admitted scope; deviation FLAGGED to the
  orchestrator in the checkpoint and the final report.
- Follow-up: none — the class split is a permanent property of text-anchor twins;
  future text-twin waves inherit it.

Course correction CC-2 — checkpoint clobbering incident (a replace-style edit of the
session checkpoint once clobbered the unit-4 progress line; repaired from session
context):

- Trigger: NONE
- Issue impact: NONE — session-progress artifact only, not a repository file.
- Specification impact: NONE.
- Plan impact: checkpoint discipline canonized: the wave-6 checkpoint is APPEND-ONLY
  via `cat >>`; existing sections are never edited.
- Tasks impact: all subsequent progress lines appended, never edited.
- Authorization impact: NONE.
- Follow-up: none — append-only canon recorded in the checkpoint discipline.

Course correction CC-3 — wait-replay negation extension (the AGENTS.md wait-replay
twin's negation list initially missed the actual rule-23 negation "without promising
background work"; the twin was extended before landing and all 9 RESUME_ENTRYPOINTS
first-match replay sections verified to carry a listed negation):

- Trigger: NONE
- Issue impact: NONE — twin-fidelity fix; no assertion weakened.
- Specification impact: NONE — R-1 twin fidelity improved.
- Plan impact: Architecture first-match gotcha bullet records the co-marker
  discipline.
- Tasks impact: T-2 note; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — gotcha documented in the checkpoint.

Course correction CC-4 — terminal bundle scoping (the full 7-marker ci-foreground
co-location fails for RELEASE_READINESS_GATE.md + project-manager.md, whose bundle
sections lack "no checkpoint-generation churn"; the twin scoped to the 6-marker
bundle that co-locates in ALL 6 contracts, with churn+foreground staying combined
SP keeps; same pattern: "not a blocker" exists only in 2 of 6 contracts —
remediable-not-blocker twin scoped to those 2, remedi+ci co-location twin for all
6):

- Trigger: NONE
- Issue impact: NONE — twin-fidelity scoping; no assertion weakened (the combined
  pins stay verbatim).
- Specification impact: NONE — R-2 SP justification recorded in-code.
- Plan impact: Architecture gotcha bullet + mapping table record the scoping.
- Tasks impact: T-3 note; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — per-doc vs combined scoping recorded in the checkpoint.

Course correction CC-5 — cutover topology normalization (the camera1_direct_h264_
cutover preamble fenced topology block prefixes continuation lines with "-> "; the
twin normalizes via removeprefix("-> ") instead of asserting raw literals —
orchestrator emergent-fix during unit 7):

- Trigger: NONE
- Issue impact: NONE — twin-fidelity fix; no assertion weakened.
- Specification impact: NONE.
- Plan impact: mapping table row records the normalization.
- Tasks impact: T-8 note; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — normalization documented in the test and the checkpoint.
