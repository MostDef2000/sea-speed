"""Issue #703 — decoder CPU baseline + keyframe/Range prototype (tests/** only).

The landed production code is ``scripts/worker/decoder_grab_baseline.py``
(stdlib-only on-demand CLI: disposable 127.0.0.1 HLS origin, wall-clock-paced
baseline replay with the production reader flags, Range prototype with strict
206 validation, /proc CPU accounting, report bound to ``--tested-sha``) plus
the frozen SDD in ``specs/703-decoder-grab-baseline/``.  Frozen thresholds
(spec.md, recorded before measurement): BASE-YIELD >= 0.90, stall gap > 3.5 s,
PROT-RANGE/INIT/KEY/STALE/DUP/MISS/FAIL = 0, PROT-OBS >= 1 per window,
CPU ratio <= 0.50, frame-ready p95 <= 3000 ms, BIND = full 40-hex.

Oracle independence: every expected value below is a hand-authored literal
from spec.md / the frozen report or hand-computed arithmetic — the tests never
derive an expectation from ``build_decision``, ``compare_arms`` or
``evaluate_range_response`` (those are observed, not consulted), so a scorer
change cannot be mirrored into the test.  The Range fixtures are hand-authored
HTTP answers; the ``run_prototype`` integration drives a scripted origin and
fixture ffmpeg executables so the counting logic is exercised without a real
decoder.

External oracle (what proves pass/fail)::

    python3 -m pytest tests/test_decoder_grab_baseline.py -q   # this suite
    python3 -m pytest tests/ -q                                # whole battery
    ruff check --config scripts/quality/ruff.toml tests/test_decoder_grab_baseline.py

RED on base 8ba614b (harness absent — ``git show 8ba614b:scripts/worker/
decoder_grab_baseline.py`` fails): every test in this file fails at import
(``ModuleNotFoundError: scripts.worker.decoder_grab_baseline``).  With the
harness present but its logic wrong, each test's docstring names the mutation
that turns it red; authoring probes ran in /tmp/opencode/703-tests/ against
shadow behaviour only — the production file was never mutated in place except
for the explicitly restored RED demonstrations.  No assertion here was
weakened to obtain green.

Honest-boundary notes (asserted, not glossed over):

- An unbound report must never look green: spec.md ("measurement is GREEN
  only when BIND ... hold") requires ``measurement == "RED"`` whenever the
  binding is UNBOUND, alongside the fail-closed
  ``recommendation == "NO_ADOPTION_RECOMMENDATION — report is UNBOUND"``,
  the binding reason and the CLI exit code 2.  The landed build_decision
  computed measurement before the UNBOUND overlay (an otherwise-complete
  unbound run reported measurement GREEN); these tests now assert RED on
  every unbound surface and stay RED until production applies the admitted
  fix (move the UNBOUND check before the measurement assignment).
- ``run_prototype``'s ``stale_segment``/``duplicate_segment`` branches are
  unreachable by construction (the batch range starts at
  ``last_sequence + 1`` over a monotonic counter).  Stale/duplicate coverage
  therefore asserts the observable contract: a regressed/re-announced playlist
  never fetches or re-presents a segment (counters stay absent/0), and a
  report carrying stale/duplicate failure counts fails the decision open
  (no adoption).
"""

from __future__ import annotations

import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.worker import decoder_grab_baseline as harness

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "worker" / "decoder_grab_baseline.py"
SCRATCH = Path("/tmp/opencode/703-tests")

# Computed at runtime: no credential-shaped 40-hex literal in test source.
VALID_SHA = "d" * 40
URL_SENTINEL = "http://127.0.0.1:9/never"
# Deliberately missing binary: truthy --ffmpeg so the skip paths stay
# deterministic on hosts with or without a real ffmpeg on PATH.
BOGUS_FFMPEG = "/nonexistent/ffmpeg-703-tests"

FRAME_BYTES = 6220800  # 1920 * 1080 * 3 raw bgr24 frame (spec output rate)
RANGE_TOTAL = 1048576  # fixture segment larger than the 500 KiB cap
RANGE_END = 511999  # bytes=0-511999: end of the frozen Range request
RANGE_LEN = 512000  # end - start + 1 = 500 KiB

# Literal transcription of spec.md's frozen workload/threshold table — the
# test's own copy; if production relaxes any number, FrozenThresholdTests and
# the ReportSchema frozen echo fail.
LITERAL_FROZEN = {
    "profiles": ["water", "road"],
    "source_seconds": 210.0,
    "segment_seconds": 2.0,
    "source_fps": 10.0,
    "source_width": 1920,
    "source_height": 1080,
    "source_bitrate_kbps": 2500,
    "source_gop_seconds": 2.0,
    "source_motion": "synthetic testsrc2 moving pattern",
    "warmup_seconds": 10.0,
    "windows": 3,
    "window_seconds": 60.0,
    "poll_seconds": 1.0,
    "range_bytes": 512000,  # 500 KiB, spec Range request bytes=0-511999
    "playlist_window_segments": 6,
    "stall_seconds": 3.5,
    "frame_yield_min": 0.90,
    "prototype_cpu_ratio_max": 0.50,
    "prototype_frame_ready_p95_ms_max": 3000.0,
    "prototype_failures_max": 0,
}

TOP_LEVEL_KEYS = {
    "contract",
    "issue",
    "tested_sha",
    "binding",
    "profile_selection",
    "frozen",
    "runtime",
    "source",
    "outcome_scope",
    "arms",
    "comparison",
    "decision",
    "not_executed",
    "duration_seconds",
}
DECISION_KEYS = {"measurement", "recommendation", "reasons", "full_outcome", "performance_criteria_met"}
PAIR_KEYS = {
    "profile",
    "baseline_status",
    "prototype_status",
    "baseline_total_cpu_s_per_s",
    "prototype_total_cpu_s_per_s",
    "cpu_ratio",
    "cpu_ratio_ok",
    "prototype_failures",
    "frame_ready_p95_ms",
    "frame_ready_p95_ok",
    "thresholds",
}
# Literal transcription of the frozen comparison thresholds (spec rows
# PROT-CPU-RATIO / PROT-LAT-P95 / PROT-FAIL).
PAIR_THRESHOLDS = {
    "cpu_ratio_max": 0.50,
    "frame_ready_p95_ms_max": 3000.0,
    "failures_max": 0,
}

# Exact CLI option surface (spec R-1/R-2/R-8: only these knobs exist).
LITERAL_OPTIONS = {
    "--output",
    "--tested-sha",
    "--profiles",
    "--ffmpeg",
    "--source-dir",
    "--source-class",
    "--labeled-events",
    "--source-seconds",
    "--warmup-seconds",
    "--window-seconds",
    "--windows",
    "--poll-seconds",
    "--range-bytes",
    "--skip-baseline",
    "--skip-prototype",
}

# Third-party network client libraries the stdlib-only harness must never
# import (spec R-1).  The stdlib check below subsumes them; this list states
# the intent explicitly.
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
# Repo-local production packages the harness must not import (R-12: the
# harness is measurement only and never touches production source).
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
# Threshold-relaxation knobs.  "skip" is deliberately NOT banned here: the
# spec sanctions --skip-baseline/--skip-prototype as investigation-only flags
# that make a run non-frozen; their fail-closed behaviour is asserted
# behaviourally in DecisionOracleTests.test_missing_arm_fails_closed_red.
RELAX_OPTION = re.compile(
    r"threshold|relax|budget|toleran|waiv|p50|p95|latency|max|limit|"
    r"override|loosen|bypass|force",
    re.I,
)

