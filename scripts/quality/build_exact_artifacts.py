#!/usr/bin/env python3
"""Build deterministic VPS and edge source artifacts from exact repository bytes."""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import SHA40_RE, repository_root, sha256_bytes, sha256_file, write_json_atomic

COMPONENT_FILES = {
    "vps": {
        "required": [
            "api/app/main.py",
            "frontend/sea-speed/index.html",
            "frontend/sea-speed/objects/index.html",
            "frontend/sea-speed/cameras/index.html",
            "frontend/root/index.html",
            "deploy/vps/deploy.sh",
        ],
        "optional": [
            "api/requirements.txt",
            "schemas/release-manifest.schema.json",
            "schemas/deployment-manifest.schema.json",
        ],
    },
    "edge": {
        "required": [
            "worker/hls_motion_yolo_worker_events.py",
            "worker/hls_motion_yolo_runtime.py",
        ],
        "optional": [
            "worker/run_worker_once.ps1",
            "worker/restart_worker.cmd",
            "worker/start_worker.cmd",
            "worker/update_worker.ps1",
            "worker/update_worker.cmd",
            "worker/requirements.txt",
        ],
    },
}
FORBIDDEN_SUFFIXES = {".jpg", ".jpeg", ".png", ".sqlite", ".sqlite3", ".db", ".env"}


def deterministic_tar_gz(root: Path, names: list[str]) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(names):
            path = root / name
            data = path.read_bytes()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o755 if path.suffix in {".sh", ".cmd", ".ps1"} else 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as handle:
        handle.write(tar_buffer.getvalue())
    return compressed.getvalue()


def build_component(root: Path, output_dir: Path, component: str, source_commit: str) -> dict:
    config = COMPONENT_FILES[component]
    missing = [name for name in config["required"] if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{component} artifact missing required files: {', '.join(missing)}")
    names = [*config["required"], *[name for name in config["optional"] if (root / name).is_file()]]
    for name in names:
        path = Path(name)
        if any(part in {".git", "output", "media", "data"} for part in path.parts):
            raise ValueError(f"runtime directory cannot enter exact artifact: {name}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ValueError(f"runtime/media file cannot enter exact artifact: {name}")
    payload = deterministic_tar_gz(root, names)
    filename = f"sea-speed-{component}-{source_commit}.tar.gz"
    artifact_path = output_dir / filename
    artifact_path.write_bytes(payload)
    files = [
        {"path": name, "sha256": sha256_file(root / name), "size": (root / name).stat().st_size}
        for name in sorted(names)
    ]
    return {
        "component": component,
        "filename": filename,
        "sha256": sha256_bytes(payload),
        "size": len(payload),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", default="dist/exact")
    args = parser.parse_args()
    source_commit = args.source_commit.lower()
    if not SHA40_RE.fullmatch(source_commit):
        raise SystemExit("source commit must be a full lowercase 40-character SHA")
    root = repository_root()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [build_component(root, output_dir, component, source_commit) for component in ("vps", "edge")]
    manifest = {
        "schema": "sea_speed_exact_artifacts_v1",
        "source_commit": source_commit,
        "artifacts": artifacts,
    }
    write_json_atomic(output_dir / "exact-artifacts.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
