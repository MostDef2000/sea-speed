# Tasks: #692 — Road/water live-feed validator parity analysis

- Spec: specs/692-sse-parity/spec.md
- Plan: specs/692-sse-parity/plan.md
- Issue: #692

## Delivery tasks

- [x] Reconnaissance spot-check of the work-order context against the tree: `api/app/live_feeds.py` road validator `54-104`, water validator `128-175`, generators `107-121` / `178-192`, rings/locks `50-52` / `124-126`; `api/app/main.py` producer POST `1292-1307` / `1330-1345`, counters `1290` / `1328`, snapshot GET `1309-1313` / `1346-1350`, stream alias pairs `1315-1326` / `1352-1363` — all match the supplied description
- [x] Call graph recorded in `spec.md` for producer POST, validation, storage, snapshot GET, both stream alias pairs and the generators
- [x] Parity matrix recorded in `spec.md` with the required columns and every required stage: producer POST, validation v1/v2, integer checks, 64-detection boundary, coordinates, degenerate boxes, serialization failure, size limit, road-only crossings, snapshot/stream GET, framing/headers, counters and locks
- [x] Paired probe harness written outside git at `/tmp/opencode/692-parity/probe.py`; it loads the real `api/app/live_feeds.py` direct-file (same load style as `tests/test_live_envelope_validators.py`) and runs the same input through **both** real validator functions
- [x] 30 paired validator cases executed (P01-P30), including valid v1/v2, all identity fields, every integer check, the 64/65 boundary, coordinates, degenerate/inverted boxes, crossings, non-serializable payloads, the exact 65536/65537-character boundary, a multibyte character-vs-byte payload and three multi-error precedence cases
- [x] Two generator probes executed (P31, P33): the initial frame, the numbered `id:`/`data:` frame and the keepalive, plus the no-replay behavior when the captured cursor equals the newest retained sequence
- [x] Normalized source diff recorded: after renaming domain nouns, the only structural difference between the two validators is one comment line and the two-line `crossings` guard (`live_feeds.py:95-96`)
- [x] Gherkin scenarios recorded in `spec.md` for valid v1/v2 acceptance, identity enforcement, structural checks, the crossings divergence, multi-error precedence, the character-based size limit and the no-replay stream start
- [x] Keep-as-is decision recorded with its rationale and the bar for any future extraction
- [x] Analysis-only boundary stated: no runtime change, no refactor, no CI gate, no test/script/worker/deploy/workflow/lockfile change
- [x] Static verification: `python3 scripts/ci/validate_sdd.py` passes and `git status --short` / `git diff --stat` show only the three new `specs/692-sse-parity/` files (observed output recorded in `plan.md`)
- [ ] PR creation, exact-head CI and exact-green-head merge belong to the delivery orchestrator; this documentation worker does not commit, push or create a PR

## Completion gate

- The delivered-file scope is exactly `specs/692-sse-parity/spec.md`, `plan.md`
  and `tasks.md`; no production, test, script, worker, deploy, workflow or
  lockfile change.
- `spec.md` carries the call graph, the full parity matrix with symbols/lines
  and evidence, the Gherkin scenarios, the explicit keep-as-is decision and
  the analysis-only boundary.
- `tasks.md` carries a real observed-results table from paired probes executed
  against both real validator functions; no result is fabricated and no
  unexecuted probe is presented as executed.
- The probe harness lives outside git under `/tmp/opencode/692-parity/`; it is
  scratch evidence, not a committed test or gate.
- The recorded verification commands were run on the admitted branch and their
  observed output is in `plan.md`.
- Routes were not booted and concurrency was not exercised; those matrix rows
  are classified `unproven`, not assumed.

## Evidence — paired probe run

**Command**

```text
cd /home/mostdef/vibe/projects/ai-playground/sea-speed
python3 /tmp/opencode/692-parity/probe.py .
```

**Environment:** Python 3.14.4, fastapi 0.162.0; `api/app/live_feeds.py` loaded
direct-file into a scratch process; no server, socket or `/opt` state.

