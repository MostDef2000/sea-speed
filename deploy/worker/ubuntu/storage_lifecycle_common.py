from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
UPDATER_DIR_RE = re.compile(r"^staging\.[A-Za-z0-9]+$")
UPDATER_FILE_RE = re.compile(r"^(unit-backup|active-marker)\.[A-Za-z0-9]+$")
EVENT_SUFFIXES = {".jpg", ".jpeg", ".png", ".json"}
SCHEMA_VERSION = 1


class LifecycleError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise LifecycleError(f"cannot read required file: {path}: {exc}") from exc


def require_sha(value: str, label: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise LifecycleError(f"{label} must be a lowercase 40-character SHA")
    return value


def path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def atomic_write_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def require_root_owned_file(path: Path, mode: int) -> None:
    try:
        info = path.stat()
    except OSError as exc:
        raise LifecycleError(f"required protected file missing: {path}: {exc}") from exc
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != mode:
        raise LifecycleError(f"protected file must be root-owned mode {mode:o}: {path}")


def load_pins(path: Path) -> set[str]:
    require_root_owned_file(path, 0o600)
    pins: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if not SHA_RE.fullmatch(value):
            raise LifecycleError(f"invalid pinned release SHA at {path}:{number}")
        pins.add(value)
    return pins


def run_systemctl(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["systemctl", *arguments],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise LifecycleError(f"systemctl unavailable: {exc}") from exc


def validate_active_state(install_root: Path, unit_file: Path, service_name: str) -> str:
    active_marker = install_root / "shared/runtime/active-source-commit"
    active_commit = require_sha(read_text(active_marker), "active source commit")
    if not unit_file.is_file() or unit_file.is_symlink():
        raise LifecycleError(f"installed worker unit missing or unsafe: {unit_file}")
    if active_commit not in read_text(unit_file):
        raise LifecycleError("installed unit and active source marker disagree")
    if run_systemctl(["is-active", "--quiet", service_name]).returncode != 0:
        raise LifecycleError("worker service is not active")
    shown = run_systemctl(["show", "-p", "ExecStart", "--value", service_name])
    if shown.returncode != 0 or active_commit not in shown.stdout:
        raise LifecycleError("running ExecStart and active source marker disagree")
    return active_commit


def tree_size(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
        root_path = Path(root)
        dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
        for name in files:
            item = root_path / name
            try:
                info = item.lstat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def fingerprint(path: Path) -> dict[str, Any]:
    info = path.lstat()
    kind = "directory" if stat.S_ISDIR(info.st_mode) else "file" if stat.S_ISREG(info.st_mode) else "other"
    return {
        "kind": kind,
        "device": info.st_dev,
        "inode": info.st_ino,
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }


def quality_marker_valid(release: Path, commit: str) -> bool:
    marker = release / "quality-approved"
    try:
        info = marker.stat()
        expected = f"source_commit={commit}\nquality_check=quality-integration"
        return (
            marker.is_file()
            and not marker.is_symlink()
            and info.st_uid == 0
            and stat.S_IMODE(info.st_mode) == 0o644
            and marker.read_text(encoding="utf-8").strip() == expected
        )
    except OSError:
        return False


def release_record(path: Path) -> dict[str, Any]:
    commit = path.name
    valid_name = bool(SHA_RE.fullmatch(commit))
    safe_directory = path.is_dir() and not path.is_symlink()
    provenance_valid = False
    quality_approved = False
    if valid_name and safe_directory:
        provenance = path / "source-commit"
        try:
            provenance_valid = provenance.is_file() and not provenance.is_symlink() and read_text(provenance) == commit
        except LifecycleError:
            provenance_valid = False
        quality_approved = provenance_valid and quality_marker_valid(path, commit)
    info = path.lstat()
    return {
        "commit": commit,
        "path": str(path),
        "valid_name": valid_name,
        "safe_directory": safe_directory,
        "provenance_valid": provenance_valid,
        "quality_approved": quality_approved,
        "mtime_ns": info.st_mtime_ns,
        "size_bytes": tree_size(path) if safe_directory else 0,
    }


def inventory_releases(releases_root: Path) -> list[dict[str, Any]]:
    if not releases_root.exists():
        return []
    return [release_record(path) for path in sorted(releases_root.iterdir(), key=lambda item: item.name)]


def determine_protected(
    releases: list[dict[str, Any]], active_commit: str, pins: set[str], keep_releases: int
) -> tuple[set[str], list[str]]:
    eligible = [item for item in releases if item["quality_approved"]]
    eligible.sort(key=lambda item: (item["mtime_ns"], item["commit"]), reverse=True)
    retained: list[str] = []
    for item in eligible:
        commit = item["commit"]
        if commit == active_commit or commit in pins:
            continue
        if len(retained) >= keep_releases:
            break
        retained.append(commit)
    return {active_commit, *pins, *retained}, retained


def acquire_lock(install_root: Path):
    updater_root = install_root / "updater"
    updater_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(updater_root, 0o700)
    lock_path = updater_root / "update.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise LifecycleError("another worker update, rollback or storage operation is running") from exc
    return handle
