# MediaMTX Compatibility Remediation for Camera 1

Status: repository source only until merge, exact quality evidence, and a separate production approval.

## Why this exists

Issue #87 has already proven the new camera path through the Ubuntu relay. The remaining production failure is narrower than network reachability or authorization:

```text
new physical camera -> Ubuntu relay -> VPS host media probe = PASS
new physical camera -> Ubuntu relay -> VPS MediaMTX canonical source = FAIL
```

The bounded cross-host investigation classified the failure as `E_RTSP_HANDSHAKE_COMPATIBILITY` and the required action class as a MediaMTX version or compatibility change. The VPS service and an `ffprobe` process running as the same `mediamtx` user share the same network namespace and both can reach and decode the credential-free relay. Ubuntu observes the VPS reader and accepts it. The configured `sourceOnDemandStartTimeout` is longer than the observed direct time to first media. This excludes service-user networking, a separate service namespace, Ubuntu reader authorization, and the configured on-demand timeout as the confirmed blocker.

This remediation therefore does not widen relay access and does not change the Camera 1 source URL. It provides a fail-closed way to prove a candidate MediaMTX build against the real relay before the production executable is replaced.

## Components

- `deploy/vps/mediamtx-compatibility-remediation.sh` performs a loopback-only compatibility canary and, only after that canary succeeds, a digest-bound production binary replacement.
- `deploy/vps/camera-source-switch.sh` remains responsible for the existing canonical `cam1` config contract and the gated removal of `cam1-new`.
- `docs/operations/CAMERA1_LIVE_REPLACEMENT.md` remains the base live-source runbook; this document is the compatibility-remediation supplement for the confirmed source-pull blocker.

## Candidate provenance

The candidate must be an official `bluenviron/mediamtx` release for the VPS architecture. OpenCode must obtain the release archive and the corresponding upstream `checksums.sha256` from the official release, verify the archive checksum before invoking repository tooling, and record the exact release version and archive SHA-256 in sanitized rollout evidence.

The repository script independently requires the approved archive SHA-256 and refuses a mismatch. It extracts only the `mediamtx` executable, verifies that the binary reports the requested candidate version, computes a separate binary SHA-256, and binds that binary digest to the canary result.

Do not use a mutable package repository, an unverified mirror, a locally rebuilt binary, or a release artifact whose checksum has not been verified.

## Loopback-only compatibility canary

Preparation is intentionally not a production binary replacement.

Example shape:

```text
mediamtx-compatibility-remediation.sh prepare \
  --config /etc/mediamtx/mediamtx.yml \
  --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 \
  --candidate-archive <verified-official-release-archive> \
  --candidate-version <exact-version> \
  --expected-archive-sha256 <approved-upstream-sha256>
```

The script requires the existing production MediaMTX service to be active and its active config to remain a protected regular file. It derives the existing non-root MediaMTX service identity and starts the candidate as that same user.

The canary binds only to loopback:

```text
RTSP 127.0.0.1:18954
HLS  127.0.0.1:18888
```

Unused public-facing protocols are disabled, RTSP listening is TCP-only, and the candidate pulls the same credential-free private Ubuntu relay with `sourceOnDemand: yes` and `rtspTransport: tcp`.

A canary passes only when it produces actual video through both its local RTSP output and its local HLS output. Static config parsing, TCP reachability, or a process staying alive are not sufficient. The production MediaMTX executable is not replaced and the production service is not restarted during this phase.

Successful preparation records a root-only marker bound to:

- candidate binary SHA-256;
- candidate version;
- verified release archive SHA-256;
- current installed MediaMTX binary SHA-256;
- current active MediaMTX config SHA-256.

If either the installed binary or active config changes after the canary, activation refuses to continue and a new canary is required.

## Production binary activation

Activation requires the exact candidate binary SHA-256 returned by successful preparation:

```text
mediamtx-compatibility-remediation.sh activate \
  --config /etc/mediamtx/mediamtx.yml \
  --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 \
  --expected-candidate-sha256 <canary-approved-binary-sha256>
```

Activation does not edit the MediaMTX YAML. It:

1. revalidates the canary marker and unchanged config/binary identities;
2. creates a root-only backup of the current MediaMTX executable;
3. preserves the installed executable owner, group and mode;
4. atomically replaces only the executable;
5. restarts only `mediamtx.service`;
6. requires the service to be active with the canary-approved version;
7. requires actual advancing video from existing VPS-local canonical HLS at `http://127.0.0.1:8888/cam1/index.m3u8`.

If service restart, version verification, or canonical HLS media fails after replacement, the script stops and reports the preserved binary backup. Automatic rollback remains prohibited; rollback is a separate governed decision.

The script never starts, stops, restarts or enables `sea-speed-worker.service`.

## One final Camera 1 completion scope

After this source is merged and a production approval covers the exact candidate artifact and final Issue #87 completion, the remaining work is designed to run as one OpenCode rollout scope rather than a chain of micro-diagnostics.

The scope should:

1. verify `sea-speed-worker.service` is inactive and `sea-speed-stream.service` is active;
2. verify the Ubuntu relay still produces advancing media from the VPS;
3. download one approved official MediaMTX candidate archive and its official checksum evidence;
4. run the loopback-only compatibility canary;
5. stop without production binary mutation if the canary fails;
6. if the canary passes, activate exactly the canary-approved binary digest;
7. prove canonical VPS-local HLS produces advancing media;
8. prove the existing unauthenticated public request still receives the expected Basic Auth challenge and that `/cams/hls/cam1/index.m3u8` is unchanged;
9. pause for human visual acceptance on `mostdef.ru` and require the exact text `CONFIRM_NEW_CAMERA` only when the new physical camera is visibly moving and the AI worker remains offline;
10. only after that confirmation, use the existing `camera-source-switch.sh prepare-cleanup` and `activate-cleanup` flow to retire `cam1-new`;
11. re-prove canonical HLS, public boundary, AI-worker-off state, secret safety and preserved backups.

A failed canary is a clean stop before production binary replacement. A failure after binary replacement preserves the current runtime state and all backups and returns for an explicit rollback or new-scope decision. No speculative config edits, network changes, nginx changes, credential changes, Ubuntu relay mutations or AI worker mutations are part of this flow.

## Acceptance boundary

Issue #87 is complete only when all of the following are proven at runtime:

- the new physical camera is visible and moving at the existing Camera 1 position on `mostdef.ru`;
- public identity remains `/cams/hls/cam1/index.m3u8`;
- canonical VPS `cam1` still uses the credential-free Ubuntu relay with `sourceOnDemand: yes` and `rtspTransport: tcp`;
- VPS-local canonical HLS produces advancing media under the active production MediaMTX binary;
- `cam1-new` has been removed only after human confirmation;
- `sea-speed-worker.service` remains inactive during clean-live acceptance;
- camera credentials are not copied to the VPS or exposed in argv, logs, reports or browser-visible URLs;
- the previous MediaMTX binary backup and existing config backups remain preserved;
- no automatic rollback occurred.
