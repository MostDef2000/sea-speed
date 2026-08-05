from __future__ import annotations

import hashlib
import json
import shutil
import stat
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
    path_within,
    release_record,
    require_root_owned_file,
    require_sha,
    utc_now,
    validate_active_state,
)

def validate_item_path(item: dict[str, Any], install_root: Path) -> tuple[Path, Path]:
    path = Path(item["path"])
    allowed_root = Path(item["allowed_root"])
    permitted_roots = {
        (install_root / "releases").resolve(),
        (install_root / "shared/output/events").resolve(),
        (install_root / "updater").resolve(),
    }
    if allowed_root.resolve() not in permitted_roots or not path_within(path, allowed_root):
        raise LifecycleError(f"planned path escapes an allowed root: {path}")
    if path == allowed_root:
        raise LifecycleError(f"refusing to delete allowed root itself: {path}")
    return path, allowed_root


def validate_planned_item(item: dict[str, Any], install_root: Path, protected: set[str]) -> tuple[Path, str]:
    path, allowed_root = validate_item_path(item, install_root)
    if not path.exists() or path.is_symlink():
        raise LifecycleError(f"planned item missing or became a symlink: {path}")
    if fingerprint(path) != item.get("fingerprint"):
        raise LifecycleError(f"planned item fingerprint changed: {path}")
    category = item.get("category")
    if category == "release":
        if path.name in protected:
            raise LifecycleError(f"release became protected after planning: {path.name}")
        record = release_record(path)
        valid = record["valid_name"] and record["safe_directory"] and record["provenance_valid"] and record["quality_approved"]
        if not valid:
            raise LifecycleError(f"release is not an exact quality-approved deletion target: {path}")
    elif category == "event_artifact":
        info = path.lstat()
        if allowed_root != install_root / "shared/output/events" or not stat.S_ISREG(info.st_mode) or path.suffix.lower() not in EVENT_SUFFIXES:
            raise LifecycleError(f"invalid event artifact target: {path}")
    elif category == "updater_temporary":
        info = path.lstat()
        known = (stat.S_ISDIR(info.st_mode) and UPDATER_DIR_RE.fullmatch(path.name)) or (
            stat.S_ISREG(info.st_mode) and UPDATER_FILE_RE.fullmatch(path.name)
        )
        if not known:
            raise LifecycleError(f"invalid updater temporary target: {path}")
    else:
        raise LifecycleError(f"unknown planned category: {category}")
    return path, category


def load_plan(path: Path) -> dict[str, Any]:
    require_root_owned_file(path, 0o600)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"cannot load plan: {path}: {exc}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise LifecycleError("unsupported storage plan schema")
    plan_id = payload.get("plan_id")
    unsigned = dict(payload)
    unsigned.pop("plan_id", None)
    if plan_id != hashlib.sha256(canonical_json(unsigned)).hexdigest():
        raise LifecycleError("storage plan digest mismatch")
    return payload


def apply_plan(args) -> dict[str, Any]:
    install_root = Path(args.install_root).resolve()
    expected_active = require_sha(args.expected_active, "expected active commit")
    plan = load_plan(Path(args.plan_file))
    if Path(plan.get("install_root", "")).resolve() != install_root:
        raise LifecycleError("storage plan install root mismatch")
    if plan.get("active_commit") != expected_active:
        raise LifecycleError("storage plan active commit does not match --expected-active")
    settings = plan.get("settings") or {}
    current_active = validate_active_state(
        install_root,
        Path(settings.get("unit_file") or args.unit_file),
        settings.get("service_name") or args.service_name,
    )
    if current_active != expected_active:
        raise LifecycleError("active commit changed after planning")
    pins = load_pins(Path(settings.get("pins_file") or install_root / "storage/protected-releases"))
    releases = inventory_releases(install_root / "releases")
    protected, retained = determine_protected(releases, current_active, pins, int(settings.get("keep_releases", 0)))
    validated = [validate_planned_item(item, install_root, protected) for item in plan.get("items", [])]

    deleted: list[dict[str, Any]] = []
    for (path, category), item in zip(validated, plan.get("items", []), strict=True):
        shutil.rmtree(path) if path.is_dir() else path.unlink()
        deleted.append({"path": str(path), "category": category, "size_bytes": item["size_bytes"]})
    return {
        "schema_version": SCHEMA_VERSION,
        "applied_at": utc_now(),
        "plan_id": plan["plan_id"],
        "install_root": str(install_root),
        "active_commit": current_active,
        "retained_rollback_candidates": retained,
        "deleted": deleted,
        "summary": {
            "deleted_count": len(deleted),
            "reclaimed_planned_bytes": sum(item["size_bytes"] for item in deleted),
        },
    }