# Fixture playlist whose metadata duration (200 s) covers the default frozen
# need (10 s warm-up + 3 x 60 s windows = 190 s) so the mocked arms run.
FIXTURE_PLAYLIST_200S = (
    "#EXTM3U\n"
    "#EXT-X-VERSION:3\n"
    "#EXT-X-TARGETDURATION:200\n"
    "#EXT-X-MEDIA-SEQUENCE:0\n"
    "#EXTINF:200.000,\n"
    "/seg00000.ts\n"
)
# Short fixture (2 s) for the real-CLI skip path: shorter than the frozen
# need, so arms are never executed and the run stays fast and deterministic.
FIXTURE_PLAYLIST_SHORT = (
    "#EXTM3U\n"
    "#EXT-X-VERSION:3\n"
    "#EXT-X-TARGETDURATION:2\n"
    "#EXT-X-MEDIA-SEQUENCE:0\n"
    "#EXTINF:2.000,\n"
    "/seg00000.ts\n"
)

# Frozen-need arithmetic asserted verbatim in the real-CLI skip message:
# default warm-up 10 s + 3 windows x 60 s = 190.0 s.
FROZEN_NEED_LITERAL = "NOT EXECUTED: source duration 2.0s shorter than frozen need 190.0s"


def scratch_dir(prefix: str) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=SCRATCH))


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


def write_short_source(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "source.m3u8").write_text(FIXTURE_PLAYLIST_SHORT, encoding="utf-8")
    (directory / "seg00000.ts").write_bytes(b"\0" * 64)


def write_fake_ffmpeg(directory: Path, name: str, byte_count: int) -> Path:
    """An executable fixture standing in for ffmpeg: emits exactly
    ``byte_count`` raw bytes (or refuses to produce a full frame)."""
    script = directory / name
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.buffer.write(b'\\0' * {byte_count})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


# ---------------------------------------------------------------------------
# Decision oracle fixtures (hand-built minimal reports; every expectation in
# DecisionOracleTests is a literal, never computed from build_decision).
# ---------------------------------------------------------------------------


def measured_baseline(profile: str) -> dict:
    return {"profile": profile, "status": "MEASURED", "verdict": "MEASURED"}


def measured_prototype(profile: str) -> dict:
    return {"profile": profile, "status": "MEASURED", "usable_observations": 3}


def passing_pair(profile: str) -> dict:
    return {
        "profile": profile,
        "cpu_ratio_ok": True,
        "frame_ready_p95_ok": True,
        "prototype_failures": 0,
    }


def decision_report(
    binding: str = "BOUND",
    full_outcome: str = "MEASURED",
    selection: list | None = None,
    baseline: list | None = None,
    prototype: list | None = None,
    pairs: list | None = None,
    not_executed: list | None = None,
) -> dict:
    """A minimal report in the exact shape build_decision consumes."""
    selection = ["water"] if selection is None else selection
    if baseline is None:
        baseline = [measured_baseline(profile) for profile in selection]
    if prototype is None:
        prototype = [measured_prototype(profile) for profile in selection]
    if pairs is None:
        pairs = [passing_pair(profile) for profile in selection]
    return {
        "arms": {"baseline": baseline, "prototype": prototype},
        "comparison": {"pairs": pairs},
        "profile_selection": selection,
        "outcome_scope": {"full_outcome": full_outcome},
        "not_executed": [] if not_executed is None else not_executed,
        "binding": binding,
    }


# ---------------------------------------------------------------------------
# Scripted origin + fixture ffmpeg for the run_prototype integration.
# ---------------------------------------------------------------------------


class _FakeSegment:
    __slots__ = ("suffix", "size", "start", "path")

    def __init__(self, name: str, size: int, start: float = 0.0):
        self.path = Path("/virtual/") / name
        self.suffix = self.path.suffix.lower()
        self.size = size
        self.start = start


class _FakeCatalog:
    def __init__(self, segments: list):
        self.segments = segments
        self.epoch = None

    def reset_epoch(self) -> None:
        import time as _time

        self.epoch = _time.monotonic()

    def available_at(self, index: int) -> float:
        return self.epoch + self.segments[index].start


def _playlist_text(segment_count: int) -> str:
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:2",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]
    for index in range(segment_count):
        lines.append("#EXTINF:2.000,")
        lines.append(f"/seg{index:05d}.ts")
    return "\n".join(lines) + "\n"


class _FakeOrigin:
    """Duck-typed stand-in for harness.Origin returning hand-authored answers.

    ``playlists`` is consumed one per poll (the last one repeats);
    ``responses`` maps segment sequence to the HTTP answer fixture.
    """

    def __init__(self, segments: list, playlists: list, responses: dict):
        self.catalog = _FakeCatalog(segments)
        self._playlists = list(playlists)
        self._responses = responses

    def playlist(self, timeout: float = 3.0) -> str:
        if len(self._playlists) > 1:
            return self._playlists.pop(0)
        return self._playlists[0]

    def segment(self, sequence: int, start: int, end: int) -> dict:
        return self._responses[sequence]


def _clean_206(total: int = RANGE_TOTAL, cap: int = RANGE_LEN) -> dict:
    end = min(cap, total) - 1
    return {
        "status": 206,
        "headers": {
            "content-range": f"bytes 0-{end}/{total}",
            "content-length": str(end + 1),
        },
        "body": b"\0" * (end + 1),
    }


# Prototype integration pacing: one measured window of 0.4 s, polled every
# 0.04 s — the first poll adopts the latest sequence, the second sees a new
# segment and fetches it (warm-up 0).
PROTO_WINDOW_SECONDS = 0.4
PROTO_POLL_SECONDS = 0.04


