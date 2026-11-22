# Spec: #690 — Bounded SSE load baseline

- Issue: #690
- Specification: specs/690-sse-load-baseline/spec.md
- Authorization: wave-5 admission (issue #690), branch
  `agent/wave5-690-692-706`, base `8675eb31b3cfa976b71b174a4b4c172e6b65a295`.
- Related: #692 (water route load), #706 (SSE hardening) share this wave's
  branch; this feature owns only the measurement harness and its SDD.

## Product outcome

Operators need a repeatable answer to "how does the real live-feed SSE path
behave when N readers watch one route at once, and where is the first wall?"
Today the only way to find out is to point artillery at production, which is
neither bounded nor safe. This feature adds one on-demand, stdlib-only CLI
that owns a disposable copy of the real API and measures a frozen workload
against it.

The harness never accepts a target URL. It binds an ephemeral IPv4 loopback
port, boots **one** child Uvicorn worker serving the **real** `api.app.main`
application against a temporary base directory and fixture credentials, and
tears the child down on every exit path. It measures the road route and the
water route **separately** at 1, 10 and 50 simultaneous readers; it never
puts 50 readers per route on the server at the same time. Each level runs
repeated connect-publish-disconnect rounds inside the same child.

What it records (all with the fixed units below): numbered data messages per
second per client and aggregate, missing and duplicate numbered IDs,
publish-start to complete-client-frame latency p50/p95/max, server-process CPU
seconds per wall second, server-side ESTABLISHED sockets at the readiness
barrier and after close (producer and control sockets excluded), response
status plus Content-Type / Cache-Control / X-Accel-Buffering on the actual
response for both alias spellings of both routes, and warmed RSS / open-FD
samples that separate a warm plateau from repeated retained growth.

Explicit boundaries: this is a **measurement tool, not a CI gate**. It is not
wired into any workflow, merge or deploy gate. It does **not** touch
production: it opens no connection except to its own child process on
loopback, and it never reads a real service URL, token or data directory. A
finite run establishes "no leak observed within this workload and tolerance",
never "leak-free". A measured threshold breach is a **valid measurement and a
failed performance criterion**: it is recorded with a linked remediation; the
threshold is never relaxed retroactively.

## Frozen workload (recorded before measurement)

The committed evidence run uses exactly these values. The CLI defaults match
them; overriding a value for investigation produces a non-frozen run and is
not evidence.

| Knob | Frozen value |
|---|---|
| Routes | `road1` and `cam1`, measured **separately** (never 50 per route together) |
| Reader levels | 1, 10, 50 simultaneous readers, one route and one level at a time |
| Rounds per level | 2 warm-up rounds, then 3 measured rounds |
| Round shape | connect N readers → readiness barrier → publish → drain → disconnect |
| Messages per round | 20 numbered synthetic envelopes, fixed schema-valid content |
| Publish interval | 50 ms start-to-start (publish window 950–1000 ms) |
| Publish mode | synchronous, one POST at a time, `t_pub` taken immediately before send |
| Readiness | every reader must have received the initial unnumbered `data: {}` frame before the first POST |
| Reader start timeout | 10 s per reader (connect + headers + initial frame) |
| Reader read timeout | 1 s per blocking read, looped until the round stops |
| Drain timeout | 10 s per round (all readers must receive all 20 ids) |
| POST timeout | 5 s |
| Server start timeout | 20 s |
| Per-level deadline | 120 s |
| Overall harness deadline | 600 s |
| Server | one child `python -m uvicorn api.app.main:app --workers 1` on 127.0.0.1 |
| Server data root | fresh temporary directory, deleted after the run |
| Machine budget | any Linux x86_64 host with ≥ 2 logical CPUs and ≥ 2 GiB free RAM; the budgets below are dimensionless or MiB so they do not assume a specific host |

Recorded evidence host: 22 logical CPUs, ~15.1 GiB RAM, Python 3.14.4,
fastapi 0.162.0, uvicorn 0.54.0, starlette 1.10.0.

The real 100 ms generator poll (`api/app/live_feeds.py`), the real event loop
and the real default thread pool are preserved. The harness must not mock
`time.sleep`, advance the generators serially, or raise the anyio thread
limit; doing so would delete the cost under review.

## Frozen thresholds (recorded before measurement)

Every threshold is evaluated per (route, reader level) cell. Units are stated;
percentiles are nearest-rank over all measured `(reader, message)` latency
samples in the cell.

| ID | Metric | Unit | Threshold |
|---|---|---|---|
| LAT-P50 | publish-start → complete-client-frame | ms | p50 ≤ 150 |
| LAT-P95 | publish-start → complete-client-frame | ms | p95 ≤ 300 |
| LAT-MAX | publish-start → complete-client-frame | ms | max ≤ 1000 |
| DEL-MISS | numbered IDs not received by a reader | count | 0 |
| DEL-DUP | numbered IDs received twice by a reader | count | 0 |
| DEL-COMPLETE | readers that received exactly the 20 published IDs | readers | N (1, 10 or 50) |
| CPU-1/10 | server CPU seconds per wall second | s/s | ≤ 0.50 |
| CPU-50 | server CPU seconds per wall second | s/s | ≤ 2.00 |
| MEM-GROW | final RSS − post-warm-up RSS | MiB | ≤ 32 |
| MEM-SPREAD | max RSS − min RSS over the 3 measured samples | MiB | ≤ 16 |
| FD-RETAIN | open FDs after final disconnect − post-warm-up FDs | count | ≤ 8 |
| SOCK-BARRIER | server-side reader ESTABLISHED sockets at the barrier | count | exactly N |
| SOCK-CLOSE | server-side reader ESTABLISHED sockets after close | count | 0 |
| HDR | status / Content-Type / Cache-Control / X-Accel-Buffering / initial frame on each alias | — | 200; prefix `text/event-stream`; contains `no-cache`; `no`; present |

A level **passes** only if every applicable row passes. The report's
`decision.overall` is PASS only when all six cells pass and the header smoke
passes for all four alias paths. An unexecutable run is recorded as
`NOT EXECUTED — environment lacks <reason>`, never as a pass.

## Metric definitions

- **Numbered delivery**: one SSE event block containing an `id:` line and a
  `data:` line, where the `id` equals a sequence number the harness published
  in that round. The initial unnumbered `data: {}` frame and `: keepalive`
  comments are **not** deliveries.
- **Per-client messages/s**: numbered deliveries received by one reader in one
  round divided by the 1.0 s publish window (all readers are connected before
  the first publish and held until drain, so the window is the same for every
  reader in the cell); the cell reports the mean across its reader-rounds.
- **Aggregate messages/s**: mean per measured round — total numbered
  deliveries across the cell's readers ÷ measured rounds ÷ the 1.0 s publish
  window; it is reported, not threshold-gated (DEL-COMPLETE already gates
  completeness).
- **Latency**: `t_recv − t_pub` in monotonic seconds, where `t_pub` is taken
  immediately before the producer's POST is sent and `t_recv` is taken when
  the reader has parsed the complete event block carrying that `id`.
- **Server CPU**: delta of `/proc/<child-pid>/stat` utime+stime over the
  cell's measured window (first measured publish start → last measured drain
  end), divided by the same monotonic wall span. It is server CPU seconds per
  wall second, i.e. core-equivalents.
