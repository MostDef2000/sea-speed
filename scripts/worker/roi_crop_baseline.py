#!/usr/bin/env python3
"""ROI crop baseline harness - offline experiment for issue #704.

This is an on-demand, stdlib-only measurement harness. It does NOT touch the
production worker, does not import the model runtime, and never contacts a
camera, relay or deployed service. It measures the inference-path geometry and
preprocessing cost of two paired arms on the same frozen synthetic frames:

Arm A - baseline (current production shape)
  The existing polygon mask is applied at full frame size
  (worker/worker_roi.py:83-105). Inference would consume the full masked frame.

Arm B - candidate (crop the masked frame to the clipped ROI bbox)
  The clipped polygon bounding box is computed, the masked frame is cropped to
  it for inference, and BOTH accepted and diagnostic boxes are shifted back
  into full-frame coordinates before any motion/ROI check.

Only geometry (crop bounds, reverse coordinate shift for accepted and
diagnostic boxes) and model-free preprocessing timings are measurable here.
The sandbox has no OpenCV (the production mask implementation) and no model
weights or labeled replay, so mask cost, inference CPU, end-to-end inference
latency and detection quality are reported as UNMEASURED with an explicit
reason. Adoption is therefore refused: the decision is always
"NO ADOPTION / insufficient evidence" until real frames, weights and labels
produce admissible measurements.

Adoption thresholds are declared in ADOPTION_THRESHOLDS below, before any
measurement runs, and are echoed into the report.

Usage::

    python3 scripts/worker/roi_crop_baseline.py \
      --tested-sha "$(git rev-parse HEAD)" \
      --output /tmp/opencode/704-roi-crop/report.json

No third-party import. Synthetic frames prove crop/restore geometry and
preprocessing timings only; model-free timings are never labelled inference.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080
FRAME_CHANNELS = 3
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS

DEFAULT_FRAMES_PER_SCENARIO = 32

# Frozen BEFORE any measurement. A measured breach is recorded, never relaxed.
ADOPTION_THRESHOLDS = {
    "min_samples_per_arm": 30,
    "candidate_preprocess_parent_cpu_ratio_max": 1.00,
    "candidate_inference_cpu_ratio_max": 0.80,
    "candidate_end_to_end_p95_ratio_max": 0.90,
    "quality_parity_required": True,
    "require_inference_cpu_measured": True,
    "require_quality_measured": True,
    "require_workload_identity_measured": True,
    "require_tested_sha": True,
}

MODEL_IDENTITY = {
    "model_name": "models/yolo26x.pt",
    "inference_image_size": 960,
    "identity_source": "worker/analytics_profiles.py (water-v1 / road-v1)",
    "inference_backend": "UNMEASURED",
    "inference_executed": False,
}

# Scenario polygons are frozen input identities, not tunable parameters.
# Each scenario exercises one required geometry case.
SCENARIOS = (
    {
        "name": "nonzero_offset",
        "case": "rectangular ROI away from the origin (nonzero crop offset)",
        "points": ((320, 180), (1280, 240), (1200, 860), (360, 900)),
    },
    {
        "name": "nonrectangular",
        "case": "irregular polygon whose mask is not its bounding box",
        "points": ((200, 150), (900, 120), (1500, 480), (1100, 950), (300, 900)),
    },
    {
        "name": "edge_clipped",
        "case": "polygon crossing the frame edge so bounds are clipped",
        "points": ((-120, 140), (1000, 100), (1900, 980), (400, 1120)),
    },
    {
        "name": "no_roi",
        "case": "no ROI / fewer than three points - identity full-frame path",
        "points": (),
    },
    {
        "name": "degenerate_bounds",
        "case": "zero-area polygon - degenerate bounds must fall back safely",
        "points": ((640, 360), (640, 360), (640, 360)),
    },
    {
        "name": "outside_frame",
        "case": "polygon entirely outside the frame - empty clipped bounds",
        "points": ((2400, 1400), (2600, 1500), (2500, 1700)),
    },
)


@dataclass(frozen=True)
class CropBox:
    """Clipped ROI crop bounds plus why they were chosen."""

    x0: int
    y0: int
    x1: int
    y1: int
    mode: str
    reason: str
    clipped: bool
    polygon_area: float
    input_area: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def as_dict(self) -> dict:
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "reason": self.reason,
            "clipped": self.clipped,
            "polygon_area_px": round(self.polygon_area, 3),
            "crop_area_px": int(self.width * self.height),
            "input_area_px": int(self.input_area),
            "offset": [self.x0, self.y0],
        }


def binding_for_sha(sha: str) -> str:
    """BOUND only for a full 40-hex commit; anything else is UNBOUND."""
    return "BOUND" if FULL_SHA_RE.fullmatch((sha or "").strip()) else "UNBOUND"


def polygon_area(points) -> float:
    """Absolute shoelace area of a polygon."""
    if len(points) < 3:
        return 0.0
    total = 0.0
    count = len(points)
    for index in range(count):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % count]
        total += float(x0) * float(y1) - float(x1) * float(y0)
    return abs(total) / 2.0


def resolve_crop(points, width: int = FRAME_WIDTH, height: int = FRAME_HEIGHT) -> CropBox:
    """Map a polygon to the clipped crop bounds used for candidate inference.

    Mirrors the production ROI mask semantics: fewer than three points means
    full frame. A zero-area polygon or empty clipped bounds falls back to the
    full frame instead of producing a zero-sized inference input.
    """
    if len(points) < 3:
        return CropBox(0, 0, width, height, "full-frame", "no-roi", False, 0.0, width * height)

    area = polygon_area(points)
    raw_x0 = min(float(point[0]) for point in points)
    raw_y0 = min(float(point[1]) for point in points)
    raw_x1 = max(float(point[0]) for point in points)
    raw_y1 = max(float(point[1]) for point in points)
    clipped = raw_x0 < 0 or raw_y0 < 0 or raw_x1 > width or raw_y1 > height

    if area <= 0.0:
        return CropBox(0, 0, width, height, "full-frame", "degenerate-zero-area", clipped, area, width * height)

    x0 = max(0, int(math.floor(raw_x0)))
    y0 = max(0, int(math.floor(raw_y0)))
    x1 = min(width, int(math.ceil(raw_x1)))
    y1 = min(height, int(math.ceil(raw_y1)))
    if x1 <= x0 or y1 <= y0:
        return CropBox(0, 0, width, height, "full-frame", "outside-frame", clipped, area, width * height)
    return CropBox(x0, y0, x1, y1, "crop", "ok", clipped, area, (x1 - x0) * (y1 - y0))


def shift_records(records, dx: int, dy: int) -> list[dict]:
    """Shift bbox_xyxy of every record by (dx, dy), preserving all other keys.

    Negative (dx, dy) maps full-frame boxes into crop coordinates; positive
    values perform the mandatory reverse shift back to full-frame coordinates.
    Accepted detections and diagnostic records share the bbox_xyxy key, so the
    same exact integer operation covers both.
    """
    shifted = []
    for record in records:
        clone = dict(record)
        if "bbox_xyxy" not in clone:
            shifted.append(clone)
            continue
        box = clone["bbox_xyxy"]
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError(
                "malformed bbox_xyxy (expected a 4-element list): "
                f"track_id={clone.get('track_id')!r} value={box!r}"
            )
        clone["bbox_xyxy"] = [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy]
        shifted.append(clone)
    return shifted


def _synthetic_boxes(count: int = 6) -> list[list[int]]:
    """Deterministic full-frame boxes, including one outside a typical ROI."""
    boxes = []
    for index in range(count):
        x0 = (index * 137 + 11) % (FRAME_WIDTH - 80)
        y0 = (index * 211 + 17) % (FRAME_HEIGHT - 80)
        boxes.append([x0, y0, x0 + 60, y0 + 40])
    boxes.append([5, 5, 55, 55])
    return boxes


def _accepted_records(boxes) -> list[dict]:
    return [
        {"track_id": index, "class_name": "car", "bbox_xyxy": list(box)}
        for index, box in enumerate(boxes)
    ]


def _diagnostic_records(boxes) -> list[dict]:
    return [
        {
            "track_id": index,
            "semantic_class": "vessel",
            "class_mapping_accepted": True,
            "bbox_xyxy": list(box),
        }
        for index, box in enumerate(boxes)
    ]


def verify_scenario(scenario: dict) -> dict:
    """Prove exact crop -> reverse-shift round trip for accepted + diagnostic."""
    points = scenario["points"]
    crop = resolve_crop(points)
    boxes = _synthetic_boxes()
    accepted = _accepted_records(boxes)
    diagnostic = _diagnostic_records(boxes)

    accepted_crop = shift_records(accepted, -crop.x0, -crop.y0)
    accepted_back = shift_records(accepted_crop, crop.x0, crop.y0)
    diagnostic_crop = shift_records(diagnostic, -crop.x0, -crop.y0)
    diagnostic_back = shift_records(diagnostic_crop, crop.x0, crop.y0)

    return {
        "name": scenario["name"],
        "case": scenario["case"],
        "points": [list(point) for point in points],
        "point_count": len(points),
        "crop": crop.as_dict(),
        "accepted_boxes": len(accepted),
        "diagnostic_boxes": len(diagnostic),
        "accepted_roundtrip_exact": accepted_back == accepted,
        "diagnostic_roundtrip_exact": diagnostic_back == diagnostic,
        "roundtrip_exact": accepted_back == accepted and diagnostic_back == diagnostic,
    }


def percentile(values, pct: float):
    """Nearest-rank percentile in the same units as the input."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return round(ordered[rank - 1], 6)


