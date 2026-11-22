# Spec: #692 — Road/water live-feed validator parity analysis

- Issue: #692
- Specification: specs/692-sse-parity/spec.md
- Authorization: wave-5 bounded documentation work order (issue #692), branch
  `agent/wave5-690-692-706`; admitted base
  `3059b1f2b848bbe5f9564375d990f120c841c909` (orchestrator-reported current
  main after #690; not present in the local clone — see plan.md Validation for
  the observed branch head).
- Related: #690 (bounded SSE load baseline) and #706 (SSE hardening) share this
  branch; this feature owns only the parity analysis and its SDD trio.

This is an **analysis-only** outcome. It changes no runtime behavior, adds no
CI gate, and delivers only `specs/692-sse-parity/{spec,plan,tasks}.md`.

## Product outcome

Issue #692 asks whether the road (`road1`) and water (`cam1`) live-feed
contours are equivalent enough to share one implementation. Both contours have
a producer POST, a live-envelope validator, a bounded ring buffer, a snapshot
GET and sequence-aware SSE stream routes. Their validators are visibly similar
(about 50 lines each, same field order and error strings), and a reader may
reasonably ask "why not one validator?".

The answer this feature must produce is evidence, not code: a complete
stage-by-stage parity map with exact symbols and lines, paired behavioral
probes executed against **both real validator functions**, an explicit
classification of every stage (`identical` / `domain-specific` / `unproven`),
and a decision. The observed answer is:

- the similarity is real and broad — 28 of 30 paired validator probes produce
  the same outcome, and 6 of those differ only in the domain noun inside the
  error message;
- whole-validator equivalence is **false** — road alone guards a non-null
  `crossings` field (`api/app/live_feeds.py:95-96`), and that guard changes
  both the verdict and the first error on multiply-invalid inputs;
- therefore the decision is **KEEP AS-IS**. No generic feed class, no shared
  validator, no counter registry and no handler rewrite are justified by this
  analysis.

What this analysis explicitly is not: it is not a refactor proposal, not a
defect report against either validator, not a runtime change, not a test
change and not a CI gate. The water path accepting a non-object `crossings`
payload is today's documented behavior; changing it would be a production
behavior change outside this analysis-only scope.

## Call graph (observed)

All line numbers are from the admitted tree (`live_feeds.py` unchanged by
#690; `main.py` route block unchanged by #690).

```text
POST /api/analytics/road1/live        main.py:1292-1307  post_road_live
  require_auth                        main.py:1294
  _validate_road_live_envelope        live_feeds.py:54-104
  deepcopy -> ROAD_LIVE_SEQ += 1 -> _live_seq/_received_at -> ROAD_LIVE.append
  return {ok, queued, live_seq}       ROAD_LIVE_LOCK held for counter+append

POST /api/cam1/live                   main.py:1330-1345  post_water_live
  require_auth                        main.py:1332
  _validate_water_live_envelope       live_feeds.py:128-175
  deepcopy -> WATER_LIVE_SEQ += 1 -> _live_seq/_received_at -> WATER_LIVE.append
  return {ok, queued, live_seq}       WATER_LIVE_LOCK held for counter+append

GET /api/analytics/road1/live         main.py:1309-1313  get_road_live
GET /api/cam1/live                    main.py:1346-1350  get_water_live
  max(1, min(limit, *_LIVE_MAX)) then list(*_LIVE)[-lim:]

GET .../road1/live/stream (2 aliases) main.py:1315-1319, 1321-1326
GET .../cam1/live/stream   (2 aliases) main.py:1352-1356, 1358-1362
  with *_LIVE_LOCK: last = *_LIVE_SEQ
  StreamingResponse(_*_live_stream_gen(last), text/event-stream,
                    Cache-Control: no-cache, X-Accel-Buffering: no)

generators                            live_feeds.py:107-121 / 178-192
  yield "data: {}\n\n"; then per 0.1 s: newer retained ids as
  "id: <seq>\ndata: <json>\n\n" or ": keepalive\n\n"
```

State: `ROAD_LIVE` / `WATER_LIVE` are independent `deque(maxlen=120)` rings
with independent `threading.Lock` objects (`live_feeds.py:50-52`,
`124-126`). The counters `ROAD_LIVE_SEQ` / `WATER_LIVE_SEQ` intentionally stay
in `main.py` (`:1290`, `:1328`): the staying route handlers mutate them through
`global`, and moving them into `live_feeds.py` would fork the counter per
module namespace (documented at `live_feeds.py:11-21`).

## Parity matrix

Classification legend:

- `identical` — the same input produces the same outcome, status and detail
  (domain nouns such as `road1`/`cam1` excluded) in both validators, or the
  same source text with only domain symbols renamed.
- `domain-specific` — an intended per-contour difference that changes what is
  accepted or rejected, not merely a domain noun inside a message.
- `unproven` — source-inspected only; not executed against a live route in this
  analysis (no route boot, no concurrency run).

The `test or probe` column names the executed paired probe (P01-P33, evidence
in `tasks.md`) or marks the evidence as source inspection.

| stage/input | road symbol + lines | water symbol + lines | observable result or first error | identical / domain-specific / unproven | test or probe |
|---|---|---|---|---|---|
| Producer POST: auth before validation | `post_road_live` `main.py:1293-1295` | `post_water_live` `main.py:1331-1333` | `require_auth` runs first; a bad token fails before any envelope check | unproven | source inspection; route not booted (app needs /opt state) |
| Producer POST: envelope validation | delegates to road validator `main.py:1295` | delegates to water validator `main.py:1333` | pure delegation: the POST failure path equals the validator outcome for every row below, including the inherited crossings divergence; no extra POST-level check | identical | P01-P30 via the validators |
| Producer POST: deep-copy, sequence, receipt, append, return | `main.py:1296-1307` | `main.py:1334-1345` | same order: deepcopy, counter increment under the ring lock, `_live_seq`, `_received_at`, append, `{ok,queued,live_seq}` | unproven | source inspection; route not booted |
| Validation: non-object envelope | `live_feeds.py:55-56` | `live_feeds.py:129-130` | 400 `live envelope must be object` | identical | P27 |
| Validation: schema v1 and v2 accepted | `live_feeds.py:57-58` | `live_feeds.py:131-132` | both v1 and v2 envelopes accepted | identical | P01, P02 |
| Validation: missing/unknown schema | `live_feeds.py:57-58` | `live_feeds.py:131-132` | 400 `schema must be sea_speed_road_live_v1/v2` vs `...water...` (same status, domain noun differs) | identical | P03 |
| Validation: camera/profile/domain identity | `live_feeds.py:59-64` | `live_feeds.py:133-138` | 400 on the first identity field with the road/water literal (`road1`/`cam1`, `road-v1`/`water-v1`, `road`/`water`) | identical | P04, P05, P06 |
| Validation: integer frame fields | `live_feeds.py:65-67` | `live_feeds.py:139-141` | 400 `frame_no must be int` / `frame_width must be int` | identical | P07, P08 |
| Validation: v2 integer timing + semantics | `live_feeds.py:69-74` | `live_feeds.py:142-147` | 400 `capture_time_unix_ms must be int`; 400 `timestamp_semantics must be worker_receive_utc` | identical | P09, P10 |
| Validation: v1 `observed_mono` numeric | `live_feeds.py:75-77` | `live_feeds.py:148-150` | 400 `observed_mono must be number` for a string | identical | P11 |
| Validation: `detections` is a list | `live_feeds.py:78-80` | `live_feeds.py:151-153` | 400 `detections must be list` | identical | P12 |
| Validation: 64-detection boundary | `live_feeds.py:81-82` | `live_feeds.py:154-155` | 64 accepted; 65 rejected with 400 `too many detections` | identical | P13, P14 |
| Validation: detection entry is an object | `live_feeds.py:83-85` | `live_feeds.py:156-158` | 400 `detection must be object` | identical | P15 |
| Validation: coordinate range/type | `live_feeds.py:86-89` | `live_feeds.py:159-162` | 400 `x2_norm must be 0..1` for 1.5; 400 `x1_norm must be 0..1` for a string | identical | P16, P17 |
| Validation: degenerate/inverted box | `live_feeds.py:90-94` | `live_feeds.py:163-167` | 400 `invalid box` when `x2<=x1` or `y2<=y1` | identical | P18, P19 |
| Validation: non-null `crossings` must be a dict | `live_feeds.py:95-96` | absent | road: 400 `crossings must be object`; water: accepted | domain-specific | P20 |
| Validation: `crossings` object or null/absent | same guard is skipped for dict/None | no guard | both accepted | identical | P21, P22 |
| Validation: serialization failure | `live_feeds.py:98-101` | `live_feeds.py:169-172` | both 400 `invalid json` for a set value (aligned by #470) | identical | P23; pinned in `tests/test_live_envelope_validators.py` |
| Validation: size limit boundary | `live_feeds.py:102-103` | `live_feeds.py:173-174` | 65536 serialized chars accepted; 65537 rejected with 400 `payload too large` | identical | P24, P25 |
| Validation: size limit unit | same | same | 40000 `é` (80000 UTF-8 bytes) accepted — the limit is characters, not bytes | identical | P26 |
| Validation: first error on multiply-invalid input (schema first) | `live_feeds.py:57` before detections/crossings | `live_feeds.py:131` before detections | both report the schema error first | identical | P28 |
| Validation: precedence, bad crossings vs serialization | `live_feeds.py:95-96` before `:98` | no crossings check, proceeds to `:169` | road 400 `crossings must be object`; water 400 `invalid json` | domain-specific | P29 |
| Validation: precedence, bad camera vs serialization | `live_feeds.py:59-60` before `:98` | `live_feeds.py:133-134` before `:169` | both report the camera error first (domain noun only) | identical | P30 |
| Snapshot GET: clamp/slice/response shape | `get_road_live` `main.py:1309-1313` | `get_water_live` `main.py:1346-1350` | same `max(1,min(limit,120))` and last-N slice; response differs only by the `camera_id` literal | unproven | source inspection; route not booted |
| Stream GET: capture current sequence | `main.py:1315-1319`, `1321-1326` | `main.py:1352-1356`, `1358-1362` | same lock-guarded `last = *_LIVE_SEQ`, same media type and headers | identical | source inspection + #690 header smoke evidence |
| Stream framing: initial frame, ids, keepalive | `_road_live_stream_gen` `live_feeds.py:107-121` | `_water_live_stream_gen` `live_feeds.py:178-192` | both start `data: {}`, then `id: <seq>\ndata: <json>`, else `: keepalive`; both sleep 0.1 s | identical | P31 |
| Stream start: no replay from zero | `live_feeds.py:110-115` (cursor = passed `last_seq`) | `live_feeds.py:181-186` | cursor equal to newest retained seq yields a keepalive, not a replay | identical | P33 |
| Counters: per-camera sequence | `ROAD_LIVE_SEQ` `main.py:1290`, incremented `:1301` | `WATER_LIVE_SEQ` `main.py:1328`, incremented `:1338` | same semantics; independent integer per camera in the route module | unproven | source inspection; concurrency not probed |
| Locks: ring buffer mutual exclusion | `ROAD_LIVE_LOCK` `live_feeds.py:52` | `WATER_LIVE_LOCK` `live_feeds.py:126` | independent `threading.Lock` instances; same append/iterate discipline | unproven | source inspection; concurrency not probed |

### Structural diff result

After normalizing domain nouns (`road1`/`cam1`, `road-v1`/`water-v1`,
`road`/`water`, schema strings and function names), the diff of the two real
validator sources contains exactly one comment line and the two-line crossings
guard:

```text
-    # v2 timing contract          (comment present only in the road function)
-    if payload.get("crossings") is not None and not isinstance(payload.get("crossings"), dict):
-        raise HTTPException(status_code=400, detail="crossings must be object")
```

Everything else in the validators is structurally the same. The generator
normalized diff is empty apart from the lock constant and symbol names (P31,
P33).

## User scenarios (Gherkin)

```gherkin
Feature: Road and water live-feed parity

  Rule: Valid v1 and v2 envelopes are accepted by both validators
    Scenario: A minimal valid v1 envelope
      Given a road v1 envelope with road1 / road-v1 / road and one valid box
      And a water v1 envelope with cam1 / water-v1 / water and one valid box
      When each envelope is passed to its own real validator
      Then both validators return the payload unchanged

    Scenario: A minimal valid v2 envelope
      Given a v2 envelope with integer capture/processed times and worker_receive_utc
      When each envelope is passed to its own real validator
      Then both validators return the payload unchanged

  Rule: Identity fields are enforced per contour
    Scenario: A road envelope sent to the water validator
      Given a valid road envelope
      When it is passed to the water validator
      Then it fails with 400 and the water camera_id message
      And the road validator would instead fail a water envelope on camera_id

  Rule: Structural checks are identical
    Scenario: The 64-detection boundary
      Given 64 valid detections
      When either validator validates the envelope
      Then both accept
      And 65 detections make both return 400 "too many detections"

    Scenario: The size limit counts characters, not bytes
      Given a payload whose serialized form is 65536 characters
      When either validator validates it
      Then both accept
      And 65537 characters make both return 400 "payload too large"
      And a payload under 65536 characters but over 65536 UTF-8 bytes is accepted by both

  Rule: The road-only crossings guard is a real divergence
    Scenario: A non-object crossings field
      Given a road envelope whose crossings is a list
      When the road validator validates it
      Then it fails with 400 "crossings must be object"
      And the water validator accepts the same shape because water has no crossings guard

  Rule: Multiply-invalid inputs fail on the same first error, except across the crossings guard
    Scenario: Schema and detections are both wrong
      Given an envelope with an unknown schema and non-list detections
      When either validator validates it
      Then both report the schema error first

    Scenario: Crossings and serialization are both invalid
      Given a road envelope with a list crossings and a non-serializable value
      When the road validator validates it
      Then it reports "crossings must be object"
      And the water validator reports "invalid json" instead

  Rule: A stream does not replay history when it starts at the current sequence
    Scenario: Cursor equals the newest retained sequence
      Given one retained envelope with _live_seq 5
      When a generator is started with last_seq 5
      Then the first frame is data: {} and the next frame is a keepalive
      And the road and water generators behave the same

  Rule: Similarity is not equivalence
    Scenario: Someone proposes one shared validator
      Given the parity matrix and the paired probe results
      When the proposal would merge the two validators
      Then the crossings divergence and the domain-noun behavior must be resolved first
      And without that resolution the decision remains keep-as-is
```

## Requirements

- R-1: record a full call graph for producer POST, validation, storage,
  snapshot GET and both stream alias pairs, with symbols and exact lines.
- R-2: record a parity matrix covering producer POST, every validator stage
  (v1/v2, integer checks, 64-detection boundary, coordinates, degenerate boxes,
  serialization failure, size limit, road-only crossings), snapshot/stream GET,
  framing/headers, counters and locks, each classified `identical` /
  `domain-specific` / `unproven` with its evidence.
- R-3: execute paired probes against **both real validator functions** with
  the same input and record exact observed outcomes; if a probe cannot run,
  record `NOT EXECUTED — <reason>` and never fabricate a result.
- R-4: record Gherkin scenarios for the parity claims, the crossings
  divergence, the multi-error precedence split, the character-based size limit
  and the no-replay stream start.
- R-5: state the decision explicitly as **keep-as-is**, with the rationale and
  the bar that a future extraction must clear before it can be considered.
- R-6: state the analysis-only boundary: no runtime change, no refactor, no CI
  gate, no test/script/worker/deploy/workflow/lockfile change.
- R-7: the only changed files are the three files under
  `specs/692-sse-parity/`.
- R-8: record the verification commands and their observed output, including
  `python3 scripts/ci/validate_sdd.py` and `git status --short` /
  `git diff --stat`.

## Acceptance criteria

- AC-001: the call graph and the full parity matrix are present with exact
  symbols/lines, the required stage coverage, observed result or first error,
  a classification, and the test or probe that supports it.
- AC-002: `tasks.md` contains a real observed-results table from paired probes
  executed against both real validator functions, with exact inputs and
  observed outputs; any unexecutable probe is marked
  `NOT EXECUTED — <reason>`.
- AC-003: `spec.md` contains Gherkin scenarios for the parity claims, the
  crossings divergence, multi-error precedence, the character-based size limit
  and the no-replay stream start.
- AC-004: an explicit keep-as-is decision is recorded with its rationale and
  the bar for any future extraction.
- AC-005: the analysis-only boundary is recorded: no production code, test,
  script, worker, deploy, workflow or lockfile change; no runtime change; no CI
  gate.
- AC-006: verification is recorded: `python3 scripts/ci/validate_sdd.py` passes
  and `git status --short` / `git diff --stat` show only the three new
  `specs/692-sse-parity/` files.

## NFR assessment

- NFR-001 | Area: Evidence accuracy | Target: every parity claim is backed by an executed paired probe or is explicitly classified `unproven`; no claim of equivalence is made from source similarity alone | Validation: run the scratch probe against both real validator functions and compare the observed outcome, status and detail per case; compare the normalized source diff | Evidence: 30 validator cases executed (28 structurally identical, 6 differing only by domain noun, 2 behaviorally different at the crossings guard) plus 2 generator probes; the classifications in the matrix match probe P01-P33 | Status: PASS
- NFR-002 | Area: No fabrication | Target: results not executed are labelled, never guessed; a probe that cannot run says NOT EXECUTED with a reason | Validation: cross-check every matrix row against a probe id or an explicit source-inspection note | Evidence: every `identical`/`domain-specific` validation row maps to a probe; route-level POST/GET and concurrency rows are marked `unproven` with the reason | Status: PASS
- NFR-003 | Area: Scope discipline | Target: documentation only — no runtime, test, script, deploy, workflow or lockfile change | Validation: `git status --short` and `git diff --stat` after writing | Evidence: exactly three new files under `specs/692-sse-parity/`; no other path touched | Status: PASS
- NFR-004 | Area: Reproducibility | Target: the probe is a fixed, inspectable script run against the admitted tree, and the recorded inputs/outputs can be re-derived | Validation: rerun `/tmp/opencode/692-parity/probe.py <repo>` and compare stdout JSON lines with the recorded table | Evidence: deterministic in-process probe, no network, no /opt state; the script stays outside git under `/tmp/opencode/692-parity/` | Status: PASS
- NFR-005 | Area: SDD validity | Target: the trio passes the repository SDD validator | Validation: `python3 scripts/ci/validate_sdd.py` | Evidence: validator exits 0 and prints its pass line; the three files carry the required sections and traceability | Status: PASS

## Runtime feedback

- This analysis boots no API and opens no socket. Probes import
  `api/app/live_feeds.py` direct-file in a scratch process and call the two
  real functions; ring/generator probes mutate only that scratch process's
  module state and are cleared afterwards.
- Route-level POST/GET execution and concurrent counter/lock behavior are not
  exercised; those rows are `unproven` rather than assumed. Existing runtime
  header evidence from the #690 evidence run (both routes, both alias
  spellings: 200, `text/event-stream`, `no-cache`, `no`, initial frame) is
  cited as prior observation, not re-run here.
- The analysis says nothing about a deployed reverse proxy or CDN, and it does
  not change production behavior. The water path's acceptance of a non-object
  `crossings` field remains today's behavior until a separate, scoped change
  decides otherwise.
