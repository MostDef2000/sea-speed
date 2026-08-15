#!/usr/bin/env python3
"""Validate exact-artifact inventory, digest, extraction safety and syntax."""
from __future__ import annotations

import argparse
import json
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
        "frontend/sea-speed/cameras/index.html",
        "frontend/root/index.html",
        "deploy/vps/deploy.sh",
    },
    "ubuntu-worker": {
        "scripts/worker/check_ubuntu_compatibility.py",
        "worker/hls_motion_yolo_worker_events.py",
        "worker/hls_motion_yolo_runtime.py",
        "worker/ubuntu_worker_entrypoint.py",
        "worker/ubuntu_ai_inference_worker.py",
        "deploy/worker/ubuntu/install-manual.sh",
        "deploy/worker/ubuntu/install-systemd.sh",
        "deploy/worker/ubuntu/update-exact.sh",
        "deploy/worker/ubuntu/rollback-exact.sh",
        "deploy/worker/ubuntu/preflight.sh",
        "deploy/worker/ubuntu/prepare-runtime.sh",
        "deploy/worker/ubuntu/requirements-runtime.txt",
        "deploy/worker/ubuntu/runtime-lock.json",
        "deploy/worker/ubuntu/worker.env.example",
        "deploy/worker/ubuntu/sea-speed-worker.service.template",
        "deploy/worker/ubuntu/sea-speed-worker-control.service.template",
        "deploy/worker/ubuntu/worker-control-agent.py",
        "deploy/worker/ubuntu/observed-worker-runner.py",
        "deploy/worker/ubuntu/verify-runtime-progression.py",
        "deploy/worker/ubuntu/check-worker-health.py",
    },
    "edge": {
        "worker/hls_motion_yolo_worker_events.py",
        "worker/hls_motion_yolo_runtime.py",
    },
}
QUALITY_EVIDENCE_COMPONENTS = {"vps", "edge"}
RELEASE_ONLY_COMPONENTS = {"ubuntu-worker"}


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise ValueError(f"unsafe archive member: {member.name}")
    return members


def validate_artifact(root: Path, manifest_path: Path, artifact: object, seen: set[str]) -> None:
    if not isinstance(artifact, dict):
        raise SystemExit("exact-artifact entry must be an object")
    component = artifact.get("component")
    if not isinstance(component, str) or component not in REQUIRED_BY_COMPONENT or component in seen:
        raise SystemExit(f"unexpected or duplicate exact-artifact component: {component}")
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
                target / "frontend/sea-speed/cameras/index.html",
                target / "frontend/root/index.html",
            ):
                text = html.read_text(encoding="utf-8-sig")
                if "<html" not in text.lower() or "</html>" not in text.lower():
                    raise SystemExit(f"invalid exact HTML artifact: {html}")
        elif component == "ubuntu-worker":
            for script in sorted((target / "deploy/worker/ubuntu").glob("*.sh")):
                subprocess.run(["bash", "-n", str(script)], check=True)
            runtime_lock = json.loads(
                (target / "deploy/worker/ubuntu/runtime-lock.json").read_text(encoding="utf-8")
            )
            if runtime_lock.get("schema_version") != 1:
                raise SystemExit("Ubuntu Worker runtime lock schema is invalid")


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

    quality_artifacts = manifest.get("artifacts", [])
    release_artifacts = manifest.get("release_artifacts", [])
    if not isinstance(quality_artifacts, list) or not isinstance(release_artifacts, list):
        raise SystemExit("exact-artifact inventories must be lists")
    if {item.get("component") for item in quality_artifacts if isinstance(item, dict)} != QUALITY_EVIDENCE_COMPONENTS:
        raise SystemExit("quality-evidence exact artifacts must remain VPS and edge")
    if {item.get("component") for item in release_artifacts if isinstance(item, dict)} != RELEASE_ONLY_COMPONENTS:
        raise SystemExit("release-specific exact artifacts must contain Ubuntu Worker")
    if len(quality_artifacts) != 2 or len(release_artifacts) != 1:
        raise SystemExit("exact-artifact manifest must contain two quality artifacts and one Ubuntu release artifact")

    seen: set[str] = set()
    for artifact in [*quality_artifacts, *release_artifacts]:
        validate_artifact(root, manifest_path, artifact, seen)

    if seen != set(REQUIRED_BY_COMPONENT):
        raise SystemExit("VPS, Ubuntu Worker, and edge exact artifacts are all required")
    print(
        "Exact artifacts valid: VPS/edge quality evidence plus Ubuntu Worker release inventory, "
        "digests, extraction and syntax"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
