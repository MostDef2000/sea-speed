    const SESSION_URL="/sea-speed/api/session";
    const SESSION_WATCHDOG_MS=15000;
    const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000];
    const HLS_MEDIA_RECOVERY_COOLDOWN_MS=5000;
    const REC_FRESH_MS=30000;
    const STATE_POLL_MS=3000;
    const STREAMS=[
      {id:"cam1",url:"/sea-speed/media/cam1/index.m3u8",stateUrl:"/sea-speed/api/cam1/state"},
      {id:"road1",url:"/sea-speed/media/road1/index.m3u8",stateUrl:"/sea-speed/api/analytics/road1/state"}
    ];
    const sessionUser=document.getElementById("sessionUser");
    let sessionIdentityEstablished=false;
    let sessionRedirecting=false;

    function redirectForReauthentication(){
      if(sessionRedirecting)return;
      sessionRedirecting=true;
      SeaSpeedAuth.showOverlay();
    }

    async function loadSessionIdentity(){
      try{
        const response=await fetch(SESSION_URL,{cache:"no-store",credentials:"same-origin"});
        let body={};
        try{body=await response.json()}catch(_error){}
        const username=String(body.username||"").trim();
        if(!response.ok||!username)throw new Error("trusted identity unavailable");
        sessionIdentityEstablished=true;
        sessionUser.textContent=username;
        sessionUser.classList.remove("bad");
      }catch(_error){
        if(sessionIdentityEstablished){redirectForReauthentication();return}
        sessionUser.textContent="недоступно";
        sessionUser.classList.add("bad");
      }
    }

    function attachStream(stream){
      const video=document.getElementById(`video-${stream.id}`);
      const frame=document.getElementById(`frame-${stream.id}`);
      const state=document.getElementById(`state-${stream.id}`);
      const error=document.getElementById(`error-${stream.id}`);
      const recBadge=document.getElementById(`rec-${stream.id}`);
      const player={hls:null,reconnectTimer:null,attempt:0,lastMediaRecoveryAt:0,destroyed:false,recDeadlineMs:0,recHideTimer:null,recSeq:0};
      const setStatus=(text,klass)=>{state.textContent=text;state.className=`state ${klass||""}`};
      const recFreshDeadline=state=>{
        if(!state||typeof state!=="object"||state.worker_online!==true||state.camera_id!==stream.id)return null;
        const raw=state.recording_last_success_at;
        if(typeof raw!=="string"||!raw)return null;
        const ts=Date.parse(raw);
        if(!Number.isFinite(ts))return null;
        const age=Date.now()-ts;
        return age>=0&&age<REC_FRESH_MS?ts+REC_FRESH_MS:null;
      };
      const hideRec=()=>{
        if(player.recHideTimer!==null){clearTimeout(player.recHideTimer);player.recHideTimer=null}
        player.recDeadlineMs=0;
        if(!recBadge)return;
        recBadge.classList.remove("on");
        recBadge.style.display="none";
        recBadge.hidden=true;
        recBadge.setAttribute("aria-hidden","true");
      };
      const showRec=()=>{
        if(!recBadge)return;
        recBadge.classList.add("on");
        recBadge.style.display="block";
        recBadge.hidden=false;
        recBadge.setAttribute("aria-hidden","false");
      };
      const armRecHide=()=>{
        if(player.recHideTimer!==null){clearTimeout(player.recHideTimer);player.recHideTimer=null}
        if(player.recDeadlineMs<=0){hideRec();return}
        const remaining=player.recDeadlineMs-Date.now();
        if(remaining<=0){hideRec();return}
        player.recHideTimer=setTimeout(()=>{player.recHideTimer=null;if(player.recDeadlineMs>0&&Date.now()<player.recDeadlineMs)armRecHide();else hideRec()},remaining);
      };
      const applyRec=(stateValue,seq)=>{
        if(seq!==player.recSeq)return;
        const deadline=recFreshDeadline(stateValue);
        if(deadline===null){hideRec();return}
        if(deadline>player.recDeadlineMs){player.recDeadlineMs=deadline;showRec();armRecHide()}
      };
      const recheckRec=()=>{
        if(player.recDeadlineMs>0&&Date.now()<player.recDeadlineMs){showRec();armRecHide()}else hideRec();
      };
      const pollState=async()=>{
        const seq=++player.recSeq;
        try{
          const response=await fetch(stream.stateUrl,{cache:"no-store",credentials:"same-origin"});
          if(!response.ok)throw new Error("state "+response.status);
          applyRec(await response.json(),seq);
        }catch(_error){
          if(seq===player.recSeq)hideRec();
        }
      };
      document.addEventListener("visibilitychange",()=>{if(document.visibilityState&&document.visibilityState!=="visible")return;recheckRec()});
      setInterval(pollState,STATE_POLL_MS);
      pollState();
      const destroyMedia=()=>{
        if(player.hls){player.hls.destroy();player.hls=null}
        video.pause();
        video.removeAttribute("src");
        video.load();
      };
      const scheduleReconnect=reason=>{
        if(player.destroyed||player.reconnectTimer)return;
        const delay=STREAM_RETRY_DELAYS_MS[Math.min(player.attempt,STREAM_RETRY_DELAYS_MS.length-1)];
        player.attempt++;
        setStatus(`повтор ${player.attempt}`,"warn");
        player.reconnectTimer=setTimeout(()=>{player.reconnectTimer=null;connect()},delay);
      };
      const connect=()=>{
        if(player.destroyed)return;
        destroyMedia();
        if(window.Hls&&Hls.isSupported()){
          const instance=new Hls({enableWorker:false,lowLatencyMode:true,backBufferLength:10,maxBufferLength:10,liveSyncDurationCount:2,liveMaxLatencyDurationCount:5});
          player.hls=instance;
          instance.on(Hls.Events.MANIFEST_PARSED,()=>video.play().catch(()=>{}));
          instance.on(Hls.Events.ERROR,(_event,data)=>{
            if(!data.fatal)return;
            if(data.type===Hls.ErrorTypes.MEDIA_ERROR&&performance.now()-player.lastMediaRecoveryAt>HLS_MEDIA_RECOVERY_COOLDOWN_MS){
              player.lastMediaRecoveryAt=performance.now();
              instance.recoverMediaError();
              return;
            }
            scheduleReconnect(data.type||"HLS fatal error");
          });
          instance.loadSource(stream.url);
          instance.attachMedia(video);
        }else if(video.canPlayType("application/vnd.apple.mpegurl")){
          video.src=stream.url;
          video.play().catch(()=>{});
        }else{
          error.textContent="HLS не поддерживается этим браузером";
          setStatus("ошибка","bad");
        }
      };
      video.addEventListener("playing",()=>{
        frame.classList.add("live");
        player.attempt=0;
        setStatus("live","good");
        error.textContent="";
      });
      connect();
    }

    for(const stream of STREAMS)attachStream(stream);
    loadSessionIdentity();
    setInterval(()=>void loadSessionIdentity(),SESSION_WATCHDOG_MS);