def _touch_frame(frame) -> int:
    """Stand-in for handing an already-masked frame to inference (no copy)."""
    return frame[0] + frame[-1]


def _crop_frame(frame, crop: CropBox) -> bytearray:
    """Copy the cropped region out of the frame buffer (candidate preprocessing)."""
    row_bytes = crop.width * FRAME_CHANNELS
    src_stride = FRAME_WIDTH * FRAME_CHANNELS
    out = bytearray(row_bytes * crop.height)
    for row in range(crop.height):
        src = (crop.y0 + row) * src_stride + crop.x0 * FRAME_CHANNELS
        dst = row * row_bytes
        out[dst:dst + row_bytes] = frame[src:src + row_bytes]
    return out


def measure_arm(arm: str, frame, frames_per_scenario: int) -> dict:
    """Measure model-free parent CPU and preprocessing latency per frame.

    No inference child is spawned: there is no model runtime or weights, so
    child CPU, inference CPU and inference latency stay UNMEASURED. The numbers
    below are preprocessing-loop measurements only.
    """
    latencies = []
    per_scenario = {}
    cpu_before = time.process_time()
    for scenario in SCENARIOS:
        points = scenario["points"]
        scenario_latencies = []
        for _ in range(frames_per_scenario):
            started = time.perf_counter_ns()
            if arm == "candidate":
                crop = resolve_crop(points)
                _touch_frame(frame)
                if crop.mode == "crop":
                    _crop_frame(frame, crop)
            else:
                _touch_frame(frame)
            scenario_latencies.append((time.perf_counter_ns() - started) / 1_000_000.0)
        per_scenario[scenario["name"]] = {
            "samples": len(scenario_latencies),
            "median_ms": percentile(scenario_latencies, 50),
            "p95_ms": percentile(scenario_latencies, 95),
        }
        latencies.extend(scenario_latencies)
    cpu_seconds = time.process_time() - cpu_before
    total_frames = len(latencies)
    return {
        "mode": (
            "masked-full-frame"
            if arm == "baseline"
            else "masked-crop-to-clipped-roi-bbox"
        ),
        "processed_frames": total_frames,
        "samples_per_scenario": per_scenario,
        "parent_cpu_seconds_per_frame": round(cpu_seconds / total_frames, 9) if total_frames else None,
        "child_cpu_seconds_per_frame": "UNMEASURED",
        "inference_cpu_seconds_per_frame": "UNMEASURED",
        "preprocess_latency_ms": {
            "median": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": round(max(latencies), 6) if latencies else None,
        },
        "inference_latency_ms": "UNMEASURED",
        "end_to_end_latency_ms": "UNMEASURED",
        "quality": "UNMEASURED",
        "notes": [
            "Both arms conceptually mask the full frame first (worker/worker_roi.py:83-105); the mask pixel cost is UNMEASURED because this stdlib-only harness does not execute OpenCV, and the candidate crop copies the frame region that would carry the mask.",
            "No inference child is spawned: there is no model runtime or weights, so child/inference CPU, inference latency, end-to-end latency and quality are UNMEASURED.",
            "Timings cover the model-free preprocessing loop only and must not be read as inference or end-to-end measurements.",
        ],
    }


