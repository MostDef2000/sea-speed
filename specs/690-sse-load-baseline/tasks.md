# Tasks: #690 — Bounded SSE load baseline

- Spec: specs/690-sse-load-baseline/spec.md
- Plan: specs/690-sse-load-baseline/plan.md
- Issue: #690

## Delivery tasks

- [x] Frozen workload and numeric thresholds recorded in `specs/690-sse-load-baseline/spec.md` **before** measurement: road and water measured separately at 1/10/50 readers; 2 warm-up + 3 measured connect-publish-disconnect rounds per cell; 20 numbered envelopes at 50 ms (1.0 s publish window); start/read/drain/POST/server-start/level/overall timeouts; latency, CPU, RSS, FD and socket budgets with units, machine budget and sample window
- [x] New stdlib-only on-demand CLI `scripts/sse_load_baseline.py`; imports only the standard library; adds no dependency and is not in unittest discovery
- [x] Disposable isolation: binds an ephemeral `127.0.0.1` port, starts exactly one in-process Uvicorn worker of the real `api.app.main` app with `--workers 1`, a fresh temporary `SEA_SPEED_BASE_DIR` and a fixture deployed-commit file written before import; no target-URL option exists and a URL-shaped argument is rejected
- [x] Fixture child environment: `SEA_SPEED_API_TOKEN` / `SEA_SPEED_EDGE_AUTH_SECRET` / `SEA_SPEED_ADMIN_USERS` / `SEA_SPEED_WORKER_CONTROL_TOKEN` set to disposable low-entropy values, `SEA_SPEED_WORKER_CONTROL_URL` loopback, `SEA_SPEED_SOURCE_COMMIT` removed
- [x] Route isolation: road and water run as separate cells at each reader level; the harness never opens 50 readers per route while the other route carries load
- [x] Real fidelity preserved: the 100 ms generator poll and the server's default thread pool are untouched (no mocked `time.sleep`, no serial generator advance, no thread-limiter change)
- [x] Delivery accounting: only numbered `id:`/`data:` events for IDs published in the round count; the unnumbered initial `data: {}` frame and `: keepalive` comments are excluded; per-reader missing and duplicate IDs are computed against the published sequence set
- [x] Metrics recorded with units: per-client and aggregate numbered messages/s, publish-start→complete-frame latency p50/p95/max (nearest-rank, ms), server CPU seconds per wall second from `/proc/<pid>/stat`, server-side ESTABLISHED reader sockets at barrier and after close via `/proc/net/tcp` (producer/control excluded by reader client port), warmed RSS MiB and open-FD plateau/growth samples
- [x] Response headers recorded on actual responses for both alias spellings of both routes: status, Content-Type, Cache-Control, X-Accel-Buffering, initial frame; described as application headers, not proxy proof
- [x] Boundedness: every blocking read/POST/start/drain has an explicit timeout, each cell has a 120 s deadline, the run has a 600 s overall deadline, and `finally` performs terminate→wait(10 s)→kill plus temp-directory cleanup
- [x] Static gates on the branch: `python3 -m py_compile scripts/sse_load_baseline.py` passes and `ruff check --config scripts/quality/ruff.toml scripts/sse_load_baseline.py` passes
- [x] SDD trio written: spec.md (what/why, frozen workload + thresholds, metrics, Gherkin, measurement-not-gate boundary, NFRs), plan.md (lifecycle, determinism/boundedness, decisions, risk/test design, correct-course check), tasks.md (this file)
- [x] One human-reviewed results table committed below from a real frozen run with tested SHA, platform/CPU allocation, dependency versions, command, workload, thresholds, measured rows and decision (all six cells and all four alias smokes PASS; exit code 0)
- [ ] PR Change Contract declares `Production impact: NONE`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: NOT REQUIRED`, `Production safety envelope: NOT REQUIRED`, `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: NOT APPLICABLE`, `Operator actions expected: 0`, plus `Risk profile: NOT REQUIRED` and `Specification: specs/690-sse-load-baseline/spec.md`
- [ ] Exact-head CI on the PR is green, including the SDD validator for this trio, the repo/contracts/quality validators and ruff
- [ ] Exact-green-head merge of the PR to main, with no deploy lane and no runtime acceptance for this measurement tool

## Completion gate

- The delivered-file scope is exactly `scripts/sse_load_baseline.py`,
  `specs/690-sse-load-baseline/spec.md`, `specs/690-sse-load-baseline/plan.md`
  and `specs/690-sse-load-baseline/tasks.md`; no test, production, deploy,
  workflow, lockfile, `scripts/quality/**` or `scripts/ci/**` change.
- The harness is stdlib-only, accepts no target URL, and opens no connection
  except to its own child on loopback plus `/proc` reads.
- The child is one in-process Uvicorn worker of the real app with a temporary
  base directory and fixture credentials created before import, and it is
  terminated, waited and if necessary killed on every exit path.
- The frozen workload and thresholds in `spec.md` were recorded before the
  evidence run; the results table below reproduces one real run and moves no
  threshold.
- A threshold breach, if any, is recorded as a FAILED criterion with a linked
  remediation; an unexecutable run is recorded as `NOT EXECUTED — <reason>`
  and never replaced by invented numbers.
- Raw run output is not in git; it lives under `/tmp/opencode/690-baseline/`.
- The test worker owns `tests/**`; this delivery records the test design and
  the observed runtime evidence, and no test file is modified here.

## Evidence — frozen baseline run (issue #690)

**Command**

```text
python3 scripts/sse_load_baseline.py \
  --output /tmp/opencode/690-baseline/report.json \
  --tested-sha 8675eb31b3cfa976b71b174a4b4c172e6b65a295
```

**Tested source:** `8675eb31b3cfa976b71b174a4b4c172e6b65a295` (admitted base;
`api/**` is unchanged by this work, so this SHA is the application source the
child served). The harness file itself is uncommitted at run time.

**Workload (frozen, from spec.md):** road1 and cam1 measured separately; 1, 10
and 50 simultaneous readers; 2 warm-up + 3 measured rounds per cell; 20
numbered synthetic envelopes per round at 50 ms start-to-start (1.0 s publish
window); readiness barrier before the first POST; real 100 ms poll and default
thread pool preserved.

**Thresholds (frozen, from spec.md, never moved):** p50 ≤ 150 ms, p95 ≤ 300 ms,
max ≤ 1000 ms; missing = 0, duplicates = 0, every reader complete; CPU ≤ 0.50
s/s at 1 and 10 readers, ≤ 2.00 s/s at 50; RSS retained growth ≤ 32 MiB, RSS
spread ≤ 16 MiB; FD retained growth ≤ 8; server-side reader ESTABLISHED
sockets = N at the barrier and 0 after close; status 200, Content-Type prefix
`text/event-stream`, Cache-Control contains `no-cache`, X-Accel-Buffering `no`,
initial frame present on each alias.

**Raw output:** `/tmp/opencode/690-baseline/report.json` and
`/tmp/opencode/690-baseline/frozen-run.log` (outside git).

<!-- RESULTS_TABLE_START -->
**Platform / CPU allocation:** Linux `x86_64`, 22 logical CPUs, 15 496.8 MiB
total RAM; Python 3.14.4; fastapi 0.162.0; uvicorn 0.54.0; starlette 1.10.0.
One in-process Uvicorn worker (single child) on an ephemeral `127.0.0.1` port;
the harness and its readers ran on the same host.

**Run:** 2 warm-up + 3 measured rounds per cell; 20 numbered envelopes per
round at 50 ms (1.0 s window); measured window per cell = 3 rounds.

| Route | Readers | p50 ms | p95 ms | max ms | miss | dup | complete reader-rounds | agg msg/s | per-client msg/s | CPU s/s | post-warm-up RSS MiB | RSS growth MiB | RSS spread MiB | FD growth | sockets barrier (reader/total) | sockets after close | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| road1 | 1 | 52.922 | 100.702 | 103.450 | 0 | 0 | 3/3 | 20.0 | 20.0 | 0.0455 | 56.34 | 0.17 | 0.11 | 0 | 1/1 | 0 | PASS |
| road1 | 10 | 55.876 | 101.909 | 105.569 | 0 | 0 | 30/30 | 200.0 | 20.0 | 0.0916 | 57.78 | 0.23 | 0.16 | 0 | 10/10 | 0 | PASS |
| road1 | 50 | 79.587 | 148.034 | 206.810 | 0 | 0 | 150/150 | 1000.0 | 20.0 | 0.2606 | 60.21 | 0.38 | 0.18 | 0 | 50/50 | 0 | PASS |
| cam1 | 1 | 52.867 | 100.233 | 102.656 | 0 | 0 | 3/3 | 20.0 | 20.0 | 0.0520 | 60.62 | 0.02 | 0.01 | 0 | 1/1 | 0 | PASS |
| cam1 | 10 | 56.375 | 102.330 | 107.759 | 0 | 0 | 30/30 | 200.0 | 20.0 | 0.0890 | 60.71 | -0.14 | 0.14 | 0 | 10/10 | 0 | PASS |
| cam1 | 50 | 80.725 | 165.152 | 209.476 | 0 | 0 | 150/150 | 1000.0 | 20.0 | 0.2295 | 60.95 | 0.43 | 0.35 | 0 | 50/50 | 0 | PASS |

**Header smoke (each alias spelling opened separately, actual response):**

| Route | Alias path | Status | Content-Type | Cache-Control | X-Accel-Buffering | Initial frame |
|---|---|---|---|---|---|---|
| road1 | `/api/analytics/road1/live/stream` | 200 | `text/event-stream; charset=utf-8` | `no-cache` | `no` | present |
| road1 | `/sea-speed/api/analytics/road1/live/stream` | 200 | `text/event-stream; charset=utf-8` | `no-cache` | `no` | present |
| cam1 | `/api/cam1/live/stream` | 200 | `text/event-stream; charset=utf-8` | `no-cache` | `no` | present |
| cam1 | `/sea-speed/api/cam1/live/stream` | 200 | `text/event-stream; charset=utf-8` | `no-cache` | `no` | present |

**Decision: PASS.** Every one of the six cells passed every frozen threshold
(LAT-P50 ≤ 150 ms, LAT-P95 ≤ 300 ms, LAT-MAX ≤ 1000 ms, DEL-MISS = 0,
DEL-DUP = 0, DEL-COMPLETE = N per round, CPU ≤ 0.50 s/s at 1/10 and ≤ 2.00 s/s
at 50, MEM-GROW ≤ 32 MiB, MEM-SPREAD ≤ 16 MiB, FD-RETAIN ≤ 8, SOCK-BARRIER =
N, SOCK-CLOSE = 0), and all four alias smokes passed. There is no threshold
breach, so no remediation item is linked from this run.

**Observations within the frozen workload:**

- Latency tracks the real 100 ms generator poll almost exactly: p50 ≈ 53 ms at
  1 reader, p95 ≈ 100 ms at 1–10 readers, and p95 rises to ≈ 148–165 ms with
  max ≈ 207–209 ms at 50 readers on one route, i.e. the default thread pool
  and the poll interval are the dominant terms, as expected. The 50-reader
  cells still delivered every numbered message with zero missing/duplicate.
- CPU stays well under budget: ≤ 0.052 s/s at 1 reader and ≤ 0.261 s/s at 50
  readers (≈ 0.26 of one core at the highest level on this host).
- Memory shows a warm plateau, not retained growth: RSS moved by ≤ 0.43 MiB
  from the post-warm-up sample, spread ≤ 0.35 MiB across the three measured
  samples (`cam1/10` shows −0.14 MiB, i.e. allocator noise). Open FDs were
  constant at 7 across every sample of every cell.
- Server-side reader ESTABLISHED sockets equalled the reader count at every
  barrier and returned to 0 after each close; producer/control sockets never
  appeared in the reader-identified count.
- Scope of the claim: a finite run establishes "no leak observed within this
  workload and tolerance", not "leak-free"; the header rows are the
  application's response headers, not evidence about a deployed proxy.
<!-- RESULTS_TABLE_END -->

## Requirements traceability

- AC-001 | Task: disposable isolation — no target URL, ephemeral loopback port, exactly one in-process Uvicorn child of the real app with temp base dir and fixture credentials created before import, reaped on every exit path | Evidence: `scripts/sse_load_baseline.py` option parser rejects URL-shaped arguments and exposes no host option; the child is `[sys.executable, "-m", "uvicorn", "api.app.main:app", "--workers", "1"]` with the fixture env; `finally` runs terminate→wait→kill and removes the temp root; observed runs boot and exit with no orphan | Coverage: COVERED
- AC-002 | Task: frozen workload and thresholds recorded before measurement, with units, machine budget and sample window, and reproduced by CLI defaults | Evidence: spec.md sections Frozen workload and Frozen thresholds; the report echoes `workload` and `thresholds`; the frozen-run table below records the same values; CLI defaults are 2 warm-up + 3 rounds, 20 messages, 50 ms, readers 1,10,50 | Coverage: COVERED
- AC-003 | Task: metric correctness — per-client/aggregate numbered messages/s, missing/duplicate IDs, latency p50/p95/max, server CPU s/s, server-side ESTABLISHED sockets at barrier/after close excluding producer/control, per-alias headers, with the unnumbered frame and keepalives excluded | Evidence: the parser classifies `initial`/`keepalive`/`delivery` and only numbered IDs enter delivery counts; the frozen-run rows below report each metric; smoke rows record both alias spellings of both routes with status and headers | Coverage: COVERED
- AC-004 | Task: boundedness and fidelity — every wait bounded, child reaped on failure/timeout, real polling and default thread pool preserved | Evidence: explicit socket/POST/start/drain timeouts, 120 s per-cell and 600 s overall deadlines; no `time.sleep` mock and no limiter change in the source; the observed run completed under its deadlines and left no `uvicorn api.app.main:app` process | Coverage: COVERED
- AC-005 | Task: evidence and decision — one human-reviewed results table with tested SHA, platform/CPU allocation, dependency versions, command, workload, thresholds, measured rows and PASS/FAIL; raw output outside git; breach recorded with remediation and no relaxation; unexecutable run marked NOT EXECUTED | Evidence: the Evidence section records the command, tested SHA, workload and thresholds; the table below is transcribed from one real run; raw files stay in `/tmp/opencode/690-baseline/`; breaches, if any, are listed with a remediation pointer | Coverage: COVERED

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
