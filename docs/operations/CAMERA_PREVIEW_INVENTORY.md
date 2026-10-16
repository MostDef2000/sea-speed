# Camera preview inventory — canonical file + operator update procedure — runbook

Canonical decision (decided 2026-10-16, owner-delegated, issue #454):
`/var/lib/sea-speed-camera-preview/inventory.json` IS the canonical
`sea_speed_camera_preview_inventory_v1` inventory. The tx #442
reconstruction (`inventory-tx442.json`) was canonicalized in place over
the stale 2026-08-12 file on 2026-10-16; its dated backup is retained
until the next box session. This runbook documents the canonical file
(AC-1) and the operator update procedure (AC-2). The `:8892` exposure
verdict is issue #522 (out of scope here).

## Canonical file

- Path: `/var/lib/sea-speed-camera-preview/inventory.json` — the single
  canonical inventory; `inventory-tx442.json` (same content) remains on
  the box as tx #442 historical evidence, not a second canonical copy.
- Constraints: `root:root`, mode `0600`, regular non-symlink file (the
  renderer enforces the same constraints on any `--inventory` input).
- Schema `sea_speed_camera_preview_inventory_v1`: `camera_id` /
  `display_name` / credential-bearing private RTSP source per camera;
  33 cameras + `road1` as of tx #442.
- Contents are credential-bearing: NEVER display values, NEVER commit;
  secrets stay pointer-referenced in evidence records.

## Producer

- Operator sysadmin transactions only (no repo-side producer today);
  executed by the sysadmin session.
- Run an inventory update when: the camera set changes
  (add/remove/rename), credentials rotate, or a relay re-render
  transaction requires it.

## Validate before replacing the live file

Run the canonical renderer against the candidate BEFORE touching the
live file. It parses/validates fail-closed and emits `CAMERA_COUNT` +
`SANITIZED_CATALOG_SHA256` with `MUTATIONS=PROTECTED_CANDIDATES_ONLY`:

```
camera-preview-relay.sh prepare --inventory <candidate.json> [options]
```

Renderer: `scripts/operations/mediamtx_path_config.py`
(`ubuntu-preview-relay` mode); CLI:
`deploy/worker/ubuntu/camera-preview-relay.sh prepare --inventory ...`.
The full prepare flag contract lives in `CAMERA_PREVIEW_RELAY.md`
(Prepare section).

## Replacement procedure (tx #442 / AC-1 handoff sequence)

Each step is a separate logged command on the box (root-equivalent
transport). `<new>.json` is the validated candidate; the date in the
backup name is the transaction date.

1. Record pre-state digests (source JSON and the current live file):

   ```
   sha256sum <new>.json
   sha256sum /var/lib/sea-speed-camera-preview/inventory.json
   ```

2. Ensure the backups directory exists:

   ```
   mkdir -p /var/lib/sea-speed-camera-preview/backups
   ```

3. Dated backup of the stale live file (its digest, recorded in step 1,
   is the pre-mutation proof):

   ```
   cp -p /var/lib/sea-speed-camera-preview/inventory.json \
     /var/lib/sea-speed-camera-preview/backups/inventory.json.stale-YYYY-MM-DD
   ```

4. Stage the candidate next to the live file:

   ```
   cp -p <new>.json /var/lib/sea-speed-camera-preview/inventory.json.new
   ```

5. Atomic replace:

   ```
   mv -f /var/lib/sea-speed-camera-preview/inventory.json.new \
     /var/lib/sea-speed-camera-preview/inventory.json
   ```

6. Restore the protected mode and ownership:

   ```
   chmod 600 /var/lib/sea-speed-camera-preview/inventory.json
   chown root:root /var/lib/sea-speed-camera-preview/inventory.json
   ```

7. Verify: live digest equals the source digest from step 1, `stat`
   shows `0600 root:root`, size is sane:

   ```
   sha256sum /var/lib/sea-speed-camera-preview/inventory.json
   stat -c '%a %U:%G %s' /var/lib/sea-speed-camera-preview/inventory.json
   ```

8. Record digests, stat and date in the transaction/handoff record.
   Rollback (digest proven pre-mutation in step 3):

   ```
   cp -p /var/lib/sea-speed-camera-preview/backups/inventory.json.stale-YYYY-MM-DD \
     /var/lib/sea-speed-camera-preview/inventory.json
   ```

9. Cleanup: the dated stale backup is removed at the next box session
   after acceptance (no-accumulation backup protocol).

## Runtime semantics

- The relay reads `inventory.json` only during prepare/activate
  rendering; serving uses the rendered artifacts under `active/`.
  Replacing `inventory.json` alone requires NO service restart.
- `active/camera-preview-catalog.json` is the sanitized runtime catalog
  (a different file), not the inventory.

## Evidence — 2026-10-16 canonicalization (tx #442 reconstruction)

- Pre-state: stale inventory sha256 `26187b00…21a9`, dated 2026-08-12.
- Post-state: `inventory-tx442.json` canonicalized in place — 5548 B,
  mtime 2026-10-11 01:04:45, sha256
  `696c40e70e06c79744b6db6793d51be40652111f4ec35d67f624f00d258a7ef5`,
  mode `0600 root:root`.
- Executed 2026-10-16 07:52:03 UTC via the root-equivalent
  docker-bridge transport (the handoff assumed a root shell; steps run
  1:1). Evidence relayed by owner.
- Dated backup retained: `backups/inventory.json.stale-2026-10-16`
  (digest proven pre-mutation); cleanup at the next box session per the
  no-accumulation backup protocol.

## Ownership

- Issue #454 AC-1 (inventory documentation) and AC-2 (documented
  operator procedure).
- The `:8892` exposure verdict is issue #522 (out of scope here).
