#!/usr/bin/env python3
"""Persistent YOLO inference child for the Ubuntu worker.

The parent owns media/state progression and can terminate this process if a
single model.track call stops returning. Stdout is reserved for the framed JSON
protocol; library diagnostics are redirected to stderr.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import struct
import sys
from typing import BinaryIO

import numpy as np

from analytics_profiles import get_profile, normalize_model_class


VEHICLE_CLASSES = set(get_profile("road-v1").model_classes)
_LENGTH = struct.Struct("!I")


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError("protocol stream ended")
        data.extend(chunk)
    return bytes(data)


def read_request(stream: BinaryIO) -> tuple[dict[str, object], bytes]:
    header_size = _LENGTH.unpack(read_exact(stream, _LENGTH.size))[0]
    if header_size <= 0 or header_size > 64 * 1024:
        raise ValueError("invalid request header size")
    header = json.loads(read_exact(stream, header_size).decode("utf-8"))
    if not isinstance(header, dict):
        raise ValueError("request header must be an object")
    frame_size = int(header.get("frame_size") or 0)
    if frame_size <= 0 or frame_size > 64 * 1024 * 1024:
        raise ValueError("invalid frame size")
    return header, read_exact(stream, frame_size)


def write_response(stream: BinaryIO, payload: dict[str, object]) -> None:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    stream.write(_LENGTH.pack(len(raw)))
    stream.write(raw)
    stream.flush()


def serialize_detections(results, analytics_profile: str = "water-v1") -> list[dict[str, object]]:
    detections: list[dict[str, object]] = []
    if not results:
        return detections

    result = results[0]
    if result.boxes is None:
        return detections

    names = result.names
    track_ids = getattr(result.boxes, "id", None)

    for index, box in enumerate(result.boxes):
        cls_id = int(box.cls[0].item())
        class_name = str(names.get(cls_id, cls_id))
        semantic = normalize_model_class(class_name, analytics_profile)
        if semantic is None:
            continue

        track_id = None
        if track_ids is not None:
            try:
                track_id = int(track_ids[index].item())
            except Exception:
                track_id = None

        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = [int(round(value)) for value in xyxy]
        detections.append(
            {
                "track_id": track_id,
                **semantic,
                "confidence": float(box.conf[0].item()),
                "bbox_xyxy": [x1, y1, x2, y2],
            }
        )

    return detections


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--analytics-profile", default="water-v1")
    parser.add_argument("--tracker", required=True)
    parser.add_argument("--image-size", type=int, required=True)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    profile = get_profile(args.analytics_profile)

    protocol_in = sys.stdin.buffer
    protocol_out = sys.stdout.buffer
    sys.stdout = sys.stderr

    with contextlib.redirect_stdout(sys.stderr):
        from ultralytics import YOLO

        model = YOLO(args.model)

    while True:
        try:
            header, raw = read_request(protocol_in)
        except EOFError:
            return 0

        width = int(header.get("width") or 0)
        height = int(header.get("height") or 0)
        channels = int(header.get("channels") or 0)
        if width <= 0 or height <= 0 or channels != 3:
            write_response(protocol_out, {"ok": False, "error": "invalid_frame_shape"})
            continue
        if len(raw) != width * height * channels:
            write_response(protocol_out, {"ok": False, "error": "frame_size_mismatch"})
            continue

        frame = np.frombuffer(raw, np.uint8).reshape((height, width, channels))
        try:
            with contextlib.redirect_stdout(sys.stderr):
                results = model.track(
                    frame,
                    persist=True,
                    tracker=args.tracker,
                    imgsz=args.image_size,
                    conf=args.confidence,
                    device=args.device,
                    verbose=False,
                )
            write_response(
                protocol_out,
                {"ok": True, "detections": serialize_detections(results, profile.name)},
            )
        except Exception as exc:
            write_response(
                protocol_out,
                {"ok": False, "error": type(exc).__name__},
            )


if __name__ == "__main__":
    raise SystemExit(main())
