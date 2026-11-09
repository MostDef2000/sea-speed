    const SESSION_URL="/sea-speed/api/session";
    const SESSION_WATCHDOG_MS=15000;
    const CAMERAS_URL="/sea-speed/api/cameras";
    const PREVIEW_STATUS_URL="/sea-speed/api/cameras/preview";
    const PREVIEW_STOP_URL="/sea-speed/api/cameras/preview/stop";
    const BATCH_STABLE_ADVANCE_SEC=3;
    const BATCH_VIDEO_READY_TIMEOUT_MS=8000;
    const BATCH_STABLE_TIMEOUT_MS=12000;
    const sessionUser=document.getElementById("sessionUser");
    const grid=document.getElementById("cameraGrid");
    const cameraCount=document.getElementById("cameraCount");
    const activeCamera=document.getElementById("activeCamera");
    const previewTtl=document.getElementById("previewTtl");
    const previewAllButton=document.getElementById("previewAllButton");
    const stopAllButton=document.getElementById("stopAllButton");
    const batchProgress=document.getElementById("batchProgress");
    let cameras=[];
    let active=null;
    let activeHls=null;
    let activeVideo=null;
    let busyCameraId=null;
    let batchRunning=false;
    let batchGeneration=0;
    let batchIndex=0;
    let sessionIdentityEstablished=false;
    let sessionRedirecting=false;
    const snapshotMeta=new Map();
    let lastCommittedSessionId=null;
    const cameraErrors=new Map();

    const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

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

    function cardFor(cameraId){
      return grid.querySelector(`[data-camera-id="${CSS.escape(cameraId)}"]`);
    }

    function formatSnapshotTime(value){
      if(!value)return "";
      const date=new Date(value);
      return Number.isNaN(date.getTime())?"":`Обновлён ${date.toLocaleString()}`;
    }

    function setSnapshotMeta(cameraId,snapshot){
      if(snapshot?.available&&snapshot.url){snapshotMeta.set(cameraId,snapshot)}else{snapshotMeta.delete(cameraId)}
      const card=cardFor(cameraId);
      if(!card)return;
      const image=card.querySelector("[data-snapshot]");
      const time=card.querySelector("[data-snapshot-time]");
      const current=snapshotMeta.get(cameraId);
      if(current?.url){
        if(image.dataset.snapshotUrl!==current.url){image.src=current.url;image.dataset.snapshotUrl=current.url}
        image.alt=`Последний хороший кадр ${cameraId}`;
        if(time)time.textContent=formatSnapshotTime(current.updated_at);
      }else{
        image.removeAttribute("src");
        delete image.dataset.snapshotUrl;
        if(time)time.textContent="";
      }
    }

    function destroyPlayer(){
      if(activeHls){activeHls.destroy();activeHls=null}
      if(activeVideo){activeVideo.pause();activeVideo.removeAttribute("src");activeVideo.load();activeVideo.remove();activeVideo=null}
    }

    async function commitActiveSnapshot(){
      if(!active?.camera_id||!active?.session_id)return false;
      if(lastCommittedSessionId===active.session_id)return true;
      const cameraId=active.camera_id;
      try{
        const data=await api(`/sea-speed/api/cameras/${encodeURIComponent(cameraId)}/snapshot/commit?session_id=${encodeURIComponent(active.session_id)}`,{method:"POST"});
        setSnapshotMeta(cameraId,data.snapshot);
        lastCommittedSessionId=active.session_id;
        cameraErrors.delete(cameraId);
        updateUi();
        return true;
      }catch(error){
        cameraErrors.set(cameraId,error.message||"Кадр не прошёл проверку качества");
        updateUi();
        return false;
      }
    }

    function stateLabel(camera){
      if(busyCameraId===camera.camera_id)return ["starting","warn"];
      if(active&&active.camera_id===camera.camera_id)return ["live","good"];
      if(cameraErrors.has(camera.camera_id))return ["ошибка","bad"];
      if(snapshotMeta.has(camera.camera_id))return ["последний кадр","snapshot"];
      return ["idle",""];
    }

    function renderCatalog(){
      cameraCount.textContent=String(cameras.length);
      if(!cameras.length){
        grid.innerHTML='<div class="empty">Каталог камер не настроен. Установите sanitized runtime catalog на VPS.</div>';
        updateUi();
        return;
      }
      grid.innerHTML=cameras.map(camera=>`<article class="card" data-camera-id="${esc(camera.camera_id)}">
        <div class="frame" data-frame>
          <div class="frame-badge live-badge">live preview</div>
          <div class="frame-badge snapshot-badge">последний кадр</div>
          <div class="placeholder"><svg viewBox="0 0 24 24"><path d="M3 5h13a2 2 0 0 1 2 2v2.2l3-1.7v9l-3-1.7V17a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm0 2v10h13V7H3z"/></svg><span>Preview не запущен</span></div>
          <img data-snapshot alt="Последний хороший кадр ${esc(camera.display_name||camera.camera_id)}">
        </div>
        <div class="body">
          <div class="head"><div><h2 class="name">${esc(camera.display_name||camera.camera_id)}</h2><div class="id">${esc(camera.camera_id)}</div><div class="snapshot-time" data-snapshot-time></div></div><div class="state" data-state>idle</div></div>
          <div class="actions"><button class="play" data-play="${esc(camera.camera_id)}">▶ Предпросмотр</button><button class="stop" data-stop disabled>■ Стоп</button></div>
          <div class="error" data-error></div>
        </div>
      </article>`).join("");
      for(const camera of cameras)setSnapshotMeta(camera.camera_id,camera.snapshot);
      updateUi();
    }

    function updateUi(){
      activeCamera.textContent=active?.display_name||active?.camera_id||"нет";
      previewTtl.textContent=active?.expires_at?new Date(active.expires_at).toLocaleTimeString():"—";
      previewAllButton.disabled=batchRunning||Boolean(busyCameraId)||!cameras.length;
      stopAllButton.disabled=!batchRunning&&!active&&!busyCameraId;
      if(batchRunning){
        const camera=cameras[batchIndex];
        batchProgress.textContent=`Обход камер: ${Math.min(batchIndex+1,cameras.length)} / ${cameras.length}${camera?` · сейчас ${camera.display_name||camera.camera_id}`:""}`;
      }else if(snapshotMeta.size){
        batchProgress.textContent=`Последних кадров на VPS: ${snapshotMeta.size} / ${cameras.length}`;
      }else{
        batchProgress.textContent="Обход не запущен";
      }
      for(const camera of cameras){
        const card=cardFor(camera.camera_id);
        if(!card)continue;
        const frame=card.querySelector("[data-frame]");
        const isActive=Boolean(active&&active.camera_id===camera.camera_id&&activeVideo);
        frame.classList.toggle("live",isActive);
        frame.classList.toggle("snapshot",!isActive&&snapshotMeta.has(camera.camera_id));
        const [label,klass]=stateLabel(camera);
        const state=card.querySelector("[data-state]");
        state.textContent=label;
        state.className=`state ${klass}`;
        card.querySelector("[data-error]").textContent=cameraErrors.get(camera.camera_id)||"";
        card.querySelector("[data-play]").disabled=batchRunning||Boolean(busyCameraId);
        card.querySelector("[data-stop]").disabled=batchRunning||!active||active.camera_id!==camera.camera_id||Boolean(busyCameraId);
      }
    }

    function waitForVideoFrame(video,timeoutMs=BATCH_VIDEO_READY_TIMEOUT_MS){
      if(video.readyState>=2&&video.videoWidth>0)return Promise.resolve(true);
      return new Promise(resolve=>{
        let settled=false;
        const finish=value=>{
          if(settled)return;
          settled=true;
          clearTimeout(timer);
          video.removeEventListener("loadeddata",ready);
          video.removeEventListener("playing",ready);
          resolve(value);
        };
        const ready=()=>finish(video.readyState>=2&&video.videoWidth>0);
        const timer=setTimeout(()=>finish(false),timeoutMs);
        video.addEventListener("loadeddata",ready,{once:true});
        video.addEventListener("playing",ready,{once:true});
      });
    }

    function waitForStableVideoFrame(video,{minAdvanceSec=BATCH_STABLE_ADVANCE_SEC,timeoutMs=BATCH_STABLE_TIMEOUT_MS}={}){
      return new Promise(resolve=>{
        const baseline=Number.isFinite(video.currentTime)?video.currentTime:0;
        const deadline=performance.now()+timeoutMs;
        const check=()=>{
          if(video!==activeVideo)return resolve(false);
          if(video.readyState>=2&&video.videoWidth>0&&Number.isFinite(video.currentTime)&&video.currentTime-baseline>=minAdvanceSec)return resolve(true);
          if(performance.now()>=deadline)return resolve(false);
          requestAnimationFrame(check);
        };
        requestAnimationFrame(check);
      });
    }

    function attachActivePlayer(){
      destroyPlayer();
      const card=active?.camera_id?cardFor(active.camera_id):null;
      if(!card||!active?.hls_url)return null;
      const frame=card.querySelector("[data-frame]");
      const video=document.createElement("video");
      video.controls=true;
      video.playsInline=true;
      video.muted=true;
      video.autoplay=true;
      frame.appendChild(video);
      activeVideo=video;
      const url=active.hls_url+(active.hls_url.includes("?")?"&":"?")+"t="+Date.now();
      if(window.Hls&&Hls.isSupported()){
        const instance=new Hls({lowLatencyMode:true,backBufferLength:5,maxBufferLength:10});
        activeHls=instance;
        instance.loadSource(url);
        instance.attachMedia(video);
        instance.on(Hls.Events.MANIFEST_PARSED,()=>video.play().catch(()=>{}));
        instance.on(Hls.Events.ERROR,(_event,data)=>{
          if(data.fatal&&active?.camera_id){
            cameraErrors.set(active.camera_id,"Ошибка воспроизведения HLS");
            updateUi();
          }
        });
      }else if(video.canPlayType("application/vnd.apple.mpegurl")){
        video.src=url;
        video.play().catch(()=>{});
      }else{
        cameraErrors.set(active.camera_id,"HLS не поддерживается этим браузером");
      }
      updateUi();
      return video;
    }

    async function api(url,options={}){
      const response=await fetch(url,{credentials:"same-origin",cache:"no-store",...options});
      let body={};
      try{body=await response.json()}catch(_error){}
      if(!response.ok)throw new Error(body.detail||`HTTP ${response.status}`);
      return body;
    }

    async function loadCatalog(){
      try{
        const data=await api(CAMERAS_URL);
        cameras=Array.isArray(data.cameras)?data.cameras:[];
        snapshotMeta.clear();
        for(const camera of cameras){if(camera.snapshot?.available&&camera.snapshot.url)snapshotMeta.set(camera.camera_id,camera.snapshot)}
        active=data.active||null;
        lastCommittedSessionId=null;
        renderCatalog();
        if(active?.hls_url)attachActivePlayer();
      }catch(error){
        grid.innerHTML=`<div class="empty">Не удалось загрузить каталог: ${esc(error.message)}</div>`;
      }
    }
    async function refreshPreviewStatus(){
      if(busyCameraId)return;
      try{
        const data=await api(PREVIEW_STATUS_URL);
        const next=data.active||null;
        if(active&&!next){
          destroyPlayer();
          active=null;
          lastCommittedSessionId=null;
          updateUi();
          return;
        }
        if(next&&(!active||next.session_id!==active.session_id)){
          destroyPlayer();
          active=next;
          lastCommittedSessionId=null;
          attachActivePlayer();
          return;
        }
        active=next;
        updateUi();
      }catch(_error){}
    }

    async function startPreview(cameraId,{batchToken=null}={}){
      if(active){
        if(activeVideo?.readyState>=2)await commitActiveSnapshot();
        destroyPlayer();
      }
      busyCameraId=cameraId;
      active=null;
      lastCommittedSessionId=null;
      cameraErrors.delete(cameraId);
      updateUi();
      try{
        const data=await api(`/sea-speed/api/cameras/${encodeURIComponent(cameraId)}/preview/start`,{method:"POST"});
        if(batchToken!==null&&batchToken!==batchGeneration){
          await api(PREVIEW_STOP_URL,{method:"POST"}).catch(()=>{});
          return false;
        }
        active=data.preview;
        lastCommittedSessionId=null;
        const video=attachActivePlayer();
        return Boolean(video);
      }catch(error){
        active=null;
        cameraErrors.set(cameraId,error.message);
        return false;
      }finally{
        busyCameraId=null;
        updateUi();
      }
    }

    async function stopPreview({preserveFrame=true}={}){
      if(preserveFrame&&activeVideo?.readyState>=2)await commitActiveSnapshot();
      busyCameraId=active?.camera_id||"stop";
      destroyPlayer();
      try{await api(PREVIEW_STOP_URL,{method:"POST"})}catch(_error){}
      active=null;
      lastCommittedSessionId=null;
      busyCameraId=null;
      updateUi();
    }

    async function runPreviewAll(){
      if(batchRunning||busyCameraId||!cameras.length)return;
      batchRunning=true;
      const token=++batchGeneration;
      updateUi();
      for(let index=0;index<cameras.length;index++){
        if(token!==batchGeneration)break;
        batchIndex=index;
        updateUi();
        const camera=cameras[index];
        const started=await startPreview(camera.camera_id,{batchToken:token});
        if(token!==batchGeneration)break;
        if(!started||!activeVideo)continue;
        const ready=await waitForVideoFrame(activeVideo);
        if(token!==batchGeneration)break;
        if(!ready){
          cameraErrors.set(camera.camera_id,"Видео не успело показать кадр");
          updateUi();
          continue;
        }
        const stable=await waitForStableVideoFrame(activeVideo);
        if(token!==batchGeneration)break;
        if(!stable){
          cameraErrors.set(camera.camera_id,"Видео не успело стабилизироваться");
          updateUi();
          continue;
        }
        const committed=await commitActiveSnapshot();
        if(!committed&&token===batchGeneration){
          cameraErrors.set(camera.camera_id,cameraErrors.get(camera.camera_id)||"Кадр не прошёл проверку качества");
        }
        updateUi();
      }
      if(token===batchGeneration){
        await stopPreview({preserveFrame:true});
      }
      if(token===batchGeneration){
        batchRunning=false;
        batchIndex=0;
        updateUi();
      }
    }

    async function stopAllPreviews(){
      batchRunning=false;
      batchGeneration++;
      batchIndex=0;
      updateUi();
      await stopPreview({preserveFrame:true});
    }

    grid.addEventListener("click",event=>{
      const play=event.target.closest("[data-play]");
      if(play&&!batchRunning)return void startPreview(play.dataset.play);
      if(event.target.closest("[data-stop]")&&!batchRunning)return void stopPreview({preserveFrame:true});
    });
    previewAllButton.addEventListener("click",()=>void runPreviewAll());
    stopAllButton.addEventListener("click",()=>void stopAllPreviews());

    addEventListener("pagehide",()=>{
      batchRunning=false;
      batchGeneration++;
      if(active||busyCameraId)fetch(PREVIEW_STOP_URL,{method:"POST",credentials:"same-origin",keepalive:true}).catch(()=>{});
      destroyPlayer();
    });

    loadSessionIdentity();
    loadCatalog();
    setInterval(()=>void loadSessionIdentity(),SESSION_WATCHDOG_MS);
    setInterval(refreshPreviewStatus,3000);
