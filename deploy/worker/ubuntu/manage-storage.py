#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from storage_lifecycle_common import LifecycleError, acquire_lock, atomic_write_json
from storage_lifecycle_apply import apply_plan
from storage_lifecycle_inventory import build_inventory, build_plan


def common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--install-root", default="/opt/sea-speed-worker")
    parser.add_argument("--unit-file", default="/etc/systemd/system/sea-speed-worker.service")
    parser.add_argument("--service-name", default="sea-speed-worker.service")
    parser.add_argument("--pins-file")
    parser.add_argument("--keep-releases", type=int, default=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded Sea Speed worker storage lifecycle")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory")
    common_arguments(inventory_parser)
    inventory_parser.add_argument("--report-file")

    plan_parser = subparsers.add_parser("plan")
    common_arguments(plan_parser)
    plan_parser.add_argument("--plan-file", required=True)
    plan_parser.add_argument("--release-min-age-days", type=float, default=14.0)
    plan_parser.add_argument("--event-retention-days", type=float, default=30.0)
    plan_parser.add_argument("--updater-temp-retention-days", type=float, default=7.0)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--install-root", default="/opt/sea-speed-worker")
    apply_parser.add_argument("--unit-file", default="/etc/systemd/system/sea-speed-worker.service")
    apply_parser.add_argument("--service-name", default="sea-speed-worker.service")
    apply_parser.add_argument("--plan-file", "--apply-plan", dest="plan_file", required=True)
    apply_parser.add_argument("--expected-active", required=True)
    apply_parser.add_argument("--report-file")

    args = parser.parse_args()
    if getattr(args, "keep_releases", 0) < 0:
        parser.error("--keep-releases must be nonnegative")
    for name in ("release_min_age_days", "event_retention_days", "updater_temp_retention_days"):
        if hasattr(args, name) and getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be nonnegative")
    return args


def main() -> int:
    args = parse_args()
    if os.geteuid() != 0:
        print("ERROR run as root", file=sys.stderr)
        return 1
    install_root = Path(args.install_root).resolve()
    lock = None
    try:
        lock = acquire_lock(install_root)
        if args.command == "inventory":
            payload = build_inventory(args)
            report = Path(args.report_file or install_root / "storage/storage-inventory.json")
        elif args.command == "plan":
            payload = build_plan(args)
            report = Path(args.plan_file)
        else:
            payload = apply_plan(args)
            report = Path(args.report_file or install_root / "storage/storage-apply-report.json")
        atomic_write_json(report, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0
    except LifecycleError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR storage operation failed: {exc}", file=sys.stderr)
        return 3
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
