"""Issue #690 — bounded SSE load baseline harness (tests/** only).

The landed production code is ``scripts/sse_load_baseline.py`` (stdlib-only
on-demand CLI: it owns a disposable in-process Uvicorn child on an ephemeral
127.0.0.1 port, a temp ``SEA_SPEED_BASE_DIR``, fixture credentials and a
deployed-commit file before import) plus the frozen SDD in
``specs/690-sse-load-baseline/``.  Frozen thresholds (spec.md, recorded
before measurement): p50 <= 150 ms, p95 <= 300 ms, max <= 1000 ms,
missing = 0, dup = 0, CPU <= 0.50 s/s at 1 and 10 readers and <= 2.00 s/s
at 50, RSS growth <= 32 MiB, spread <= 16 MiB, FD growth <= 8, sockets = N
at the barrier and 0 after close, headers 200 / ``text/event-stream`` /
``no-cache`` / ``no`` / initial frame present.

Oracle independence: every expected value below is a hand-authored literal
from spec.md or hand-computed nearest-rank arithmetic — the tests never
call ``percentile`` or ``parse_sse_block`` to derive an expectation, so a
scorer change cannot be mirrored into the test.  The only production code
exercised directly is the harness itself; the CLI guard tests run the REAL
script in a subprocess.

External oracle (what proves pass/fail)::

    python3 -m pytest tests/test_sse_load_baseline.py -q   # this suite
    python3 -m pytest tests/ -q                            # whole battery
    ruff check --config scripts/quality/ruff.toml tests/test_sse_load_baseline.py

RED on base 8675eb3 (harness absent — ``git show 8675eb3:scripts/
sse_load_baseline.py`` fails): every test in this file fails at import
(``ModuleNotFoundError: scripts.sse_load_baseline``).  With the harness
present but its logic wrong each test's docstring names the mutation that
turns it red; mutations were executed against shadow copies in
/tmp/opencode/690-tests/ during authoring (production file never touched).
No assertion here was weakened to obtain green.

Peer-review defect coverage (this revision):
- DEFECT 1: ``EvidenceBindingTests`` — a report built with an empty or
  ``"unknown"`` tested_sha must yield ``decision.overall == "UNBOUND"``
  (the chosen non-PASS literal, asserted verbatim), while a valid 40-hex
  SHA with all cells passing still yields ``"PASS"``; the report records
  the SHA it was given and a malformed SHA still exits 2 (existing test).
- DEFECT 2: ``SpecThresholdParityTests`` parses the frozen threshold table
  out of ``specs/690-sse-load-baseline/spec.md`` with a row-prefix scan and
  compares it to ``harness.THRESHOLDS`` against LITERAL transcriptions of
  the spec — expectations never derive from the harness, so drift on
  either side fails.
"""

from __future__ import annotations

import ast
import json
import os
import platform
import re
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from scripts import sse_load_baseline as harness

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "sse_load_baseline.py"
SCRATCH = Path("/tmp/opencode/690-tests")
# Computed at runtime: no credential-shaped 40-hex literal in test source.
VALID_SHA = "d" * 40
URL_SENTINEL = "http://127.0.0.1:9/never"
OUTPUT_SENTINEL = "/tmp/opencode/690-tests/raw-report-sentinel.json"

# Literal transcription of spec.md "Frozen thresholds" — the test's own copy;
# if production relaxes a number, test_frozen_threshold_table_matches_spec
# and the breach tests fail.
FROZEN_THRESHOLDS = {
    "latency_ms": {"p50": 150.0, "p95": 300.0, "max": 1000.0},
    "delivery": {"missing": 0, "duplicates": 0, "complete_readers_per_round": "N"},
    "cpu_seconds_per_wall_second": {"1": 0.50, "10": 0.50, "50": 2.00},
    "memory_mib": {"retained_growth": 32.0, "spread": 16.0},
    "fds": {"retained_growth": 8},
    "sockets_established": {"at_barrier_reader": "N", "after_close_reader": 0},
    "headers": {
        "status": 200,
        "content_type_prefix": "text/event-stream",
        "cache_control_contains": "no-cache",
        "x_accel_buffering": "no",
        "initial_frame": True,
    },
}

