#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).parent.name == 'ci' else Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend/sea-speed/index.html'
TESTS = ROOT / 'tests/test_frontend_contract.py'
EXPECTED_FRONTEND_BLOB = 'a3a2a7453657dc78c3221bbdda12413decebfefd'
EXPECTED_TEST_BLOB = '904037ac1c6fab88d8a2a0f6cc6b24929d240116'

OLD_STATE = 'let hls=null,lastEventsSignature="",roiPoints=[],roiEditing=false,speedLineEditing=null,speedLines={enabled:false,distance_m:57,line_a:[],line_b:[]};'
NEW_STATE = 'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000];\nlet hls=null,streamDesired=false,connectInFlight=false,playInFlight=false,reconnectAttempt=0,reconnectTimer=null,streamGeneration=0,lastEventsSignature="",roiPoints=[],roiEditing=false,speedLineEditing=null,speedLines={enabled:false,distance_m:57,line_a:[],line_b:[]};'

OLD_STREAM = '''function connectStream(){disconnectStream(false);setStatus(streamStatus,"connecting","warn");if(video.canPlayType("application/vnd.apple.mpegurl")){video.src=HLS_URL;video.play().then(()=>setStatus(streamStatus,"online","good")).catch(()=>setStatus(streamStatus,"error","bad"));return}if(window.Hls&&Hls.isSupported()){hls=new Hls({lowLatencyMode:true,backBufferLength:10});hls.loadSource(HLS_URL);hls.attachMedia(video);hls.on(Hls.Events.MANIFEST_PARSED,()=>video.play().then(()=>setStatus(streamStatus,"online","good")));hls.on(Hls.Events.ERROR,(e,d)=>{if(d.fatal)setStatus(streamStatus,"error","bad")})}}
function disconnectStream(l=true){if(hls){hls.destroy();hls=null}video.pause();video.removeAttribute("src");video.load();setStatus(streamStatus,"idle","warn");if(l)log("HLS disconnected")}
'''

NEW_STREAM = '''function clearReconnectTimer(){if(reconnectTimer!==null){clearTimeout(reconnectTimer);reconnectTimer=null}}
function destroyStreamMedia(){if(hls){hls.destroy();hls=null}video.pause();video.removeAttribute("src");video.load()}
function scheduleStreamReconnect(reason){if(!streamDesired||reconnectTimer!==null)return;if(reconnectAttempt>=STREAM_RETRY_DELAYS_MS.length){connectInFlight=false;setStatus(streamStatus,"error","bad");log(`HLS reconnect exhausted: ${reason}`);return}let delay=STREAM_RETRY_DELAYS_MS[reconnectAttempt],attempt=reconnectAttempt+1;reconnectAttempt=attempt;setStatus(streamStatus,`reconnecting ${attempt}/${STREAM_RETRY_DELAYS_MS.length}`,"warn");log(`HLS reconnect ${attempt}/${STREAM_RETRY_DELAYS_MS.length} in ${delay}ms: ${reason}`);reconnectTimer=setTimeout(()=>{reconnectTimer=null;if(!streamDesired)return;connectInFlight=false;connectStream({resetRetry:false,reason:"retry"})},delay)}
async function attemptVideoPlay(generation=streamGeneration){if(!streamDesired||generation!==streamGeneration||playInFlight)return;playInFlight=true;setStatus(streamStatus,"buffering","warn");try{await video.play()}catch(e){if(streamDesired&&generation===streamGeneration){connectInFlight=false;log(`HLS play rejected: ${e?.message||e}`);scheduleStreamReconnect("play rejected")}}finally{playInFlight=false}}
function connectStream({resetRetry=true,reason="manual"}={}){if(resetRetry){streamDesired=true;reconnectAttempt=0;clearReconnectTimer()}else if(!streamDesired)return;if(streamDesired&&!video.paused&&!video.ended){connectInFlight=false;return}if(connectInFlight)return;connectInFlight=true;playInFlight=false;destroyStreamMedia();let generation=++streamGeneration;setStatus(streamStatus,"connecting","warn");log(`HLS connect: ${reason}`);if(video.canPlayType("application/vnd.apple.mpegurl")){video.src=HLS_URL;video.load();attemptVideoPlay(generation);return}if(window.Hls&&Hls.isSupported()){let instance=new Hls({lowLatencyMode:true,backBufferLength:10,maxBufferLength:20});hls=instance;instance.on(Hls.Events.MEDIA_ATTACHED,()=>{if(streamDesired&&generation===streamGeneration&&hls===instance)instance.loadSource(HLS_URL)});instance.on(Hls.Events.MANIFEST_PARSED,()=>attemptVideoPlay(generation));instance.on(Hls.Events.ERROR,(_event,data)=>{if(!streamDesired||generation!==streamGeneration||hls!==instance||!data.fatal)return;connectInFlight=false;if(data.type===Hls.ErrorTypes.NETWORK_ERROR){log("HLS fatal network error; attempting startLoad");try{instance.startLoad()}catch(e){log(e)}scheduleStreamReconnect("network error");return}if(data.type===Hls.ErrorTypes.MEDIA_ERROR){log("HLS fatal media error; attempting recoverMediaError");try{instance.recoverMediaError()}catch(e){log(e)}scheduleStreamReconnect("media error");return}log(`HLS fatal error: ${data.details||data.type||"unknown"}`);instance.destroy();if(hls===instance)hls=null;scheduleStreamReconnect("fatal error")});instance.attachMedia(video);return}streamDesired=false;connectInFlight=false;setStatus(streamStatus,"unsupported","bad");log("HLS playback is unsupported")}
function disconnectStream(l=true){streamDesired=false;streamGeneration++;clearReconnectTimer();reconnectAttempt=0;connectInFlight=false;playInFlight=false;destroyStreamMedia();setStatus(streamStatus,"idle","warn");if(l)log("HLS disconnected")}
video.addEventListener("loadedmetadata",()=>attemptVideoPlay());
video.addEventListener("canplay",()=>attemptVideoPlay());
video.addEventListener("playing",()=>{if(!streamDesired)return;clearReconnectTimer();reconnectAttempt=0;connectInFlight=false;setStatus(streamStatus,"online","good")});
video.addEventListener("waiting",()=>{if(streamDesired)setStatus(streamStatus,"buffering","warn")});
video.addEventListener("stalled",()=>{if(streamDesired){connectInFlight=false;scheduleStreamReconnect("stalled")}});
video.addEventListener("ended",()=>{if(streamDesired){connectInFlight=false;scheduleStreamReconnect("ended")}});
video.addEventListener("error",()=>{if(streamDesired){connectInFlight=false;scheduleStreamReconnect("video error")}});
'''

