# Camera preview relay (dedicated service) — runbook

The dedicated preview relay (`sea-speed-camera-preview-relay.service`) serves
on-demand camera previews (`preview_{camera_id}` paths) on a private RFC1918
RTSP address, fully isolated from the accepted Camera 1 relay
(`sea-speed-stream.service`) and the AI worker. Since issue #442 the config
and the sanitized catalog are rendered by the canonical renderer module
(`scripts/operations/mediamtx_path_config.py`, `ubuntu-preview-relay` mode);
the shell (`deploy/worker/ubuntu/camera-preview-relay.sh`) is a thin CLI.

## Prepare (no service change)

```
camera-preview-relay.sh prepare \
  --inventory /path/to/preview-inventory.json \
  --private-rtsp-address <RFC1918 IPv4:PORT> \
  --reader-ip <RFC1918 IPv4> [--reader-ip <RFC1918 IPv4> ...]
```

- `--inventory` must be a root-owned mode-0600 regular non-symlink file with
  schema `sea_speed_camera_preview_inventory_v1` (camera_id / display_name /
  credential-bearing private RTSP source per camera); validation is
  fail-closed in the renderer.
- `--reader-ip` is repeatable and comma-separated; every occurrence is
  forwarded to the renderer and rendered into the single marked reader rule
  in input order.
- Output: `PREPARED_PREVIEW_RELAY=YES`, `CAMERA_COUNT`,
  `READER_AUTH_SCOPE` (`preview-single-rfc1918-peer` /
  `preview-multi-rfc1918-peer-count-N`), the three candidate digests
  (`CONFIG_SHA256`, `UNIT_SHA256`, `SANITIZED_CATALOG_SHA256`) and paths.
  Only protected 0600 candidates under
  `/var/lib/sea-speed-camera-preview/candidates/` are written
  (`MUTATIONS=PROTECTED_CANDIDATES_ONLY`, `SERVICE_RESTARTED=NO`,
  `SECRETS_DISPLAYED=NO`).

## Activate (digest-bound)

```
camera-preview-relay.sh activate \
  --private-rtsp-address <same> \
  --expected-config-sha256 <digest> --expected-unit-sha256 <digest> \
  --expected-catalog-sha256 <digest>
```

Digest gates bind the install to the exact prepared candidates; backups are
retained for an explicit rollback decision
(`AUTOMATIC_ROLLBACK=NO` — automatic rollback is not authorized). Only the
dedicated preview service is restarted/enabled; Camera 1 and the AI worker
are untouched (`CAM1_RELAY_CHANGED=NO`, `AI_WORKER_CHANGED=NO`). A preview
restart is a road-worker analytics interruption window (the road worker
consumes `preview_road1` live) — schedule accordingly.

## Render contract (byte discipline)

- Re-rendering the same inventory + inputs is byte-identical; the digest
  evidence binds activation to those exact bytes.
- One-time documented drifts versus the pre-#442 inline heredoc (like the
  #437 drifted-rule remediation): (1) the reader rule now carries the
  canonical marker
  `# Sea Speed least-privilege reader for canonical preview-contour (path-pattern ~^preview_[a-z0-9._-]+$)`
  (one line, inserted after `authInternalUsers:`); (2) the catalog no longer
  carries the non-deterministic `generated_at` field (no consumer reads it).
  Everything else is byte-identical to the legacy render for the same
  inputs.
- The marked preview rule is verifiable by repo tooling:
  `python3 scripts/operations/mediamtx_path_config.py verify-preview-auth
  --config <live-or-candidate-config> --reader-ip <IP>...` — closes the
  #362-class drift blind spot for the preview contour.
- RFC1918 validation is single-sourced through the renderer
  `check-address` verb (reader-ip and private-rtsp kinds) in both relay
  shells.

## Open on-box questions (resolve at runtime acceptance)

1. Live preview relay bind address/port is not in the repo (fixtures use
   10.0.0.8:8555; the KB mentions 8892) — confirm on-box before the
   re-render transaction.
2. `sea_speed_camera_preview_inventory_v1` has no repo producer — the
   inventory is a runtime artifact; confirm its live location/producer.
3. Top-level vs path-level transport pinning policy is unresolved — the
   renderer keeps the legacy shape (both global `rtspTransports: [tcp]` and
   per-path `rtspTransport: tcp`).
4. Confirm the road worker's live pull state before/after the bounded
   re-render transaction.
