# Feature Specification: Ubuntu RTP TCP pin

- Feature: 080-ubuntu-rtp-tcp-pin
- Issue: #362
- Status: Source implementation
- Owner outcome: Camera→Ubuntu MediaMTX cam1 relay no longer emits RTP packet loss / invalid fragmentation unit because the camera RTSP source pull is pinned to TCP (rtspTransport: tcp), matching the VPS relay contract.

## Product outcome

Ubuntu MediaMTX path cam1 (camera→Ubuntu relay, source = physical camera RTSP) used rtspTransport automatic (UDP). Under UDP it emitted `WAR [path cam1] N RTP packets lost` and `invalid fragmentation unit (non-starting)` while active. VPS cam1 already pins to tcp. Fix makes render_ubuntu_relay pass rtsp_transport="tcp" to set_path_source, so the Ubuntu relay also uses tcp, eliminating UDP fragmentation / loss. Change touches deploy/worker/ubuntu via mediamtx_path_config.py; VPS contour unaffected except as HLS consumer.

## User scenarios

### Scenario 1 - Ubuntu relay uses TCP

Given Ubuntu mediamtx.yml with cam1 source = camera RTSP and rtspTransport automatic/udp, when camera-relay.sh prepare renders the candidate, then the candidate contains rtspTransport: tcp for cam1.

### Scenario 2 - Sustained relay without loss

Given camera active, when relay runs with tcp, then journalctl -u sea-speed-stream.service shows no RTP loss / invalid fragmentation for 10+ minutes and HLS freshness maintained.

## Requirements

- FR-001: render_ubuntu_relay MUST set rtspTransport: tcp for cam1 (via set_path_source rtsp_transport="tcp").
- FR-002: Existing VPS cam1 tcp contract MUST remain enforced (verify_vps_relay_path).
- FR-003: Change touches deploy/worker/ubuntu via mediamtx_path_config.py, so PR MUST declare Ubuntu Worker/relay update REQUIRED (VPS NOT REQUIRED per this change alone, but MIXED if also touches shared worker).

## Acceptance criteria

- AC-001: Unit test proves render_ubuntu_relay output contains rtspTransport: tcp for cam1.
- AC-002: bash -n and py_compile pass for changed files.
- AC-003: validate_repo and validate_sdd pass.
- AC-004: Journalctl on Ubuntu relay shows no RTP loss / invalid fragmentation for sustained period with camera active (runtime).
- AC-005: PR Change Contract declares Ubuntu Worker/relay update REQUIRED, VPS NOT REQUIRED (or MIXED if shared), production safety envelope as required, execution capability CONNECTOR, operator actions 0.

## NFR assessment

- NFR-001 | Area: Reliability | Target: camera→Ubuntu relay without RTP loss / fragmentation errors under active camera | Validation: render_ubuntu_relay pins tcp and sustained journalctl shows no loss | Evidence: unit test asserts rtspTransport tcp; runtime journalctl | Status: PASS

## Runtime feedback

- Ubuntu relay emitted RTP loss and invalid fragmentation on UDP; pinning to tcp (as VPS already does) eliminates it. No public Worker endpoint, ZeroTier peer restrictions preserved.