- **Server-side sockets**: `/proc/net/tcp` entries in state `01` (ESTABLISHED)
  whose local port is the child's listen port, counted at the barrier and
  after the final close. Reader sockets are identified by the reader client
  local ports returned by `getsockname`; producer and control connections are
  excluded by that set, not by subtraction guesswork. Where `/proc` is
  unavailable the field is reported as `null` with a reason; the run is then
  non-conclusive for socket thresholds.
- **Warm plateau vs retained growth**: RSS and open FDs are sampled once after
  the warm-up rounds and after every measured round. Retained growth is the
  final sample minus the post-warm-up sample; spread is max minus min over the
  measured samples. A finite run bounds observed growth only.

## Response headers (application, not proxy)

The harness records the headers the **application** returned on the actual
SSE response: status, Content-Type, Cache-Control and X-Accel-Buffering. It
smoke-tests each alias spelling separately: `/api/analytics/road1/live/stream`
and `/sea-speed/api/analytics/road1/live/stream`, `/api/cam1/live/stream` and
`/sea-speed/api/cam1/live/stream`. These are application headers; they are
**not** proof about any deployed reverse proxy, edge or CDN. This harness
says nothing about production buffering.

## User scenarios (Gherkin)

```gherkin
Feature: Bounded SSE load baseline

  Rule: The harness owns its server and accepts no target
    Scenario: Boot the real app on an ephemeral loopback port
      Given the repository at base 8675eb31b3cfa976b71b174a4b4c172e6b65a295
      When the harness starts
      Then it binds an ephemeral 127.0.0.1 port itself
      And it starts exactly one child Uvicorn worker serving api.app.main
      And the child uses a temporary base directory and fixture credentials
      And no command-line option can point it at an existing service URL
      And the child is terminated and reaped on every exit path

  Rule: Each route is measured alone at 1, 10 and 50 readers
    Scenario: Measure the road route at 10 readers
      Given the child is ready
      When the harness opens 10 road readers and waits for every initial frame
      And it publishes 20 numbered envelopes at 50 ms intervals
      Then the road route alone carries the measured readers
      And the water route is not opened during that cell

  Rule: Only numbered deliveries count
    Scenario: Initial frame and keepalives are excluded
      Given a reader has received the unnumbered initial data frame
      And the generator emits a keepalive comment while idle
      When the harness counts deliveries
      Then the initial frame and keepalives are not deliveries
      And every counted delivery is a numbered id published in that round

  Rule: A threshold breach is a failed criterion, not a relaxed threshold
    Scenario: p95 latency exceeds 300 ms at 50 readers
      Given the frozen thresholds from this specification
      When the measured p95 is 340 ms
      Then the level is recorded as FAILED
      And the measured value is committed in the results table
      And a linked remediation is recorded
      And the threshold stays 300 ms

  Rule: A run that cannot execute is not a pass
    Scenario: Uvicorn is not installed in the measuring environment
      Given the child cannot boot within the start timeout
      When the harness exits
      Then the evidence table says "NOT EXECUTED — environment lacks uvicorn"
      And no measured numbers are invented
```

