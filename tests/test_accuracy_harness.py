"""Issue #695 — offline accuracy harness (black-box CLI tests, tests/** only).

The landed production code is ``scripts/worker/accuracy_harness.py`` (stdlib
CLI: ``python3 scripts/worker/accuracy_harness.py --pairs INPUT --output
REPORT``) plus the committed fixture
``scripts/worker/accuracy_pairs_synthetic_v1.json`` (13 hand-authored cases).
The closed metric contract lives in
``specs/695-offline-accuracy-harness/spec.md``:

- cells A..F over truth x outcome, N = A+B+C+D+E+F;
- false_pass_rate_on_violation = D / (D+E+F)   (F stays in the denominator);
- unknown_fraction             = (C+F) / N;
- recognized_accuracy          = (A+E) / (A+B+D+E);
- zero denominator -> JSON null; empty input rejected; all-unknown valid.

Oracle independence: every expected count and rate in this file is
HAND-COUNTED from the committed fixture's raw labels — the test never imports
``confusion_counts``/``build_report`` to derive an expectation (the arithmetic
oracle asserts literal values, so a scorer formula change cannot be mirrored
into the test). The only direct import of production code is
``rounded_rate`` in the rounding probe, and even there every expectation is a
hand-computed literal (spec NFR-002 explicitly calls for a direct unit probe);
everything else runs the REAL CLI in a subprocess.

External oracle (what proves pass/fail):

    python3 -m pytest tests/test_accuracy_harness.py -q     # this suite
    python3 -m pytest tests/ -q                             # whole battery

RED on base 91570fb (harness absent): every subprocess invocation fails
(FileNotFoundError / nonzero rc) and every report-content assertion fails.
GREEN only when the harness implements the closed contract above. Per-test
RED conditions are stated in each test's docstring. No assertion here was
weakened to obtain green.
"""

from __future__ import annotations

import ast
import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.worker.accuracy_harness import rounded_rate

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "worker" / "accuracy_harness.py"
FIXTURE = ROOT / "scripts" / "worker" / "accuracy_pairs_synthetic_v1.json"

# Determinism scratch per the work order: /tmp/opencode/695-tests/ (ephemeral,
# outside the repo, pre-approved scratch space).
SCRATCH_ROOT = Path("/tmp/opencode/695-tests")

CONTRACT_ID = "sea_speed_accuracy_report_v1"
TOP_LEVEL_KEYS = ("contract", "counts", "dataset_sha256", "rates")

# Hand-counted from the fixture's raw labels (see FixtureIntegrityTests for
# the independent recount that pins this distribution against silent edits):
# truth=pass    x4 pass, x1 non_pass, x2 unknown  -> A=4 B=1 C=2
# truth=non_pass x2 pass, x3 non_pass, x1 unknown -> D=2 E=3 F=1
EXPECTED_COUNTS = {"A": 4, "B": 1, "C": 2, "D": 2, "E": 3, "F": 1}
# Hand-computed: 2/6 = 0.3333333... -> 0.333333; 3/13 = 0.23076923...
# -> 0.230769; 7/10 = 0.7 exactly.
EXPECTED_RATES = {
    "false_pass_rate_on_violation": 0.333333,
    "recognized_accuracy": 0.7,
    "unknown_fraction": 0.230769,
}


