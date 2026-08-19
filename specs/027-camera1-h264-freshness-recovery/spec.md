# Feature Specification: Camera 1 H264 Freshness Recovery

- Feature: 027-camera1-h264-freshness-recovery
- Issue: #226
- Status: Source implementation
- Owner outcome: the authenticated Camera 1 clean stream shows current advancing video instead of a stale VPS H264/HLS playlist, without changing the camera, Ubuntu relay, browser media URL, Auth topology, or AI workers.

## Product outcome

Restore the canonical Camera 1 clean live path when the Ubuntu private RTSP relay remains readable but the VPS H264 compatibility producer is stuck on a valid non-advancing HLS playlist. The existing protected browser path remains:

`Ubuntu private RTSP relay -> VPS FFmpeg H264 compatibility output -> 127.0.0.1:18889/cam1/ -> nginx -> /sea-speed/media/cam1/index.m3u8`.

The existing exact-source-bound no-argument privileged helper remains the only root boundary. During the canonical VPS deployment `reconcile` transaction it verifies local HLS media-sequence progression. If HLS already advances, Camera 1 recovery is a no-op. If HLS is valid but static, the helper first proves one decodable frame from the fixed credential-free private relay `rtsp://10.123.239.102:8554/cam1`, restarts only `sea-speed-camera1-h264.service`, and then requires the local HLS media sequence to advance before returning success. A reconcile failure prevents the existing VPS deployment transaction from writing accepted `runtime_verified` state.

This Outcome does not modify the physical camera, Ubuntu relay configuration, nginx/Auth topology, HLS HTTP service, MediaMTX, Water/Road AI workers, browser URL, analytics, API, or storage.

## User scenarios

### Scenario 1 - Current live stream is already healthy

Given the local Camera 1 HLS playlist is valid and its media sequence advances across the fixed sampling interval, when the canonical VPS reconcile runs, then Camera 1 recovery returns PASS as a no-op and no H264 service restart or private-relay probe occurs.

### Scenario 2 - VPS H264 producer is stale while private relay is healthy

Given the local HLS playlist is valid but its media sequence does not advance, and the fixed Ubuntu private relay produces a decodable frame, when canonical reconcile runs, then only `sea-speed-camera1-h264.service` is restarted and the transaction succeeds only after two post-restart HLS samples prove sequence progression.

### Scenario 3 - Private relay is unavailable

Given local HLS is static but the fixed private Ubuntu relay cannot produce a frame, when recovery runs, then it fails before any service restart and the VPS deployment cannot be accepted.

### Scenario 4 - H264 restart does not restore fresh media

Given local HLS is static and the private relay is healthy, but the H264 producer remains static after the fixed restart, when recovery runs, then the privileged transaction fails closed and the deployment cannot reach `runtime_verified`.

### Scenario 5 - Root execution remains fixed and non-parameterized

Given an unprivileged deployment caller can only submit the existing exact-source request file and invoke one no-argument installed helper, then no service name, media URL, shell command, arbitrary argument, nginx/MediaMTX/worker restart, or arbitrary root execution can be selected by that caller.

## Requirements