## Requirements

- R-1: the harness is `scripts/sse_load_baseline.py`, a stdlib-only on-demand
  CLI; it imports no third-party package and adds no dependency.
- R-2: the harness accepts no target URL; it binds an ephemeral 127.0.0.1 port
  and starts exactly one child Uvicorn worker of the real app.
- R-3: the child's environment uses a fresh temporary `SEA_SPEED_BASE_DIR`, a
  fixture deployed-commit file created before import, fixture credentials and
  no inherited `SEA_SPEED_SOURCE_COMMIT`.
- R-4: road and water are measured separately at 1, 10 and 50 readers; no
  level mixes routes.
- R-5: every wait is bounded (start, read, drain, POST, per-level and overall
  deadlines) and the child is terminated, waited and if necessary killed in a
  `finally` block.
- R-6: real polling and server thread-pool defaults are preserved; `time.sleep`
  is never mocked and generators are never advanced serially.
- R-7: the workload and numeric thresholds of this spec are frozen before the
  evidence run; the CLI defaults reproduce them.
- R-8: deliveries count only numbered `id:`/`data:` events for IDs published in
  the round; the unnumbered initial frame and keepalives are excluded.
- R-9: the report records per-client and aggregate numbered messages/s,
  missing and duplicate IDs, latency p50/p95/max, server CPU seconds per wall
  second, server-side ESTABLISHED sockets at barrier and after close
  (producer/control excluded), and warmed RSS/FO samples.
- R-10: actual response headers (status, Content-Type, Cache-Control,
  X-Accel-Buffering) are recorded for each alias spelling separately, and are
  described as application headers, not proxy proof.
- R-11: `tasks.md` carries one human-reviewed results table with tested SHA,
  platform/CPU allocation, dependency versions, command, workload, thresholds,
  measured rows and decision; raw run output stays outside git.
- R-12: the change touches no production source, test, worker, deploy,
  workflow, lockfile, `scripts/quality/**` or `scripts/ci/**` file.