TOP_LEVEL_KEYS = {
    "contract",
    "tested_sha",
    "platform",
    "workload",
    "thresholds",
    "smoke",
    "results",
    "decision",
}
PLATFORM_KEYS = {
    "python",
    "system",
    "machine",
    "cpu_count",
    "mem_total_mib",
    "fastapi",
    "uvicorn",
    "starlette",
}
WORKLOAD_KEYS = {
    "routes",
    "readers_levels",
    "warmup_rounds",
    "measured_rounds",
    "messages_per_round",
    "publish_interval_ms",
    "read_timeout_s",
    "start_timeout_s",
    "drain_timeout_s",
    "post_timeout_s",
    "server_start_timeout_s",
    "level_deadline_s",
    "overall_deadline_s",
}
FROZEN_WORKLOAD = {
    "routes": ["road1", "cam1"],
    "readers_levels": [1, 10, 50],
    "warmup_rounds": 2,
    "measured_rounds": 3,
    "messages_per_round": 20,
    "publish_interval_ms": 50,
    "read_timeout_s": 1.0,
    "start_timeout_s": 10.0,
    "drain_timeout_s": 10.0,
    "post_timeout_s": 5.0,
    "server_start_timeout_s": 20.0,
    "level_deadline_s": 120.0,
    "overall_deadline_s": 600.0,
}
ROW_KEYS = {
    "route",
    "readers",
    "rounds_measured",
    "publish_errors",
    "latency_ms",
    "delivery",
    "throughput",
    "server_cpu",
    "memory",
    "fds",
    "sockets",
    "verdict",
    "failures",
}
ALIAS_PATHS = [
    "/api/analytics/road1/live/stream",
    "/sea-speed/api/analytics/road1/live/stream",
    "/api/cam1/live/stream",
    "/sea-speed/api/cam1/live/stream",
]
# Third-party network client libraries the stdlib-only harness must never
# import (spec R-1).  The stdlib check below subsumes them; this list states
# the intent explicitly.  stdlib ``http.client``/``socket`` are the
# sanctioned loopback-only client of the harness's own child.
BANNED_NETWORK_LIBS = {
    "requests",
    "aiohttp",
    "httpx",
    "urllib3",
    "websocket",
    "websockets",
    "paramiko",
    "httpcore",
    "pycurl",
}
# Repo-local production packages the harness must not import — it boots the
# real app as a subprocess instead of importing it.
BANNED_PRODUCTION_ROOTS = {
    "api",
    "app",
    "core",
    "worker",
    "frontend",
    "deploy",
    "contracts",
    "schemas",
    "sea_speed",
}
URLISH_OPTION = re.compile(r"url|target|host|endpoint|address|remote|origin", re.I)
RELAX_OPTION = re.compile(
    r"threshold|relax|budget|toleran|waiv|p50|p95|latency|max|limit|"
    r"override|loosen|skip|bypass|force",
    re.I,
)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the REAL CLI exactly as documented; rejection paths exit before boot."""
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        check=False,
    )


def passing_summary(readers: int) -> dict:
    """A synthetic cell summary that passes every frozen threshold."""
    return {
        "latency_ms": {"samples": 60, "p50": 40.0, "p95": 90.0, "max": 120.0},
        "delivery": {
            "expected_ids_per_round": 20,
            "missing_total": 0,
            "duplicates_total": 0,
            "complete_reader_rounds": 3 * readers,
            "reader_rounds": 3 * readers,
        },
        "publish_errors": 0,
        "server_cpu": {"cpu_seconds": 2.0, "wall_seconds": 10.0, "cpu_per_wall": 0.2},
        "memory": {
            "post_warmup_rss_mib": 100.0,
            "measured_rss_mib": [101.0, 102.0, 103.0],
            "retained_growth_mib": 3.0,
            "spread_mib": 2.0,
        },
        "fds": {
            "post_warmup_fds": 40,
            "measured_fds": [41, 42, 43],
            "retained_growth": 3,
        },
        "sockets": {
            "at_barrier_reader": readers,
            "at_barrier_total": readers + 2,
            "after_close_reader": 0,
        },
    }


def passing_smoke_item(path: str = ALIAS_PATHS[0]) -> dict:
    """A synthetic header-smoke row that satisfies every HDR threshold."""
    return {
        "path": path,
        "status": 200,
        "content_type": "text/event-stream; charset=utf-8",
        "cache_control": "no-cache",
        "x_accel_buffering": "no",
        "initial_frame": True,
        "error": None,
    }


def make_args(*extra: str):
    return harness.parse_args(
        ["--output", OUTPUT_SENTINEL, "--tested-sha", VALID_SHA, *extra]
    )


def make_cell(route: str, readers: int, args) -> dict:
    """One synthetic measured cell: 3 rounds x 20 samples, all passing."""
    samples = [50.0] * args.messages
    rounds = []
    for _ in range(args.rounds):
        rounds.append(
            {
                "publish_errors": [],
                "expected_ids": list(range(1, args.messages + 1)),
                "latency_samples_ms": list(samples),
                "readers": [],
                "barrier_sockets": {
                    "total_established": readers + 2,
                    "reader_established": readers,
                },
                "close_sockets": {"total_established": 2, "reader_established": 0},
                "drain_seconds": 0.1,
                "publish_seconds": 1.0,
                "wall_seconds": 2.0,
                "error": None,
                "missing_total": 0,
                "duplicate_total": 0,
                "complete_readers": readers,
                "received_total": readers * args.messages,
            }
        )
    return {
        "route": route,
        "readers": readers,
        "status": "measured",
        "error": None,
        "rounds": rounds,
        "post_warmup": {"cpu_seconds": 1.0, "rss_mib": 100.0, "fds": 40.0},
        "measured_samples": [
            {"cpu_seconds": 1.1, "rss_mib": 101.0, "fds": 41.0},
            {"cpu_seconds": 1.2, "rss_mib": 102.0, "fds": 42.0},
            {"cpu_seconds": 1.3, "rss_mib": 103.0, "fds": 43.0},
        ],
        "cpu_window": {"cpu_seconds": 2.0, "wall_seconds": 10.0, "cpu_per_wall": 0.2},
    }


def make_smoke() -> list:
    return [
        {**passing_smoke_item(path), "route": route}
        for route, path in (
            ("road1", ALIAS_PATHS[0]),
            ("road1", ALIAS_PATHS[1]),
            ("cam1", ALIAS_PATHS[2]),
            ("cam1", ALIAS_PATHS[3]),
        )
    ]


def all_passing_cells(args) -> list:
    return [
        make_cell(route, readers, args)
        for route in ("road1", "cam1")
        for readers in (1, 10, 50)
    ]


class SseParserOracleTests(unittest.TestCase):
    """parse_sse_block classification against hand-authored SSE strings."""

    def test_numbered_block_is_delivery_with_extracted_id(self) -> None:
        """RED if id extraction breaks or numbered blocks stop being deliveries."""
        cases = [
            ('id: 7\ndata: {"seq":7}', ("delivery", 7)),
            ('id:  9 \ndata: {}', ("delivery", 9)),  # surrounding spaces stripped
            ('id: 4\r\ndata: {"x":1}', ("delivery", 4)),  # CRLF block
            ('data: {"x":1}\nid: 5', ("delivery", 5)),  # id after data still counts
            (
                'id: 3\ndata: line1\ndata: line2',
                ("delivery", 3),  # multi-line data
            ),
        ]
        for block, expected in cases:
            with self.subTest(block=block):
                self.assertEqual(harness.parse_sse_block(block), expected)

    def test_initial_frame_and_keepalive_are_not_deliveries(self) -> None:
        """RED if scaffolding frames are counted as deliveries (spec R-8)."""
        initial = "data: {}\n\n"
        keepalive = ": keepalive\n\n"
        self.assertEqual(harness.parse_sse_block(initial), ("initial", None))
        self.assertEqual(harness.parse_sse_block(keepalive), ("keepalive", None))
        for block in (initial, keepalive):
            kind, _seq = harness.parse_sse_block(block)
            self.assertNotEqual(kind, "delivery", f"{block!r} must not be a delivery")

    def test_malformed_and_truncated_blocks_are_other(self) -> None:
        """RED if malformed ids or id-without-data blocks are accepted."""
        cases = [
            ("id: abc\ndata: x", ("other", None)),  # non-integer id
            ("id: 5", ("other", None)),  # truncated: no data line
            ("", ("other", None)),  # empty block
            ("data", ("other", None)),  # not an SSE field at all
        ]
        for block, expected in cases:
            with self.subTest(block=block):
                self.assertEqual(harness.parse_sse_block(block), expected)

    def test_reader_consume_counts_only_numbered_deliveries(self) -> None:
        """RED if the reader counts the initial frame, keepalives or junk.

        Feeds one raw stream through the real Reader._consume: initial frame,
        keepalive, two numbered events and one malformed block.  The initial
        frame and keepalive must never appear in deliveries (spec R-8).
        """
        reader = harness.Reader(
            "127.0.0.1", 9, "/stream", 1.0, 1.0, threading.Event()
        )
        stream = (
            "data: {}\n\n"
            ": keepalive\n\n"
            'id: 1\ndata: {"seq":1}\n\n'
            'id: 2\ndata: {"seq":2}\n\n'
            "id: bad\ndata: x\n\n"
        )
        leftover = reader._consume(stream)
        self.assertEqual(leftover, "")
        self.assertTrue(reader.initial, "initial frame must arm readiness")
        self.assertEqual(reader.snapshot_ids(), [1, 2])
        self.assertEqual(reader.keepalives, 1)
        self.assertEqual(reader.malformed, 1)

    def test_consume_buffers_unterminated_tail(self) -> None:
        """RED if a partial event block is dropped or counted prematurely."""
        reader = harness.Reader(
            "127.0.0.1", 9, "/stream", 1.0, 1.0, threading.Event()
        )
        leftover = reader._consume('data: {}\n\nid: 9\ndata: {"seq":9}')
        self.assertEqual(leftover, 'id: 9\ndata: {"seq":9}')
        self.assertEqual(reader.snapshot_ids(), [], "unterminated block is not delivered")
        reader._consume(leftover + "\n\n")
        self.assertEqual(reader.snapshot_ids(), [9])


class PercentileOracleTests(unittest.TestCase):
    """Nearest-rank percentiles against hand-computed literals only."""

    def test_nearest_rank_odd_and_even_lengths(self) -> None:
        """RED if p50 interpolates/averages (statistics.median) instead of rank."""
        # (samples, pct, expected) — every expectation hand-computed:
        # rank = ceil(pct/100 * n), value = sorted[rank-1].
        cases = [
            ([1, 2, 3, 4, 5], 50, 3),  # ceil(2.5)=3 -> 3rd smallest
            ([1, 2, 3, 4], 50, 2),  # ceil(2.0)=2 -> 2nd smallest, NOT 2.5
            ([1, 2], 50, 1),  # ceil(1.0)=1 -> smallest, NOT 1.5
            ([1, 2, 3, 4], 95, 4),  # ceil(3.8)=4 -> largest
            ([1, 2, 3, 4], 75, 3),  # ceil(3.0)=3 -> 3rd smallest
        ]
        for samples, pct, expected in cases:
            with self.subTest(samples=samples, pct=pct):
                self.assertEqual(harness.percentile(samples, pct), expected)

    def test_nearest_rank_duplicates_single_unsorted_and_empty(self) -> None:
        """RED if sorting, dedup or the empty-list guard breaks."""
        self.assertEqual(harness.percentile([10, 10, 10, 10], 95), 10)
        self.assertEqual(harness.percentile([7], 50), 7)
        self.assertEqual(harness.percentile([7], 99), 7)
        self.assertEqual(harness.percentile([5, 1, 4, 2, 3], 50), 3)  # unsorted input
        self.assertIsNone(harness.percentile([], 50))
        self.assertIsNone(harness.percentile([], 95))

    def test_nearest_rank_on_larger_lists(self) -> None:
        """RED if the rank formula drifts on n=20/100 (no interpolation)."""
        # ceil(0.95*20)=19 -> 19th smallest = 19 (interpolation would give 19.05).
        self.assertEqual(harness.percentile(list(range(1, 21)), 95), 19)
        # ceil(0.95*100)=95 -> 95th smallest = 95 (interpolation gives 95.05).
        self.assertEqual(harness.percentile(list(range(1, 101)), 95), 95)
        # ceil(0.5*100)=50 -> 50th smallest = 50 (median would average 50/51).
        self.assertEqual(harness.percentile(list(range(1, 101)), 50), 50)


class ArgumentGuardTests(unittest.TestCase):
    """URL rejection, required --output, sha validation, frozen defaults."""

    def test_target_url_option_is_rejected_by_real_cli(self) -> None:
        """RED if a --target option is accepted (spec R-2, NFR-001).

        Real subprocess: must exit 1 with the guard's message on stderr and
        must NOT boot a child (no server output, immediate exit).
        """
        proc = run_cli("--target", URL_SENTINEL)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("no target URL", proc.stderr)
        self.assertIn("refusing argument", proc.stderr)
        self.assertIn(URL_SENTINEL, proc.stderr)

    def test_bare_url_argv_is_rejected_by_real_cli(self) -> None:
        """RED if a positional URL argument is accepted (spec R-2)."""
        proc = run_cli(URL_SENTINEL)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("no target URL", proc.stderr)
        self.assertIn(URL_SENTINEL, proc.stderr)

    def test_main_rejects_url_before_any_boot(self) -> None:
        """RED if main() stops routing argv through the URL guard."""
        with self.assertRaises(SystemExit) as ctx:
            harness.main(["--target", URL_SENTINEL])
        self.assertIn("no target URL", str(ctx.exception))

    def test_output_is_required(self) -> None:
        """RED if --output becomes optional (spec: report path is mandatory).

        Real subprocess: argparse error, exit code 2, stderr names --output.
        """
        proc = run_cli()
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("the following arguments are required: --output", proc.stderr)

    def test_tested_sha_must_be_40_hex_when_provided(self) -> None:
        """RED if a malformed --tested-sha is accepted (evidence binding).

        Real subprocess: exit code 2 with the parser's exact stderr text;
        the run must abort before writing any report.
        """
        never_created = SCRATCH / "never-created.json"
        if never_created.exists():
            never_created.unlink()
        proc = run_cli("--output", str(never_created), "--tested-sha", "not-a-sha")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("--tested-sha must be a 40-hex commit", proc.stderr)
        self.assertFalse(never_created.exists(), "invalid run must not write a report")

    def test_frozen_workload_defaults(self) -> None:
        """RED if any CLI default drifts from spec.md's frozen workload table."""
        args = harness.parse_args(["--output", OUTPUT_SENTINEL])
        self.assertEqual(args.output, OUTPUT_SENTINEL)
        # DEFECT 1 strengthening (was: "no --tested-sha means unbound report",
        # which pinned the unbound default as expected behavior): the CLI may
        # still default to an empty SHA, but a report built from it must never
        # read PASS — the chosen non-PASS marker is the literal "UNBOUND".
        self.assertEqual(args.tested_sha, "", "CLI default is an unbound run")
        unbound = harness.build_report(args, make_smoke(), all_passing_cells(args), [])
        self.assertEqual(
            unbound["decision"]["overall"],
            "UNBOUND",
            "empty --tested-sha must yield decision UNBOUND, never PASS",
        )
        self.assertNotEqual(unbound["decision"]["overall"], "PASS")
        self.assertEqual(args.routes, FROZEN_WORKLOAD["routes"])
        self.assertEqual(args.readers, FROZEN_WORKLOAD["readers_levels"])
        self.assertEqual(args.warmup_rounds, 2)
        self.assertEqual(args.rounds, 3)
        self.assertEqual(args.messages, 20)
        self.assertEqual(args.interval_ms, 50)
        self.assertEqual(args.read_timeout, 1.0)
        self.assertEqual(args.start_timeout, 10.0)
        self.assertEqual(args.drain_timeout, 10.0)
        self.assertEqual(args.post_timeout, 5.0)
        self.assertEqual(args.server_start_timeout, 20.0)
        self.assertEqual(args.level_deadline, 120.0)
        self.assertEqual(args.overall_deadline, 600.0)