def run_harness(pairs: Path, output: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Run the real CLI exactly as documented (R-2), in a subprocess."""
    return subprocess.run(
        [sys.executable, str(HARNESS), "--pairs", str(pairs), "--output", str(output)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def make_rows(count_unknown: int, total: int, truth: str) -> list[dict[str, str]]:
    """``count_unknown`` abstentions plus ``total - count_unknown`` answers,
    all under one truth class (used for tie-sized datasets)."""
    rows = [
        {"id": f"unk-{i:03d}", "truth": truth, "outcome": "unknown"}
        for i in range(count_unknown)
    ]
    rows += [
        {"id": f"ans-{i:03d}", "truth": truth, "outcome": "pass"}
        for i in range(total - count_unknown)
    ]
    return rows


class AccuracyHarnessTestBase(unittest.TestCase):
    """Shared temp-dir plumbing; each case gets its own scratch directory."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-695-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)


class FixtureOracleTests(AccuracyHarnessTestBase):
    """1. INDEPENDENT ARITHMETIC ORACLE on the committed fixture (SC-4).

    Expected values are hand-counted literals — never derived by calling the
    scorer. RED if the harness is absent (subprocess fails), if any cell is
    miscounted (e.g. B counted as D), if a formula changed (rate literals
    mismatch), if the contract id changed, or if the fingerprint is not a
    64-hex SHA256. A report object with extra/missing top-level keys (e.g. a
    timestamp or git field sneaking in) also fails.
    """

    def test_fixture_report_matches_hand_counted_oracle(self) -> None:
        output = self.tmp / "report.json"
        completed = run_harness(FIXTURE, output, ROOT)
        self.assertEqual(
            completed.returncode,
            0,
            f"harness failed on the committed fixture\n"
            f"stdout: {completed.stdout!r}\nstderr: {completed.stderr!r}",
        )
        report = json.loads(output.read_text(encoding="utf-8"))

        self.assertIsInstance(report, dict, "the report must be a JSON object")
        self.assertEqual(
            tuple(sorted(report)),
            tuple(sorted(TOP_LEVEL_KEYS)),
            "report must have exactly the four contract top-level keys "
            f"{TOP_LEVEL_KEYS}; observed {sorted(report)}",
        )

        self.assertEqual(report["contract"], CONTRACT_ID)

        counts = report["counts"]
        self.assertEqual(
            counts,
            EXPECTED_COUNTS,
            "hand-counted cell distribution A,B,C=4,1,2 D,E,F=2,3 (N=13) "
            "changed — either the fixture labels or the scoring formula moved",
        )
        self.assertTrue(
            all(type(value) is int for value in counts.values()),
            f"cell counts must be JSON integers, got {counts!r}",
        )
        self.assertEqual(sum(counts.values()), 13, "N must be 13")

        self.assertEqual(
            report["rates"],
            EXPECTED_RATES,
            "closed-contract rates changed (2/6 -> 0.333333, 3/13 -> "
            "0.230769, 7/10 -> 0.7 at 6 decimals)",
        )

        fingerprint = report["dataset_sha256"]
        self.assertIsInstance(fingerprint, str)
        self.assertRegex(
            fingerprint,
            r"^[0-9a-f]{64}$",
            "dataset_sha256 must be 64 lowercase hex chars",
        )


class DeterminismTests(AccuracyHarnessTestBase):
    """2. DETERMINISM (SC-1 / AC-001 / NFR-001): byte-identical reports from
    two different cwd with reversed input rows, and no environment-derived
    state in the bytes.

    RED if: the fingerprint depended on input iteration order (reversed rows
    change bytes), serialization embedded a timestamp/hostname/cwd/output path
    (bytes differ between runs, or the environment scan finds the string),
    or the harness is absent (subprocess fails).
    """

    def setUp(self) -> None:
        super().setUp()
        # Scratch under /tmp/opencode/695-tests/ per the work order; two
        # sibling directories, one per cwd so the cwd itself is observable.
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.work_a = Path(tempfile.mkdtemp(dir=SCRATCH_ROOT, prefix="cwd-a-"))
        self.work_b = Path(tempfile.mkdtemp(dir=SCRATCH_ROOT, prefix="cwd-b-"))
        self.addCleanup(self._cleanup_scratch)

    def _cleanup_scratch(self) -> None:
        for directory in (self.work_a, self.work_b):
            for path in sorted(directory.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            directory.rmdir()

    def test_reversed_rows_from_other_cwd_yield_identical_bytes(self) -> None:
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
        reversed_pairs = self.work_b / "pairs-reversed.json"
        reversed_pairs.write_text(
            json.dumps(list(reversed(rows)), ensure_ascii=False), encoding="utf-8"
        )
        # Prove the second input really is the reversed row order.
        self.assertEqual(len(rows), 13)
        self.assertEqual(json.loads(reversed_pairs.read_text(encoding="utf-8"))[0]["id"], "synthetic-case-13")

        report_a = self.work_a / "report-root.json"
        report_b = self.work_b / "report-tmp.json"

        completed_a = run_harness(FIXTURE, report_a, cwd=ROOT)
        self.assertEqual(
            completed_a.returncode,
            0,
            f"run A (cwd=repo root, fixture rows) failed\n"
            f"stderr: {completed_a.stderr!r}",
        )
        completed_b = run_harness(reversed_pairs, report_b, cwd=self.work_b)
        self.assertEqual(
            completed_b.returncode,
            0,
            f"run B (cwd=temp dir, reversed rows) failed\n"
            f"stderr: {completed_b.stderr!r}",
        )

        bytes_a = report_a.read_bytes()
        bytes_b = report_b.read_bytes()
        self.assertEqual(
            bytes_a,
            bytes_b,
            "SC-1: reports must be byte-identical across cwd and row order "
            "(order-sensitive fingerprint or non-deterministic serialization)",
        )
        self.assertTrue(bytes_a.endswith(b"\n"), "report must end with one LF")
        self.assertFalse(bytes_a.endswith(b"\n\n"), "exactly one trailing LF")

        self._assert_no_environment_state(bytes_a, report_a, report_b, reversed_pairs)

    def _assert_no_environment_state(
        self, payload: bytes, *paths: Path
    ) -> None:
        text = payload.decode("utf-8")
        needles = [str(ROOT), str(self.work_a), str(self.work_b), FIXTURE.name]
        needles += [str(path) for path in paths]
        needles += [path.name for path in paths]
        for needle in needles:
            self.assertNotIn(
                needle,
                text,
                "report bytes must not embed cwd, input or output paths "
                f"(found {needle!r})",
            )
        for host in (platform.node(), os.environ.get("HOSTNAME", "")):
            if len(host) >= 4:
                self.assertNotIn(
                    host, text, "report bytes must not embed the hostname"
                )
        # Timestamp shapes: dashed dates and clock times (the hex fingerprint
        # can contain neither dashes nor colons, so these cannot false-hit).
        self.assertNotRegex(text, r"\d{4}-\d{2}-\d{2}", "no date in report")
        self.assertNotRegex(text, r"\d{2}:\d{2}:\d{2}", "no clock time in report")


class ZeroDenominatorTests(AccuracyHarnessTestBase):
    """3. ZERO DENOMINATORS (SC-2 / R-5): null, never NaN/0/perfect score.

    Two directions of the zero-denominator rule, both hand-checked:

    (a) all-unknown input WITH both truth classes: recognized_accuracy has a
        0/0 denominator (A=B=D=E=0) -> JSON null; unknown_fraction = 5/5 =
        1.0; false_pass_rate_on_violation = D/(D+E+F) = 0/3 = 0.0 because
        the three truth=non_pass abstentions are F and spec AC-005 keeps F in
        the false-pass denominator (so the denominator is NOT zero here).
    (b) all-unknown input with ONLY truth=pass rows: D+E+F = 0 ->
        false_pass_rate_on_violation is JSON null (the "no actual
        non-passes" direction of the work order), recognized_accuracy null,
        unknown_fraction 1.0.

    RED if: a zero denominator is serialized as 0, 1.0, "NaN" or a string;
    if all-unknown input is rejected; if abstentions leak into B/D/E; or if
    the harness is absent.
    """

    def score(self, rows: list[dict[str, str]], name: str) -> tuple[dict, bytes]:
        pairs = self.tmp / f"{name}.json"
        output = self.tmp / f"{name}-report.json"
        pairs.write_text(json.dumps(rows), encoding="utf-8")
        completed = run_harness(pairs, output, ROOT)
        self.assertEqual(
            completed.returncode,
            0,
            f"all-unknown input must be valid (R-5)\n"
            f"stderr: {completed.stderr!r}",
        )
        raw = output.read_bytes()
        self.assertNotIn(b"NaN", raw, "no NaN in report")
        self.assertNotIn(b"Infinity", raw, "no Infinity in report")
        return json.loads(raw), raw

    def test_all_unknown_with_both_truth_classes(self) -> None:
        rows = [
            {"id": f"unk-{i}", "truth": truth, "outcome": "unknown"}
            for i, truth in enumerate(
                ["pass", "pass", "non_pass", "non_pass", "non_pass"]
            )
        ]
        report, raw = self.score(rows, "all-unknown-both")
        self.assertEqual(
            report["counts"],
            {"A": 0, "B": 0, "C": 2, "D": 0, "E": 0, "F": 3},
            "abstentions belong in C/F only, never in B/D/E",
        )
        rates = report["rates"]
        self.assertIsNone(
            rates["recognized_accuracy"],
            "0/0 denominator must serialize as JSON null — never 0, NaN or "
            "a perfect score",
        )
        self.assertIn(b'"recognized_accuracy": null', raw)
        self.assertEqual(
            rates["unknown_fraction"], 1.0, "every case abstained -> 1.0"
        )
        # D/(D+E+F) = 0/3 here: F=3 actual non-passes stay in the
        # denominator (spec AC-005), so the rate is a real 0.0, not null.
        self.assertEqual(rates["false_pass_rate_on_violation"], 0.0)

    def test_all_unknown_pass_truth_only_nulls_false_pass_rate(self) -> None:
        rows = [
            {"id": f"pass-unk-{i}", "truth": "pass", "outcome": "unknown"}
            for i in range(3)
        ]
        report, raw = self.score(rows, "all-unknown-pass-only")
        self.assertEqual(
            report["counts"],
            {"A": 0, "B": 0, "C": 3, "D": 0, "E": 0, "F": 0},
        )
        rates = report["rates"]
        self.assertIsNone(
            rates["recognized_accuracy"],
            "0/0 denominator must serialize as JSON null",
        )
        self.assertIn(b'"recognized_accuracy": null', raw)
        self.assertIsNone(
            rates["false_pass_rate_on_violation"],
            "no truth=non_pass rows -> D+E+F = 0 -> JSON null (never 0 or "
            "a perfect score)",
        )
        self.assertIn(b'"false_pass_rate_on_violation": null', raw)
        self.assertEqual(rates["unknown_fraction"], 1.0)


class InvalidInputTests(AccuracyHarnessTestBase):
    """4. INVALID INPUT (SC-3 / AC-004 / R-3): exit 2, output untouched.

    Every malformed input must exit exactly 2, leave a pre-existing valid
    report byte-identical (validation happens before the output is opened),
    and never create a report at a fresh output path. A VALID input with
    terrible accuracy still exits 0 — the harness is not a CI gate.

    RED if: any case exits 0 (contract not enforced), exits something other
    than 2, prints nothing on stderr, truncates/replaces the previous report,
    creates a fresh output for invalid input, or if poor accuracy makes the
    harness exit nonzero (CI-threshold behaviour).
    """

    INVALID_CASES = (
        ("empty array", "[]"),
        (
            "duplicate ids",
            json.dumps(
                [
                    {"id": "dup-case", "truth": "pass", "outcome": "pass"},
                    {"id": "dup-case", "truth": "non_pass", "outcome": "non_pass"},
                ]
            ),
        ),
        ("blank id", json.dumps([{"id": "   ", "truth": "pass", "outcome": "pass"}])),
        ("missing field", json.dumps([{"id": "m1", "truth": "pass"}])),
        (
            "extra field",
            json.dumps(
                [{"id": "e1", "truth": "pass", "outcome": "pass", "note": "x"}]
            ),
        ),
        (
            "non-string field",
            json.dumps([{"id": "n1", "truth": 7, "outcome": "pass"}]),
        ),
        (
            "unknown truth",
            json.dumps([{"id": "t1", "truth": "PASS", "outcome": "pass"}]),
        ),
        (
            "unknown outcome",
            json.dumps([{"id": "o1", "truth": "pass", "outcome": "maybe"}]),
        ),
        ("malformed JSON", '[{"id": "broken"'),
        (
            "non-array root",
            json.dumps({"id": "r1", "truth": "pass", "outcome": "pass"}),
        ),
        (
            "duplicated JSON object keys",
            '[{"id": "k1", "truth": "pass", "outcome": "pass", "id": "k2"}]',
        ),
    )

    def setUp(self) -> None:
        super().setUp()
        self.pairs = self.tmp / "pairs.json"
        self.output = self.tmp / "report.json"
        completed = run_harness(FIXTURE, self.output, ROOT)
        self.assertEqual(
            completed.returncode,
            0,
            f"baseline valid run failed\nstderr: {completed.stderr!r}",
        )
        self.baseline = self.output.read_bytes()

    def test_invalid_inputs_exit_2_and_leave_previous_report_untouched(
        self,
    ) -> None:
        for label, content in self.INVALID_CASES:
            with self.subTest(case=label):
                self.pairs.write_text(content, encoding="utf-8")

                # (i) pre-existing valid report at the output path survives.
                completed = run_harness(self.pairs, self.output, ROOT)
                self.assertEqual(
                    completed.returncode,
                    2,
                    f"{label}: invalid input must exit 2 (got "
                    f"{completed.returncode})\nstderr: {completed.stderr!r}",
                )
                self.assertIn(
                    "invalid pairs input",
                    completed.stderr,
                    f"{label}: must report a clear input error on stderr",
                )
                self.assertEqual(
                    self.output.read_bytes(),
                    self.baseline,
                    f"{label}: a pre-existing valid report must keep its "
                    "exact bytes (R-3: validate before opening the output)",
                )

                # (ii) a fresh output path is never created for bad input.
                fresh = self.tmp / "fresh-report.json"
                if fresh.exists():
                    fresh.unlink()
                completed_fresh = run_harness(self.pairs, fresh, ROOT)
                self.assertEqual(
                    completed_fresh.returncode,
                    2,
                    f"{label}: invalid input must exit 2 (fresh output run)",
                )
                self.assertFalse(
                    fresh.exists(),
                    f"{label}: no report may be written for invalid input",
                )

    def test_valid_input_with_poor_accuracy_exits_zero(self) -> None:
        """A valid dataset where every answer is wrong still scores rc=0 —
        the harness must never act as a CI threshold (spec: "not a CI gate")."""
        rows = [
            {"id": f"wrong-{i}", "truth": "pass", "outcome": "non_pass"}
            for i in range(4)
        ]
        pairs = self.tmp / "poor.json"
        output = self.tmp / "poor-report.json"
        pairs.write_text(json.dumps(rows), encoding="utf-8")
        completed = run_harness(pairs, output, ROOT)
        self.assertEqual(
            completed.returncode,
            0,
            f"valid input with poor accuracy must exit 0 (not a CI gate)\n"
            f"stderr: {completed.stderr!r}",
        )
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["counts"]["B"], 4)
        self.assertEqual(
            report["rates"]["recognized_accuracy"],
            0.0,
            "0 correct of 4 answered -> 0.0, still exit 0",
        )

    # -- peer-review findings: inputs that must be InputError, not crashes --

    def test_lone_surrogate_id_exits_2_and_keeps_previous_report(self) -> None:
        """F1 (peer review): a lone-surrogate id must be an input error.

        RED on current code: ``load_rows`` accepts the lone surrogate (it is
        a nonblank unique str), then ``dataset_fingerprint`` calls
        ``.encode("utf-8")`` on the canonical JSON and raises
        UnicodeEncodeError, which ``main`` does not catch -> exit 1 with a
        traceback instead of the contract's exit 2 (and no "invalid pairs
        input" on stderr). Output is not written either way (fail-closed),
        so the byte-identical assertion holds; the exit-code assertion is
        what fails.

        The surrogate is built at RUNTIME (``chr(0xD800)``) and serialized
        with ``json.dumps``' default ensure_ascii escaping, so the file
        bytes carry the JSON ``\\ud800`` escape — no surrogate or
        credential-shaped literal appears in this source file.
        """
        content = json.dumps(
            [{"id": chr(0xD800), "truth": "pass", "outcome": "pass"}]
        )
        self.pairs.write_text(content, encoding="utf-8")
        self.assertIn(
            b"\\ud800",
            self.pairs.read_bytes(),
            "the pairs file must carry the JSON \\ud800 escape, not a raw "
            "surrogate character",
        )
        completed = run_harness(self.pairs, self.output, ROOT)
        self.assertEqual(
            completed.returncode,
            2,
            "F1: a lone-surrogate id must exit 2 as an input error, not "
            f"crash the fingerprint encoder\nstderr: {completed.stderr!r}",
        )
        self.assertIn("invalid pairs input", completed.stderr)
        self.assertEqual(
            self.output.read_bytes(),
            self.baseline,
            "F1: a pre-existing valid report must keep its exact bytes",
        )

    def test_deeply_nested_json_exits_2_and_keeps_previous_report(self) -> None:
        """F2 (peer review): a pathologically nested array must be an input
        error, not an interpreter crash.

        RED on current code: ``json.loads`` on ``"[" * 100000`` raises
        RecursionError, which is neither ``JSONDecodeError`` nor
        ``InputError``, so ``main`` does not catch it -> exit 1 with a
        traceback instead of exit 2 (and no "invalid pairs input" on
        stderr). The previous report stays untouched either way; the
        exit-code assertion is what fails.
        """
        self.pairs.write_text("[" * 100000, encoding="utf-8")
        completed = run_harness(self.pairs, self.output, ROOT)
        self.assertEqual(
            completed.returncode,
            2,
            "F2: deeply nested input must exit 2 as an input error, not "
            f"raise RecursionError\nstderr: {completed.stderr!r}",
        )
        self.assertIn("invalid pairs input", completed.stderr)
        self.assertEqual(
            self.output.read_bytes(),
            self.baseline,
            "F2: a pre-existing valid report must keep its exact bytes",
        )


class RoundingTests(AccuracyHarnessTestBase):
    """5. ROUNDING (R-6 / NFR-002): exact fractions, 6 decimals,
    nearest-ties-to-even — pinned with HAND-COMPILED literals (expectations
    are never derived by calling rounded_rate).

    Tie cases (7th decimal exactly 5):
      1/128 = 0.0078125 -> 0.007812 (preceding digit 2 is even -> down)
      3/128 = 0.0234375 -> 0.023438 (preceding digit 7 is odd   -> up)

    RED if: rounding is half-up (0.0078125 -> 0.007813), if float drift
    changes a boundary (e.g. 3/13), if 0/0 returns 0 instead of None, or if
    serialization re-rounds the value (end-to-end tie test).
    """

    def test_rounded_rate_half_even_six_decimals_unit_probe(self) -> None:
        # Non-tie fractions (spec NFR-002 direct unit probe).
        self.assertEqual(rounded_rate(1, 3), 0.333333)   # 0.3333333...
        self.assertEqual(rounded_rate(3, 13), 0.230769)  # 0.23076923...
        self.assertEqual(rounded_rate(7, 10), 0.7)       # exact
        # Ties at the 7th decimal: half-to-EVEN both ways.
        self.assertEqual(
            rounded_rate(1, 128),
            0.007812,
            "0.0078125 must tie to the even neighbour 0.007812 (half-up "
            "would give 0.007813)",
        )
        self.assertEqual(
            rounded_rate(3, 128),
            0.023438,
            "0.0234375 must tie to the even neighbour 0.023438 (half-down "
            "would give 0.023437)",
        )
        # Zero denominator / zero numerator.
        self.assertIsNone(rounded_rate(0, 0))
        self.assertEqual(rounded_rate(0, 5), 0.0)

    def test_half_even_tie_survives_cli_serialization(self) -> None:
        """End-to-end: a tie-sized dataset through the real CLI must come back
        with the hand-computed tie values (proves rounding is not recomputed
        or degraded during JSON serialization)."""
        for count_unknown, expected in ((1, 0.007812), (3, 0.023438)):
            with self.subTest(unknown=count_unknown):
                rows = make_rows(count_unknown, total=128, truth="pass")
                pairs = self.tmp / f"tie-{count_unknown}.json"
                output = self.tmp / f"tie-{count_unknown}-report.json"
                pairs.write_text(json.dumps(rows), encoding="utf-8")
                completed = run_harness(pairs, output, ROOT)
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"stderr: {completed.stderr!r}",
                )
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["counts"]["C"], count_unknown)
                self.assertEqual(
                    report["rates"]["unknown_fraction"],
                    expected,
                    f"{count_unknown}/128 is an exact half at the 7th decimal "
                    "and must round half-to-even",
                )


