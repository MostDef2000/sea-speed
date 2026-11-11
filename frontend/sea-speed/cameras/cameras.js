    const SESSION_URL="/sea-speed/api/session";
    const SESSION_WATCHDOG_MS=15000;
    const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000];
    const HLS_MEDIA_RECOVERY_COOLDOWN_MS=5000;
    const STREAMS=[
      {id:"cam1",url:"/sea-speed/media/cam1/index.m3u8"},
      {id:"road1",url:"/sea-speed/media/road1/index.m3u8"}
    ];
    const sessionUser=document.getElementById("sessionUser");
    let sessionIdentityEstablished=false;
    let sessionRedirecting=false;

    function redirectForReauthentication(){
      if(sessionRedirecting)return;
      sessionRedirecting=true;
      const protectedUrl=window.location.pathname+window.location.search+window.location.hash;
      window.top.location.replace(protectedUrl);
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
      const player={hls:null,reconnectTimer:null,attempt:0,lastMediaRecoveryAt:0,destroyed:false};
      const setStatus=(text,klass)=>{state.textContent=text;state.className=`state ${klass||""}`};
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
          const instance=new Hls({lowLatencyMode:true,backBufferLength:10,maxBufferLength:20});
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
