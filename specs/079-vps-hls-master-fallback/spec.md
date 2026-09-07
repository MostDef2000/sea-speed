# Feature Specification: VPS HLS master fallback

- Feature: 079-vps-hls-master-fallback
- Issue: #335
- Status: Source implementation
- Owner outcome: VPS helper and watchdog accept MediaMTX fmp4 master playlist (STREAM-INF without MEDIA-SEQUENCE) as healthy, so HLS advancing check does not false-fail when master has no EXT-X-MEDIA-SEQUENCE.

## Product outcome

After 078, helper and watchdog use curl -L and get master playlist for fmp4 HLS. Master contains #EXTM3U and #EXT-X-STREAM-INF but no #EXT-X-MEDIA-SEQUENCE, so HLS_MEDIA_SEQUENCE_RE misses and helper raised "has no media sequence". Fix makes _camera1_hls_sequence return 0 when #EXTM3U present but no MEDIA-SEQUENCE, and _advancing return True for 0,0 (master). Change touches deploy/vps/**, VPS REQUIRED.

## User scenarios

### Scenario 1 - Master accepted

Given HLS returns master with STREAM-INF and #EXTM3U but no MEDIA-SEQUENCE, when helper runs _camera1_hls_sequence, then it returns 0 instead of raising.

### Scenario 2 - Advancing with master

Given two consecutive master reads both 0, when _advancing runs, then it returns True.

## Requirements

- FR-001: helper _camera1_hls_sequence MUST return 0 when #EXTM3U present but no MEDIA-SEQUENCE.
- FR-002: watchdog _hls_sequence same.
- FR-003: advancing MUST return True for 0,0.
- FR-004: Change touches deploy/vps/**, VPS REQUIRED.

## Acceptance criteria

- AC-001: master playlist with STREAM-INF returns 0
- AC-002: media playlist with MEDIA-SEQUENCE returns its number
- AC-003: py_compile PASS
- AC-004: PR Change Contract VPS REQUIRED

## NFR assessment

- NFR-001 | Area: Reliability | Target: master without MEDIA-SEQUENCE not false-fail | Validation: helper returns 0 for #EXTM3U | Evidence: manual curl master PASS | Status: PASS

## Runtime feedback

- Master #EXTM3U+STREAM-INF without MEDIA-SEQUENCE caused helper to fail; 0 fallback fixes.
