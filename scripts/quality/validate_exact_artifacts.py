#!/usr/bin/env python3
"""Validate exact-artifact inventory, digest, extraction safety and syntax."""
from __future__ import annotations

import argparse
import py_compile
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import load_json, repository_root, sha256_file

REQUIRED_BY_COMPONENT = {
    "vps": {
        "api/app/main.py",
        "frontend/sea-speed/index.html",
        "frontend/sea-speed/objects/index.html",
        "frontend/root/index.html",
        "deploy/vps/deploy.sh",
    },
    "edge": {
        "worker/hls_motion_yolo_worker_events.py",
        "worker/hls_motion_yolo_runtime.py",
    },
}


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise ValueError(f"unsafe archive member: {member.name}")
    return members


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    root = repository_root()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    manifest = load_json(manifest_path)
    if manifest.get("schema") != "sea_speed_exact_artifacts_v1":
        raise SystemExit("unexpected exact-artifact manifest schema")
    if len(manifest.get("artifacts", [])) != 2:
        raise SystemExit("exact-artifact manifest must contain edge and VPS artifacts")

    seen: set[str] = set()
    for artifact in manifest["artifacts"]:
        component = artifact["component"]
        seen.add(component)
        archive_path = manifest_path.parent / artifact["filename"]
        if sha256_file(archive_path) != artifact["sha256"]:
            raise SystemExit(f"artifact digest mismatch: {component}")
        if archive_path.stat().st_size != artifact["size"]:
            raise SystemExit(f"artifact size mismatch: {component}")
        expected_files = {entry["path"] for entry in artifact["files"]}
        if not REQUIRED_BY_COMPONENT[component].issubset(expected_files):
            raise SystemExit(f"required inventory missing from {component}")
        for entry in artifact["files"]:
            source = root / entry["path"]
            if sha256_file(source) != entry["sha256"] or source.stat().st_size != entry["size"]:
                raise SystemExit(f"source inventory mismatch: {entry['path']}")

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            with tarfile.open(archive_path, mode="r:gz") as archive:
                members = safe_members(archive)
                member_names = {member.name for member in members if member.isfile()}
                if member_names != expected_files:
                    raise SystemExit(f"archive inventory mismatch: {component}")
                archive.extractall(target, members=members)
            for entry in artifact["files"]:
                extracted = target / entry["path"]
                if sha256_file(extracted) != entry["sha256"]:
                    raise SystemExit(f"extracted bytes mismatch: {entry['path']}")
            for py_path in target.rglob("*.py"):
                py_compile.compile(str(py_path), doraise=True)
            if component == "vps":
                subprocess.run(["bash", "-n", str(target / "deploy/vps/deploy.sh")], check=True)
                for html in (
                    target / "frontend/sea-speed/index.html",
                    target / "frontend/sea-speed/objects/index.html",
                    target / "frontend/root/index.html",
                ):
                    text = html.read_text(encoding="utf-8-sig")
                    if "<html" not in text.lower() or "</html>" not in text.lower():
                        raise SystemExit(f"invalid exact HTML artifact: {html}")

    if seen != {"edge", "vps"}:
        raise SystemExit("both edge and VPS exact artifacts are required")
    print("Exact artifacts valid: edge and VPS inventory, digests, extraction and syntax")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
