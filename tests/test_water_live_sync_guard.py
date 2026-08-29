from pathlib import Path


WATER_HTML = Path("frontend/sea-speed/index.html")


def _source() -> str:
    return WATER_HTML.read_text(encoding="utf-8")


def test_water_live_overlay_clears_without_media_time() -> None:
    source = _source()
    assert 'if(raw==null){clearLive();return}' in source
    assert 'if(raw==null){if(liveBuffer.length)drawLive(liveBuffer[liveBuffer.length-1]);else clearLive();return}' not in source


def test_water_live_overlay_never_falls_back_to_unmatched_latest_envelope() -> None:
    source = _source()
    expected = (
        'if(!br){const near=closestEarlierEnvelope(mediaMs);'
        'if(near&&((getCaptureMs(near)||0)>=mediaMs-2000))drawLive(near);'
        'else clearLive();return}'
    )
    assert expected in source
    assert 'else if(liveBuffer.length)drawLive(liveBuffer[liveBuffer.length-1]);else clearLive();return' not in source


def test_water_live_overlay_keeps_timestamp_bracketing_and_interpolation() -> None:
    source = _source()
    assert 'SeaSpeedLiveSync.bracketForMedia' in source
    assert 'maxGapMs:500' in source
    assert 'drawLive(interpolate(br.lo,br.hi,br.t))' in source
    assert 'closestEarlierEnvelope(mediaMs)' in source
    assert 'mediaMs-2000' in source


def test_water_single_hls_and_worker_metadata_only_invariants_remain() -> None:
    source = _source()
    assert source.count('new Hls(') == 1
    assert 'instance.attachMedia(waterMainVideo)' in source
    assert 'AI worker stopped; live HLS unchanged' in source
    assert 'if(!workerServiceActive)window.clearWaterLiveOverlay?.()' in source
