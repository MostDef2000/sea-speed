# Feature Specification: Cutover tooling transcode path and HLS port

- Feature: 076-cutover-tooling-transcode-path-hls-port
- Issue: #335
- Status: Source implementation
- Owner outcome: the Camera 1 HEVC->H264 cutover tooling produces a correct Worker MediaMTX `cam1-h264` publisher path and a correct VPS cutover that verifies the real HLS port, so a future re-run of the cutover needs no manual config edits.

## Product outcome

Two defects were worked around by hand during the #335 cutover and must be fixed in repository source so the tooling is correct for future runs:

1. `scripts/operations/mediamtx_path_config.py` mode `ubuntu-transcode-reader` (invoked by `deploy/worker/ubuntu/camera1-h264-transcode.sh prepare`) only added the least-privilege reader+publish rule for `cam1-h264` but did NOT create the `paths: cam1-h264:` publisher block. Without it the Worker MediaMTX has no `cam1-h264` path and the ffmpeg transcode unit cannot publish; the VPS relay stays empty. The manual fix inserted `cam1-h264: source: publisher` before `cam1:` on the Worker.

2. `deploy/vps/camera-source-switch.sh` had three defects observed during the VPS cutover:
   - the canonical VPS-local HLS check URL defaulted to `http://127.0.0.1:8888/cam1/index.m3u8` (MediaMTX default port) instead of the configured `--hls-address` (`:18889`), so `activate` failed with "canonical VPS-local HLS did not become available";
   - it restarted MediaMTX before disabling the retired external units `sea-speed-camera1-h264.service` and `sea-speed-camera1-hls-http.service`, which still occupied `:18889`, causing a bind conflict;
   - it did not pin `0640 root:mediamtx` on the live config before restart, so a config with wrong perms caused `permission denied` on the credential-bearing `/etc/mediamtx/mediamtx.yml`.

This Outcome changes only repository tooling. It does NOT mutate any running host, does NOT change Issue #335 (already DONE), and does NOT change API/frontend/contracts. The change touches `deploy/vps/**`, so the VPS contour is in policy scope and the PR declares `VPS deployment: REQUIRED` with `Production safety envelope: REQUIRED`; this PR performs no deployment itself.

## User scenarios

### Scenario 1 - Worker transcode candidate contains the publisher path

Given a Worker MediaMTX config with only the `cam1` path, when `camera1-h264-transcode.sh prepare` runs `ubuntu-transcode-reader`, then the rendered candidate contains a `paths: cam1-h264:` block with `source: "publisher"` and `sourceOnDemand: no`, plus the least-privilege reader+publish rule, and the transcode unit can publish into it.

### Scenario 2 - VPS activate verifies the real HLS port

Given `--hls-address :18889` is passed, when `camera-source-switch.sh activate` runs, then the post-activate HLS check targets `http://127.0.0.1:18889/cam1/index.m3u8` (not `:8888`) and passes once MediaMTX serves HLS on `:18889`.

### Scenario 3 - VPS activate frees the HLS port before restart

Given `--retire-external` is passed, when `activate` runs, then the external units are disabled before MediaMTX restarts, so `:18889` is free and MediaMTX binds HLS without conflict.

### Scenario 4 - VPS live config has secure perms before restart

Given the live `/etc/mediamtx/mediamtx.yml` carries legacy camera credentials, when `install_candidate` installs the switched config, then the live config is pinned `0640 root:mediamtx` before MediaMTX restarts, so the `mediamtx` user can read it.

## Requirements

- FR-001: `render_ubuntu_transcode_reader` MUST create the `paths: cam1-h264:` block with `source: "publisher"` and `sourceOnDemand: no` when the path does not already exist.
- FR-002: `render_ubuntu_transcode_reader` MUST still add and verify the least-privilege reader+publish rule for `cam1-h264` (VPS reader IP + Ubuntu publisher IP).
- FR-003: `camera-source-switch.sh` MUST derive `hls_check_url` from `--hls-address` when provided (`:18889` -> `http://127.0.0.1:18889/cam1/index.m3u8`; `host:port` -> `http://host:port/cam1/index.m3u8`), overriding the `:8888` default.
- FR-004: `camera-source-switch.sh activate` MUST disable `sea-speed-camera1-h264.service` and `sea-speed-camera1-hls-http.service` (when `--retire-external`) BEFORE `install_candidate` restarts MediaMTX.
- FR-005: `install_candidate` MUST pin the live config to `root:mediamtx` owner/group and `0640` mode before restarting MediaMTX.
- FR-006: Existing `validate_config_security` (no world-access) MUST remain satisfied by the pinned `0640` mode.
- FR-007: The change touches `deploy/vps/**`, so the VPS contour is in policy scope; the PR MUST declare `VPS deployment: REQUIRED` and `Production safety envelope: REQUIRED`. Ubuntu Worker/relay update MUST remain NOT REQUIRED.

## Acceptance criteria

- AC-001: Unit test proves `render_ubuntu_transcode_reader` output contains `cam1-h264:`, `source: "publisher"`, and `sourceOnDemand: no`.
- AC-002: `bash -n deploy/vps/camera-source-switch.sh` passes (no syntax errors).
- AC-003: `scripts/ci/validate_repo.py` passes on the changed tree.
- AC-004: `python3 -m unittest tests/test_vps_transcode_to_ubuntu.py` passes (6 tests).
- AC-005: PR Change Contract declares VPS deployment REQUIRED, Ubuntu worker/relay update NOT REQUIRED, production safety envelope REQUIRED, VPS execution capability CONNECTOR, Ubuntu worker execution capability NOT APPLICABLE, operator actions expected 0.

## NFR assessment

- NFR-001 | Area: Security | Target: live MediaMTX config retains 0640 root:mediamtx (no world access) | Validation: validate_config_security (no world-access) remains satisfied by the pinned perms | Evidence: unit test asserts the perms pin; validate_repo passes | Status: PASS
- NFR-002 | Area: Reliability | Target: a future cutover re-run needs no manual config edits | Validation: renderer emits the cam1-h264 publisher path; script derives the configured HLS port and frees :18889 before restart | Evidence: extended unit test; bash -n | Status: PASS

## Runtime feedback

- During the #335 VPS cutover the operator inserted `cam1-h264: source: publisher` by hand on the Worker because `ubuntu-transcode-reader` omitted the path block.
- During the #335 VPS `activate` the operator hit "canonical VPS-local HLS did not become available" (`:8888` default), a `:18889` bind conflict (external units still up), and `permission denied` on `/etc/mediamtx/mediamtx.yml` (wrong perms) — all three are addressed here.
- The live hosts already carry the equivalent manual edits; this PR makes the repository tooling correct so a future re-run needs no hand edits.
- No production deployment is triggered; standing delegation and policy evaluation are unchanged.
