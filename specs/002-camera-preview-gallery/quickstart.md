# Quickstart: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Issue: #103

## Repository validation

Run the focused checks before PR publication:

```bash
python3 -m py_compile api/app/main.py
bash -n deploy/worker/ubuntu/camera-preview-relay.sh
bash -n deploy/vps/deploy.sh
python3 -m unittest tests.test_camera_preview_gallery
```

The normal repository PR/quality workflows remain mandatory.

## Runtime inventory boundary

Do not commit a populated inventory. On Ubuntu, create a root-owned mode-0600 JSON file using this shape:

```json
{
  "schema": "sea_speed_camera_preview_inventory_v1",
  "cameras": [
    {
      "camera_id": "cam18",
      "display_name": "Example camera",
      "source": "rtsp://USER:PASSWORD@10.0.0.10:554/EXAMPLE_PATH"
    }
  ]
}
```

The example placeholders are not production credentials.

## Prepare-only Ubuntu flow

After separate runtime authorization, use the helper's `prepare` mode first. It validates the protected inventory and renders three protected candidates under its state root:

- standalone MediaMTX preview config;
- dedicated systemd unit;
- sanitized VPS catalog containing credential-free private relay URLs only.

`prepare` does not start or restart services.

## Product acceptance

1. Open `/sea-speed/` and verify existing Camera 1 live is still healthy.
2. Open `/sea-speed/cameras/` from the new `Камеры` link.
3. Confirm every configured catalog camera appears while no preview is active.
4. Press Play on one candidate and wait for advancing video.
5. Press Play on a second candidate and confirm the first preview is released/replaced.
6. Press Stop and confirm the gallery returns to idle.
7. Start one preview and leave it untouched; confirm the server hard TTL eventually returns to idle.
8. Try one known invalid/offline candidate and confirm its error does not break other cards.
9. Re-check Camera 1 live.

A camera candidate failing to start is not by itself evidence that the IP is not a camera; an incorrect RTSP path remains a valid runtime diagnosis.
