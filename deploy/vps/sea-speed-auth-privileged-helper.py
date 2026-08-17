#!/usr/bin/env python3
"""Least-privilege root helper for the Sea Speed Auth v1 VPS boundary.

The sudo policy permits only this installed root-owned executable with no command-line
arguments. The unprivileged deployment process communicates through one fixed request
file. Every request is bound to one exact source SHA and to a root-owned bundle whose
asset digests must match the staged exact release before any privileged mutation runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

AUTHENTIK_UPSTREAM = "http://10.123.239.102:19000"
WORKER_PRIVATE_LISTEN = "10.123.239.101:18080"
WORKER_PRIVATE_PEER = "10.123.239.102"

ASSET_PATHS = (
    "deploy/vps/sea-speed-auth-cutover.sh",
    "scripts/operations/nginx_cam1_direct_h264.py",
    "scripts/operations/nginx_sea_speed_auth.py",
)


@dataclass(frozen=True)
class RuntimePaths:
    request_file: Path = Path("/opt/sea-speed-deploy/state/auth-privileged-request.json")
    releases_root: Path = Path("/opt/sea-speed-deploy/releases")
    bundle_root: Path = Path("/usr/local/lib/sea-speed-auth-privileged")
    helper_path: Path = Path("/usr/local/sbin/sea-speed-auth-privileged-helper")


class BoundaryError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_secure(path: Path, required_uid: int) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise BoundaryError(f"required file missing: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise BoundaryError(f"required path is not a regular non-symlink file: {path}")
    if metadata.st_uid != required_uid:
        raise BoundaryError(f"required file has unexpected owner: {path}")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise BoundaryError(f"required file is group/world writable: {path}")


def require_request_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise BoundaryError(f"privileged request missing: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise BoundaryError("privileged request must be a regular non-symlink file")
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise BoundaryError("privileged request must not be accessible to group/other")


def load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundaryError(f"invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise BoundaryError(f"JSON root must be an object: {path}")
    return payload


def validate_release_path(paths: RuntimePaths, source_sha: str, raw: object) -> Path:
    if not isinstance(raw, str):
        raise BoundaryError("release_path must be a string")
    expected = paths.releases_root / source_sha
    if raw != str(expected):
        raise BoundaryError("release_path must be the exact canonical release directory")
    try:
        resolved = expected.resolve(strict=True)
        releases_resolved = paths.releases_root.resolve(strict=True)
    except OSError as exc:
        raise BoundaryError("release path cannot be resolved") from exc
    if resolved != releases_resolved / source_sha:
        raise BoundaryError("release path escapes the canonical releases root")
    metadata = expected.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise BoundaryError("release path must be a real directory")
    return expected


def require_release_asset(release: Path, relative: str) -> Path:
    current = release
    for part in Path(relative).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise BoundaryError(f"staged exact-release asset is missing: {relative}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise BoundaryError(f"staged exact-release path contains a symlink: {relative}")
    if not current.is_file():
        raise BoundaryError(f"staged exact-release asset is not a regular file: {relative}")
    return current


def validate_request(paths: RuntimePaths) -> tuple[str, str, Path]:
    require_request_file(paths.request_file)
    request = load_json(paths.request_file)
    if request.get("schema") != "sea_speed_auth_privileged_request_v1":
        raise BoundaryError("unexpected privileged request schema")
    if set(request) != {"schema", "action", "source_sha", "release_path"}:
        raise BoundaryError("privileged request contains unexpected fields")
    action = request.get("action")
    if action not in {"status", "reconcile"}:
        raise BoundaryError("unsupported privileged action")
    source_sha = request.get("source_sha")
    if not isinstance(source_sha, str) or not SHA40_RE.fullmatch(source_sha):
        raise BoundaryError("source_sha must be a lowercase 40-character SHA")
    release = validate_release_path(paths, source_sha, request.get("release_path"))
    return action, source_sha, release


def validate_bundle(
    paths: RuntimePaths,
    source_sha: str,
    release: Path,
    *,
    required_uid: int,
) -> Path:
    manifest_path = paths.bundle_root / "manifest.json"
    require_regular_secure(manifest_path, required_uid)
    require_regular_secure(paths.helper_path, required_uid)
    manifest = load_json(manifest_path)
    if manifest.get("schema") != "sea_speed_auth_privileged_bundle_v1":
        raise BoundaryError("unexpected privileged bundle schema")
    if set(manifest) != {"schema", "source_sha", "helper_sha256", "assets"}:
        raise BoundaryError("privileged bundle manifest contains unexpected fields")
    if manifest.get("source_sha") != source_sha:
        raise BoundaryError("privileged bundle source SHA does not match request")
    helper_sha = manifest.get("helper_sha256")
    if not isinstance(helper_sha, str) or not SHA256_RE.fullmatch(helper_sha):
        raise BoundaryError("invalid helper digest in privileged bundle")
    if sha256_file(paths.helper_path) != helper_sha:
        raise BoundaryError("installed privileged helper digest mismatch")
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or set(assets) != set(ASSET_PATHS):
        raise BoundaryError("privileged bundle asset inventory mismatch")

    repo_root = paths.bundle_root / "repo"
    for relative in ASSET_PATHS:
        expected_sha = assets.get(relative)
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
            raise BoundaryError(f"invalid bundle digest for {relative}")
        installed = repo_root / relative
        staged = require_release_asset(release, relative)
        require_regular_secure(installed, required_uid)
        installed_sha = sha256_file(installed)
        staged_sha = sha256_file(staged)
        if installed_sha != expected_sha:
            raise BoundaryError(f"installed privileged asset digest mismatch: {relative}")
        if staged_sha != expected_sha:
            raise BoundaryError(f"staged release does not match installed privileged bundle: {relative}")
    return repo_root


def run_cutover(repo_root: Path, runner: Callable[..., subprocess.CompletedProcess[str]]) -> str:
    cutover = repo_root / "deploy/vps/sea-speed-auth-cutover.sh"
    common = [
        "--authentik-upstream",
        AUTHENTIK_UPSTREAM,
        "--worker-private-listen",
        WORKER_PRIVATE_LISTEN,
        "--worker-private-peer",
        WORKER_PRIVATE_PEER,
        "--require-protected-baseline",
    ]
    prepared = runner(
        ["bash", str(cutover), "prepare", *common],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = prepared.stdout or ""
    if prepared.returncode != 0:
        raise BoundaryError(f"Auth v1 prepare failed rc={prepared.returncode}\n{output.rstrip()}")
    candidate = ""
    for line in output.splitlines():
        if line.startswith("CANDIDATE_SHA256="):
            candidate = line.split("=", 1)[1].strip()
    if not SHA256_RE.fullmatch(candidate):
        raise BoundaryError("Auth v1 prepare did not return an exact candidate SHA256")

    activated = runner(
        ["bash", str(cutover), "activate", *common, "--expected-sha256", candidate],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output += activated.stdout or ""
    if activated.returncode != 0:
        raise BoundaryError(f"Auth v1 activate failed rc={activated.returncode}\n{output.rstrip()}")
    for marker in (
        "SEA_SPEED_AUTH_CUTOVER=PASS",
        "WORKER_PRIVATE_ROAD_API_BASE=",
        "ROLLBACK_CAPABILITY=VERIFIED",
    ):
        if marker not in output:
            raise BoundaryError(f"Auth v1 activation missing marker: {marker}")
    return output


def execute_request(
    paths: RuntimePaths = RuntimePaths(),
    *,
    required_uid: int = 0,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    action, source_sha, release = validate_request(paths)
    repo_root = validate_bundle(paths, source_sha, release, required_uid=required_uid)
    lines = [
        "SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS",
        f"SOURCE_SHA={source_sha}",
        f"ACTION={action}",
        "PRIVILEGED_TOPOLOGY=FIXED",
        "ARBITRARY_ROOT_EXECUTION=NO",
    ]
    if action == "reconcile":
        output = run_cutover(repo_root, runner)
        lines.extend(output.rstrip().splitlines())
        lines.append("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS")
    return lines


def main() -> int:
    if os.geteuid() != 0:
        print("ERROR privileged helper must run as root", file=sys.stderr)
        return 1
    if len(sys.argv) != 1:
        print("ERROR privileged helper accepts no command-line arguments", file=sys.stderr)
        return 2
    try:
        for line in execute_request():
            print(line)
    except BoundaryError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