class DecisionOracleTests(unittest.TestCase):
    """build_decision against hand-computed literal expectations.

    RED if any decision branch changes: the recommendation/measurement/reasons
    literals below are transcribed from spec.md's decision rules and the
    frozen report, never derived from the function.
    """

    def test_complete_bound_report_is_green_and_adoption_eligible(self) -> None:
        """RED if ADOPTION_ELIGIBLE stops requiring a complete bound report
        whose every frozen comparison threshold passed (spec decision table)."""
        decision = harness.build_decision(decision_report())
        self.assertEqual(
            decision,
            {
                "measurement": "GREEN",
                "recommendation": "ADOPTION_ELIGIBLE",
                "reasons": [],
                "full_outcome": "MEASURED",
                "performance_criteria_met": True,
            },
        )

    def test_short_pair_coverage_is_red_with_exact_reason(self) -> None:
        """RED if a comparison that misses a selected profile is tolerated."""
        report = decision_report(
            selection=["water", "road"],
            baseline=[measured_baseline("water")],
            prototype=[measured_prototype("water")],
            pairs=[passing_pair("water")],
        )
        decision = harness.build_decision(report)
        self.assertEqual(decision["measurement"], "RED")
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — measurement is RED",
        )
        self.assertEqual(
            decision["reasons"],
            ["paired comparison does not cover every selected profile"],
        )

    def test_unbound_report_never_claims_a_positive_outcome(self) -> None:
        """RED if an unbound report can read like a pass.

        The UNBOUND overlay must force measurement RED (spec: measurement is
        GREEN only when BIND holds) and the NO_ADOPTION recommendation with
        the exact binding reason, never ADOPTION_ELIGIBLE, and never the
        token PASS; the non-empty reasons are what makes the CLI exit 2
        (asserted end-to-end in ReportSchemaTests and ArgumentGuardTests).
        """
        decision = harness.build_decision(decision_report(binding="UNBOUND"))
        self.assertEqual(decision["measurement"], "RED")
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — report is UNBOUND",
        )
        self.assertEqual(
            decision["reasons"],
            ["tested SHA is missing or not a full 40-hex commit"],
        )
        self.assertNotEqual(decision["recommendation"], "ADOPTION_ELIGIBLE")
        self.assertNotIn("PASS", json.dumps(decision))
        self.assertTrue(
            decision["reasons"],
            "the binding reason is the CLI's fail-closed exit condition",
        )

    def test_full_outcome_unmeasured_blocks_adoption_even_when_green(self) -> None:
        """RED if synthetic evidence (full outcome UNMEASURED) can recommend
        adoption even with measurement GREEN and every threshold passed."""
        decision = harness.build_decision(decision_report(full_outcome="UNMEASURED"))
        self.assertEqual(decision["measurement"], "GREEN")
        self.assertTrue(decision["performance_criteria_met"])
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED",
        )

    def test_cpu_ratio_above_threshold_blocks_adoption(self) -> None:
        """RED if a PROT-CPU-RATIO breach (frozen <= 0.50) stops blocking
        adoption, or if GREEN measurement leaks into a positive verdict."""
        pair = passing_pair("water")
        pair["cpu_ratio_ok"] = False  # observed breach, e.g. 0.7065 > 0.50
        report = decision_report(pairs=[pair], full_outcome="UNMEASURED")
        decision = harness.build_decision(report)
        # A threshold breach adds no RED reason; measurement stays GREEN but
        # performance_criteria_met must be False...
        self.assertEqual(decision["measurement"], "GREEN")
        self.assertFalse(decision["performance_criteria_met"])
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED; "
            "frozen comparison threshold failed",
        )
        # ...and even with an approved representative source the same breach
        # must refuse adoption (DO_NOT_ADOPT, never ADOPTION_ELIGIBLE).
        report["outcome_scope"]["full_outcome"] = "MEASURED"
        decision = harness.build_decision(report)
        self.assertEqual(
            decision["recommendation"],
            "DO_NOT_ADOPT — frozen comparison threshold failed",
        )
        self.assertNotEqual(decision["recommendation"], "ADOPTION_ELIGIBLE")

    def test_prototype_failure_counts_block_adoption(self) -> None:
        """RED if summed prototype failures (PROT-FAIL = 0, the sum that
        carries stale/duplicate/init/keyframe/range rejections) stop failing
        the decision when CPU and latency still pass."""
        pair = passing_pair("water")
        pair["prototype_failures"] = 2  # e.g. one stale + one duplicate
        report = decision_report(pairs=[pair], full_outcome="UNMEASURED")
        decision = harness.build_decision(report)
        self.assertEqual(decision["measurement"], "GREEN")
        self.assertFalse(decision["performance_criteria_met"])
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED; "
            "frozen comparison threshold failed",
        )
        self.assertNotEqual(decision["recommendation"], "ADOPTION_ELIGIBLE")

    def test_missing_arm_fails_closed_red(self) -> None:
        """RED if an arm that did not run (--skip-baseline/--skip-prototype,
        no ffmpeg, short source) can yield anything but RED with its exact
        reason — the sanctioned skip flags must never look green."""
        skip_baseline = harness.build_decision(decision_report(baseline=[]))
        self.assertEqual(skip_baseline["measurement"], "RED")
        self.assertEqual(skip_baseline["reasons"], ["baseline arm did not run"])
        self.assertEqual(
            skip_baseline["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — measurement is RED",
        )
        skip_prototype = harness.build_decision(decision_report(prototype=[]))
        self.assertEqual(skip_prototype["measurement"], "RED")
        self.assertEqual(skip_prototype["reasons"], ["prototype arm did not run"])
        self.assertEqual(
            skip_prototype["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — measurement is RED",
        )

    def test_zero_usable_observations_fails_the_observation_floor(self) -> None:
        """RED if a prototype window with zero usable observations (PROT-OBS
        floor) is not a measurement failure (spec Gherkin: zero usable
        observations is never a win)."""
        row = measured_prototype("water")
        row["usable_observations"] = 0
        decision = harness.build_decision(decision_report(prototype=[row]))
        self.assertEqual(decision["measurement"], "RED")
        self.assertEqual(
            decision["reasons"],
            ["a prototype window has zero usable observations"],
        )

    def test_frame_yield_breach_fails_baseline_validity(self) -> None:
        """RED if a baseline verdict below the frozen BASE-YIELD floor (0.90)
        stops invalidating the measurement."""
        row = measured_baseline("water")
        row["verdict"] = "INVALID"
        decision = harness.build_decision(decision_report(baseline=[row]))
        self.assertEqual(decision["measurement"], "RED")
        self.assertEqual(
            decision["reasons"],
            ["baseline frame yield below the frozen validity floor"],
        )


class RangeValidationTests(unittest.TestCase):
    """evaluate_range_response against hand-authored HTTP answers (R-4).

    RED if any listed answer is accepted (ok True) or its exact failure
    literal changes — the expected failure lists below are hand-authored,
    never read back from the function's own output shape.
    """

    @staticmethod
    def check(
        status: int,
        content_range: str | None,
        content_length: str | None,
        body_len: int,
        total: int = RANGE_TOTAL,
        start: int = 0,
        end: int = RANGE_END,
    ) -> dict:
        return harness.evaluate_range_response(
            status, content_range, content_length, body_len, total, start, end
        )

    def test_strict_206_answer_with_exact_length_is_accepted(self) -> None:
        """RED if the strict acceptance path rejects a compliant 206 or flips
        any field of the echoed validation record."""
        result = self.check(206, "bytes 0-511999/1048576", "512000", 512000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["status"], 206)
        self.assertEqual(result["content_range"], "bytes 0-511999/1048576")
        self.assertEqual(result["content_length"], "512000")
        self.assertEqual(result["requested"], {"start": 0, "end": 511999})
        self.assertEqual(result["body_len"], 512000)
        self.assertEqual(result["total"], 1048576)

    # (label, status, content_range, content_length, body_len, exact failures)
    REJECTIONS = [
        (
            "200 full body presented as Range success",
            200,
            None,
            "1048576",
            1048576,
            [
                "range_not_honored_status_200",
                "content_range_missing_or_malformed",
                "content_length_mismatch",
                "body_length_1048576_expected_512000",
            ],
        ),
        (
            "Content-Range header missing",
            206,
            None,
            "512000",
            512000,
            ["content_range_missing_or_malformed"],
        ),
        (
            "Content-Range without total",
            206,
            "bytes 0-511999",
            "512000",
            512000,
            ["content_range_missing_or_malformed"],
        ),
        (
            "Content-Range garbage",
            206,
            "bytes banana",
            "512000",
            512000,
            ["content_range_missing_or_malformed"],
        ),
        (
            "Content-Range span mismatch",
            206,
            "bytes 0-999/1048576",
            "512000",
            512000,
            ["content_range_span_mismatch"],
        ),
        (
            "Content-Range unsatisfied-form answer",
            206,
            "bytes */1048576",
            "512000",
            512000,
            ["content_range_span_mismatch"],
        ),
        (
            "Content-Range total mismatch",
            206,
            "bytes 0-511999/1048575",
            "512000",
            512000,
            ["content_range_total_mismatch"],
        ),
        (
            "truncated body",
            206,
            "bytes 0-511999/1048576",
            "512000",
            500000,
            ["body_length_500000_expected_512000"],
        ),
        (
            "Content-Length missing",
            206,
            "bytes 0-511999/1048576",
            None,
            512000,
            ["content_length_missing"],
        ),
        (
            "Content-Length mismatch",
            206,
            "bytes 0-511999/1048576",
            "511999",
            512000,
            ["content_length_mismatch"],
        ),
    ]

    def test_every_nonconforming_answer_is_rejected_with_exact_failures(self) -> None:
        """RED if ANY of these answers validates (ok True) or its failure
        literal changes — each case breaches exactly one contract point of an
        otherwise-correct answer except the 200 case, which must list all four."""
        for label, status, content_range, content_length, body_len, expected in self.REJECTIONS:
            with self.subTest(case=label):
                result = self.check(status, content_range, content_length, body_len)
                self.assertFalse(result["ok"], f"{label}: must not validate")
                self.assertEqual(
                    result["failures"],
                    expected,
                    f"{label}: exact failure list changed",
                )


class PrototypeFailureCountingTests(unittest.TestCase):
    """run_prototype with a scripted origin: every rejection is a counted
    FAILURE, never a discarded sample (spec R-5 / AC-004 / Gherkin rules).

    The origin returns hand-authored HTTP answers and the fixture ffmpeg
    "decodes" (or refuses) the capped bytes; what is under test is the
    harness's classification and counting, not ffmpeg itself.  RED if any
    rejection below is silently dropped (failures stay 0 / usable counts the
    bad observation) or the clean path reports a phantom failure.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.scratch = scratch_dir("proto-counting-")
        good = write_fake_ffmpeg(cls.scratch, "fake-ffmpeg-good", FRAME_BYTES)
        short = write_fake_ffmpeg(cls.scratch, "fake-ffmpeg-short", 100)
        two_segments = [
            _FakeSegment("seg00000.ts", RANGE_TOTAL),
            _FakeSegment("seg00001.ts", RANGE_TOTAL),
        ]

        def run(origin: _FakeOrigin, ffmpeg: Path) -> dict:
            return harness.run_prototype(
                str(ffmpeg),
                origin,
                "water",
                window_seconds=PROTO_WINDOW_SECONDS,
                windows=1,
                warmup_seconds=0.0,
                poll_seconds=PROTO_POLL_SECONDS,
                range_bytes=RANGE_LEN,
            )

        # A: clean 206 + decodable keyframe.
        cls.clean = run(
            _FakeOrigin(two_segments, [_playlist_text(1), _playlist_text(2)],
                        {1: _clean_206()}),
            good,
        )
        # B: origin ignores Range and answers 200 with the whole segment.
        cls.full_200 = run(
            _FakeOrigin(
                two_segments,
                [_playlist_text(1), _playlist_text(2)],
                {1: {"status": 200,
                     "headers": {"content-length": str(RANGE_TOTAL)},
                     "body": b"\0" * RANGE_TOTAL}},
            ),
            good,
        )
        # C: fMP4 segment without a fetched init segment.
        fmp4 = [
            _FakeSegment("seg00000.ts", RANGE_TOTAL),
            _FakeSegment("seg00001.m4s", RANGE_TOTAL),
        ]
        fmp4_playlist = _playlist_text(2).replace("seg00001.ts", "seg00001.m4s")
        cls.missing_init = run(
            _FakeOrigin(fmp4, [_playlist_text(1), fmp4_playlist], {1: _clean_206()}),
            good,
        )
        # D: capped bytes that do not decode a usable keyframe.
        cls.short_decode = run(
            _FakeOrigin(two_segments, [_playlist_text(1), _playlist_text(2)],
                        {1: _clean_206()}),
            short,
        )
        # E: playlist regresses then re-announces the same segment — a stale
        # or duplicate fetch presented as new must never happen.
        cls.regression = run(
            _FakeOrigin(
                two_segments,
                [_playlist_text(1), _playlist_text(2), _playlist_text(1),
                 _playlist_text(2), _playlist_text(2)],
                {1: _clean_206()},
            ),
            good,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.scratch, ignore_errors=True)

    @staticmethod
    def _only_window(result: dict) -> dict:
        windows = result["windows"]
        assert len(windows) == 1, "fixture runs exactly one measured window"
        return windows[0]

    def test_clean_206_yields_one_usable_observation_and_zero_failures(self) -> None:
        """RED if the clean path reports a phantom failure, drops the
        observation, or counts stale/duplicate on a well-behaved origin."""
        result = self.clean
        self.assertEqual(result["status"], "MEASURED")
        self.assertEqual(result["observations"], 1)
        self.assertEqual(result["usable_observations"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["failure_reasons"], {})
        window = self._only_window(result)
        self.assertEqual(window["failures"], 0)
        self.assertTrue(window["ok"])
        segment = window["segments"][0]
        self.assertTrue(segment["range_ok"])
        self.assertEqual(segment["range_failures"], [])
        self.assertTrue(segment["decode_ok"])
        self.assertEqual(segment["init_data"], "in-band-mpegts")
        # PROT-STALE / PROT-DUP are 0: no stale or duplicate counter fires.
        self.assertNotIn("stale_segment", result["failure_reasons"])
        self.assertNotIn("duplicate_segment", result["failure_reasons"])

    def test_200_full_body_is_counted_as_four_failures_not_discarded(self) -> None:
        """RED if the ignored Range (200) is treated as a success, counted as
        one generic failure, or dropped from the books entirely (R-5)."""
        result = self.full_200
        self.assertEqual(result["status"], "MEASURED")
        # The attempt stays in the books...
        self.assertEqual(result["observations"], 1)
        # ...but is NOT usable and every violated contract point is counted:
        self.assertEqual(result["usable_observations"], 0)
        self.assertEqual(
            result["failure_reasons"],
            {
                "range_not_honored_status_200": 1,
                "content_range_missing_or_malformed": 1,
                "content_length_mismatch": 1,
                "body_length_1048576_expected_512000": 1,
            },
        )
        self.assertEqual(result["failures"], 4)
        window = self._only_window(result)
        self.assertEqual(window["failures"], 1)
        self.assertFalse(window["ok"])
        self.assertFalse(window["segments"][0]["range_ok"])

    def test_missing_init_data_is_counted_as_a_failure(self) -> None:
        """RED if an fMP4 segment without a fetched init segment (PROT-INIT
        = 0) is presented without the missing_init_data failure (R-5)."""
        result = self.missing_init
        self.assertEqual(result["observations"], 1)
        self.assertEqual(result["failure_reasons"], {"missing_init_data": 1})
        self.assertEqual(result["failures"], 1)
        segment = self._only_window(result)["segments"][0]
        self.assertEqual(segment["init_data"], "missing-fmp4-init")

    def test_incomplete_keyframe_is_counted_as_a_failure(self) -> None:
        """RED if capped bytes that yield no usable keyframe (PROT-KEY = 0)
        are counted usable or dropped from the failure total (R-5)."""
        result = self.short_decode
        self.assertEqual(result["observations"], 1)
        self.assertEqual(result["usable_observations"], 0)
        self.assertEqual(result["failure_reasons"], {"incomplete_keyframe": 1})
        self.assertEqual(result["failures"], 1)
        window = self._only_window(result)
        self.assertEqual(window["failures"], 1)
        self.assertFalse(window["ok"])
        segment = window["segments"][0]
        self.assertFalse(segment["decode_ok"])
        self.assertEqual(segment["decode_reason"], "no keyframe decoded")

    def test_regression_and_reannounce_never_fetch_stale_or_duplicate(self) -> None:
        """RED if a regressed playlist re-fetches an older segment (stale)
        or a re-announced sequence is fetched twice (duplicate) — PROT-STALE
        and PROT-DUP must stay 0 and the observation count must not grow."""
        result = self.regression
        self.assertEqual(result["observations"], 1)
        self.assertEqual(result["usable_observations"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["failure_reasons"], {})
        self.assertNotIn("stale_segment", result["failure_reasons"])
        self.assertNotIn("duplicate_segment", result["failure_reasons"])


class CompareArmsTests(unittest.TestCase):
    """compare_arms ratio/threshold arithmetic against hand-computed literals.

    RED if the ratio direction flips, the frozen <= 0.50 boundary becomes
    strict, the p95 bound drifts, or the pair schema/threshold echo changes.
    """

    @staticmethod
    def compare(baseline_total: float, proto_total, p95, failures: int = 0) -> dict:
        baseline = [{
            "profile": "water",
            "status": "MEASURED",
            "total_arm_cpu_s_per_s": baseline_total,
        }]
        prototype = [{
            "profile": "water",
            "status": "MEASURED",
            "total_arm_cpu_s_per_s": proto_total,
            "frame_ready_latency_ms": {"p95": p95},
            "failures": failures,
        }]
        return harness.compare_arms(baseline, prototype)["pairs"][0]

    def test_cpu_ratio_at_frozen_boundary_passes_and_above_fails(self) -> None:
        # Hand-computed: 0.05 / 0.1 = 0.5 (<= 0.50 -> ok);
        # 0.06 / 0.1 = 0.6 (> 0.50 -> breach).
        at_boundary = self.compare(0.1, 0.05, 91.4)
        self.assertEqual(at_boundary["cpu_ratio"], 0.5)
        self.assertTrue(at_boundary["cpu_ratio_ok"])
        above = self.compare(0.1, 0.06, 91.4)
        self.assertEqual(above["cpu_ratio"], 0.6)
        self.assertFalse(above["cpu_ratio_ok"])

    def test_frame_ready_p95_at_frozen_boundary_passes_and_above_fails(self) -> None:
        at_boundary = self.compare(0.1, 0.05, 3000.0)
        self.assertEqual(at_boundary["frame_ready_p95_ms"], 3000.0)
        self.assertTrue(at_boundary["frame_ready_p95_ok"])
        above = self.compare(0.1, 0.05, 3001.0)
        self.assertEqual(above["frame_ready_p95_ms"], 3001.0)
        self.assertFalse(above["frame_ready_p95_ok"])

    def test_pair_schema_and_frozen_thresholds_are_echoed_verbatim(self) -> None:
        """RED if a unit-bearing pair field disappears or any frozen
        threshold number in the report's own copy drifts."""
        pair = self.compare(0.1, 0.05, 91.4, failures=2)
        self.assertEqual(set(pair), PAIR_KEYS)
        self.assertEqual(pair["thresholds"], PAIR_THRESHOLDS)
        self.assertEqual(pair["profile"], "water")
        self.assertEqual(pair["baseline_status"], "MEASURED")
        self.assertEqual(pair["prototype_status"], "MEASURED")
        self.assertEqual(pair["baseline_total_cpu_s_per_s"], 0.1)
        self.assertEqual(pair["prototype_total_cpu_s_per_s"], 0.05)
        self.assertEqual(pair["prototype_failures"], 2)
        self.assertEqual(pair["frame_ready_p95_ms"], 91.4)


# ---------------------------------------------------------------------------
# In-process REAL main() with only the two measurement arms mocked out.
# ---------------------------------------------------------------------------


def _canned_baseline(ffmpeg_path, origin, profile, window_seconds, windows, warmup_seconds) -> dict:
    """Row shaped exactly like run_baseline's measured output (keys
    transcribed from the production result dict), with hand-chosen values."""
    return {
        "status": "MEASURED",
        "profile": profile,
        "mode": "hls-persistent-rawvideo",
        "warmup_seconds": warmup_seconds,
        "window_seconds": window_seconds,
        "windows": [],
        "decoder_cpu_s_per_s": 0.0409,
        "pipeline_cpu_s_per_s": 0.0591,
        "total_arm_cpu_s_per_s": 0.1,
        "frames_delivered": 300,
        "frame_yield": 1.0,
        "stalls": 0,
        "misses": 0,
        "rss_mib": 100.0,
        "verdict": "MEASURED",
        "notes": ["live HLS timeline paced by the loopback origin; no -re/fast-seek flag"],
    }


def _canned_prototype(
    ffmpeg_path, origin, profile, window_seconds, windows, warmup_seconds,
    poll_seconds, range_bytes,
) -> dict:
    """Row shaped exactly like run_prototype's measured output after
    measure_prototype_cpu (keys transcribed from production)."""
    return {
        "status": "MEASURED",
        "profile": profile,
        "mode": "hls-range-first-keyframe",
        "range_bytes": range_bytes,
        "poll_seconds": poll_seconds,
        "warmup_seconds": warmup_seconds,
        "window_seconds": window_seconds,
        "windows": [{
            "index": 0,
            "status": "MEASURED",
            "observations": 3,
            "usable_observations": 3,
            "failures": 0,
            "child_cpu_seconds": 0.0,
            "segments": [],
        }],
        "observations": 3,
        "usable_observations": 3,
        "failures": 0,
        "failure_reasons": {},
        "frame_ready_latency_ms": {"p50": 80.0, "p95": 91.4, "max": 200.0},
        "notes": ["latest complete segment only; Range capped before decode"],
    }


def run_mocked_main(scratch: Path, argv: list, name: str = "report.json"):
    """Run the REAL main() in-process; only the two measurement arms and the
    ffmpeg source generator are mocked.

    Argument parsing, source loading, the loopback Origin lifecycle,
    compare_arms, build_decision and JSON serialization are the production
    code.  The arms are mocked because a real frozen run costs 3 x 60 s per
    profile; their parsed call arguments are captured so the frozen CLI
    defaults remain observable.  read_proc_cpu is pinned to 0.0 so the
    mocked arm's pipeline CPU is deterministic.
    """
    out = scratch / name
    capture: dict = {}

    def generate(ffmpeg_path, out_dir, seconds):
        capture["source_seconds"] = seconds
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "source.m3u8").write_text(FIXTURE_PLAYLIST_200S, encoding="utf-8")
        (out_dir / "seg00000.ts").write_bytes(b"\0" * 64)

    with (
        mock.patch.object(harness, "run_baseline", side_effect=_canned_baseline) as baseline_mock,
        mock.patch.object(harness, "run_prototype", side_effect=_canned_prototype) as prototype_mock,
        mock.patch.object(harness, "read_proc_cpu", return_value=0.0),
        mock.patch.object(harness, "generate_source", side_effect=generate),
    ):
        rc = harness.main(["--output", str(out), "--ffmpeg", BOGUS_FFMPEG, *argv])
    capture["baseline_calls"] = [call.args for call in baseline_mock.call_args_list]
    capture["prototype_calls"] = [call.args for call in prototype_mock.call_args_list]
    report = json.loads(out.read_text(encoding="utf-8"))
    return rc, report, capture, out


class ReportSchemaTests(unittest.TestCase):
    """The real report assembly: exact keys, units, zeros, clean bytes.

    RED if the report drops/renames a top-level section, stops echoing the
    tested SHA, loses a unit-bearing cell or failure counter, leaks the
    output path/hostname/timestamp, or the decision stops matching the
    frozen run's own shape.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.scratch = scratch_dir("report-schema-")
        cls.rc, cls.report, cls.capture, cls.output = run_mocked_main(
            cls.scratch, ["--tested-sha", VALID_SHA]
        )
        cls.serialized = cls.output.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.scratch, ignore_errors=True)

    def test_exact_top_level_schema_and_contract(self) -> None:
        """RED if any top-level key is added, dropped or renamed, or the
        contract id changes (deterministic report structure, R-9)."""
        self.assertEqual(self.rc, 0, "a complete bound run must exit 0")
        self.assertEqual(set(self.report), TOP_LEVEL_KEYS)
        self.assertEqual(self.report["contract"], "issue-703-decoder-grab-baseline-v1")
        self.assertEqual(self.report["issue"], 703)
        self.assertEqual(self.report["not_executed"], [])
        self.assertIsInstance(self.report["duration_seconds"], (int, float))
        self.assertGreaterEqual(self.report["duration_seconds"], 0.0)
        self.assertEqual(set(self.report["decision"]), DECISION_KEYS)

    def test_tested_sha_echo_and_bound_marker(self) -> None:
        """RED if the report stops echoing the SHA it was given or the
        BOUND/UNBOUND marker changes (R-9)."""
        self.assertEqual(self.report["tested_sha"], VALID_SHA)
        self.assertEqual(self.report["binding"], "BOUND")

    def test_frozen_workload_is_echoed_verbatim(self) -> None:
        """RED if any frozen workload/threshold value drifts from the
        spec.md table (AC-002)."""
        self.assertEqual(self.report["frozen"], LITERAL_FROZEN)

    def test_cli_defaults_reproduce_the_frozen_workload(self) -> None:
        """RED if any CLI default stops reproducing the frozen table (R-8):
        the real main() was invoked with no workload overrides, so the
        captured arm calls expose the parsed defaults."""
        baseline_calls = self.capture["baseline_calls"]
        self.assertEqual(len(baseline_calls), 2, "one baseline arm per profile")
        self.assertEqual([call[2] for call in baseline_calls], ["water", "road"])
        for call in baseline_calls:
            with self.subTest(profile=call[2]):
                # (ffmpeg, origin, profile, window_seconds, windows, warmup)
                self.assertEqual(call[3:], (60.0, 3, 10.0))
        prototype_calls = self.capture["prototype_calls"]
        self.assertEqual(len(prototype_calls), 2, "one prototype arm per profile")
        self.assertEqual([call[2] for call in prototype_calls], ["water", "road"])
        for call in prototype_calls:
            with self.subTest(profile=call[2]):
                # (..., window_seconds, windows, warmup, poll, range_bytes)
                self.assertEqual(call[3:], (60.0, 3, 10.0, 1.0, 512000))
        self.assertEqual(self.capture["source_seconds"], 210.0)
        # --profiles / --source-class / --source-dir / --labeled-events
        # defaults observed in the report itself:
        self.assertEqual(self.report["profile_selection"], ["water", "road"])
        self.assertEqual(self.report["source"]["class"], "synthetic")
        self.assertEqual(self.report["source"]["mode"], "generated")
        self.assertEqual(
            self.report["outcome_scope"]["labeled_events"], "UNMEASURED"
        )

    def test_per_profile_cells_carry_units_and_zero_failure_counters(self) -> None:
        """RED if a unit-suffixed cell field or a failure counter (including
        its zero) disappears from either arm or the paired comparison (R-7,
        AC-003/AC-004)."""
        arms = self.report["arms"]
        self.assertEqual(len(arms["baseline"]), 2)
        self.assertEqual([row["profile"] for row in arms["baseline"]], ["water", "road"])
        for row in arms["baseline"]:
            with self.subTest(profile=row["profile"]):
                for field in (
                    "decoder_cpu_s_per_s",
                    "pipeline_cpu_s_per_s",
                    "total_arm_cpu_s_per_s",
                    "frame_yield",
                    "stalls",
                    "misses",
                    "rss_mib",
                ):
                    self.assertIn(field, row, f"baseline cell {field} missing")
                self.assertEqual(row["stalls"], 0)
                self.assertEqual(row["misses"], 0)
        self.assertEqual(len(arms["prototype"]), 2)
        self.assertEqual([row["profile"] for row in arms["prototype"]], ["water", "road"])
        for row in arms["prototype"]:
            with self.subTest(profile=row["profile"]):
                for field in (
                    "cpu_s_per_s",
                    "pipeline_cpu_s_per_s",
                    "total_arm_cpu_s_per_s",
                    "frame_ready_latency_ms",
                    "range_bytes",
                    "poll_seconds",
                ):
                    self.assertIn(field, row, f"prototype cell {field} missing")
                self.assertEqual(set(row["frame_ready_latency_ms"]), {"p50", "p95", "max"})
                self.assertEqual(row["failures"], 0)
                self.assertEqual(row["failure_reasons"], {})
        pairs = self.report["comparison"]["pairs"]
        self.assertEqual(len(pairs), 2)
        self.assertEqual([pair["profile"] for pair in pairs], ["water", "road"])
        for pair in pairs:
            with self.subTest(profile=pair["profile"]):
                self.assertEqual(set(pair), PAIR_KEYS)
                self.assertEqual(pair["thresholds"], PAIR_THRESHOLDS)
                self.assertEqual(pair["prototype_failures"], 0)
                self.assertTrue(pair["cpu_ratio_ok"])
                self.assertTrue(pair["frame_ready_p95_ok"])

    def test_decision_block_matches_the_frozen_synthetic_run(self) -> None:
        """RED if the decision block loses a field or a synthetic bound run
        stops reading measurement GREEN + NO_ADOPTION full outcome (the
        frozen run's own decision shape)."""
        decision = self.report["decision"]
        self.assertEqual(set(decision), DECISION_KEYS)
        self.assertEqual(decision["measurement"], "GREEN")
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED",
        )
        self.assertEqual(decision["reasons"], [])
        self.assertEqual(decision["full_outcome"], "UNMEASURED")
        self.assertTrue(decision["performance_criteria_met"])
        self.assertEqual(self.report["outcome_scope"]["full_outcome"], "UNMEASURED")

    def test_outcome_scope_states_every_required_caveat(self) -> None:
        """RED if an R-10 caveat (synthetic workload, no labeled events,
        HLS-only, frame-ready vs detection latency) is dropped or flipped."""
        scope = self.report["outcome_scope"]
        self.assertEqual(scope["workload_representativeness"], "UNMEASURED")
        self.assertEqual(scope["labeled_events"], "UNMEASURED")
        self.assertEqual(scope["full_outcome"], "UNMEASURED")
        notes = "\n".join(scope["notes"])
        self.assertIn(
            "A generated moving-pattern fixture tests accounting and Range mechanics only.",
            notes,
        )
        self.assertIn("Both arms use HLS; the comparison is HLS-only.", notes)
        self.assertIn("Frame-ready latency is not detection latency.", notes)
        source = self.report["source"]
        self.assertEqual(source["motion"], "synthetic testsrc2 moving pattern")
        self.assertEqual(source["resolution"], "1920x1080")
        self.assertEqual(source["bitrate_kbps"], 2500)
        self.assertEqual(source["segment_format"], "mpegts")
        self.assertEqual(source["codec"], "h264")
        self.assertTrue(source["hls_only"])
        self.assertEqual(source["duration_seconds"], 200.0)
        self.assertEqual(source["segment_count"], 1)
        self.assertRegex(source["fingerprint"], r"^[0-9a-f]{64}$")

    def test_serialized_bytes_have_no_output_path_hostname_or_timestamp(self) -> None:
        """RED if the --output path, repo path, hostname or a timestamp leaks
        into the serialized report (deterministic evidence, R-9)."""
        text = self.serialized
        self.assertNotIn(str(self.output), text, "raw --output path leaked")
        self.assertNotIn(self.output.name, text, "output file name leaked")
        self.assertNotIn(str(ROOT), text, "repo path leaked")
        for host in (platform.node(), os.environ.get("HOSTNAME", "")):
            if len(host) >= 4:
                self.assertNotIn(host, text, f"hostname {host!r} leaked")
        self.assertNotRegex(text, r"\d{4}-\d{2}-\d{2}", "no date in report")
        self.assertNotRegex(text, r"\d{2}:\d{2}:\d{2}", "no clock time in report")
        self.assertNotIn("PASS", text, "the PASS token must never be emitted")

    def test_adoption_eligible_end_to_end_with_approved_source_and_events(self) -> None:
        """RED if a bound run with an approved source and labeled events
        stops reaching ADOPTION_ELIGIBLE (spec decision table, exit 0)."""
        scratch = scratch_dir("report-adoption-")
        try:
            events = scratch / "events.txt"
            events.write_text("evt-a\nevt-b\n", encoding="utf-8")
            rc, report, _, _ = run_mocked_main(
                scratch,
                [
                    "--tested-sha", VALID_SHA,
                    "--source-class", "approved",
                    "--labeled-events", str(events),
                ],
                name="adoption.json",
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        self.assertEqual(rc, 0, "complete adoption-eligible run must exit 0")
        decision = report["decision"]
        self.assertEqual(decision["measurement"], "GREEN")
        self.assertEqual(decision["recommendation"], "ADOPTION_ELIGIBLE")
        self.assertEqual(decision["reasons"], [])
        self.assertTrue(decision["performance_criteria_met"])
        scope = report["outcome_scope"]
        self.assertEqual(scope["full_outcome"], "MEASURED")
        self.assertEqual(scope["labeled_events"], "present:2")
        self.assertEqual(scope["workload_representativeness"], "CLAIMED_BY_OPERATOR")
        self.assertEqual(report["binding"], "BOUND")
        self.assertEqual(report["tested_sha"], VALID_SHA)

    def test_unbound_run_fails_closed_end_to_end(self) -> None:
        """RED if a run without --tested-sha can exit 0 or read like a pass.

        binding UNBOUND, tested_sha the UNBOUND marker, measurement RED
        (spec: measurement is GREEN only when BIND holds), the exact
        NO_ADOPTION recommendation with the binding reason, no PASS token,
        exit code 2.
        """
        scratch = scratch_dir("report-unbound-")
        try:
            rc, report, _, _ = run_mocked_main(scratch, [], name="unbound.json")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        self.assertEqual(
            rc, 2, "an unbound report must fail the CLI closed (never exit 0)"
        )
        self.assertEqual(report["binding"], "UNBOUND")
        self.assertEqual(report["tested_sha"], "UNBOUND")
        decision = report["decision"]
        self.assertEqual(decision["measurement"], "RED")
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — report is UNBOUND",
        )
        self.assertIn(
            "tested SHA is missing or not a full 40-hex commit", decision["reasons"]
        )
        self.assertNotEqual(decision["recommendation"], "ADOPTION_ELIGIBLE")
        self.assertNotIn("PASS", json.dumps(decision))


class RuntimeHonestyTests(unittest.TestCase):
    """No ffmpeg on the host: NOT EXECUTED with the exact reason, no
    fabricated runtime, RED decision (spec runtime-feedback section)."""

    def test_missing_ffmpeg_is_not_executed_with_exact_reason(self) -> None:
        """RED if a host without ffmpeg fabricates numbers, invents a
        runtime build string, or lets the report exit green."""
        scratch = scratch_dir("no-ffmpeg-")
        try:
            out = scratch / "report.json"
            with mock.patch.object(harness.shutil, "which", return_value=None):
                rc = harness.main(
                    ["--output", str(out), "--tested-sha", VALID_SHA]
                )
            report = json.loads(out.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        self.assertEqual(rc, 2)
        self.assertEqual(
            report["not_executed"],
            ["environment lacks ffmpeg", "decoder/prototype arms skipped"],
        )
        self.assertEqual(report["runtime"], {"ffmpeg_build": "unavailable"})
        self.assertEqual(report["arms"], {"baseline": [], "prototype": []})
        self.assertEqual(report["decision"]["measurement"], "RED")
        self.assertIn("baseline arm did not run", report["decision"]["reasons"])
        self.assertIn("prototype arm did not run", report["decision"]["reasons"])


class ArgumentGuardTests(unittest.TestCase):
    """Real-CLI argv guards: no target URL, required --output, SHA binding,
    frozen defaults (spec R-1/R-2/R-9).

    RED if the parser starts accepting a URL-shaped argv, makes --output
    optional, binds a malformed SHA, or the skip-path message stops
    reflecting the default frozen arithmetic (10 + 3 x 60 = 190.0 s).
    """

    def setUp(self) -> None:
        self.scratch = scratch_dir("arg-guard-")

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)

    def test_output_is_required(self) -> None:
        """RED if --output becomes optional: argparse must exit 2 naming it."""
        proc = run_cli()
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(
            "the following arguments are required: --output", proc.stderr
        )

    def test_target_url_option_is_rejected_by_real_cli(self) -> None:
        """RED if a --target option is accepted (spec R-2: no target URL).

        Real subprocess: exit 2 with argparse's unrecognized-arguments error
        naming both the flag and the URL, and no report written.
        """
        out = self.scratch / "never.json"
        proc = run_cli("--output", str(out), "--target", URL_SENTINEL)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("unrecognized arguments: --target", proc.stderr)
        self.assertIn(URL_SENTINEL, proc.stderr)
        self.assertFalse(out.exists(), "rejected argv must not write a report")

    def test_bare_url_argv_is_rejected_by_real_cli(self) -> None:
        """RED if a positional URL argument is accepted (spec R-2)."""
        out = self.scratch / "never.json"
        proc = run_cli("--output", str(out), URL_SENTINEL)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(f"unrecognized arguments: {URL_SENTINEL}", proc.stderr)
        self.assertFalse(out.exists(), "rejected argv must not write a report")

    def test_malformed_tested_sha_fails_closed_unbound(self) -> None:
        """RED if a malformed --tested-sha can bind the report.

        The harness has no argparse-level SHA guard (unlike #690): rejection
        is at binding level — the run must still fail closed with exit 2, a
        report marked UNBOUND (never BOUND), the exact binding reason and
        the UNBOUND recommendation.  tested_sha echoes what it was given.
        """
        source = self.scratch / "src"
        write_short_source(source)
        out = self.scratch / "malformed.json"
        proc = run_cli(
            "--output", str(out),
            "--tested-sha", "not-a-sha",
            "--ffmpeg", BOGUS_FFMPEG,
            "--source-dir", str(source),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["binding"], "UNBOUND")
        self.assertNotEqual(report["binding"], "BOUND")
        self.assertEqual(report["tested_sha"], "not-a-sha")
        decision = report["decision"]
        self.assertEqual(
            decision["measurement"],
            "RED",
            "spec: measurement is GREEN only when BIND holds",
        )
        self.assertEqual(
            decision["recommendation"],
            "NO_ADOPTION_RECOMMENDATION — report is UNBOUND",
        )
        self.assertIn(
            "tested SHA is missing or not a full 40-hex commit", decision["reasons"]
        )
        self.assertNotIn("PASS", json.dumps(decision))

    def test_default_window_arithmetic_in_skip_message(self) -> None:
        """RED if a CLI default drifts from the frozen table: the real skip
        message must read exactly 'source duration 2.0s shorter than frozen
        need 190.0s' (2.0 s fixture; default warm-up 10 s + 3 x 60 s = 190),
        and a valid full 40-hex SHA must still bind the report."""
        source = self.scratch / "src"
        write_short_source(source)
        out = self.scratch / "bound.json"
        proc = run_cli(
            "--output", str(out),
            "--tested-sha", VALID_SHA,
            "--ffmpeg", BOGUS_FFMPEG,
            "--source-dir", str(source),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(FROZEN_NEED_LITERAL, proc.stdout)
        self.assertIn("NOT EXECUTED: decoder/prototype arms skipped", proc.stdout)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["binding"], "BOUND")
        self.assertEqual(report["tested_sha"], VALID_SHA)
        self.assertEqual(report["frozen"], LITERAL_FROZEN)

    def test_dead_segment_seconds_option_is_rejected(self) -> None:
        """RED if the removed --segment-seconds knob returns (rule 31: dead
        mechanisms are deleted entirely).

        The option was parsed but never read by main() — generate_source
        uses FROZEN["segment_seconds"] directly, which stays the real used
        configuration constant (asserted in FrozenThresholdTests).  The real
        CLI must exit 2 with argparse's unrecognized-arguments error and
        write no report; --ffmpeg/--source-dir keep the RED-state run on the
        fast skip path.
        """
        source = self.scratch / "src"
        write_short_source(source)
        out = self.scratch / "segment-seconds.json"
        proc = run_cli(
            "--output", str(out),
            "--segment-seconds", "2.0",
            "--ffmpeg", BOGUS_FFMPEG,
            "--source-dir", str(source),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("unrecognized arguments: --segment-seconds", proc.stderr)
        self.assertFalse(out.exists(), "rejected argv must not write a report")


class FrozenThresholdTests(unittest.TestCase):
    """The FROZEN table equals the literal transcription of spec.md.

    RED if ANY frozen number is relaxed or moved after measurement (NFR-004:
    a threshold is never relaxed after seeing data).
    """

    def test_frozen_table_matches_literal_spec_transcription(self) -> None:
        self.assertEqual(harness.FROZEN, LITERAL_FROZEN)

    def test_mode_tokens_and_profile_fps_are_frozen(self) -> None:
        self.assertEqual(harness.READER_MODE, "hls-persistent-rawvideo")
        self.assertEqual(harness.PROTOTYPE_MODE, "hls-range-first-keyframe")
        self.assertEqual(harness.PROFILE_FPS, {"water": 5.0, "road": 10.0})
        self.assertEqual(harness.FRAME_BYTES, 6220800)


class ScopeGuardTests(unittest.TestCase):
    """Static guards over the harness source: imports, shell, option surface.

    RED on any third-party/production import, shell=True, an option outside
    the exact literal surface, a URL-shaped option or a threshold-relaxation
    knob.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = HARNESS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    @staticmethod
    def _collect_options(tree: ast.AST) -> list:
        options = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    options.append(node.args[0].value)
        return options

    def test_imports_are_stdlib_only_with_no_production_imports(self) -> None:
        """RED on any third-party import (spec R-1), production import or
        relative import — the harness is a standalone measurement tool."""
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
            "no production imports — the harness only measures (R-12)",
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

    def test_option_surface_is_exactly_the_literal_set(self) -> None:
        """RED if any option is added to or removed from the CLI surface
        (spec R-1/R-2/R-8: only these knobs exist)."""
        options = self._collect_options(self.tree)
        self.assertTrue(options, "sanity: the CLI parser must define options")
        self.assertEqual(
            set(options), LITERAL_OPTIONS, "CLI option surface changed"
        )

    def test_no_target_url_option(self) -> None:
        """RED if any argparse option can name a target/URL/host (spec R-2)."""
        options = self._collect_options(self.tree)
        self.assertTrue(options, "sanity: the CLI parser must define options")
        for option in options:
            with self.subTest(option=option):
                self.assertTrue(option.startswith("-"), f"positional arg {option!r}")
                self.assertIsNone(
                    URLISH_OPTION.search(option),
                    f"option {option!r} looks like a target-URL knob",
                )

    def test_no_threshold_relaxation_option(self) -> None:
        """RED if a flag appears that can loosen a frozen threshold
        (NFR-004: a threshold is never relaxed after seeing data).

        "skip" is not banned by the regex — --skip-baseline/--skip-prototype
        are spec-sanctioned investigation flags whose fail-closed behaviour is
        pinned in DecisionOracleTests.test_missing_arm_fails_closed_red —
        and they are the ONLY skip options allowed.
        """
        options = self._collect_options(self.tree)
        self.assertTrue(options, "sanity: the CLI parser must define options")
        for option in options:
            with self.subTest(option=option):
                self.assertIsNone(
                    RELAX_OPTION.search(option),
                    f"option {option!r} looks like a threshold-relaxation knob",
                )
        skip_options = sorted(option for option in options if "skip" in option)
        self.assertEqual(
            skip_options, ["--skip-baseline", "--skip-prototype"],
            "only the two sanctioned investigation skip flags may exist",
        )


if __name__ == "__main__":
    unittest.main()
