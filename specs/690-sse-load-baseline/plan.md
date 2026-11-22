# Plan: #690 — Bounded SSE load baseline

- Issue: #690
- Specification: specs/690-sse-load-baseline/spec.md

## Architecture

One stdlib-only CLI, `scripts/sse_load_baseline.py`, that owns a throwaway
copy of the real API for the duration of a measurement. There is no runtime,
deploy or CI wiring.

Lifecycle:

1. Parse the frozen CLI (`--output` required, `--tested-sha` optional,
   workload knobs defaulted to the values frozen in spec.md). There is no
   `--url`/`--target` option; an unknown option is an error.
2. Create a temporary base directory and write the deployed-commit file into
   it **before** the child imports anything. Build the child environment:
   `SEA_SPEED_BASE_DIR`, `SEA_SPEED_DEPLOYED_COMMIT_FILE`, fixture
   `SEA_SPEED_API_TOKEN` / `SEA_SPEED_EDGE_AUTH_SECRET` /
   `SEA_SPEED_ADMIN_USERS` / `SEA_SPEED_WORKER_CONTROL_TOKEN`, a loopback
   `SEA_SPEED_WORKER_CONTROL_URL`, and `SEA_SPEED_SOURCE_COMMIT` removed.
3. Bind an ephemeral `127.0.0.1` port, close the probe socket, spawn exactly
   one child: `[sys.executable, "-m", "uvicorn", "api.app.main:app",
   "--host", "127.0.0.1", "--port", PORT, "--workers", "1",
   "--log-level", "warning"]` with `cwd` = repository root. `--workers 1`
   makes Uvicorn serve in-process, so the spawned PID is the server whose
   `/proc/<pid>/{stat,status,fd}` the harness samples.
4. Poll `GET /api/health` on the child until 200 or the start timeout. On a
   bind failure (child exits early) retry with a fresh port a bounded number
   of times; on any other early exit, report the captured stderr and stop.
5. Header smoke: open one connection to each of the four alias paths
   separately; record status and Content-Type / Cache-Control /
   X-Accel-Buffering and whether the initial unnumbered frame arrived. Close.
6. For each route in (road, water), for each level in (1, 10, 50):
   - run `warmup_rounds` then `measured_rounds` connect-publish-disconnect
     rounds in the same child;
   - after the warm-up rounds sample RSS and open FDs (post-warm-up baseline);
   - each measured round samples RSS/FDs after drain and counts server-side
     ESTABLISHED reader sockets at the barrier and after close;
   - CPU is sampled at the first measured publish start and the last measured
     drain end of the cell.
7. Compute per-cell metrics, compare with the frozen thresholds, write the
   JSON report to `--output`, print a compact human summary, and exit 0 only
   when every cell and the header smoke pass.
8. `finally`: stop readers, close sockets, `terminate` → bounded `wait` →
   `kill` the child, remove the temporary directory. Re-entry is safe.

Round mechanics (the unit the workload is frozen in):

- The harness opens N reader threads. Each reader does an `http.client`
  `GET` on the route, reads the response headers, then reads events until it
  has consumed the initial unnumbered `data: {}` frame; that is its readiness
  signal. The main thread waits for all N readiness signals (start timeout).
- The main thread publishes 20 fixed, schema-valid envelopes with a
  synchronous POST per message. `t_pub` is `time.monotonic()` taken
  immediately before the POST is sent; the POST response carries `live_seq`,
  which the harness records in a `seq → t_pub` map.
- Readers keep reading after readiness. Each complete event block is parsed:
  an `id:` line plus a `data:` line is a numbered delivery (record `id`,
  `t_recv`); a `data:` block with no `id:` is the initial frame; a line
  starting with `:` is a keepalive. The unnumbered frame and keepalives are
  never counted.
- The main thread waits (drain timeout) until every reader's received-id set
  covers the published seq set, then sets the stop flag, closes the
  connections and joins the threads with a bounded timeout.
- Expected IDs per round are exactly the seqs returned by the 20 POSTs.
  Missing = expected − received; duplicates = ids received more than once.

Metric derivation:

- Per-client messages/s = receiver count per round / 1.0 s publish window,
  mean across the cell's reader-rounds. Aggregate = mean per measured round:
  total received across readers / measured rounds / 1.0 s. Both are reported;
  completeness is the gated property.
- Latency samples are `(seq, t_recv)` per reader joined with the `seq → t_pub`
  map; percentiles are nearest-rank over the cell's pooled samples.
