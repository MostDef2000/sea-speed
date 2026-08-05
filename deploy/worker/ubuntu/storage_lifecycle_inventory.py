from __future__ import annotations

import hashlib
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_lifecycle_common import (
    EVENT_SUFFIXES,
    SCHEMA_VERSION,
    UPDATER_DIR_RE,
    UPDATER_FILE_RE,
    LifecycleError,
    canonical_json,
    determine_protected,
    fingerprint,
    inventory_releases,
    load_pins,
    tree_size,
    utc_now,
    validate_active_state,
)


def age_days(mtime_ns: int, now_ns: int) -> float:
    return max(0.0, (now_ns - mtime_ns) / 1_000_000_000 / 86400)


def make_item(path: Path, allowed_root: Path, category: str, reason: str) -> dict[str, Any]:
    info = fingerprint(path)
    size_bytes = tree_size(path) if info["kind"] == "directory" else info["size"]
    return {
        "path": str(path),
        "allowed_root": str(allowed_root),
        "category": category,
        "reason": reason,
        "size_bytes": size_bytes,
        "fingerprint": info,
    }


def build_inventory(args) -> dict[str, Any]:
    install_root = Path(args.install_root).resolve()
    active_commit = validate_active_state(install_root, Path(args.unit_file), args.service_name)
    pins_file = Path(args.pins_file or install_root / "storage/protected-releases")
    pins = load_pins(pins_file)
    releases = inventory_releases(install_root / "releases")
    protected, retained = determine_protected(releases, active_commit, pins, args.keep_releases)
    usage = shutil.disk_usage(install_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "install_root": str(install_root),
        "active_commit": active_commit,
        "pins": sorted(pins),
        "retained_rollback_candidates": retained,
        "protected_commits": sorted(protected),
        "disk": {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free},
        "releases": releases,
    }


def build_plan(args) -> dict[str, Any]:
    inventory = build_inventory(args)
    install_root = Path(inventory["install_root"])
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
    protected = set(inventory["protected_commits"])
    items: list[dict[str, Any]] = []

    releases_root = install_root / "releases"
    for record in inventory["releases"]:
        commit = record["commit"]
        valid = record["valid_name"] and record["safe_directory"] and record["provenance_valid"] and record["quality_approved"]
        if not valid or commit in protected:
            continue
        if age_days(record["mtime_ns"], now_ns) >= args.release_min_age_days:
            items.append(make_item(Path(record["path"]), releases_root, "release", "unprotected_exact_release_past_minimum_age"))

    events_root = install_root / "shared/output/events"
    if events_root.exists() and events_root.is_dir() and not events_root.is_symlink():
        for path in sorted(events_root.iterdir(), key=lambda item: item.name):
            try:
                info = path.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode) or path.is_symlink() or path.suffix.lower() not in EVENT_SUFFIXES:
                continue
            if age_days(info.st_mtime_ns, now_ns) >= args.event_retention_days:
                items.append(make_item(path, events_root, "event_artifact", "event_file_past_retention"))

    updater_root = install_root / "updater"
    if updater_root.exists() and updater_root.is_dir() and not updater_root.is_symlink():
        for path in sorted(updater_root.iterdir(), key=lambda item: item.name):
            try:
                info = path.lstat()
            except OSError:
                continue
            known = (stat.S_ISDIR(info.st_mode) and UPDATER_DIR_RE.fullmatch(path.name)) or (
                stat.S_ISREG(info.st_mode) and UPDATER_FILE_RE.fullmatch(path.name)
            )
            if known and not path.is_symlink() and age_days(info.st_mtime_ns, now_ns) >= args.updater_temp_retention_days:
                items.append(make_item(path, updater_root, "updater_temporary", "stale_known_updater_temporary"))

    items.sort(key=lambda item: (item["category"], item["path"]))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "install_root": str(install_root),
        "active_commit": inventory["active_commit"],
        "settings": {
            "keep_releases": args.keep_releases,
            "release_min_age_days": args.release_min_age_days,
            "event_retention_days": args.event_retention_days,
            "updater_temp_retention_days": args.updater_temp_retention_days,
            "pins_file": str(Path(args.pins_file or install_root / "storage/protected-releases")),
            "unit_file": args.unit_file,
            "service_name": args.service_name,
        },
        "protected_commits": inventory["protected_commits"],
        "retained_rollback_candidates": inventory["retained_rollback_candidates"],
        "items": items,
        "summary": {
            "item_count": len(items),
            "reclaimable_bytes": sum(item["size_bytes"] for item in items),
        },
    }
    payload["plan_id"] = hashlib.sha256(canonical_json(payload)).hexdigest()
    return payload

