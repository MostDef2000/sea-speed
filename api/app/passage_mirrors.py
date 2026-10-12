"""Passage -> object registry mirror layer for the Sea Speed API (issue #396, wave 2).

Functions extracted verbatim from ``api/app/main.py``: the water-passage to
objects-registry mirror write (``persist_passage_object``), the startup
backfill (``import_existing_passages``) and the mirror lifecycle prunes
(``_delete_passage_mirrors`` / ``reconcile_passage_mirrors``).

Depends on ``objects_registry`` for the objects DB layer and on
``open_passages_db`` for the water-passages store. The passages store stays
in ``main.py`` this wave, and importing ``main`` from here would create an
import cycle, so ``main.py`` binds the connection factory into this module
right after its definition (the ``open_passages_db`` sentinel below is
replaced before any caller can run: main's module-level mirror backfill at
the bottom of its import sequence follows the binding). Same dual import
idiom as ``main.py``/``identity.py``: one canonical instance per import mode.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:  # package context (api.app.passage_mirrors) and direct-file load both supported
    from . import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .identity import now_iso
    from . import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .objects_registry import (
        open_objects_db,
        optional_float,
        optional_int,
        prune_objects_registry,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from identity import now_iso
    import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from objects_registry import (
        open_objects_db,
        optional_float,
        optional_int,
        prune_objects_registry,
    )

__all__ = [
    "persist_passage_object",
    "import_existing_passages",
    "_delete_passage_mirrors",
    "reconcile_passage_mirrors",
]

# Bound by main.py immediately after its open_passages_db definition (the
# water-passages store remains in main.py this wave). Never called before
# that binding: every caller lives in main.py's module tail or route handlers.
open_passages_db = None

def persist_passage_object(passage: Dict[str, Any]) -> bool:
    snapshot_url = passage.get("snapshot_url")
    if not snapshot_url or not str(snapshot_url).strip().startswith("/sea-speed/media/"):
        return False
    passage_id = str(passage.get("passage_id") or "").strip()
    if not passage_id:
        return False
    object_id = f"passage-{passage_id}"
    started_at = str(passage.get("started_at") or passage.get("last_seen_at") or now_iso())
    class_name = str(passage.get("class_name") or "vessel")
    fragments = passage.get("track_fragments")
    track_id = None
    if isinstance(fragments, list):
        for value in fragments:
            track_id = optional_int(value)
            if track_id is not None:
                break
    original_event_json = json.dumps(
        {"registry_mirror_schema": "sea_speed_water_passage_registry_mirror_v1", "passage": passage},
        ensure_ascii=False,
        sort_keys=True,
    )
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                analytics_profile, domain, object_type, model_class,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, 'cam1', ?, ?, ?, 'water-v1', 'water', ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            ON CONFLICT(object_id) DO UPDATE SET
                track_id=excluded.track_id,
                class_name=excluded.class_name,
                object_type=excluded.object_type,
                model_class=excluded.model_class,
                confidence=excluded.confidence,
                speed_kmh=excluded.speed_kmh,
                snapshot_url=excluded.snapshot_url,
                original_event_json=excluded.original_event_json,
                updated_at=excluded.updated_at
            """,
            (
                object_id,
                track_id,
                started_at,
                class_name,
                class_name,
                class_name,
                optional_float(passage.get("confidence")),
                optional_float(passage.get("speed_kmh")),
                passage.get("snapshot_url"),
                original_event_json,
                started_at,
                now_iso(),
            ),
        )
        inserted_or_updated = cursor.rowcount > 0
        if inserted_or_updated:
            prune_objects_registry(connection)
        return inserted_or_updated


def import_existing_passages() -> int:
    try:
        with open_passages_db() as connection:
            rows = connection.execute("SELECT * FROM water_passages").fetchall()
    except Exception:
        return 0
    mirrored = 0
    for row in rows:
        try:
            if persist_passage_object(dict(row)):
                mirrored += 1
        except Exception as error:
            print(f"passage registry mirror failed for {row['passage_id']}: {error}", file=sys.stderr)
    return mirrored


def _delete_passage_mirrors(passage_ids: List[str]) -> int:
    ids = [str(value) for value in passage_ids if str(value or "").strip()]
    if not ids:
        return 0
    targets = [f"passage-{value}" for value in ids]
    placeholders = ",".join("?" for _ in targets)
    try:
        with open_objects_db() as connection:
            cursor = connection.execute(
                f"DELETE FROM objects WHERE object_id IN ({placeholders})", targets
            )
            return max(0, cursor.rowcount)
    except Exception as error:
        print(f"passage mirror sync failed: {error}", file=sys.stderr)
        return 0


def reconcile_passage_mirrors() -> int:
    try:
        with open_passages_db() as connection:
            rows = connection.execute("SELECT passage_id FROM water_passages").fetchall()
    except Exception:
        return 0
    live = {f"passage-{str(row['passage_id'])}" for row in rows}
    with open_objects_db() as connection:
        mirrors = connection.execute(
            "SELECT object_id FROM objects WHERE object_id LIKE 'passage-%'"
        ).fetchall()
        orphans = [str(row["object_id"]) for row in mirrors if str(row["object_id"]) not in live]
        if not orphans:
            return 0
        placeholders = ",".join("?" for _ in orphans)
        cursor = connection.execute(
            f"DELETE FROM objects WHERE object_id IN ({placeholders})", orphans
        )
        return max(0, cursor.rowcount)