**Tested source:** branch `agent/wave5-690-692-706`, HEAD
`093f3a2d940149be6850ccf18552af3bb9d75b3e` (the #690 commit). The work-order
base `3059b1f2b848bbe5f9564375d990f120c841c909` is absent from the local clone
(`git rev-parse 3059b1f2` → `unknown revision`), so byte identity with that SHA
is unverified here; the validator and route sources match the supplied
description line-for-line. `api/**` is unchanged by the #690 commit.

**Raw output:** `/tmp/opencode/692-parity/probe-results.jsonl` (outside git).

### Paired validator results (same input through both real functions)

A "valid envelope" is the minimal shape that passes its own validator:
road = `sea_speed_road_live_v1`, `road1`, `road-v1`, `road`,
`frame_no/generation/frame_width/frame_height = 7/0/1920/1080`,
`observed_mono = 123.5`, one box `(0.1, 0.1, 0.2, 0.2)`; water is the same
with `sea_speed_water_live_v1`, `cam1`, `water-v1`, `water`. `v2` replaces
`observed_mono` with `capture_time_unix_ms = 1700000000000`,
`processed_time_unix_ms = 1700000000010`, `timestamp_semantics =
worker_receive_utc` and changes the schema string only.

| Probe | Input (delta from its own valid v1/v2 envelope) | Road observed | Water observed | Verdict |
|---|---|---|---|---|
| P01 | none (valid v1) | OK (payload returned) | OK (payload returned) | identical |
| P02 | none (valid v2) | OK | OK | identical |
| P03 | `schema = None` | 400 `schema must be sea_speed_road_live_v1/v2` | 400 `schema must be sea_speed_water_live_v1/v2` | identical (domain text) |
| P04 | `camera_id = cam1` (road) / `road1` (water) | 400 `camera_id must be road1` | 400 `camera_id must be cam1` | identical (domain text) |
| P05 | `analytics_profile = water-v1` / `road-v1` | 400 `analytics_profile must be road-v1` | 400 `analytics_profile must be water-v1` | identical (domain text) |
| P06 | `domain = water` / `road` | 400 `domain must be road` | 400 `domain must be water` | identical (domain text) |
| P07 | `frame_no = 7.0` | 400 `frame_no must be int` | 400 `frame_no must be int` | identical |
| P08 | `frame_width = "1920"` | 400 `frame_width must be int` | 400 `frame_width must be int` | identical |
| P09 | v2 `capture_time_unix_ms = None` | 400 `capture_time_unix_ms must be int` | 400 `capture_time_unix_ms must be int` | identical |
| P10 | v2 `timestamp_semantics = camera_clock` | 400 `timestamp_semantics must be worker_receive_utc` | 400 `timestamp_semantics must be worker_receive_utc` | identical |
| P11 | v1 `observed_mono = "123.5"` | 400 `observed_mono must be number` | 400 `observed_mono must be number` | identical |
| P12 | `detections = {}` | 400 `detections must be list` | 400 `detections must be list` | identical |
| P13 | 64 valid detections | OK | OK | identical |
| P14 | 65 valid detections | 400 `too many detections` | 400 `too many detections` | identical |
| P15 | `detections = [1.0]` | 400 `detection must be object` | 400 `detection must be object` | identical |
| P16 | one box `x2_norm = 1.5` | 400 `x2_norm must be 0..1` | 400 `x2_norm must be 0..1` | identical |
| P17 | one box `x1_norm = "0.0"` | 400 `x1_norm must be 0..1` | 400 `x1_norm must be 0..1` | identical |
| P18 | box `x1=x2=0.5` | 400 `invalid box` | 400 `invalid box` | identical |
| P19 | box `y1=0.8, y2=0.2` | 400 `invalid box` | 400 `invalid box` | identical |
| P20 | `crossings = []` | 400 `crossings must be object` | OK | **domain-specific (different)** |
| P21 | `crossings = {"line": 3}` | OK | OK | identical |
| P22 | `crossings` absent | OK | OK | identical |
| P23 | `tags = {"a", "b"}` (set) | 400 `invalid json` | 400 `invalid json` | identical |
| P24 | padded to exactly 65536 serialized characters | OK | OK | identical |
| P25 | padded to 65537 serialized characters | 400 `payload too large` | 400 `payload too large` | identical |
| P26 | `pad = "é" × 40000` (40000 chars, 80000 UTF-8 bytes) | OK | OK | identical (limit is characters) |
| P27 | payload is `[]` | 400 `live envelope must be object` | 400 `live envelope must be object` | identical |
| P28 | `schema = "nope"`, `detections = {}`, `crossings = []` | 400 schema error first | 400 schema error first | identical (schema precedence) |
| P29 | `crossings = []`, `tags = {"a"}` (set) | 400 `crossings must be object` | 400 `invalid json` | **domain-specific (precedence split)** |
| P30 | `camera_id = cam1` / `road1`, `tags = {"a"}` (set) | 400 `camera_id must be road1` | 400 `camera_id must be cam1` | identical (camera precedence) |

**Validator summary:** 30 cases executed; 28 identical (6 of them differ only
in the domain noun inside the message) and 2 domain-specific, both attributable
to the road-only `crossings` guard. The two differing cases are the only
behavioral asymmetry found.

### Generator results

`ROAD_LIVE` / `WATER_LIVE` were seeded with one envelope
`{"schema": "sea_speed_{road,water}_live_v2", "_live_seq": 5, "frame_no": 5}`
and the generators were advanced two frames, then the rings were cleared.

| Probe | Input | Road observed (JSON string) | Water observed (JSON string) | Verdict |
|---|---|---|---|---|
| P31 | `_*_live_stream_gen(0)` with retained seq 5 | first `data: {}\n\n`; second `id: 5\ndata: {"schema": "sea_speed_road_live_v2", "_live_seq": 5, "frame_no": 5}\n\n` | same first frame; second with the water schema string | identical framing |
| P33 | `_*_live_stream_gen(5)` with retained seq 5 | first `data: {}\n\n`; second `: keepalive\n\n` | first `data: {}\n\n`; second `: keepalive\n\n` | identical (no replay) |

### Source-diff result

Normalizing domain nouns in the two real validator sources leaves exactly one
normalized comment line (`# v2 timing contract`) and the road-only block
`if payload.get("crossings") is not None and not isinstance(payload.get("crossings"), dict): raise HTTPException(400, "crossings must be object")`.
No other structural difference was observed.

## Requirements traceability

- AC-001 | Task: call graph plus the full parity matrix with exact symbols/lines, required stage coverage, observed result or first error, classification and evidence | Evidence: spec.md sections Call graph and Parity matrix; every matrix row cites `live_feeds.py`/`main.py` lines and a probe id or an explicit source-inspection note | Coverage: COVERED
- AC-002 | Task: a real observed-results table from paired probes against both real validator functions, with exact inputs and outputs, and no fabricated results | Evidence: the Evidence section above records the command, environment, tested tree, all 30 validator cases and the 2 generator probes from `/tmp/opencode/692-parity/probe-results.jsonl`; unproven route/concurrency rows are labelled in spec.md rather than presented as executed | Coverage: COVERED
- AC-003 | Task: Gherkin scenarios for the parity claims, crossings divergence, multi-error precedence, character-based size limit and no-replay stream start | Evidence: spec.md section User scenarios contains those scenarios as Feature/Rule/Scenario blocks; the observed outcomes they assert match P01-P33 | Coverage: COVERED
- AC-004 | Task: explicit keep-as-is decision with rationale and the extraction bar | Evidence: spec.md Product outcome states KEEP AS-IS; plan.md Decisions records the rationale and the five-part bar (same inputs, returns/identity, mutation, exception status/detail and precedence, paired examples plus a concrete benefit) | Coverage: COVERED
- AC-005 | Task: analysis-only boundary — no production/test/script/worker/deploy/workflow/lockfile change, no runtime change, no CI gate | Evidence: `git status --short` shows only the three new `specs/692-sse-parity/` files; no `api/`, `tests/`, `scripts/`, `worker/`, `deploy/`, `.github/` or lockfile change; the probe lives outside git | Coverage: COVERED
- AC-006 | Task: verification recorded — SDD validator passes and git shows only the three new files | Evidence: plan.md Validation records the observed `python3 scripts/ci/validate_sdd.py` output and the observed `git status --short` / `git diff --stat` output | Coverage: COVERED

## Definition of Done

- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