class FixtureIntegrityTests(AccuracyHarnessTestBase):
    """6. FIXTURE INTEGRITY: the committed fixture still has 13 unique
    synthetic ids and exactly the hand-counted cell distribution.

    RED if a future edit to scripts/worker/accuracy_pairs_synthetic_v1.json
    silently changes labels, drops/duplicates/renames a case, or adds a
    non-synthetic id — the hand-counted oracle in FixtureOracleTests would no
    longer describe this file, so this guard fails first and loudly.
    """

    def test_committed_fixture_ids_and_cell_distribution(self) -> None:
        self.assertEqual(
            FIXTURE.name, "accuracy_pairs_synthetic_v1.json", "R-9 file name"
        )
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))

        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 13, "the frozen fixture has 13 cases")
        ids = [row["id"] for row in rows]
        self.assertEqual(
            ids,
            [f"synthetic-case-{i:02d}" for i in range(1, 14)],
            "ids must stay unique, ordered and explicitly synthetic",
        )
        self.assertEqual(len(set(ids)), 13, "ids must be unique")
        for row in rows:
            self.assertEqual(set(row), {"id", "truth", "outcome"})
            self.assertIn(row["truth"], {"pass", "non_pass"})
            self.assertIn(row["outcome"], {"pass", "non_pass", "unknown"})

        # Independent recount straight from the raw labels using the spec's
        # cell definitions (NOT the scorer's confusion_counts).
        def cell(truth: str, outcome: str) -> int:
            return sum(
                1
                for row in rows
                if row["truth"] == truth and row["outcome"] == outcome
            )

        counts = {
            "A": cell("pass", "pass"),
            "B": cell("pass", "non_pass"),
            "C": cell("pass", "unknown"),
            "D": cell("non_pass", "pass"),
            "E": cell("non_pass", "non_pass"),
            "F": cell("non_pass", "unknown"),
        }
        self.assertEqual(
            counts,
            EXPECTED_COUNTS,
            "frozen decision distribution A,B,C=4,1,2 D,E,F=2,3 changed — "
            "the hand-counted oracle in this suite no longer matches",
        )
        self.assertEqual(sum(counts.values()), 13)


