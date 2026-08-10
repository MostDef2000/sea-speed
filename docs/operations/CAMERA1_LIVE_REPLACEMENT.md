# Camera 1 Live Source Replacement

Status: Source implementation only until a separately approved production rollout.

## Product goal

Keep one public camera identity, `cam1`, while replacing the legacy live source with the new physical RTSP camera.

The target media path is:

```text
new physical camera
  -> Ubuntu sea-speed-stream / MediaMTX private RTSP relay `cam1`
  -> ZeroTier private network
  -> VPS MediaMTX canonical path `cam1`
  -> existing nginx Basic Auth boundary
  -> /cams/hls/cam1/index.m3u8
```

The live relay is intentionally independent of `sea-speed-worker.service`. Stopping the AI worker must not stop the clean live camera view.

This task does not create `cam2` and does not change the frontend HLS URL.

## Security model

Camera credentials stay on the Ubuntu host only.

The Ubuntu candidate renderer reads `HLS_URL` from the existing protected mode-0600 worker environment file without shell-sourcing it. The credential-bearing value is written only into a root-protected MediaMTX candidate/config and is never passed as a command-line argument or printed by the repository tools.

The VPS receives only a credential-free private relay URL such as:

```text
rtsp://<ubuntu-private-ip>:8554/cam1
```

Ubuntu MediaMTX keeps internal authentication enabled. The repository renderer preserves all existing authentication rules and adds exactly one generated credential-free rule that grants only `read` on `cam1` to a single VPS ZeroTier peer identified by one literal RFC1918 IPv4 address. It does not grant publish, playback, API, metrics, pprof, or read access to any other path. The generated rule is idempotent and a later prepare attempt with a different reader IP is rejected instead of silently widening or replacing access.

The renderer rejects VPS relay URLs containing userinfo and rejects non-private literal IP addresses. It also rejects a camera source that is not RTSP or does not contain protected userinfo. Ubuntu relay preparation rejects a non-RFC1918 reader IP, a non-internal MediaMTX auth method, or a systemd environment override of MediaMTX authentication because those states cannot be safely reconciled by the bounded config renderer.

Do not print or copy:

- the camera URL with credentials;
- `worker.env` contents;
- generated Ubuntu MediaMTX config contents;
- Basic Auth values;
- API/GitHub tokens;
- Authorization headers.

Do not use camera credentials in CLI arguments, process titles, issue comments, shell history or reports.

## Repository components

- `scripts/operations/mediamtx_path_config.py` performs bounded MediaMTX YAML transformations without a PyYAML dependency, including the exact `cam1` reader authorization rule.
- `deploy/worker/ubuntu/camera-relay.sh` prepares and activates the Ubuntu private relay while refusing to activate the AI worker.
- `deploy/vps/camera-source-switch.sh` prepares and activates the canonical VPS `cam1` switch and separately retires `cam1-new` after public validation.

Both runtime commands use protected candidate files with SHA-256 binding. An activation command must provide the exact candidate digest returned by its preceding prepare command.

## Repository / runtime boundary

Merge is not deployment. None of these files change production merely by existing on `main`.

Before production use, require:

1. exact merged source commit;
2. successful `Quality integration gate / quality-integration` for that exact source;
3. explicit production rollout approval for Issue #87;
4. fresh discovery of the actual Ubuntu and VPS MediaMTX config paths and service names;
5. fresh discovery of the exact VPS ZeroTier peer IPv4 that will be allowed to read `cam1`;
6. confirmed current rollback state.

OpenCode may perform non-secret diagnostics remotely. A root-required operation follows `docs/operations/OPENCODE_WORKER_REMOTE_ACCESS.md`: OpenCode prepares the bounded exact command/helper, then the operator runs the exact `sudo ...` command and enters the password locally. Never pass a sudo password to OpenCode.

## Controlled rollout order

### 1. Prepare Ubuntu relay candidate

From an exact merged repository checkout on the Ubuntu host, determine the existing MediaMTX config path, the ZeroTier-only RTSP listen address, and the exact VPS ZeroTier peer IPv4 without displaying secret configuration.

Then run the repository command with `prepare` under the approved root boundary:

```text
camera-relay.sh prepare --config <ubuntu-mediamtx-config> --private-rtsp-address <ubuntu-private-ip>:8554 --reader-ip <vps-zerotier-ip>
```

Expected sanitized evidence includes:

```text
PREPARED_RELAY_CANDIDATE=YES
CAMERA_SOURCE_SCHEME=rtsp
CAMERA_SOURCE_USERINFO=YES
RELAY_PATH=cam1
READER_AUTH_SCOPE=cam1-single-rfc1918-peer
READER_AUTH_PERMISSION=read-only
SERVICE_RESTARTED=NO
AI_WORKER_STARTED=NO
SECRETS_DISPLAYED=NO
```

Preparation writes only a protected candidate under `/var/lib/sea-speed-camera-relay`. It does not restart MediaMTX and does not touch the AI worker. Existing MediaMTX authentication rules remain unchanged; the candidate only appends the exact generated reader rule described above.

