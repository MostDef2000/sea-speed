#!/usr/bin/env python3
"""Evaluate local Sea Speed worker health without reading secrets."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds(value: object) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def run_command(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return completed.returncode, completed.stdout.strip()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, default=Path("/opt/sea-speed-worker"))
    parser.add_argument("--service-name", default="sea-speed-worker.service")
    parser.add_argument("--unit-path", type=Path)
    parser.add_argument("--expected-commit", default="")
    parser.add_argument("--expected-profile", default="")
    parser.add_argument("--expected-camera-id", default="")
    parser.add_argument("--heartbeat", type=Path)
    parser.add_argument("--write-report", type=Path)
    parser.add_argument("--max-heartbeat-age-sec", type=float, default=30.0)
    parser.add_argument("--max-frame-age-sec", type=float, default=30.0)
    parser.add_argument("--max-state-post-age-sec", type=float, default=90.0)
    parser.add_argument("--min-free-gib", type=float, default=10.0)
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()

    if args.expected_commit and not SHA40_RE.fullmatch(args.expected_commit):
        raise SystemExit("expected commit must be a lowercase 40-character SHA")
    for value, label in (
        (args.max_heartbeat_age_sec, "max heartbeat age"),
        (args.max_frame_age_sec, "max frame age"),
        (args.max_state_post_age_sec, "max state post age"),
        (args.min_free_gib, "minimum free GiB"),
    ):
        if value < 0:
            raise SystemExit(f"{label} must be non-negative")

    install_root = args.install_root
    active_marker = install_root / "shared/runtime/active-source-commit"
    heartbeat_path = args.heartbeat or install_root / "shared/runtime/worker-heartbeat.json"
    report_path = args.write_report or install_root / "observability/worker-health-report.json"
    unit_path = args.unit_path or Path("/etc/systemd/system") / args.service_name

    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    active_commit = ""
    try:
        active_commit = active_marker.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    add("active_marker", bool(SHA40_RE.fullmatch(active_commit)), "valid" if SHA40_RE.fullmatch(active_commit) else "missing_or_invalid")

    if args.expected_commit:
        add("expected_commit", active_commit == args.expected_commit, "match" if active_commit == args.expected_commit else "mismatch")

    release_root = install_root / "releases" / active_commit if SHA40_RE.fullmatch(active_commit) else install_root / "releases/invalid"
    provenance = ""
    try:
        provenance = (release_root / "source-commit").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    add("release_provenance", provenance == active_commit and bool(active_commit), "match" if provenance == active_commit and active_commit else "mismatch")

    quality_content = ""
    try:
        quality_content = (release_root / "quality-approved").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    expected_quality = f"source_commit={active_commit}\nquality_check=quality-integration" if active_commit else ""
    quality_ok = bool(active_commit) and quality_content == expected_quality
    add("quality_approved", quality_ok, "exact" if quality_ok else "missing_or_mismatch")

    unit_text = ""
    try:
        unit_text = unit_path.read_text(encoding="utf-8")
    except OSError:
        pass
    unit_matches = bool(active_commit) and active_commit in unit_text and "observed-worker-runner.py" in unit_text
    add("installed_unit", unit_matches, "exact_observed_runner" if unit_matches else "missing_or_mismatch")
    if args.expected_profile:
        profile_marker = f"Environment=ANALYTICS_PROFILE={args.expected_profile}"
        profile_ok = profile_marker in unit_text
        add("analytics_profile", profile_ok, args.expected_profile if profile_ok else "missing_or_mismatch")
    if args.expected_camera_id:
        camera_marker = f"Environment=CAMERA_ID={args.expected_camera_id}"
        camera_ok = camera_marker in unit_text
        add("camera_id", camera_ok, args.expected_camera_id if camera_ok else "missing_or_mismatch")

    active_rc, _ = run_command(["systemctl", "is-active", "--quiet", args.service_name])
    add("service_active", active_rc == 0, "active" if active_rc == 0 else "inactive")

    exec_rc, exec_start = run_command(["systemctl", "show", "-p", "ExecStart", "--value", args.service_name])
    exec_matches = exec_rc == 0 and bool(active_commit) and active_commit in exec_start and "observed-worker-runner.py" in exec_start
    add("running_exec", exec_matches, "exact_observed_runner" if exec_matches else "missing_or_mismatch")

    heartbeat: dict[str, Any] = {}
    try:
        loaded = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            heartbeat = loaded
    except (OSError, json.JSONDecodeError):
        pass

    heartbeat_age = age_seconds(heartbeat.get("observed_at"))
    heartbeat_fresh = heartbeat_age is not None and heartbeat_age <= args.max_heartbeat_age_sec
    add("heartbeat_fresh", heartbeat_fresh, "fresh" if heartbeat_fresh else "missing_or_stale")

    heartbeat_commit_ok = heartbeat.get("source_commit") == active_commit and bool(active_commit)
    add("heartbeat_commit", heartbeat_commit_ok, "match" if heartbeat_commit_ok else "mismatch")

    phase_ok = heartbeat.get("phase") == "running"
    add("worker_phase", phase_ok, "running" if phase_ok else "not_running")

    frame_age = age_seconds(heartbeat.get("last_frame_at"))
    frame_progress = isinstance(heartbeat.get("frame_progress_sequence"), int) and heartbeat.get("frame_progress_sequence", 0) > 0
    frame_fresh = frame_progress and frame_age is not None and frame_age <= args.max_frame_age_sec
    add("frame_progress", frame_fresh, "fresh" if frame_fresh else "missing_or_stale")

    state_post_age = age_seconds(heartbeat.get("last_state_post_at"))
    state_post_ok = heartbeat.get("last_state_post_ok") is True and state_post_age is not None and state_post_age <= args.max_state_post_age_sec
    add("state_post", state_post_ok, "recent_success" if state_post_ok else "missing_failed_or_stale")

    try:
        disk = shutil.disk_usage(install_root)
        free_bytes = int(disk.free)
    except OSError:
        free_bytes = -1
    minimum_free_bytes = int(args.min_free_gib * (1024**3))
    disk_ok = free_bytes >= minimum_free_bytes
    add("disk_headroom", disk_ok, "sufficient" if disk_ok else "insufficient_or_unknown")

    gpu_count = 0
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        gpu_rc, gpu_output = run_command([
            nvidia_smi,
            "--query-gpu=index",
            "--format=csv,noheader,nounits",
        ])
        if gpu_rc == 0:
            gpu_count = len([line for line in gpu_output.splitlines() if line.strip()])
    gpu_visible = gpu_count > 0
    add("gpu_visible", gpu_visible or not args.require_gpu, "visible" if gpu_visible else ("required_missing" if args.require_gpu else "not_required"))

    healthy = all(bool(check["ok"]) for check in checks)
    report = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "overall": "healthy" if healthy else "unhealthy",
        "active_commit": active_commit or None,
        "expected_commit": args.expected_commit or None,
        "heartbeat_age_sec": round(heartbeat_age, 3) if heartbeat_age is not None else None,
        "frame_age_sec": round(frame_age, 3) if frame_age is not None else None,
        "state_post_age_sec": round(state_post_age, 3) if state_post_age is not None else None,
        "frame_progress_sequence": heartbeat.get("frame_progress_sequence") if isinstance(heartbeat.get("frame_progress_sequence"), int) else None,
        "state_post_success_count": heartbeat.get("state_post_success_count") if isinstance(heartbeat.get("state_post_success_count"), int) else None,
        "state_post_failure_count": heartbeat.get("state_post_failure_count") if isinstance(heartbeat.get("state_post_failure_count"), int) else None,
        "event_post_success_count": heartbeat.get("event_post_success_count") if isinstance(heartbeat.get("event_post_success_count"), int) else None,
        "disk_free_bytes": free_bytes if free_bytes >= 0 else None,
        "gpu_count": gpu_count,
        "checks": checks,
    }

    atomic_write_json(report_path, report)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