class ScopeGuardTests(AccuracyHarnessTestBase):
    """7. SCOPE GUARD (static, source-text; R-1 / NFR-004): the harness stays
    stdlib-only with no network/git/clock imports and carries no CI
    threshold.

    RED if any import outside the documented allowlist appears (socket, urllib,
    subprocess, git, datetime, time, os, ...), or if threshold/gate wording or
    environment reads appear in the source. The behavioural half of "not a CI
    gate" is InvalidInputTests.test_valid_input_with_poor_accuracy_exits_zero.
    """

    # NFR-004 evidence: "imports are argparse, hashlib, json, sys and pathlib
    # only" (+ __future__ annotations).
    ALLOWED_IMPORT_ROOTS = {"__future__", "argparse", "hashlib", "json", "sys", "pathlib"}

    @staticmethod
    def imported_roots(source: str) -> set[str]:
        roots: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        return roots

    def test_harness_imports_are_exactly_the_stdlib_allowlist(self) -> None:
        source = HARNESS.read_text(encoding="utf-8")
        observed = self.imported_roots(source)
        self.assertEqual(
            observed,
            self.ALLOWED_IMPORT_ROOTS,
            "R-1/NFR-004: the harness must import exactly the stdlib "
            "allowlist — no network (socket/urllib/requests), no git, no "
            "clock (datetime/time), no os/env, no subprocess",
        )

    def test_harness_contains_no_ci_threshold_or_environment_state(self) -> None:
        source = HARNESS.read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"(?i)threshold|accuracy[_ ]?gate|ci[_ ]?gate|"
            r"minimum[_ ]accuracy|min[_ ]accuracy|fail[_ ]?(?:if|below)",
            "the harness is an offline reporter, not a CI gate (R-1/spec "
            "boundary): no accuracy threshold may appear in its source",
        )
        self.assertNotIn("environ", source, "no environment state may be read")
        self.assertNotIn("getenv", source, "no environment state may be read")


if __name__ == "__main__":
    unittest.main()