def build_comparison(baseline: dict, candidate: dict) -> dict:
    baseline_cpu = baseline.get("parent_cpu_seconds_per_frame")
    candidate_cpu = candidate.get("parent_cpu_seconds_per_frame")
    preprocess_ratio = None
    if isinstance(baseline_cpu, (int, float)) and baseline_cpu > 0 and isinstance(candidate_cpu, (int, float)):
        preprocess_ratio = round(candidate_cpu / baseline_cpu, 6)
    preprocess_ok = (
        None
        if preprocess_ratio is None
        else preprocess_ratio <= ADOPTION_THRESHOLDS["candidate_preprocess_parent_cpu_ratio_max"]
    )
    return {
        "preprocess_only_parent_cpu_ratio": preprocess_ratio,
        "preprocess_only_threshold_met": preprocess_ok,
        "inference_cpu_ratio": "UNMEASURED",
        "end_to_end_p95_ratio": "UNMEASURED",
        "quality_parity": "UNMEASURED",
        "adoption_evaluable": False,
        "notes": [
            "A preprocessing ratio is model-free and cannot justify adoption.",
            "The candidate's possible inference saving is unmeasured without weights and frames.",
        ],
    }


def build_unmeasured_cells() -> list[dict]:
    return [
        {
            "cell": "baseline.preprocess_mask_cost",
            "reason": "production mask is cv2.fillPoly + bitwise_and; this stdlib-only harness does not import OpenCV",
        },
        {
            "cell": "baseline.inference_cpu_seconds_per_frame",
            "reason": "no model weights or inference runtime were executed",
        },
        {
            "cell": "candidate.inference_cpu_seconds_per_frame",
            "reason": "no model weights or inference runtime were executed",
        },
        {
            "cell": "baseline.inference_latency_ms",
            "reason": "no model weights or inference runtime were executed",
        },
        {
            "cell": "candidate.inference_latency_ms",
            "reason": "no model weights or inference runtime were executed",
        },
        {
            "cell": "baseline.end_to_end_latency_ms",
            "reason": "end-to-end latency includes inference, which was not executed",
        },
        {
            "cell": "candidate.end_to_end_latency_ms",
            "reason": "end-to-end latency includes inference, which was not executed",
        },
        {
            "cell": "quality",
            "reason": "the repository has no labeled replay, weights or external fixtures for an honest quality comparison",
        },
        {
            "cell": "workload_identity",
            "reason": "synthetic zero-filled frames prove geometry and copy cost only, not the target camera workload",
        },
        {
            "cell": "child_cpu_seconds_per_frame",
            "reason": "no inference child process exists to account for",
        },
    ]