class ThresholdEvaluationTests(unittest.TestCase):
    """evaluate_cell/smoke_failures: one breach at a time, exact reasons."""

    def test_frozen_threshold_table_matches_spec(self) -> None:
        """RED if ANY frozen threshold number is relaxed or moved (spec NFR-004)."""
        self.assertEqual(harness.THRESHOLDS, FROZEN_THRESHOLDS)

    def test_passing_row_yields_pass_at_exact_boundaries(self) -> None:
        """RED if the evaluator rejects a compliant row or flips <= to <."""
        summary = passing_summary(10)
        # Exact frozen boundaries must pass (thresholds are <=, not <).
        summary["latency_ms"]["p50"] = 150.0
        summary["latency_ms"]["p95"] = 300.0
        summary["latency_ms"]["max"] = 1000.0
        summary["memory"]["retained_growth_mib"] = 32.0
        summary["memory"]["spread_mib"] = 16.0
        summary["fds"]["retained_growth"] = 8
        summary["server_cpu"]["cpu_per_wall"] = 0.50
        self.assertEqual(harness.evaluate_cell(10, summary), [])

    def test_each_frozen_threshold_breach_fails_with_exact_reason(self) -> None:
        """RED if any breach goes unmarked or its reason string changes.

        Each case breaches exactly ONE threshold of an otherwise-passing
        row; the evaluator must return exactly that one failure.
        """
        breaches = [
            # (readers, mutate(summary), expected failure literal)
            (10, lambda s: s["latency_ms"].update(p50=151.0), "LAT-P50 151.0 ms > 150.0 ms"),
            (10, lambda s: s["latency_ms"].update(p95=301.0), "LAT-P95 301.0 ms > 300.0 ms"),
            (10, lambda s: s["latency_ms"].update(max=1001.0), "LAT-MAX 1001.0 ms > 1000.0 ms"),
            (10, lambda s: s["delivery"].update(missing_total=3), "DEL-MISS 3 missing numbered IDs"),
            (10, lambda s: s["delivery"].update(duplicates_total=1), "DEL-DUP 1 duplicate numbered IDs"),
            (
                10,
                lambda s: s["delivery"].update(complete_reader_rounds=27),
                "DEL-COMPLETE 27/30 complete reader-rounds",
            ),
            (10, lambda s: s.update(publish_errors=2), "publish errors: 2"),
            (10, lambda s: s["server_cpu"].update(cpu_per_wall=0.51), "CPU-10 0.51 s/s > 0.5 s/s"),
            (50, lambda s: s["server_cpu"].update(cpu_per_wall=2.01), "CPU-50 2.01 s/s > 2.0 s/s"),
            (10, lambda s: s["memory"].update(retained_growth_mib=33.0), "MEM-GROW 33.0 MiB > 32.0 MiB"),
            (10, lambda s: s["memory"].update(spread_mib=17.0), "MEM-SPREAD 17.0 MiB > 16.0 MiB"),
            (10, lambda s: s["fds"].update(retained_growth=9), "FD-RETAIN 9 > 8"),
            (10, lambda s: s["sockets"].update(at_barrier_reader=9), "SOCK-BARRIER 9 != 10"),
            (10, lambda s: s["sockets"].update(after_close_reader=2), "SOCK-CLOSE 2 != 0"),
        ]
        for readers, mutate, expected in breaches:
            with self.subTest(expected=expected):
                # Each mutate() flips exactly one field of an otherwise
                # passing row; the remaining latency fields stay within
                # budget so only the intended threshold can fire.
                summary = passing_summary(readers)
                mutate(summary)
                self.assertEqual(
                    harness.evaluate_cell(readers, summary),
                    [expected],
                    f"breach of {expected!r} must yield exactly that failure",
                )

    def test_cpu_budget_is_reader_level_specific(self) -> None:
        """RED if the 1/10 vs 50 reader budgets collapse into one number."""
        for readers in (1, 10):
            summary = passing_summary(readers)
            summary["server_cpu"]["cpu_per_wall"] = 0.6  # > 0.50, <= 2.00
            self.assertEqual(
                harness.evaluate_cell(readers, summary),
                [f"CPU-{readers} 0.6 s/s > 0.5 s/s"],
                f"0.6 s/s must FAIL at {readers} readers (budget 0.50)",
            )
        summary = passing_summary(50)
        summary["server_cpu"]["cpu_per_wall"] = 0.6
        self.assertEqual(
            harness.evaluate_cell(50, summary),
            [],
            "0.6 s/s must PASS at 50 readers (budget 2.00)",
        )

    def test_header_smoke_breaches_fail_with_exact_reason(self) -> None:
        """RED if any HDR threshold (spec row HDR) is dropped or loosened."""
        path = ALIAS_PATHS[0]
        prefix = f"SMOKE {path}"
        breaches = [
            ("status", 501, f"{prefix}: status 501"),
            ("content_type", "application/json", f"{prefix}: content-type application/json"),
            ("cache_control", "max-age=60", f"{prefix}: cache-control max-age=60"),
            ("x_accel_buffering", "yes", f"{prefix}: x-accel-buffering yes"),
            ("initial_frame", False, f"{prefix}: no initial frame"),
            ("error", "TimeoutError: read timed out", f"{prefix}: TimeoutError: read timed out"),
        ]
        for field, value, expected in breaches:
            with self.subTest(field=field):
                item = passing_smoke_item(path)
                item[field] = value
                self.assertEqual(harness.smoke_failures([item]), [expected])
        self.assertEqual(harness.smoke_failures([passing_smoke_item(path)]), [])

    def test_breaching_cell_is_verdict_fail_and_decision_fail(self) -> None:
        """RED if build_report stops propagating evaluator failures to verdict."""
        args = make_args()
        # 60 samples: 48x100 ms (p50 rank 30 -> 100, passes) and 12x400 ms
        # (p95 rank 57 -> 400 > 300, breaches; max 400 <= 1000, passes).
        pool = [100.0] * 16 + [400.0] * 4
        cells = all_passing_cells(args)
        cells[1]["rounds"] = [
            {**round_item, "latency_samples_ms": list(pool)} for round_item in cells[1]["rounds"]
        ]
        report = harness.build_report(args, make_smoke(), cells, [])
        row = report["results"][1]
        self.assertEqual(row["route"], "road1")
        self.assertEqual(row["readers"], 10)
        self.assertEqual(row["failures"], ["LAT-P95 400.0 ms > 300.0 ms"])
        self.assertEqual(row["verdict"], "FAIL")
        self.assertEqual(report["decision"]["overall"], "FAIL")
        self.assertIn(
            "road1/10: LAT-P95 400.0 ms > 300.0 ms",
            report["decision"]["failures"],
        )


