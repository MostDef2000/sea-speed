from __future__ import annotations

from pathlib import Path

FRONTEND = Path("frontend/sea-speed/index.html")
TESTS = Path("tests/test_frontend_contract.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


frontend = FRONTEND.read_text(encoding="utf-8-sig")

frontend = replace_once(
    frontend,
    'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000];\n'
    'let hls=null,streamDesired=false,connectInFlight=false,playInFlight=false,reconnectAttempt=0,reconnectTimer=null,streamGeneration=0,lastEventsSignature="",roiPoints=[],roiEditing=false,speedLineEditing=null,speedLines={enabled:false,distance_m:57,line_a:[],line_b:[]};',
    'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000];\n'
    'const STREAM_STALL_GRACE_MS=2500;\n'
    'const STREAM_RECOVERY_GRACE_MS=3500;\n'
    'let hls=null,streamDesired=false,connectInFlight=false,playInFlight=false,reconnectAttempt=0,reconnectTimer=null,playbackWatchdogTimer=null,recoveryTimer=null,streamGeneration=0,lastPlaybackTime=0,lastPlaybackProgressAt=0,lastEventsSignature="",roiPoints=[],roiEditing=false,speedLineEditing=null,speedLines={enabled:false,distance_m:57,line_a:[],line_b:[]};',
    "stream state",
)

old_block = '''function clearReconnectTimer(){if(reconnectTimer!==null){clearTimeout(reconnectTimer);reconnectTimer=null}}
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
video.addEventListener("error",()=>{if(streamDesired){connectInFlight=false;scheduleStreamReconnect("video error")}});'''

new_block = '''function clearReconnectTimer(){if(reconnectTimer!==null){clearTimeout(reconnectTimer);reconnectTimer=null}}
function clearPlaybackWatchdog(){if(playbackWatchdogTimer!==null){clearTimeout(playbackWatchdogTimer);playbackWatchdogTimer=null}}
function clearRecoveryTimer(){if(recoveryTimer!==null){clearTimeout(recoveryTimer);recoveryTimer=null}}
function clearStreamRecoveryTimers(){clearReconnectTimer();clearPlaybackWatchdog();clearRecoveryTimer()}
function destroyStreamMedia(){if(hls){hls.destroy();hls=null}video.pause();video.removeAttribute("src");video.load()}
function markStreamOnline(){if(!streamDesired)return;clearStreamRecoveryTimers();reconnectAttempt=0;connectInFlight=false;setStatus(streamStatus,"online","good")}
function notePlaybackProgress(){let current=Number(video.currentTime)||0;if(current<lastPlaybackTime||current>lastPlaybackTime+0.02){lastPlaybackTime=current;lastPlaybackProgressAt=Date.now();markStreamOnline()}}
function playbackIsAdvancing(maxAgeMs=STREAM_STALL_GRACE_MS){return streamDesired&&!video.paused&&!video.ended&&lastPlaybackProgressAt>0&&Date.now()-lastPlaybackProgressAt<=maxAgeMs}
function schedulePlaybackWatchdog(reason){if(!streamDesired||playbackWatchdogTimer!==null)return;let baseline=Number(video.currentTime)||0;setStatus(streamStatus,"buffering","warn");playbackWatchdogTimer=setTimeout(()=>{playbackWatchdogTimer=null;if(!streamDesired)return;let current=Number(video.currentTime)||0;if(current>baseline+0.05||playbackIsAdvancing()){lastPlaybackTime=current;lastPlaybackProgressAt=Date.now();markStreamOnline();return}connectInFlight=false;scheduleStreamReconnect(reason)},STREAM_STALL_GRACE_MS)}
function scheduleRecoveryCheck(reason){if(!streamDesired||recoveryTimer!==null)return;let baseline=Number(video.currentTime)||0;setStatus(streamStatus,"buffering","warn");recoveryTimer=setTimeout(()=>{recoveryTimer=null;if(!streamDesired)return;let current=Number(video.currentTime)||0;if(current>baseline+0.05||playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS)){lastPlaybackTime=current;lastPlaybackProgressAt=Date.now();markStreamOnline();return}connectInFlight=false;scheduleStreamReconnect(reason)},STREAM_RECOVERY_GRACE_MS)}
function scheduleStreamReconnect(reason){if(!streamDesired||reconnectTimer!==null)return;clearPlaybackWatchdog();clearRecoveryTimer();if(reconnectAttempt>=STREAM_RETRY_DELAYS_MS.length){connectInFlight=false;setStatus(streamStatus,"error","bad");log(`HLS reconnect exhausted: ${reason}`);return}let delay=STREAM_RETRY_DELAYS_MS[reconnectAttempt],attempt=reconnectAttempt+1;reconnectAttempt=attempt;setStatus(streamStatus,`reconnecting ${attempt}/${STREAM_RETRY_DELAYS_MS.length}`,"warn");log(`HLS reconnect ${attempt}/${STREAM_RETRY_DELAYS_MS.length} in ${delay}ms: ${reason}`);reconnectTimer=setTimeout(()=>{reconnectTimer=null;if(!streamDesired)return;let current=Number(video.currentTime)||0;if(current>lastPlaybackTime+0.05||playbackIsAdvancing()){lastPlaybackTime=current;lastPlaybackProgressAt=Date.now();markStreamOnline();return}connectInFlight=false;connectStream({resetRetry:false,reason:"retry"})},delay)}
async function attemptVideoPlay(generation=streamGeneration){if(!streamDesired||generation!==streamGeneration||playInFlight)return;playInFlight=true;setStatus(streamStatus,"buffering","warn");try{await video.play()}catch(e){if(streamDesired&&generation===streamGeneration){connectInFlight=false;log(`HLS play rejected: ${e?.message||e}`);scheduleStreamReconnect("play rejected")}}finally{playInFlight=false}}
function connectStream({resetRetry=true,reason="manual"}={}){if(resetRetry){streamDesired=true;reconnectAttempt=0;clearStreamRecoveryTimers()}else if(!streamDesired)return;if(playbackIsAdvancing()){markStreamOnline();return}if(connectInFlight)return;connectInFlight=true;playInFlight=false;lastPlaybackTime=0;lastPlaybackProgressAt=0;destroyStreamMedia();let generation=++streamGeneration;setStatus(streamStatus,"connecting","warn");log(`HLS connect: ${reason}`);if(video.canPlayType("application/vnd.apple.mpegurl")){video.src=HLS_URL;video.load();attemptVideoPlay(generation);return}if(window.Hls&&Hls.isSupported()){let instance=new Hls({lowLatencyMode:true,backBufferLength:10,maxBufferLength:20});hls=instance;instance.on(Hls.Events.MEDIA_ATTACHED,()=>{if(streamDesired&&generation===streamGeneration&&hls===instance)instance.loadSource(HLS_URL)});instance.on(Hls.Events.MANIFEST_PARSED,()=>attemptVideoPlay(generation));instance.on(Hls.Events.ERROR,(_event,data)=>{if(!streamDesired||generation!==streamGeneration||hls!==instance||!data.fatal)return;connectInFlight=false;if(data.type===Hls.ErrorTypes.NETWORK_ERROR){log("HLS fatal network error; attempting startLoad");try{instance.startLoad()}catch(e){log(e)}scheduleRecoveryCheck("network recovery timeout");return}if(data.type===Hls.ErrorTypes.MEDIA_ERROR){log("HLS fatal media error; attempting recoverMediaError");try{instance.recoverMediaError()}catch(e){log(e)}scheduleRecoveryCheck("media recovery timeout");return}log(`HLS fatal error: ${data.details||data.type||"unknown"}`);instance.destroy();if(hls===instance)hls=null;scheduleStreamReconnect("fatal error")});instance.attachMedia(video);return}streamDesired=false;connectInFlight=false;setStatus(streamStatus,"unsupported","bad");log("HLS playback is unsupported")}
function disconnectStream(l=true){streamDesired=false;streamGeneration++;clearReconnectTimer();clearPlaybackWatchdog();clearRecoveryTimer();reconnectAttempt=0;connectInFlight=false;playInFlight=false;lastPlaybackTime=0;lastPlaybackProgressAt=0;destroyStreamMedia();setStatus(streamStatus,"idle","warn");if(l)log("HLS disconnected")}
video.addEventListener("loadedmetadata",()=>attemptVideoPlay());
video.addEventListener("canplay",()=>attemptVideoPlay());
video.addEventListener("playing",()=>{if(!streamDesired)return;lastPlaybackTime=Number(video.currentTime)||0;lastPlaybackProgressAt=Date.now();markStreamOnline()});
video.addEventListener("timeupdate",notePlaybackProgress);
video.addEventListener("waiting",()=>schedulePlaybackWatchdog("waiting timeout"));
video.addEventListener("stalled",()=>schedulePlaybackWatchdog("stalled timeout"));
video.addEventListener("ended",()=>{if(streamDesired){connectInFlight=false;scheduleStreamReconnect("ended")}});
video.addEventListener("error",()=>schedulePlaybackWatchdog("video error timeout"));'''

frontend = replace_once(frontend, old_block, new_block, "stream lifecycle")
FRONTEND.write_text(frontend, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8-sig")

anchor = '''    def test_stream_autoconnects_and_recovers_video_events(self) -> None:
'''
addition = '''    def test_stalled_stream_uses_progress_watchdog_before_reconnect(self) -> None:
        for marker in (
            'const STREAM_STALL_GRACE_MS=2500',
            'playbackWatchdogTimer=null',
            'function schedulePlaybackWatchdog',
            'video.currentTime)||0',
            'current>baseline+0.05',
            'video.addEventListener("timeupdate",notePlaybackProgress)',
            'schedulePlaybackWatchdog("waiting timeout")',
            'schedulePlaybackWatchdog("stalled timeout")',
            'schedulePlaybackWatchdog("video error timeout")',
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn('scheduleStreamReconnect("stalled")', self.source)
        self.assertNotIn('scheduleStreamReconnect("video error")', self.source)

    def test_hls_builtin_recovery_gets_grace_period(self) -> None:
        for marker in (
            'const STREAM_RECOVERY_GRACE_MS=3500',
            'recoveryTimer=null',
            'function scheduleRecoveryCheck',
            'scheduleRecoveryCheck("network recovery timeout")',
            'scheduleRecoveryCheck("media recovery timeout")',
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn('scheduleStreamReconnect("network error")', self.source)
        self.assertNotIn('scheduleStreamReconnect("media error")', self.source)

    def test_playback_progress_clears_stale_reconnect_status(self) -> None:
        self.assertIn('function markStreamOnline()', self.source)
        self.assertIn('function playbackIsAdvancing', self.source)
        self.assertIn('if(playbackIsAdvancing()){markStreamOnline();return}', self.source)
        mark_start = self.source.index('function markStreamOnline()')
        mark_end = self.source.index('function notePlaybackProgress()', mark_start)
        mark_source = self.source[mark_start:mark_end]
        for marker in (
            'clearStreamRecoveryTimers()',
            'reconnectAttempt=0',
            'connectInFlight=false',
            'setStatus(streamStatus,"online","good")',
        ):
            self.assertIn(marker, mark_source)

    def test_stop_cancels_watchdog_and_recovery_timers(self) -> None:
        start = self.source.index('function disconnectStream(')
        end = self.source.index('video.addEventListener("loadedmetadata"', start)
        disconnect_source = self.source[start:end]
        for marker in (
            'clearReconnectTimer()',
            'clearPlaybackWatchdog()',
            'clearRecoveryTimer()',
            'lastPlaybackTime=0',
            'lastPlaybackProgressAt=0',
        ):
            self.assertIn(marker, disconnect_source)

'''

tests = replace_once(tests, anchor, addition + anchor, "frontend tests anchor")
TESTS.write_text(tests, encoding="utf-8")

print("Applied HLS false reconnect fix")
