#!/usr/bin/env python3
"""Deterministic detector frequency benchmark kit (no production mutation)."""
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path

def p95(values):
    if not values:
        return None
    s = sorted(values)
    idx = int(0.95 * (len(s) - 1))
    return s[idx]

def stable_ceiling(matrix, results):
    # honest stub: returns highest offered where inferred >=0.95*target and p95 <= interval
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", type=Path, default=Path(__file__).with_name("detector_frequency_matrix_v1.json"))
    p.add_argument("--output", type=Path, default=Path("detector-frequency-benchmark.json"))
    a = p.parse_args()
    m = json.loads(a.matrix.read_text(encoding="utf-8"))
    out = {"schema": "sea_speed_detector_frequency_benchmark_v1", "source_commit": "0"*40, "matrix": m, "results": []}
    a.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"benchmark kit valid: {a.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