- CPU/core-equivalents = `(Δutime+Δstime)/CLK_TCK / Δmonotonic` over the cell's
  measured window.
- Sockets: parse `/proc/net/tcp`, keep state `01`, local port = child port,
  and count entries whose remote port is in the reader-client-port set (exact
  exclusion of producer/control, which use their own ephemeral ports). Raw
  totals are also reported for context.
- Memory/FD: `/proc/<pid>/status` `VmRSS` (kB → MiB) and
  `len(os.listdir("/proc/<pid>/fd"))`. Retained growth = final − post-warm-up;
  spread = max − min over the measured samples.

Report shape (one JSON object): `contract`, `tested_sha`, `platform`,
`workload`, `thresholds`, `smoke[]`, `results[]` (per route × level with
latency, delivery, throughput, cpu, sockets, memory, fd, verdicts) and
`decision {overall, failures[]}`. The report is measurement output, not a
deterministic artifact; raw runs live outside git (`/tmp/opencode/690-baseline/`).

## Decisions

- **Disposable child, no target URL.** The issue is a *bounded* baseline. A
  URL option would invite production load and make the number meaningless;
  owning the server keeps the measurement hermetic and safe. The process is
  the real app, so the code under review is not stubbed.
- **One Uvicorn worker, in-process.** `--workers 1` runs Uvicorn in the
  spawned process, so `/proc/<pid>` is the true server. A supervisor/worker
  split would silently measure the wrong PID (near-zero CPU).
- **Routes and levels isolated.** 50 readers per route is a different cost
  model from 100 readers across two routes; mixing them would hide which
  route hits the wall. Each cell starts from a freshly connected reader set.
- **Warm-up rounds are not measured.** They absorb first-connection, import,
  JIT-ish and allocator warm-up so the plateau sampling is meaningful; the
  measured rounds are identical in shape (`equal warmed rounds`).
- **Polling and thread pool untouched.** The 100 ms generator poll and the
  anyio default thread limiter (40) are exactly the cost under review.
  Mocking sleep or bumping the limiter would produce a flattering number that
  does not describe the shipped code.
- **Only numbered IDs count.** The initial `data: {}` and keepalives are
  transport scaffolding, not deliveries; counting them would inflate
  throughput and hide missing messages.
- **Reader client ports identify server sockets.** Counting by remote port is
  exact; subtracting "producer and control" by guesswork is not.
- **Frozen thresholds, derived decision.** Thresholds are a data table in the
  spec and in the report; the verdict is computed from them. A breach is a
  failed criterion with a remediation, never a reason to move the line.
- **Raw output outside git.** Reports contain host state and are generated
  output; only the human-reviewed summary table is committed.
- **No test edits here.** A separate test worker owns `tests/**`; this plan
  records the test design/oracles the test worker should pin. The harness is
  under `scripts/`, not `scripts/quality/` (which is CONTROL_PLANE per
  `data/contracts/change-control-policy-v1.json`), and is not in unittest
  discovery.

## Affected contours

- Repository: `scripts/sse_load_baseline.py` (new) and the SDD trio under
  `specs/690-sse-load-baseline/` (new).
- VPS: NONE — no `api/**`, `frontend/**` or `deploy/**` change.
- Ubuntu worker/relay: NONE — no `worker/**` change.
- Windows worker/AI: NONE.
- Public interfaces: NONE — no endpoint, schema or contract change; the
  harness only consumes existing routes.
- CI interfaces: NONE — no workflow, gate or artifact upload.
- Tests: NONE in this scope — `tests/**` belongs to the separate test worker.
- Change-control impact: NONE (top-level `scripts/` is not a CONTROL_PLANE
  pattern; the harness is a developer tool, not a quality/CI gate).
- Explicitly unchanged: production source, all deploy and workflow files, all
  lockfiles, `scripts/quality/**`, `scripts/ci/**` and every existing test.

## Validation

- Static: `python3 -m py_compile scripts/sse_load_baseline.py`,
  `ruff check --config scripts/quality/ruff.toml scripts/sse_load_baseline.py`,
  `python3 scripts/ci/validate_sdd.py`, and `git status --short` showing only
  the four allowed new paths.
- Self-containment oracle: `python3 scripts/sse_load_baseline.py --help`
  parses with no option that names a host or URL, and the only outbound target
  is the child's ephemeral loopback port.