class ReportSchemaTests(unittest.TestCase):
    """The committed report shape: keys, units, metadata, no raw paths."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.args = make_args()
        cls.report = harness.build_report(
            cls.args, make_smoke(), all_passing_cells(cls.args), []
        )
        cls.serialized = json.dumps(cls.report)

    def test_top_level_schema_and_pass_decision(self) -> None:
        """RED if the report drops/renames a top-level section or mis-decides."""
        self.assertEqual(set(self.report), TOP_LEVEL_KEYS)
        self.assertEqual(self.report["contract"], "sea_speed_sse_load_baseline_v1")
        self.assertEqual(self.report["tested_sha"], VALID_SHA)
        self.assertEqual(self.report["thresholds"], FROZEN_THRESHOLDS)
        self.assertEqual(set(self.report["decision"]), {"overall", "failures"})
        self.assertEqual(self.report["decision"]["overall"], "PASS")
        self.assertEqual(self.report["decision"]["failures"], [])

    def test_platform_and_workload_metadata(self) -> None:
        """RED if platform/dependency metadata or frozen workload echo breaks."""
        platform_meta = self.report["platform"]
        self.assertEqual(set(platform_meta), PLATFORM_KEYS)
        self.assertEqual(platform_meta["python"], platform.python_version())
        self.assertEqual(platform_meta["system"], platform.system())
        self.assertEqual(platform_meta["machine"], platform.machine())
        self.assertEqual(platform_meta["cpu_count"], os.cpu_count())
        self.assertIsInstance(platform_meta["mem_total_mib"], (int, float))
        for dep in ("fastapi", "uvicorn", "starlette"):
            self.assertIsInstance(platform_meta[dep], str)
            self.assertTrue(platform_meta[dep], f"{dep} version must not be empty")
        workload = self.report["workload"]
        self.assertEqual(set(workload), WORKLOAD_KEYS)
        self.assertEqual(workload, FROZEN_WORKLOAD)

    def test_per_cell_results_schema_with_units(self) -> None:
        """RED if a per-cell metric field or its unit suffix disappears."""
        rows = self.report["results"]
        self.assertEqual(len(rows), 6, "2 routes x 3 reader levels")
        observed = [(row["route"], row["readers"]) for row in rows]
        self.assertEqual(
            observed,
            [
                ("road1", 1),
                ("road1", 10),
                ("road1", 50),
                ("cam1", 1),
                ("cam1", 10),
                ("cam1", 50),
            ],
        )
        for row in rows:
            with self.subTest(route=row["route"], readers=row["readers"]):
                self.assertEqual(set(row), ROW_KEYS)
                self.assertEqual(row["verdict"], "PASS")
                self.assertEqual(row["failures"], [])
                self.assertEqual(row["rounds_measured"], 3)
                self.assertEqual(set(row["latency_ms"]), {"samples", "p50", "p95", "max"})
                self.assertEqual(row["latency_ms"]["samples"], 60)
                self.assertEqual(
                    set(row["delivery"]),
                    {
                        "expected_ids_per_round",
                        "missing_total",
                        "duplicates_total",
                        "complete_reader_rounds",
                        "reader_rounds",
                    },
                )
                self.assertEqual(row["delivery"]["missing_total"], 0)
                self.assertEqual(row["delivery"]["duplicates_total"], 0)
                self.assertEqual(
                    row["delivery"]["complete_reader_rounds"],
                    row["delivery"]["reader_rounds"],
                )
                self.assertEqual(
                    set(row["throughput"]),
                    {
                        "publish_window_seconds",
                        "aggregate_numbered_msgs_per_s",
                        "per_client_numbered_msgs_per_s",
                    },
                )
                self.assertEqual(row["throughput"]["publish_window_seconds"], 1.0)
                self.assertEqual(
                    set(row["server_cpu"]), {"cpu_seconds", "wall_seconds", "cpu_per_wall"}
                )
                self.assertLessEqual(row["server_cpu"]["cpu_per_wall"], 2.00)
                self.assertEqual(
                    set(row["memory"]),
                    {
                        "post_warmup_rss_mib",
                        "measured_rss_mib",
                        "retained_growth_mib",
                        "spread_mib",
                    },
                )
                self.assertLessEqual(row["memory"]["retained_growth_mib"], 32.0)
                self.assertLessEqual(row["memory"]["spread_mib"], 16.0)
                self.assertEqual(
                    set(row["fds"]), {"post_warmup_fds", "measured_fds", "retained_growth"}
                )
                self.assertLessEqual(row["fds"]["retained_growth"], 8)
                self.assertEqual(
                    set(row["sockets"]),
                    {"at_barrier_reader", "at_barrier_total", "after_close_reader"},
                )
                self.assertEqual(
                    row["sockets"]["at_barrier_reader"], row["readers"], "SOCK-BARRIER"
                )
                self.assertEqual(row["sockets"]["after_close_reader"], 0, "SOCK-CLOSE")

    def test_smoke_records_all_four_alias_paths(self) -> None:
        """RED if per-alias header smoke coverage shrinks (spec R-10)."""
        smoke = self.report["smoke"]
        self.assertEqual([item["path"] for item in smoke], ALIAS_PATHS)
        for item in smoke:
            with self.subTest(path=item["path"]):
                self.assertEqual(item["status"], 200)
                self.assertTrue(
                    item["content_type"].startswith("text/event-stream"),
                    item["content_type"],
                )
                self.assertIn("no-cache", item["cache_control"])
                self.assertEqual(item["x_accel_buffering"], "no")
                self.assertTrue(item["initial_frame"])
                self.assertIsNone(item["error"])

    def test_raw_output_paths_are_not_embedded(self) -> None:
        """RED if --output path, child log or temp base dir leaks into report."""
        self.assertNotIn(OUTPUT_SENTINEL, self.serialized, "raw --output path leaked")
        self.assertNotIn("child.log", self.serialized, "child log path leaked")
        self.assertNotIn("sea-speed-690-", self.serialized, "temp base dir leaked")
        self.assertNotIn(str(ROOT), self.serialized, "repo path leaked")


class EvidenceBindingTests(unittest.TestCase):
    """DEFECT 1 (peer review): unbound evidence must never read PASS.

    Chosen non-PASS decision literal: ``"UNBOUND"`` — asserted verbatim, so
    the fix must emit exactly that marker when tested_sha is empty or
    ``"unknown"``.  A valid 40-hex SHA with all cells passing must stay PASS,
    and the report must record the SHA it was given.
    """

    @staticmethod
    def _report(args) -> dict:
        return harness.build_report(args, make_smoke(), all_passing_cells(args), [])

    def _assert_unbound(self, report: dict) -> None:
        overall = report["decision"]["overall"]
        self.assertNotEqual(overall, "PASS", "unbound evidence must not PASS")
        self.assertEqual(
            overall,
            "UNBOUND",
            "chosen non-PASS marker for unbound tested_sha is the literal 'UNBOUND'",
        )
        self.assertFalse(
            re.fullmatch(r"[0-9a-f]{40}", str(report["tested_sha"])),
            f"unbound report must not carry a bound SHA: {report['tested_sha']!r}",
        )

    def test_empty_tested_sha_yields_unbound_not_pass(self) -> None:
        """RED today: build_report with tested_sha='' still returns PASS."""
        args = harness.parse_args(["--output", OUTPUT_SENTINEL])
        self.assertEqual(args.tested_sha, "", "fixture: CLI default is unbound")
        self._assert_unbound(self._report(args))

    def test_unknown_tested_sha_yields_unbound_not_pass(self) -> None:
        """RED today: build_report writes tested_sha 'unknown' yet PASSes."""
        args = make_args()
        args.tested_sha = "unknown"  # exactly what build_report emits today
        self._assert_unbound(self._report(args))

    def test_valid_tested_sha_passes_and_is_recorded(self) -> None:
        """GREEN today and after the fix: bound evidence can still PASS."""
        args = make_args()
        report = self._report(args)
        self.assertEqual(report["tested_sha"], VALID_SHA, "report records its SHA")
        self.assertEqual(report["decision"]["overall"], "PASS")
        self.assertEqual(report["decision"]["failures"], [])


class SpecThresholdParityTests(unittest.TestCase):
    """DEFECT 2 (peer review): spec.md frozen table vs harness.THRESHOLDS.

    Rows are read from ``specs/690-sse-load-baseline/spec.md`` with a
    row-prefix scan; every expectation is a literal transcription of the
    spec (150/300/1000, 0.50/0.50/2.00, 32/16, 8, 200/text-event-stream/
    no-cache/no), never derived from the harness.
    """

    SPEC_PATH = ROOT / "specs" / "690-sse-load-baseline" / "spec.md"

    @classmethod
    def setUpClass(cls) -> None:
        cls.spec_text = cls.SPEC_PATH.read_text(encoding="utf-8")

    def _cell(self, row_id: str) -> str:
        prefix = f"| {row_id} |"
        for line in self.spec_text.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                cells = [part.strip() for part in stripped.strip("|").split("|")]
                self.assertTrue(cells, f"row {row_id} has no cells")
                return cells[-1]
        raise AssertionError(f"spec.md has no threshold row {prefix!r}")

    def _bound(self, row_id: str) -> float:
        cell = self._cell(row_id)
        match = re.search(r"(?:≤|<=)\s*([0-9]+(?:\.[0-9]+)?)", cell)
        self.assertIsNotNone(match, f"row {row_id}: no ≤ bound in {cell!r}")
        return float(match.group(1))

    def _headers(self) -> dict:
        cell = self._cell("HDR")
        tokens = re.findall(r"`([^`]+)`", cell)
        self.assertEqual(len(tokens), 3, f"HDR cell must quote 3 values: {cell!r}")
        status = re.match(r"\s*(\d+)", cell)
        self.assertIsNotNone(status, f"HDR cell must start with status: {cell!r}")
        self.assertIn("present", cell, "initial frame must be required")
        return {
            "status": int(status.group(1)),
            "content_type_prefix": tokens[0],
            "cache_control_contains": tokens[1],
            "x_accel_buffering": tokens[2],
            "initial_frame": True,
        }

    def test_spec_table_parses_to_literal_expectations(self) -> None:
        """The parse itself, asserted against literals transcribed from spec.md."""
        self.assertEqual(self._bound("LAT-P50"), 150.0)
        self.assertEqual(self._bound("LAT-P95"), 300.0)
        self.assertEqual(self._bound("LAT-MAX"), 1000.0)
        self.assertEqual(self._bound("CPU-1/10"), 0.50)
        self.assertEqual(self._bound("CPU-50"), 2.00)
        self.assertEqual(self._bound("MEM-GROW"), 32.0)
        self.assertEqual(self._bound("MEM-SPREAD"), 16.0)
        self.assertEqual(self._bound("FD-RETAIN"), 8.0)
        self.assertEqual(
            self._headers(),
            {
                "status": 200,
                "content_type_prefix": "text/event-stream",
                "cache_control_contains": "no-cache",
                "x_accel_buffering": "no",
                "initial_frame": True,
            },
        )

    def test_spec_table_equals_harness_thresholds(self) -> None:
        """Parity: every parsed spec value equals the harness THRESHOLDS entry."""
        latency = harness.THRESHOLDS["latency_ms"]
        cpu = harness.THRESHOLDS["cpu_seconds_per_wall_second"]
        memory = harness.THRESHOLDS["memory_mib"]
        self.assertEqual(self._bound("LAT-P50"), latency["p50"])
        self.assertEqual(self._bound("LAT-P95"), latency["p95"])
        self.assertEqual(self._bound("LAT-MAX"), latency["max"])
        self.assertEqual(self._bound("CPU-1/10"), cpu["1"])
        self.assertEqual(self._bound("CPU-1/10"), cpu["10"])
        self.assertEqual(self._bound("CPU-50"), cpu["50"])
        self.assertEqual(self._bound("MEM-GROW"), memory["retained_growth"])
        self.assertEqual(self._bound("MEM-SPREAD"), memory["spread"])
        self.assertEqual(self._bound("FD-RETAIN"), harness.THRESHOLDS["fds"]["retained_growth"])
        for key, value in self._headers().items():
            self.assertEqual(
                harness.THRESHOLDS["headers"][key], value, f"headers.{key} drifted"
            )


class ScopeGuardTests(unittest.TestCase):
    """Static guards over the harness source: imports, shell, option surface."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = HARNESS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_imports_are_stdlib_only_with_no_production_imports(self) -> None:
        """RED on any third-party import (spec R-1), production import or
        relative import — the harness boots the real app as a subprocess,
        it must not import it."""
        roots = set()
        relative = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    relative.append(node.lineno)
                elif node.module:
                    roots.add(node.module.split(".")[0])
        self.assertEqual(relative, [], "relative imports bind production packages")
        self.assertTrue(roots, "sanity: the harness must import something")
        non_stdlib = sorted(roots - set(sys.stdlib_module_names))
        self.assertEqual(non_stdlib, [], "stdlib-only CLI (spec R-1)")
        self.assertEqual(
            sorted(roots & BANNED_NETWORK_LIBS),
            [],
            "no third-party network client library",
        )
        self.assertEqual(
            sorted(roots & BANNED_PRODUCTION_ROOTS),
            [],
            "no production imports — the app runs in the child process",
        )

    def test_no_subprocess_shell_true_and_no_os_system(self) -> None:
        """RED if any call enables shell=True or reaches os.system/os.popen."""
        shell_enabled = []
        os_system = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            for kw in node.keywords:
                if kw.arg == "shell":
                    literal_false = (
                        isinstance(kw.value, ast.Constant) and kw.value.value is False
                    )
                    if not literal_false:
                        shell_enabled.append(node.lineno)
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and func.attr in ("system", "popen")
            ):
                os_system.append(node.lineno)
        self.assertEqual(shell_enabled, [], "shell=True is forbidden")
        self.assertEqual(os_system, [], "os.system/os.popen are forbidden")

    def test_no_target_url_option(self) -> None:
        """RED if any argparse option can name a target/URL/host (spec R-2)."""
        options = self._collect_options()
        self.assertTrue(options, "sanity: the CLI parser must define options")
        for option in options:
            with self.subTest(option=option):
                self.assertTrue(option.startswith("-"), f"positional arg {option!r}")
                self.assertIsNone(
                    URLISH_OPTION.search(option),
                    f"option {option!r} looks like a target-URL knob",
                )

    def test_no_threshold_relaxation_option(self) -> None:
        """RED if a flag appears that can loosen a frozen threshold (NFR-004)."""
        options = self._collect_options()
        self.assertTrue(options, "sanity: the CLI parser must define options")
        for option in options:
            with self.subTest(option=option):
                self.assertIsNone(
                    RELAX_OPTION.search(option),
                    f"option {option!r} looks like a threshold-relaxation knob",
                )

    def _collect_options(self) -> list:
        options = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    options.append(node.args[0].value)
        return options


if __name__ == "__main__":
    unittest.main()
