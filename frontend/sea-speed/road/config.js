(function(){
  const API="/sea-speed/api/analytics/road1";
  const cxStatus=document.getElementById("cxStatus");
  const cxOffBtn=document.getElementById("cxOffBtn");
  const cfg={enabled:false,line:[]};

  async function init(){
    try{
      const res=await fetch(API+"/crossing-line",{cache:"no-store",credentials:"same-origin"});
      const data=await res.json();
      if(data&&typeof data.enabled==="boolean")cfg.enabled=data.enabled;
      if(Array.isArray(data.line))cfg.line=data.line;
    }catch(_){}
    // Boot status: "линия активна" / "линия выключена"
    if(cxStatus)cxStatus.textContent=cfg.enabled?"линия активна":"линия выключена";
    if(cxOffBtn)cxOffBtn.textContent=cfg.enabled?"Выключить":"Включить";
  }

  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
