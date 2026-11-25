"""Issue #704 — offline ROI crop baseline harness.

The production side landed with the code worker (the stdlib-only
``scripts/worker/roi_crop_baseline.py`` experiment plus its SDD trio); these
tests pin the OUTCOMES of ``specs/704-roi-crop-baseline/`` — never the
mechanism beyond what an observable requires. Synthetic frames only: no media,
no weights, no labeled replay, nothing private.

Sections (one class each):

* ``RoiCropGeometryRoundTripTests`` — for each of the six frozen scenarios
  (nonzero_offset, nonrectangular, edge_clipped, no_roi, degenerate_bounds,
  outside_frame) the crop → "inference" → reverse-shift round trip returns the
  accepted AND diagnostic boxes exactly equal to the original full-frame
  coordinates, with the literal clipped crop bounds asserted per scenario
  (nonzero offsets, nonrectangular masks, edge clipping, the two full-frame
  fallbacks and the outside-frame fallback all handled). The harness's own
  ``verify_scenario`` oracle must agree.
* ``RoiCropReportRefusalTests`` — a real report run refuses adoption: the
  decision is exactly ``NO ADOPTION / insufficient evidence`` with
  ``adoption is False``, all ten required cells are present with reasons, every
  unmeasured cell carries the literal ``UNMEASURED`` marker instead of a
  number, and the measured cells are model-free preprocessing only.
* ``RoiCropThresholdTests`` — ``ADOPTION_THRESHOLDS`` is a module-level
  constant declared before any measurement, is echoed verbatim into the report
  (``frozen`` and ``decision``), and editing ONLY the measurement section can
  never produce adoption while quality / workload identity stay unmeasured.
* ``RoiCropScopeGuardTests`` — the pinned change set touches only
  ``tests/``, the harness script and ``specs/704-roi-crop-baseline/``;
  ``worker/``, ``api/``, ``deploy/``, ``.github/`` and lockfiles are
  forbidden, with the pinned-range + fail-closed pattern used by #696/#701.

Environment: the battery is stdlib-only (``scripts/run_tests.py``), and so is
the harness — no third-party import is needed to run any test here.

RED spot-check (what fails on base ``36f28bec2c434dd60e682c5741159ae6c13b7df4``,
before the production change; measured by running this file against a
``git archive`` of the base):

* Every harness test fails at ``load_harness()`` — the base tree has no
  ``scripts/worker/roi_crop_baseline.py`` at all (``FileNotFoundError`` from
  the loader), so there is no report, no geometry function, no thresholds and
  no decision to assert.
* The scope guard's two change-set tests cannot run against a ``git archive``
  extract (no ``.git`` → the fail-closed ``git diff`` raises), which is an
  artifact of the RED harness, not of the base code; its synthetic-predicate
  test is tree-independent and stays GREEN.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "worker" / "roi_crop_baseline.py"

COMMIT40 = "0123456789abcdef0123456789abcdef01234567"

# Issue #704 scope-guard pins: the #701 merge commit (this branch's point)
# and this branch's tip. HEAD_SHA stays the literal "HEAD" only until #704
# merges — then it MUST be re-pinned to the #704 merge commit, the same
# merge-time duty as #696/#701, so a later issue's branch never diffs against
# a moving HEAD and false-positives against #704's allowlist.
BASE_SHA = "36f28bec2c434dd60e682c5741159ae6c13b7df4"
HEAD_SHA = "HEAD"


def load_harness():
    """Import scripts/worker/roi_crop_baseline.py by its runtime path.

    The module must be registered in ``sys.modules`` BEFORE exec: its
    ``@dataclass`` decorator resolves annotations through
    ``sys.modules[cls.__module__]`` and raises AttributeError otherwise. On
    base 36f28b the file does not exist, so this raises FileNotFoundError —
    the RED signal for every harness test in this file.
    """
    spec = importlib.util.spec_from_file_location("roi_crop_baseline_704", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_report(tmp: Path, *, tested_sha: str = COMMIT40) -> dict:
    """Run the harness script and return the JSON report it writes.

    A SUBPROCESS (the harness's documented usage) rather than an in-process
    ``main()`` call: the battery's guarded-optional suites leave stub modules
    in ``sys.modules`` — a spec-less ``cv2`` stub makes the harness's own
    ``importlib.util.find_spec("cv2")`` raise ``ValueError`` — and a fresh
    interpreter keeps this test independent of whatever ran before it while
    exercising the real CLI end to end.
    """
    if not HARNESS_PATH.is_file():
        raise FileNotFoundError(f"the #704 harness does not exist: {HARNESS_PATH}")
    output = tmp / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(HARNESS_PATH),
            "--output",
            str(output),
            "--tested-sha",
            tested_sha,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"harness exited {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if not output.is_file():
        raise AssertionError("harness exited 0 but wrote no report")
    return json.loads(output.read_text(encoding="utf-8"))


# The six frozen scenarios in issue order, with their literal clipped crop
# bounds (bounding box of the polygon, clipped to the 1920x1080 frame; fewer
# than three points, zero area or empty clipped bounds fall back to the full
# frame): (mode, reason, x0, y0, x1, y1, width, height, clipped).
EXPECTED_CROPS = {
    "nonzero_offset": ("crop", "ok", 320, 180, 1280, 900, 960, 720, False),
    "nonrectangular": ("crop", "ok", 200, 120, 1500, 950, 1300, 830, False),
    "edge_clipped": ("crop", "ok", 0, 100, 1900, 1080, 1900, 980, True),
    "no_roi": ("full-frame", "no-roi", 0, 0, 1920, 1080, 1920, 1080, False),
    "degenerate_bounds": (
        "full-frame",
        "degenerate-zero-area",
        0,
        0,
        1920,
        1080,
        1920,
        1080,
        False,
    ),
    "outside_frame": ("full-frame", "outside-frame", 0, 0, 1920, 1080, 1920, 1080, True),
}

# The ten cells the report must refuse on, in report order.
EXPECTED_UNMEASURED_CELLS = [
    "baseline.preprocess_mask_cost",
    "baseline.inference_cpu_seconds_per_frame",
    "candidate.inference_cpu_seconds_per_frame",
    "baseline.inference_latency_ms",
    "candidate.inference_latency_ms",
    "baseline.end_to_end_latency_ms",
    "candidate.end_to_end_latency_ms",
    "quality",
    "workload_identity",
    "child_cpu_seconds_per_frame",
]

# Literal synthetic full-frame boxes (no media): one inside a typical ROI,
# one large box near the far corner, one in the frame corner.
ACCEPTED_RECORDS = [
    {"track_id": 0, "class_name": "car", "bbox_xyxy": [100, 120, 260, 300]},
    {"track_id": 1, "class_name": "truck", "bbox_xyxy": [1400, 700, 1780, 1010]},
    {"track_id": 2, "class_name": "car", "bbox_xyxy": [5, 5, 55, 55]},
]
DIAGNOSTIC_RECORDS = [
    {
        "track_id": 0,
        "semantic_class": "vessel",
        "class_mapping_accepted": True,
        "bbox_xyxy": [100, 120, 260, 300],
    },
    {
        "track_id": 1,
        "semantic_class": "buoy",
        "class_mapping_accepted": False,
        "bbox_xyxy": [1400, 700, 1780, 1010],
    },
    {
        "track_id": 2,
        "semantic_class": "vessel",
        "class_mapping_accepted": True,
        "bbox_xyxy": [5, 5, 55, 55],
    },
]


# ---------------------------------------------------------------------------
# 1. geometry round-trip: crop -> "infer" -> reverse shift is exact
# ---------------------------------------------------------------------------


class RoiCropGeometryRoundTripTests(unittest.TestCase):
    def test_six_scenarios_round_trip_to_the_original_full_frame_boxes(self) -> None:
        """Every scenario restores accepted AND diagnostic boxes byte-exactly.

        The coordinate contract under test: boxes are moved into crop space by
        ``(-x0, -y0)`` and back by ``(+x0, +y0)`` with exact integer
        arithmetic, so the reverse shift returns the original full-frame
        coordinates for both record kinds in all six geometry cases.
        """
        harness = load_harness()

        self.assertEqual(
            [scenario["name"] for scenario in harness.SCENARIOS],
            list(EXPECTED_CROPS),
            "the six frozen scenarios, in issue order",
        )

        for scenario in harness.SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                crop = harness.resolve_crop(scenario["points"])
                self.assertEqual(
                    (
                        crop.mode,
                        crop.reason,
                        crop.x0,
                        crop.y0,
                        crop.x1,
                        crop.y1,
                        crop.width,
                        crop.height,
                        crop.clipped,
                    ),
                    EXPECTED_CROPS[scenario["name"]],
                    f"{scenario['name']}: literal clipped crop bounds",
                )

                # crop -> "inference" -> reverse shift (model-free: inference
                # itself is UNMEASURED, only the coordinate contract is proven)
                accepted_crop = harness.shift_records(ACCEPTED_RECORDS, -crop.x0, -crop.y0)
                accepted_back = harness.shift_records(accepted_crop, crop.x0, crop.y0)
                self.assertEqual(
                    accepted_back,
                    ACCEPTED_RECORDS,
                    f"{scenario['name']}: accepted boxes must round-trip exactly",
                )
                diagnostic_crop = harness.shift_records(DIAGNOSTIC_RECORDS, -crop.x0, -crop.y0)
                diagnostic_back = harness.shift_records(diagnostic_crop, crop.x0, crop.y0)
                self.assertEqual(
                    diagnostic_back,
                    DIAGNOSTIC_RECORDS,
                    f"{scenario['name']}: diagnostic boxes must round-trip exactly",
                )

                if crop.mode == "crop":
                    # The crop step really moved the boxes (exact -x0/-y0).
                    self.assertEqual(
                        accepted_crop[0]["bbox_xyxy"],
                        [100 - crop.x0, 120 - crop.y0, 260 - crop.x0, 300 - crop.y0],
                        "crop-space coordinates are the full-frame box minus the offset",
                    )
                    self.assertEqual(
                        diagnostic_crop[2]["bbox_xyxy"],
                        [5 - crop.x0, 5 - crop.y0, 55 - crop.x0, 55 - crop.y0],
                    )
                else:
                    # Full-frame identity fallback: nothing shifts at all.
                    self.assertEqual(accepted_crop, ACCEPTED_RECORDS)
                    self.assertEqual(diagnostic_crop, DIAGNOSTIC_RECORDS)

                # Non-identity keys survive both shifts untouched.
                self.assertEqual(accepted_back[0]["class_name"], "car")
                self.assertEqual(diagnostic_back[1]["semantic_class"], "buoy")
                self.assertIs(diagnostic_back[1]["class_mapping_accepted"], False)

                # The harness's own oracle agrees with the independent run.
                row = harness.verify_scenario(scenario)
                self.assertTrue(row["roundtrip_exact"], row)
                self.assertTrue(row["accepted_roundtrip_exact"], row)
                self.assertTrue(row["diagnostic_roundtrip_exact"], row)
                self.assertEqual(row["accepted_boxes"], row["diagnostic_boxes"], row)
                self.assertGreater(row["accepted_boxes"], 0)


# ---------------------------------------------------------------------------
# 2. report refusal: no fabricated numbers, adoption refused
# ---------------------------------------------------------------------------


class RoiCropReportRefusalTests(unittest.TestCase):
    def test_report_refuses_adoption_with_every_required_cell_unmeasured(self) -> None:
        """A real report run refuses adoption, cell by cell.

        With quality, inference timing and workload identity missing the
        decision must be exactly ``NO ADOPTION / insufficient evidence`` with
        ``adoption is False``; all ten required cells are present with a
        reason each and every unmeasured field carries the literal
        ``UNMEASURED`` marker — never a fabricated number.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = run_report(Path(tmp.name))

        self.assertEqual(report["contract"], "issue-704-roi-crop-baseline-v1")
        self.assertEqual(report["binding"], "BOUND")
        self.assertEqual(report["tested_sha"], COMMIT40)

        decision = report["decision"]
        self.assertEqual(
            decision["value"],
            "NO ADOPTION / insufficient evidence",
            "the refusal decision is a literal, not a paraphrase",
        )
        self.assertIs(decision["adoption"], False)
        reasons = decision["reasons"]
        self.assertIsInstance(reasons, list)
        self.assertTrue(reasons, "a refusal must say why")
        for expected in (
            "inference was not executed: no model runtime or weights in the harness",
            "quality is UNMEASURED: no labeled replay or fixtures",
            "workload identity is UNMEASURED: synthetic frames only",
            "candidate inference CPU ratio is UNMEASURED",
        ):
            self.assertIn(expected, reasons)

        # All ten required cells, in report order, each with a reason.
        unmeasured = report["unmeasured"]
        self.assertEqual(len(unmeasured), 10, "exactly ten unmeasured cells")
        self.assertEqual([cell["cell"] for cell in unmeasured], EXPECTED_UNMEASURED_CELLS)
        for cell in unmeasured:
            with self.subTest(cell=cell["cell"]):
                self.assertTrue(
                    str(cell["reason"]).strip(),
                    f"{cell['cell']} must carry an explicit reason",
                )

        # Every unmeasured field is the literal marker, never a number.
        for arm in ("baseline", "candidate"):
            arm_report = report["arms"][arm]
            for key in (
                "child_cpu_seconds_per_frame",
                "inference_cpu_seconds_per_frame",
                "inference_latency_ms",
                "end_to_end_latency_ms",
                "quality",
            ):
                with self.subTest(arm=arm, field=key):
                    self.assertEqual(arm_report[key], "UNMEASURED")
        self.assertEqual(report["quality"]["status"], "UNMEASURED")
        self.assertTrue(report["quality"]["reason"].strip())
        self.assertEqual(report["input"]["workload_identity"], "UNMEASURED")
        self.assertEqual(report["comparison"]["inference_cpu_ratio"], "UNMEASURED")
        self.assertEqual(report["comparison"]["end_to_end_p95_ratio"], "UNMEASURED")
        self.assertEqual(report["comparison"]["quality_parity"], "UNMEASURED")
        self.assertIs(report["comparison"]["adoption_evaluable"], False)
        self.assertIs(report["model"]["inference_executed"], False)
        self.assertEqual(report["model"]["inference_backend"], "UNMEASURED")

        # What IS measured stays model-free preprocessing (real numbers) and
        # the geometry proof of the same run is exact.
        for arm in ("baseline", "candidate"):
            self.assertIsInstance(
                report["arms"][arm]["parent_cpu_seconds_per_frame"], (int, float)
            )
            self.assertIsInstance(
                report["arms"][arm]["preprocess_latency_ms"]["median"], (int, float)
            )
            self.assertEqual(report["arms"][arm]["processed_frames"], 6 * 32)
        self.assertIs(report["geometry"]["all_roundtrip_exact"], True)
        self.assertEqual(report["geometry"]["scenarios_checked"], 6)

    def test_binding_is_unbound_without_a_full_sha(self) -> None:
        """``--tested-sha`` must be a full 40-hex commit to bind a report."""
        harness = load_harness()
        self.assertEqual(harness.binding_for_sha(COMMIT40), "BOUND")
        self.assertEqual(harness.binding_for_sha(""), "UNBOUND")
        self.assertEqual(harness.binding_for_sha("main"), "UNBOUND")
        self.assertEqual(harness.binding_for_sha("0123456789abcdef"), "UNBOUND")


# ---------------------------------------------------------------------------
# 3. thresholds are declared before measurement and cannot be edited away
# ---------------------------------------------------------------------------


class RoiCropThresholdTests(unittest.TestCase):
    def test_thresholds_are_module_level_and_echoed_into_the_report(self) -> None:
        """ADOPTION_THRESHOLDS is a module-level constant, declared before
        any measurement runs, and appears verbatim in the report."""
        harness = load_harness()

        self.assertIn("ADOPTION_THRESHOLDS", vars(harness), "module-level constant")
        thresholds = harness.ADOPTION_THRESHOLDS
        self.assertIsInstance(thresholds, dict)
        # Literal frozen values (declared, not derived from any measurement).
        self.assertEqual(thresholds["min_samples_per_arm"], 30)
        self.assertEqual(thresholds["candidate_preprocess_parent_cpu_ratio_max"], 1.00)
        self.assertEqual(thresholds["candidate_inference_cpu_ratio_max"], 0.80)
        self.assertEqual(thresholds["candidate_end_to_end_p95_ratio_max"], 0.90)
        self.assertIs(thresholds["quality_parity_required"], True)
        self.assertIs(thresholds["require_inference_cpu_measured"], True)
        self.assertIs(thresholds["require_quality_measured"], True)
        self.assertIs(thresholds["require_workload_identity_measured"], True)
        self.assertIs(thresholds["require_tested_sha"], True)

        # Declared BEFORE measurement in the source: the constant's assignment
        # precedes both the measurement function and main().
        source = HARNESS_PATH.read_text(encoding="utf-8")
        declaration = source.index("ADOPTION_THRESHOLDS = {")
        self.assertLess(declaration, source.index("def measure_arm"))
        self.assertLess(declaration, source.index("def main"))

        # ...and echoed verbatim into the report the harness actually writes.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = run_report(Path(tmp.name))
        self.assertEqual(report["frozen"]["adoption_thresholds"], thresholds)
        self.assertEqual(report["decision"]["thresholds"], thresholds)
        self.assertIn("never relaxed", report["frozen"]["note"])

    def test_editing_only_the_measurement_section_cannot_adopt(self) -> None:
        """Fabricating every measured cell still refuses while quality and
        workload identity are unmeasured — those are NOT measurement-section
        edits (no labels and no real frames exist to measure them with)."""
        harness = load_harness()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = run_report(Path(tmp.name))

        # Eagerly "fill in" every cell the measurement section owns.
        for arm in ("baseline", "candidate"):
            arm_report = report["arms"][arm]
            arm_report["inference_cpu_seconds_per_frame"] = 0.01
            arm_report["inference_latency_ms"] = {"median": 1.0, "p95": 2.0}
            arm_report["end_to_end_latency_ms"] = {"median": 5.0, "p95": 8.0}
        report["model"]["inference_executed"] = True
        report["comparison"]["inference_cpu_ratio"] = 0.50
        report["comparison"]["end_to_end_p95_ratio"] = 0.70
        report["comparison"]["adoption_evaluable"] = True

        # quality + workload identity remain UNMEASURED: untouched, because
        # they are not measurement-section cells.
        self.assertEqual(report["quality"]["status"], "UNMEASURED")
        self.assertEqual(report["input"]["workload_identity"], "UNMEASURED")

        decision = harness.build_decision(report)
        self.assertEqual(decision["value"], "NO ADOPTION / insufficient evidence")
        self.assertIs(decision["adoption"], False)
        self.assertEqual(decision["thresholds"], harness.ADOPTION_THRESHOLDS)
        reasons = "\n".join(decision["reasons"])
        self.assertIn("quality is UNMEASURED", reasons)
        self.assertIn("workload identity is UNMEASURED", reasons)


# ---------------------------------------------------------------------------
# 4. scope guard — only the admitted #704 surface
# ---------------------------------------------------------------------------


class RoiCropScopeGuardTests(unittest.TestCase):
    """The pinned #704 change set (BASE_SHA..HEAD_SHA), fail-closed.

    The pinned range is the #696/#701 pattern: while #704 is uncommitted
    HEAD == BASE_SHA and the range is empty, so the working-tree view is
    consulted instead (the change set exists only there); from the first
    #704 commit the range carries it and the status half never runs again.
    A failing ``git diff`` raises instead of checking something weaker.
    """

    ALLOWED_CHANGE_PREFIXES = (
        "tests/",
        "scripts/worker/roi_crop_baseline.py",
        "specs/704-roi-crop-baseline/",
    )
    FORBIDDEN_PREFIXES = ("worker/", "api/", "deploy/", ".github/", ".gitlab")

    @classmethod
    def _offenders(cls, paths: list[str]) -> list[str]:
        return [
            path
            for path in paths
            if not any(path.startswith(prefix) for prefix in cls.ALLOWED_CHANGE_PREFIXES)
        ]

    @staticmethod
    def _changed_paths() -> list[str]:
        """The pinned #704 change set (fail-closed on a failing ``git diff``)."""
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--name-only", BASE_SHA, HEAD_SHA],
                capture_output=True,
                text=True,
                check=True,
            )
        except OSError as exc:
            raise AssertionError(
                "scope guard cannot run git to read the pinned #704 change set "
                f"({type(exc).__name__}: {exc}) — failing closed"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise AssertionError(
                "scope guard cannot read the pinned #704 change set: "
                f"`git diff --name-only {BASE_SHA} {HEAD_SHA}` failed with rc="
                f"{exc.returncode} ({detail or 'no output'}) — shallow clone or "
                "missing object? Failing closed: a guard that cannot read its "
                "pinned range must not pass."
            ) from exc
        paths: set[str] = {
            line.strip().strip('"')
            for line in result.stdout.splitlines()
            if line.strip()
        }
        if paths:
            return sorted(paths)
        # Pre-commit window only: this branch has no commits yet (HEAD ==
        # BASE_SHA), so the working tree is the only place the #704 change
        # set exists. Never reached again once #704 is committed.
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.add(path.strip().strip('"'))
        return sorted(paths)

    def test_change_set_touches_only_the_704_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #704 change set (committed or "
            f"uncommitted): {offenders}",
        )

    def test_no_worker_api_deploy_workflow_or_lockfile_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES),
                    f"forbidden path in the #704 change set: {path}",
                )
                self.assertFalse(
                    path.endswith(".lock") or path.endswith(".lock.txt"),
                    f"lockfile in the #704 change set: {path}",
                )
                self.assertNotIn("package-lock.json", path)
                self.assertNotIn("runtime-lock.json", path)

    def test_scope_predicate_rejects_every_forbidden_path(self) -> None:
        """The guard itself must bite: feed it synthetic offenders.

        Proves the decision logic rejects the forbidden surface without
        touching the working tree (an out-of-scope path cannot be created
        from inside the admitted scope).
        """
        forbidden = [
            "worker/worker_outbox.py",
            "worker/worker_crossings.py",
            "api/app/analytics.py",
            "deploy/vps/deploy.sh",
            "deploy/worker/ubuntu/worker.env.example",
            ".github/workflows/quality-integration.yml",
            ".gitlab-ci.yml",
            "package-lock.json",
            "runtime-lock.json",
            "api/requirements-api.lock.txt",
            "scripts/worker/some_other_tool.py",
            "specs/701-crossing-votes/spec.md",
        ]
        for path in forbidden:
            with self.subTest(path=path):
                self.assertTrue(self._offenders([path]), f"{path} must be rejected")
        admitted = [
            "tests/test_roi_crop_baseline.py",
            "scripts/worker/roi_crop_baseline.py",
            "specs/704-roi-crop-baseline/spec.md",
        ]
        self.assertEqual(self._offenders(admitted), [], "the admitted surface must pass")


if __name__ == "__main__":
    unittest.main()