OLD_INIT = 'connectBtn.onclick=connectStream;disconnectBtn.onclick=()=>disconnectStream(true);loadRoi();loadSpeedLines();loadSpeedConfig();refreshState();refreshEvents();setInterval(refreshState,1500);setInterval(refreshEvents,3000);'
NEW_INIT = 'connectBtn.onclick=()=>connectStream({resetRetry:true,reason:"manual"});disconnectBtn.onclick=()=>disconnectStream(true);loadRoi();loadSpeedLines();loadSpeedConfig();refreshState();refreshEvents();setInterval(refreshState,1500);setInterval(refreshEvents,3000);setTimeout(()=>connectStream({resetRetry:true,reason:"auto"}),0);'

TEST_ANCHOR = '''    def test_detection_history_is_capped_and_does_not_use_bottom_panel(self) -> None:\n'''
TEST_ADDITION = '''    def test_clean_live_has_controlled_retry_lifecycle(self) -> None:\n        for marker in (\n            'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]',\n            'streamDesired=false',\n            'connectInFlight=false',\n            'playInFlight=false',\n            'reconnectAttempt=0',\n            'reconnectTimer=null',\n            'function scheduleStreamReconnect',\n            'function attemptVideoPlay',\n            'function destroyStreamMedia',\n        ):\n            self.assertIn(marker, self.source)\n        self.assertIn('if(connectInFlight)return', self.source)\n        self.assertEqual(self.source.count('new Hls('), 1)\n\n    def test_hls_errors_use_network_and_media_recovery(self) -> None:\n        for marker in (\n            'Hls.ErrorTypes.NETWORK_ERROR',\n            'instance.startLoad()',\n            'Hls.ErrorTypes.MEDIA_ERROR',\n            'instance.recoverMediaError()',\n        ):\n            self.assertIn(marker, self.source)\n\n    def test_stream_status_tracks_actual_playback_and_stop_cancels_retry(self) -> None:\n        self.assertIn('video.addEventListener("playing"', self.source)\n        self.assertEqual(self.source.count('setStatus(streamStatus,"online","good")'), 1)\n        self.assertNotIn(\n            'MANIFEST_PARSED,()=>video.play().then(()=>setStatus(streamStatus,"online"',\n            self.source,\n        )\n        start = self.source.index('function disconnectStream(')\n        end = self.source.index('async function refreshState', start)\n        disconnect_source = self.source[start:end]\n        for marker in (\n            'streamDesired=false',\n            'clearReconnectTimer()',\n            'destroyStreamMedia()',\n            'setStatus(streamStatus,"idle","warn")',\n        ):\n            self.assertIn(marker, disconnect_source)\n        self.assertIn('video.removeAttribute("src")', self.source)\n\n    def test_stream_autoconnects_and_recovers_video_events(self) -> None:\n        for marker in (\n            'video.addEventListener("stalled"',\n            'video.addEventListener("ended"',\n            'video.addEventListener("error"',\n            'setTimeout(()=>connectStream({resetRetry:true,reason:"auto"}),0)',\n        ):\n            self.assertIn(marker, self.source)\n\n'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        if new in source:
            return source
        raise RuntimeError(f'missing replacement anchor: {label}')
    return source.replace(old, new, 1)


def git_blob(path: Path) -> str:
    return subprocess.check_output(['git', 'hash-object', str(path)], cwd=ROOT, text=True).strip()


def main() -> int:
    frontend = FRONTEND.read_text(encoding='utf-8-sig')
    frontend = replace_once(frontend, OLD_STATE, NEW_STATE, 'frontend state')
    frontend = replace_once(frontend, OLD_STREAM, NEW_STREAM, 'stream lifecycle')
    frontend = replace_once(frontend, OLD_INIT, NEW_INIT, 'frontend init')
    FRONTEND.write_text(frontend, encoding='utf-8', newline='\n')

    tests = TESTS.read_text(encoding='utf-8-sig')
    if TEST_ADDITION not in tests:
        if TEST_ANCHOR not in tests:
            raise RuntimeError('missing frontend test anchor')
        tests = tests.replace(TEST_ANCHOR, TEST_ADDITION + TEST_ANCHOR, 1)
    TESTS.write_text(tests, encoding='utf-8', newline='\n')

    actual_frontend = git_blob(FRONTEND)
    actual_tests = git_blob(TESTS)
    if actual_frontend != EXPECTED_FRONTEND_BLOB:
        raise RuntimeError(f'frontend blob mismatch: {actual_frontend}')
    if actual_tests != EXPECTED_TEST_BLOB:
        raise RuntimeError(f'test blob mismatch: {actual_tests}')
    print(f'frontend blob: {actual_frontend}')
    print(f'test blob: {actual_tests}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