- FR-001: The privileged reconcile transaction MUST sample `http://127.0.0.1:18889/cam1/index.m3u8` twice across a fixed interval and require a valid `#EXT-X-MEDIA-SEQUENCE` value.
- FR-002: If the second HLS sequence is greater than the first, recovery MUST return PASS without probing the private relay and without restarting any service.
- FR-003: A malformed or unavailable local HLS playlist MUST fail closed and MUST NOT be treated as proof that the H264 producer alone is stale.
- FR-004: When valid local HLS is static, the helper MUST decode one frame from exactly `rtsp://10.123.239.102:8554/cam1` over TCP before any restart. The fixed VPS FFmpeg argv MUST use `-rtsp_transport tcp -timeout 10000000` and MUST NOT use the production-incompatible `-rw_timeout` option.
- FR-005: If the fixed private relay frame probe fails, recovery MUST fail before any service restart.
- FR-006: After a successful static-HLS/relay precondition, the helper MUST restart only `sea-speed-camera1-h264.service` and MUST verify that exact service is active.
- FR-007: After the restart, the helper MUST require a newly advancing local HLS media sequence; otherwise the transaction MUST fail closed.
- FR-008: The recovery code MUST NOT restart nginx, `sea-speed-camera1-hls-http.service`, MediaMTX, `sea-speed-worker.service`, or `sea-speed-road-worker.service`.
- FR-009: Camera relay URL, local HLS URL, H264 service name and sampling commands MUST be fixed constants inside the exact-source privileged helper; caller-controlled root parameters are forbidden.
- FR-010: Existing exact-source bundle validation, request-file schema, no-argument sudo boundary, `PRIVILEGED_TOPOLOGY=FIXED`, and `ARBITRARY_ROOT_EXECUTION=NO` semantics MUST remain intact.
- FR-011: Existing Auth v1 reconcile MUST complete before Camera 1 freshness recovery; Camera 1 failure MUST propagate as reconcile failure.
- FR-012: Existing VPS deployment acceptance MUST remain behind successful `run_auth_boundary`; therefore a failed Camera 1 reconcile MUST prevent accepted `runtime_verified` state without requiring a separate deploy-script behavior change.
- FR-013: Browser media URL MUST remain `/sea-speed/media/cam1/index.m3u8` and nginx/Auth/Ubuntu relay topology MUST remain unchanged.
- FR-014: Runtime impact is VPS only. Ubuntu Worker/relay deployment MUST remain NOT REQUIRED.
- FR-015: Because the installed root helper changes, production execution capability for the release MUST be `ONE_COMMAND_FALLBACK` with exactly one repository-owned exact-source privilege-boundary bootstrap before canonical GitHub Actions VPS deployment.

## Acceptance criteria