### 2. Activate Ubuntu private relay

Use only the exact SHA-256 returned by preparation and the same VPS reader IP:

```text
camera-relay.sh activate --config <ubuntu-mediamtx-config> --private-rtsp-address <ubuntu-private-ip>:8554 --reader-ip <vps-zerotier-ip> --expected-sha256 <candidate-sha256>
```

Before installing the candidate, activation verifies that it contains exactly one generated `cam1` read rule for the supplied reader IP and no broader generated permission.

The activation:

- requires `sea-speed-worker.service` to be inactive;
- rejects MediaMTX auth environment overrides that would supersede the bounded file configuration;
- makes a root-only backup of the prior MediaMTX config;
- installs the reviewed candidate with permissions suitable for the existing relay service identity;
- restarts only `sea-speed-stream.service`;
- checks the private RTSP TCP listener;
- never starts/stops/restarts/enables the AI worker;
- performs no automatic rollback.

At this point the VPS canonical public source is still unchanged.

### 3. Validate private relay from the VPS

Before changing canonical `cam1`, validate the credential-free private relay from the exact VPS ZeroTier peer that was authorized in the Ubuntu candidate.

A controlled media probe may be used only after production rollout approval. Its command line must contain only the credential-free private relay URL. Confirm that the relay can produce actual media from the new camera while `sea-speed-worker.service` remains stopped.

Do not proceed to the VPS switch on TCP reachability alone; private media must be proven. A reader from an unapproved peer must not be treated as an acceptance path.

### 4. Prepare VPS canonical switch

Use the credential-free private relay URL:

```text
camera-source-switch.sh prepare --config <vps-mediamtx-config> --relay-url rtsp://<ubuntu-private-ip>:8554/cam1
```

Preparation preserves the temporary `cam1-new` mapping and does not restart VPS MediaMTX.

### 5. Activate VPS canonical `cam1`

Use the exact candidate digest:

```text
camera-source-switch.sh activate --config <vps-mediamtx-config> --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 --expected-sha256 <candidate-sha256>
```

The script:

- verifies private relay TCP reachability;
- backs up the previous VPS MediaMTX config as root-only because it can contain the legacy credential-bearing source;
- changes canonical `cam1` to the credential-free Ubuntu relay;
- restarts only VPS `mediamtx.service`;
- waits for VPS-local `/cam1/index.m3u8` HLS to become available;
- leaves `cam1-new` in place until public validation;
- performs no automatic rollback.

Nginx and `/cams/hls/cam1/index.m3u8` are intentionally unchanged.

### 6. Public acceptance before cleanup

Using the existing protected website authentication path, verify:

- `/cams/hls/cam1/index.m3u8` is reachable through the existing nginx Basic Auth boundary;
- video is from the new physical camera;
- video advances for multiple samples;
- live video continues while `sea-speed-worker.service` is inactive;
- Ubuntu relay read access is limited to the approved single VPS ZeroTier peer and canonical path `cam1`;
- no camera credentials appear in browser-visible URLs, process argv, sanitized service logs or reports.

Only after this evidence is accepted may the temporary `cam1-new` mapping be retired.

### 7. Retire `cam1-new`

Prepare cleanup only after public HLS has been confirmed:

```text
camera-source-switch.sh prepare-cleanup --config <vps-mediamtx-config> --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 --confirmed-public-hls
```

Then activate the exact cleanup candidate:

```text
camera-source-switch.sh activate-cleanup --config <vps-mediamtx-config> --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 --expected-sha256 <candidate-sha256> --confirmed-public-hls
```

Cleanup refuses to proceed unless canonical `cam1` is already bound to the expected private relay. It restarts MediaMTX and rechecks canonical VPS-local HLS.

## Rollback boundary

The activation commands preserve root-only backups but deliberately do not restore them automatically.

If Ubuntu relay activation or the VPS canonical switch fails:

1. stop the rollout;
2. record only sanitized failure evidence and the non-secret backup path;
3. do not run further cleanup;
4. obtain an explicit rollback decision;
5. restore the appropriate previously captured config and restart only the affected relay service;
6. re-verify the restored canonical HLS behavior.

The legacy source must not be deleted before the new canonical public path has passed acceptance.

## Acceptance result

Issue #87 is runtime-accepted only when:

- the public path remains `/cams/hls/cam1/index.m3u8`;
- it shows the new physical camera;
- the Ubuntu relay supplies canonical private `cam1` over ZeroTier;
- Ubuntu MediaMTX grants credential-free `cam1` read only to the exact approved VPS ZeroTier peer and preserves all unrelated auth rules;
- the VPS canonical `cam1` contains no camera credentials;
- the live view works with the AI worker stopped;
- `cam1-new` has been retired after validation;
- rollback evidence remains available;
- no secret was disclosed.

Until that controlled rollout is performed, runtime remains `UNKNOWN` for this source change.
