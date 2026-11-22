# Plan: #692 — Road/water live-feed validator parity analysis

- Issue: #692
- Specification: specs/692-sse-parity/spec.md

## Architecture

This is a read-only analysis. There is no runtime component, no production
edit and no CI wiring; the only deliverables are this trio.

Method, in the order it was executed:

1. Read the two validators, the two generators, the ring/lock declarations and
   the route block, and record the call graph with exact `file:line` anchors
   (`api/app/live_feeds.py`, `api/app/main.py`).
2. Write a scratch probe outside git at `/tmp/opencode/692-parity/probe.py`.
   It loads the **real** `api/app/live_feeds.py` direct-file with
   `importlib.util.spec_from_file_location` — the same load style used by
   `tests/test_live_envelope_validators.py` — so the functions under test are
   the shipped ones, not copies. `fastapi` is installed in the probe
   environment (0.162.0), so no stub is needed.
3. For each case, pass the same logical input (each contour's own valid
   envelope shape plus one delta) through `_validate_road_live_envelope` and
   `_validate_water_live_envelope`, catch `HTTPException`, and record
   `(outcome, exception type, status, detail)`.
4. Classify: `identical` when outcome/status/detail match modulo the
   per-contour noun; `domain-specific` when the difference changes what is
   accepted or rejected; `unproven` when the only evidence is source
   inspection (route not booted, concurrency not exercised).
5. Produce a normalized source diff with `difflib` after replacing the domain
   nouns (`road1`/`cam1`, `road-v1`/`water-v1`, `road`/`water`, schema strings
   and function names) to show exactly what differs structurally.
6. Probe the generators separately: seed the ring in the scratch process with
   one `_live_seq = 5` envelope, advance each generator two frames with
   `last_seq = 0` (replay) and `last_seq = 5` (no replay), and clear the ring.
7. Transcribe the observed outcomes into `spec.md` (matrix, Gherkin, decision)
   and this trio's evidence; run the repository SDD validator and
   `git status`/`git diff --stat`.

Probe coverage design: 30 validator cases (P01-P30) split across valid v1/v2,
every identity field, all four integer frame fields plus v2 timing and v1
`observed_mono`, the `detections` type and the 64/65 boundary, detection-entry
type, coordinate range/type, degenerate and inverted boxes, `crossings`
non-object/object/absent, non-serializable values, the exact 65536/65537
character boundary, a multibyte chars-vs-bytes payload, a non-dict payload and
three multi-error precedence cases. Two generator cases (P31, P33) cover
framing and no-replay.

## Decisions

- **KEEP AS-IS.** The similarity is real (about 50 lines each, same field
  order and structural checks) but whole-validator equivalence is false: road
  guards a non-null `crossings` field (`live_feeds.py:95-96`) and water does
  not, which changes both the verdict (P20) and the first error on a
  multiply-invalid payload (P29). Merging the validators would either add that
  check to water (water starts rejecting payloads it accepts today) or remove
  it from road (weaker road validation). Both are production behavior changes;
  neither is justified by, or in scope of, an analysis-only issue.
- **Extraction bar (must be cleared before any future refactor).** Any
  extraction of even a small shared block must demonstrate: identical inputs;
  identical return value and object identity behavior; identical mutation;
  identical exception status and detail; identical *precedence* on
  multiply-invalid inputs; paired behavioral examples for road and water; and
  a concrete, measured benefit. The `crossings` divergence must be resolved
  deliberately (a product decision about whether water should reject it)
  before a merged validator can exist.
- **No generic feed class, no shared counter registry, no handler rewrite.**
  The counters intentionally live in `main.py` because the staying route
  handlers mutate them via `global`; moving them into `live_feeds.py` would
  fork the counter per module namespace (`live_feeds.py:11-21`). The stream
  routes are byte-identical apart from symbols and already share the
  generator/service seam; a class would rename state and increase the blast
  radius for no behavioral gain.
- **Probe the real functions, not a paraphrase.** A table derived from reading
  the source would repeat the reader's assumptions; executing both functions
  is the only way to observe precedence and exception detail.
- **Character, not byte, limit is recorded as a finding.** Both validators
  compare `len(json.dumps(...))` (characters), so a payload with 40000 `é`
  (80000 UTF-8 bytes) is accepted. This is identical in both contours and is
  documented as observed behavior; changing it is out of scope.
- **Scratch probe stays outside git.** It is evidence, not a committed test or
  a CI gate; `tests/**` is forbidden to this worker and the #692 outcome is
  documentation only.

## Affected contours

- Repository: three new files under `specs/692-sse-parity/` (spec, plan,
  tasks). No tracked source file changes.
- VPS: NONE. Ubuntu worker/relay: NONE. Windows worker/AI: NONE.
- Public interfaces: NONE — no endpoint, schema or response change; the
  analysis only reads existing code.
- CI interfaces: NONE — no workflow, gate or artifact; `validate_sdd.py` is a
  local verification command, not a new gate.