## Acceptance criteria

- AC-001: disposable isolation — the harness accepts no target URL, binds an
  ephemeral loopback port, boots exactly one child Uvicorn worker of the real
  app with a temporary base directory and fixture credentials created before
  import, and reaps the child on every exit path.
- AC-002: frozen workload and thresholds — spec.md records the workload and
  numeric latency/CPU/memory/FD budgets, units, machine budget and sample
  window before any measurement, and the CLI defaults reproduce it.
- AC-003: metric correctness — per-client and aggregate numbered messages/s,
  missing and duplicate IDs, publish-start to complete-frame latency
  p50/p95/max, server CPU seconds per wall second, server-side ESTABLISHED
  sockets at barrier and after close excluding producer/control, and per-alias
  status plus Content-Type/Cache-Control/X-Accel-Buffering, with the
  unnumbered initial frame and keepalives excluded.
- AC-004: boundedness and fidelity — every wait is bounded, the child is
  reaped on failure and timeout, and the real 100 ms polling plus default
  server thread pool are preserved (no mocked sleep, no serial generator
  advance).
- AC-005: evidence and decision — tasks.md holds one human-reviewed results
  table with tested SHA, platform/CPU allocation, dependency versions, command,
  workload, thresholds, measured rows and PASS/FAIL decision; raw output is
  outside git; a breach is recorded as a failed criterion with a linked
  remediation and no threshold relaxation; an unexecutable run says
  "NOT EXECUTED — environment lacks X".

## NFR assessment

- NFR-001 | Area: Isolation | Target: the harness opens no connection except to its own child on 127.0.0.1, uses one ephemeral port and a temp data root, and accepts no target URL | Validation: source inspection of the option parser and socket targets, plus a run with the child killed mid-cell | Evidence: no URL option exists; all client connections target the child's 127.0.0.1 port; the temp root is removed and the child reaped on normal, failed and interrupted exits | Status: PASS
- NFR-002 | Area: Boundedness | Target: no wait is unbounded; start, read, drain, POST, per-level and overall deadlines are finite and the child is killed if it ignores termination | Validation: source inspection of every blocking call plus a run with a forced drain timeout | Evidence: every socket has an explicit timeout, each level has a 120 s deadline, the overall run has a 600 s deadline, and `finally` performs terminate→wait→kill | Status: PASS
- NFR-003 | Area: Measurement fidelity | Target: only numbered `id:`/`data:` events for IDs published in the round count; the unnumbered initial frame and keepalives never count; missing and duplicate IDs are computed per reader | Validation: run the harness and inspect the per-reader received-id sets against the published-seq set for every cell | Evidence: the results table reports zero missing/duplicate IDs against the 20 published IDs per reader in every passing cell, and the initial/keepalive frames are excluded by parsing | Status: PASS
- NFR-004 | Area: Evidence integrity | Target: thresholds are frozen before measurement; a breach is recorded as a failed criterion with a remediation and never relaxed; an unexecutable run is marked NOT EXECUTED | Validation: compare spec.md thresholds with the tasks.md results table and the report's own threshold echo | Evidence: the tasks.md table carries the same numeric thresholds and the observed rows; the decision field is derived from them | Status: PASS
- NFR-005 | Area: Static quality | Target: the new script and SDD pass the repository's static gates without touching production, tests, deploy, workflow, quality or lockfile paths | Validation: `python3 -m py_compile`, `ruff check --config scripts/quality/ruff.toml`, `python3 scripts/ci/validate_sdd.py`, `git status --short` | Evidence: all three gates pass and only the three new SDD files plus `scripts/sse_load_baseline.py` are added | Status: PASS

## Runtime feedback

- The harness is a measurement tool: it is not a CI gate, not a deploy lane and
  not a production probe. It says nothing about a deployed proxy or CDN.
- A single run is a bounded observation on one host; it is not a capacity
  guarantee and it does not prove the absence of leaks. Repeated retained
  growth is distinguished from a warm plateau only within the measured sample
  window.
- Where the environment cannot boot the child or lacks `/proc`, the affected
  rows are reported as `null`/`NOT EXECUTED` with a reason; no number is
  fabricated.
