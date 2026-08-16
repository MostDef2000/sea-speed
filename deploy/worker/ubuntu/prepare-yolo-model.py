#!/usr/bin/env python3
"""Stage and verify the exact YOLO26x checkpoint in the shared model store."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--runtime-python", required=True, type=Path)
    parser.add_argument("--install-root", type=Path, default=Path("/opt/sea-speed-worker"))
    args = parser.parse_args()
    expected = args.expected_sha256.lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise SystemExit("ERROR expected SHA-256 must be 64 lowercase hex")
    if not args.source.is_file() or args.source.is_symlink():
        raise SystemExit("ERROR model source must be a regular local file")
    if not args.runtime_python.is_file() or not os.access(args.runtime_python, os.X_OK):
        raise SystemExit("ERROR exact runtime python is unavailable")
    actual = sha256_file(args.source)
    if actual != expected:
        raise SystemExit("ERROR model source SHA-256 mismatch")

    models = args.install_root / "shared/models"
    models.mkdir(parents=True, exist_ok=True)
    target = models / "yolo26x.pt"
    temp = models / f".yolo26x.{os.getpid()}.pt"
    shutil.copyfile(args.source, temp)
    os.chmod(temp, 0o640)
    if sha256_file(temp) != expected:
        temp.unlink(missing_ok=True)
        raise SystemExit("ERROR staged model SHA-256 mismatch")

    validation = subprocess.run(
        [
            str(args.runtime_python),
            "-c",
            "import numpy as np, torch; from ultralytics import YOLO; "
            "assert torch.cuda.is_available(), 'cuda unavailable'; "
            "m=YOLO(r'" + str(temp) + "'); "
            "r=m.predict(np.zeros((576,704,3),dtype=np.uint8),imgsz=960,conf=0.15,device=0,verbose=False); "
            "assert isinstance(r,list)",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=180,
        check=False,
    )
    if validation.returncode != 0:
        temp.unlink(missing_ok=True)
        raise SystemExit("ERROR YOLO26x CUDA load/self-test failed")
    os.replace(temp, target)
    os.chmod(target, 0o644)
    manifest = models / "yolo26x.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "sea_speed_model_manifest_v1",
                "model": "yolo26x.pt",
                "sha256": expected,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "cuda_self_test": True,
                "image_size": 960,
                "confidence": 0.15,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(manifest, 0o644)
    print(f"MODEL_PREPARED=yolo26x.pt SHA256={expected}")
    print("CUDA_SELF_TEST=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