- Tests: NONE — `tests/**` is explicitly forbidden to this worker.
- Change-control impact: NONE (documentation paths only).

## Validation

**Probe run (executed against both real validators):**

```text
$ cd /home/mostdef/vibe/projects/ai-playground/sea-speed
$ python3 /tmp/opencode/692-parity/probe.py .
... 30 JSON case lines ...
{"id": "P31", ... "road": {"first": "data: {}\n\n", "second": "id: 5\ndata: {...}"}, ...}
{"id": "P33", ... "second": ": keepalive\n\n" ...}
{"id": "SUMMARY", "case_count": 30, "identical": 28, "different": ["P20", "P29"]}
```

Observed: 30 validator cases; 28 identical (6 differing only in the domain
noun in the message); 2 domain-specific (`P20` crossings verdict, `P29`
precedence split). Generator probes P31/P33 identical.

**SDD validator:**

```text
$ python3 scripts/ci/validate_sdd.py
Sea Speed SDD validation passed
exit=0
```

**Scope check:**

```text
$ git status --short
?? specs/692-sse-parity/
$ git diff --stat
(empty — all three files are new/untracked)
$ git ls-files --others --exclude-standard specs/692-sse-parity
specs/692-sse-parity/spec.md
specs/692-sse-parity/plan.md
specs/692-sse-parity/tasks.md
```

**Base observation:** `git rev-parse 3059b1f2` fails with
`fatal: ambiguous argument '3059b1f2': unknown revision`; the branch head is
`093f3a2d940149be6850ccf18552af3bb9d75b3e` (feat #690). The validator and
route sources match the work-order description line-for-line, and `api/**` is
unchanged by #690, but byte identity with the reported base SHA cannot be
proven in this clone.

## Runtime feedback

- No API process is started, no port is opened and no `/opt` state is read.
  Probes run in a scratch process and mutate only that process's module state.
- Route-level POST/GET behavior and concurrent counter/lock behavior are
  `unproven`; the analysis does not claim them from source similarity. The
  #690 evidence run's header observations are cited as prior runtime evidence,
  not re-run here.
- The analysis is not a CI gate and changes nothing in production. The water
  contour's current acceptance of a non-object `crossings` remains until a
  separately scoped change decides otherwise.

## Risk profile

- Risk profile: NOT REQUIRED
- Justification: the change adds three documentation files under `specs/` and
  nothing else. It touches no production runtime, API, test, script, worker,
  deploy path, workflow, schema, secret, migration or lockfile; it adds no
  dependency and starts no service. The probe runs outside git. No security,
  schema, destructive or MIXED trigger applies, and the production impact is
  NONE.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: spec.md Call graph and Parity matrix carry exact symbols/lines and map every stage to a probe id or an explicit source-inspection note; the required stages (producer POST, v1/v2, integer checks, 64 boundary, coordinates, degenerate boxes, serialization, size limit, crossings, snapshot/stream GET, framing/headers, counters/locks) are all present
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: probe run P01-P30 executed the real validators with the recorded inputs and observed outputs; P31/P33 executed the real generators; the tasks.md table is a transcription of `/tmp/opencode/692-parity/probe-results.jsonl`
- TEST-003 | Covers: AC-003 | Level: runtime-manual | Priority: P0 | Evidence: the Gherkin scenarios in spec.md assert exactly the observed probe outcomes (valid v1/v2, 64/65, character limit, crossings split, schema-first precedence, no-replay); manual review confirms each scenario's Then matches a probe id
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: manual review of the KEEP AS-IS decision and the five-part extraction bar in spec.md and this plan; the crossings divergence is named as the blocking fact
- TEST-005 | Covers: AC-005 | Level: runtime-manual | Priority: P0 | Evidence: `git status --short` / `git diff --stat` show only the three new spec files; no forbidden path is staged or modified; the probe file lives under `/tmp/opencode/692-parity/`
- TEST-006 | Covers: AC-006 | Level: runtime-manual | Priority: P0 | Evidence: `python3 scripts/ci/validate_sdd.py` was run and printed its pass line with exit 0; the same command and output are recorded in the Validation section above

## Correct-course check

- Trigger: NONE
- Issue impact: none — the scope matches issue #692 as admitted: a parity analysis of the two live-feed contours plus its SDD trio.
- Specification impact: none — the required stage coverage, evidence standard and keep-as-is decision are recorded as required; no production or test file is changed.
- Plan impact: none — the executed method (paired probes against both real validators, normalized diff, generator probes) follows the admitted plan.
- Tasks impact: none — the evidence table, traceability and scope check are delivered; PR creation, CI and merge remain with the orchestrator.
- Authorization impact: NONE — bounded documentation worker work order from the delivery orchestrator on branch `agent/wave5-690-692-706`; the orchestrator owns the Git lifecycle, PR admission and CI evidence.
- Follow-up: none for this issue. Any future extraction attempt must first clear the five-part bar and resolve the crossings divergence as a separately authorized behavior decision; the character-based size limit and unlocked snapshot reads are recorded observations, not remediation items here.