- AC-001: Unit test proves advancing HLS emits `CAMERA1_H264_RECOVERY=NOOP` and issues no `ffmpeg` or `systemctl restart` operation.
- AC-002: Unit test proves static HLS plus a successful fixed relay frame probe uses the exact VPS-compatible FFmpeg argv containing `-timeout 10000000` and no `-rw_timeout`, restarts exactly `sea-speed-camera1-h264.service`, and then requires advancing HLS.
- AC-003: Unit test proves private-relay failure occurs before any restart.
- AC-004: Unit test proves still-static HLS after the fixed restart raises a fail-closed error.
- AC-005: Tests prove the fixed relay URL, local HLS URL and H264 service name are constants and unsupported privileged request actions remain rejected.
- AC-006: Tests prove recovery never invokes nginx, HLS HTTP, MediaMTX, Water worker, or Road worker service names.
- AC-007: Reconcile integration test proves successful Auth v1 reconcile followed by healthy Camera 1 freshness returns both Auth and Camera 1 PASS markers.
- AC-008: Deployment-contract test proves accepted `runtime_verified` state remains behind successful `run_auth_boundary`, so Camera 1 reconcile failure blocks acceptance.
- AC-009: Final source diff is a subset of the exact approved Issue #226 paths, contains no secret/runtime media, and passes PR Validation plus aggregate Quality on one exact head.
- AC-010: Expected-head merge is followed by exact-main Quality before any production authorization decision.
- AC-011: Production bootstrap from the exact approved release reports `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact source SHA, fixed helper/no-args sudo scope, no root shell, and fixed privileged topology.
- AC-012: Canonical VPS deployment succeeds for the exact authorized release and produces accepted `runtime_verified` evidence with Camera 1 freshness PASS.
- AC-013: Authenticated browser acceptance shows current-day advancing Camera 1 clean video while Water/Road worker state remains unaffected.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: no caller-controlled privileged command/service/URL and no arbitrary root execution | Validation: exact constants, request-action rejection, installer no-args sudo contract, focused privileged-helper tests | Evidence: helper accepts no CLI arguments; recovery code names one fixed relay URL, one fixed local HLS URL and one fixed service | Status: PASS
- NFR-002 | Area: FAIL_CLOSED | Target: no restart without valid static-HLS evidence plus readable fixed relay; no accepted deployment without post-restart freshness | Validation: missing-relay and post-restart-static tests plus deployment gate assertion | Evidence: focused tests in `tests/test_vps_auth_privilege_boundary.py` | Status: PASS
- NFR-003 | Area: BLAST_RADIUS | Target: restart only `sea-speed-camera1-h264.service`; preserve nginx, HLS HTTP, MediaMTX and AI workers | Validation: captured command assertions | Evidence: forbidden-service assertions in focused tests | Status: PASS
- NFR-004 | Area: BACKWARD_COMPATIBILITY | Target: preserve Auth v1 reconcile, browser URL, existing camera/relay topology, and compatibility with the installed production VPS FFmpeg CLI | Validation: existing privilege-boundary/Auth tests plus exact fixed FFmpeg argv assertion | Evidence: helper uses `-timeout 10000000`; regression test rejects `-rw_timeout`; camera/nginx/worker configs remain absent from diff | Status: PASS
- NFR-005 | Area: OPERABILITY | Target: stale valid HLS self-recovers through canonical deployment while healthy HLS is no-op | Validation: no-op/restart test scenarios and production HLS sequence evidence | Evidence: source tests pending corrective PR CI; production evidence pending a new exact-SHA authorization | Status: CONCERNS
- NFR-006 | Area: PROVENANCE | Target: privileged recovery bytes are exact-source-bound before root execution | Validation: existing bundle SHA validation and exact-source installer | Evidence: existing privilege-boundary tests remain active; release requires one exact-source bootstrap | Status: PASS

## Runtime feedback

- On 2026-08-19 the operator reported that the authenticated `Чистый поток` still displayed a frame stamped 2026-08-18 and the UI remained `buffering`.
- Earlier bounded VPS diagnostics recorded on Issue #218 comment `5337443938` showed that the Ubuntu private relay at `10.123.239.102:8554/cam1` could produce a frame while local VPS HLS at `127.0.0.1:18889/cam1/index.m3u8` remained static across repeated samples.
- The first authorized production attempt for merged source `28e9f4f30554de40ace25ddc1e65184e9a68e6b8` passed the exact-source privilege boundary but failed closed before any Camera 1 restart because the relay probe invoked `ffmpeg` with `-rw_timeout`, which the installed VPS FFmpeg rejected as `Option rw_timeout not found`; the deployment rolled back successfully to the previous accepted VPS source.
- A bounded read-only operator probe using the same fixed relay URL and `-rtsp_transport tcp -timeout 10000000` opened the relay and reached HEVC decoding, proving the immediate production failure was the helper CLI compatibility defect rather than the earlier option-parsing path being evidence of relay unavailability.
- This narrows the observed fault to the VPS H264 compatibility producer/recovery path rather than the physical camera, Ubuntu relay topology, browser cache, Water worker, nginx, or Authentik.
- The accepted browser topology already routes through the protected H264 output, and ordinary VPS deployment already accepts runtime state only after privileged `run_auth_boundary` succeeds.
- Correct-course design therefore keeps `deploy/vps/deploy.sh` behavior unchanged and changes only the fixed FFmpeg timeout token inside the exact-source-bound privileged reconcile transaction, with exact argv regression coverage. This minimizes changed runtime surface while preserving stale Camera 1 HLS as a deployment acceptance gate.
- The prior production authorization is bound to `28e9f4f...` and does not authorize the corrective merge. After exact-green corrective merge and exact-main Quality, the new release requires a new fingerprint, separate exact-SHA production authorization, and one exact-source privilege-boundary bootstrap before canonical VPS deployment.