- Lifecycle oracle: a real run boots the child, performs the smoke and every
  cell, writes the report and exits; `pgrep -f "uvicorn api.app.main:app"`
  returns nothing afterwards, and the temporary base directory is gone.
- Measurement oracle: the report's per-cell numbers are checked against the
  frozen table in `spec.md`; the committed results table in `tasks.md` is a
  human-readable transcription of one real run.
- Negative/no-fabrication oracle: if the child cannot boot, the run exits
  nonzero with `NOT EXECUTED — environment lacks …` and the tasks table is
  marked accordingly; zero measured numbers are invented.
- Test ownership: the test worker's `tests/**` cases should pin the pure
  helpers (SSE block parsing excludes the initial/keepalive frames; percentile
  nearest-rank; envelope builders are schema-valid), the option parser
  rejecting a URL-looking option, and the threshold-evaluation truth table.
  This worker records the design only.

## Runtime feedback

- This is an on-demand measurement tool with no runtime contour, no deploy
  lane and no acceptance probe against a deployed service.
- The committed evidence run is bound to one host and one base commit
  (`8675eb31b3cfa976b71b174a4b4c172e6b65a295`); different hardware, a different
  Python/fastapi/uvicorn version or a different base commit makes a new run a
  new baseline, not a contradiction of this one.
- The harness measures application behaviour only: recorded
  Cache-Control/X-Accel-Buffering are the app's response headers and are not
  evidence about a deployed proxy.

## Risk profile

- Risk profile: NOT REQUIRED
- Justification: the change adds an on-demand, stdlib-only developer tool plus
  SDD text under `scripts/` and `specs/`. It touches no production runtime,
  deploy path, workflow, schema, secret or migration, adds no dependency, and
  the change-control policy classifies every changed path as
  `Production impact: NONE`. The tool binds loopback only and never accepts a
  target. No security, schema, destructive or MIXED trigger applies.

## Test design

- TEST-001 | Covers: AC-001 | Level: runtime-manual | Priority: P0 | Evidence: the committed evidence run boots one child Uvicorn worker on an ephemeral loopback port with a temp base dir and fixture credentials, performs the smoke and every cell, and leaves no `uvicorn api.app.main:app` process behind afterwards; the parser exposes no host/URL option
- TEST-002 | Covers: AC-002 | Level: runtime-manual | Priority: P0 | Evidence: spec.md records the frozen workload and numeric thresholds with units and sample window; the CLI defaults are the same values and the report echoes them in its `workload`/`thresholds` objects
- TEST-003 | Covers: AC-003 | Level: runtime-manual | Priority: P0 | Evidence: the evidence run reports per-client and aggregate numbered messages/s, missing/duplicate IDs against the 20 published IDs, latency p50/p95/max, server CPU seconds per wall second, server-side ESTABLISHED sockets at barrier/after close, and per-alias status plus Content-Type/Cache-Control/X-Accel-Buffering; the initial frame and keepalives are excluded by parsing
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P1 | Evidence: every blocking call carries an explicit timeout, the level/overall deadlines are finite, and `finally` performs terminate→wait→kill; the run preserves the real 100 ms poll and default thread pool (no sleep mock, no limiter change)
- TEST-005 | Covers: AC-005 | Level: runtime-manual | Priority: P0 | Evidence: tasks.md carries one human-reviewed results table with tested SHA, platform/CPU allocation, dependency versions, command, workload, thresholds, measured rows and decision; raw output stays in `/tmp/opencode/690-baseline/`; any breach is recorded with a linked remediation and no threshold moved

## Correct-course check

- Trigger: NONE
- Issue impact: none — the scope matches issue #690 as admitted: a bounded SSE load baseline harness plus its SDD, measuring the existing road and water stream routes.
- Specification impact: none — the workload and thresholds are stated up front as required; no production or test file is changed.
- Plan impact: none — the implementation follows the admitted disposable-server, per-route/per-level, numbered-delivery, bounded-lifecycle design.
- Tasks impact: none — implementation, SDD and the committed evidence table are delivered; the PR lifecycle, CI and any test-worker coverage remain with the orchestrator and the test worker.
- Authorization impact: NONE — bounded worker work order from the delivery orchestrator on branch `agent/wave5-690-692-706`; the orchestrator owns the Git lifecycle, PR admission and CI evidence.
- Follow-up: if a cell breaches a frozen threshold, the linked remediation is recorded in tasks.md; hardening the thread pool or stream path belongs to #706 and is out of scope here.