def _is_ratio(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def build_decision(report: dict) -> dict:
    """Refuse adoption whenever quality, timing, identity or a ratio threshold fails."""
    thresholds = ADOPTION_THRESHOLDS
    comparison = report["comparison"]
    quality_status = report["quality"]["status"]
    workload_identity = report["input"]["workload_identity"]
    inference_ratio = comparison.get("inference_cpu_ratio")
    end_to_end_ratio = comparison.get("end_to_end_p95_ratio")
    preprocess_ratio = comparison.get("preprocess_only_parent_cpu_ratio")
    quality_parity = comparison.get("quality_parity")
    reasons = []

    if thresholds["require_tested_sha"] and report["binding"] != "BOUND":
        reasons.append("report is UNBOUND: --tested-sha is missing or not a full 40-hex commit")
    if report["frozen"].get("investigation_only"):
        reasons.append(
            "--frames-per-scenario differs from the frozen default: this is an "
            "investigation run, not frozen evidence"
        )
    if not report["model"]["inference_executed"]:
        reasons.append("inference was not executed: no model runtime or weights in the harness")
    for arm in ("baseline", "candidate"):
        if report["arms"][arm]["inference_cpu_seconds_per_frame"] == "UNMEASURED":
            reasons.append(f"{arm} inference CPU is UNMEASURED")
        if report["arms"][arm]["inference_latency_ms"] == "UNMEASURED":
            reasons.append(f"{arm} inference latency is UNMEASURED")
        if report["arms"][arm]["end_to_end_latency_ms"] == "UNMEASURED":
            reasons.append(f"{arm} end-to-end latency is UNMEASURED")
        samples = report["arms"][arm]["processed_frames"]
        if samples < thresholds["min_samples_per_arm"]:
            reasons.append(
                f"{arm} arm has {samples} samples, below the frozen floor "
                f"{thresholds['min_samples_per_arm']}"
            )

    if thresholds["require_quality_measured"] and quality_status != "MEASURED":
        if quality_status == "UNMEASURED":
            reasons.append("quality is UNMEASURED: no labeled replay or fixtures")
        else:
            reasons.append(f"quality is {quality_status}, not MEASURED")
    if thresholds["quality_parity_required"] and quality_parity != "MEASURED":
        reasons.append(f"quality parity is {quality_parity}, not MEASURED")
    if thresholds["require_workload_identity_measured"] and workload_identity != "MEASURED":
        if workload_identity == "UNMEASURED":
            reasons.append("workload identity is UNMEASURED: synthetic frames only")
        else:
            reasons.append(f"workload identity is {workload_identity}, not MEASURED")

    if thresholds["require_inference_cpu_measured"] and not _is_ratio(inference_ratio):
        reasons.append("candidate inference CPU ratio is UNMEASURED")
    elif _is_ratio(inference_ratio) and inference_ratio > thresholds["candidate_inference_cpu_ratio_max"]:
        reasons.append(
            f"candidate inference CPU ratio {inference_ratio} exceeds the frozen maximum "
            f"{thresholds['candidate_inference_cpu_ratio_max']}"
        )
    if _is_ratio(end_to_end_ratio) and end_to_end_ratio > thresholds["candidate_end_to_end_p95_ratio_max"]:
        reasons.append(
            f"candidate end-to-end p95 ratio {end_to_end_ratio} exceeds the frozen maximum "
            f"{thresholds['candidate_end_to_end_p95_ratio_max']}"
        )
    if _is_ratio(preprocess_ratio) and preprocess_ratio > thresholds["candidate_preprocess_parent_cpu_ratio_max"]:
        reasons.append(
            f"candidate preprocess CPU ratio {preprocess_ratio} exceeds the frozen maximum "
            f"{thresholds['candidate_preprocess_parent_cpu_ratio_max']}"
        )

    adoption = False
    value = "NO ADOPTION / insufficient evidence"
    # An adoption-eligible decision requires every measured cell above plus a
    # measured win under every declared ratio threshold. While inference,
    # quality or workload identity is UNMEASURED this branch cannot be reached;
    # it exists so the rule is explicit, not to claim a result.
    ratios_ok = (
        _is_ratio(inference_ratio)
        and inference_ratio <= thresholds["candidate_inference_cpu_ratio_max"]
        and _is_ratio(end_to_end_ratio)
        and end_to_end_ratio <= thresholds["candidate_end_to_end_p95_ratio_max"]
        and _is_ratio(preprocess_ratio)
        and preprocess_ratio <= thresholds["candidate_preprocess_parent_cpu_ratio_max"]
    )
    quality_ok = (
        not thresholds["require_quality_measured"] or quality_status == "MEASURED"
    ) and (not thresholds["quality_parity_required"] or quality_parity == "MEASURED")
    identity_ok = (
        not thresholds["require_workload_identity_measured"] or workload_identity == "MEASURED"
    )
    if (
        not reasons
        and comparison.get("adoption_evaluable")
        and report["model"]["inference_executed"]
        and ratios_ok
        and quality_ok
        and identity_ok
    ):
        adoption = True
        value = "ADOPTION_ELIGIBLE"

    return {
        "value": value,
        "adoption": adoption,
        "thresholds": dict(thresholds),
        "reasons": reasons,
    }


def _read_cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def _read_cgroup_cpu_quota() -> str:
    candidates = (
        Path("/sys/fs/cgroup/cpu.max"),
        Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
    )
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            return f"{path}: {text}"
    return "unknown"


def runtime_identity() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "cpu_model": _read_cpu_model(),
        "cgroup_cpu_quota": _read_cgroup_cpu_quota(),
        "mask_implementation": "cv2.fillPoly + cv2.bitwise_and (worker/worker_roi.py:83-105)",
        "opencv_available": importlib.util.find_spec("cv2") is not None,
        "opencv_used_by_harness": False,
    }


def input_fingerprint(frames_per_scenario: int) -> str:
    payload = {
        "frame": [FRAME_WIDTH, FRAME_HEIGHT, FRAME_CHANNELS],
        "frames_per_scenario": frames_per_scenario,
        "scenarios": SCENARIOS,
        "thresholds": ADOPTION_THRESHOLDS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline ROI crop baseline harness (issue #704).",
        epilog="Measurement only: no production change, no camera/relay access, no model inference.",
    )
    parser.add_argument("--output", required=True, help="JSON report path")
    parser.add_argument("--tested-sha", default="", help="Full 40-hex commit the report is bound to")
    parser.add_argument(
        "--frames-per-scenario",
        type=int,
        default=DEFAULT_FRAMES_PER_SCENARIO,
        help="Frames processed per scenario per arm (frozen default 32)",
    )
    args = parser.parse_args(argv)

    if args.frames_per_scenario <= 0:
        parser.error("--frames-per-scenario must be positive")

    started = time.monotonic()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = bytearray(FRAME_BYTES)

    report = {
        "contract": "issue-704-roi-crop-baseline-v1",
        "issue": 704,
        "tested_sha": args.tested_sha.strip() or "UNBOUND",
        "binding": binding_for_sha(args.tested_sha),
        "frozen": {
            "scenarios": [scenario["name"] for scenario in SCENARIOS],
            "frames_per_scenario": args.frames_per_scenario,
            "frames_per_scenario_default": DEFAULT_FRAMES_PER_SCENARIO,
            "investigation_only": args.frames_per_scenario != DEFAULT_FRAMES_PER_SCENARIO,
            "adoption_thresholds": dict(ADOPTION_THRESHOLDS),
            "note": (
                "Thresholds are declared before measurement and never relaxed after seeing data."
                if args.frames_per_scenario == DEFAULT_FRAMES_PER_SCENARIO
                else "Non-default --frames-per-scenario is an investigation run, not frozen evidence."
            ),
        },
        "runtime": runtime_identity(),
        "model": dict(MODEL_IDENTITY),
        "input": {
            "class": "synthetic",
            "workload_identity": "UNMEASURED",
            "pixel_source": "zero-filled synthetic buffers",
            "frame_width": FRAME_WIDTH,
            "frame_height": FRAME_HEIGHT,
            "frame_channels": FRAME_CHANNELS,
            "frame_bytes": FRAME_BYTES,
            "scenario_count": len(SCENARIOS),
            "frames_per_scenario": args.frames_per_scenario,
            "fingerprint": input_fingerprint(args.frames_per_scenario),
            "notes": [
                "Synthetic frames prove crop/restore geometry and preprocessing timings only.",
                "No labeled replay, weights or external fixtures exist in the repository for an honest quality comparison.",
            ],
        },
        "quality": {
            "status": "UNMEASURED",
            "reason": "no labeled replay, weights or external fixtures for an honest quality comparison",
        },
        "scenarios": [],
        "arms": {},
        "comparison": {},
        "decision": None,
        "unmeasured": build_unmeasured_cells(),
        "duration_seconds": None,
    }

    report["scenarios"] = [verify_scenario(scenario) for scenario in SCENARIOS]
    report["geometry"] = {
        "all_roundtrip_exact": all(row["roundtrip_exact"] for row in report["scenarios"]),
        "scenarios_checked": len(report["scenarios"]),
        "crop_used": sum(1 for row in report["scenarios"] if row["crop"]["mode"] == "crop"),
        "identity_fallback": sum(1 for row in report["scenarios"] if row["crop"]["mode"] == "full-frame"),
        "edge_clipped": sum(1 for row in report["scenarios"] if row["crop"]["clipped"]),
    }

    report["arms"]["baseline"] = measure_arm("baseline", frame, args.frames_per_scenario)
    report["arms"]["candidate"] = measure_arm("candidate", frame, args.frames_per_scenario)
    report["comparison"] = build_comparison(report["arms"]["baseline"], report["arms"]["candidate"])
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    report["decision"] = build_decision(report)

    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"binding: {report['binding']} tested_sha={report['tested_sha']}")
    print(f"geometry_roundtrip_exact: {report['geometry']['all_roundtrip_exact']}")
    print(f"decision: {report['decision']['value']}")
    for reason in report["decision"]["reasons"]:
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
