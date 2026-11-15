(function(){
function initCxLayer(){
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
const layer=document.getElementById("crossingsLayer");
const viewBtn=document.getElementById("cxViewBtn");
const fromInput=document.getElementById("cxDfrom");
const toInput=document.getElementById("cxDto");
const showBtn=document.getElementById("cxShow");
const out=document.getElementById("cxOut");
if(!layer||!viewBtn)return;
const requestedView=new URLSearchParams(window.location.search).get("view");
const vlzToday=()=>new Date(Date.now()+10*3600e3).toISOString().slice(0,10);
let active=false;
function camFor(){
  try{return (registryScopeKey==="road")?"road1":"cam1"}
  catch(e){return "cam1"}
}
function setHidden(hidden){
  ["filters","objectsGrid"].forEach(id=>{const el=document.getElementById(id);if(el)el.style.display=hidden?"none":""});
  document.querySelectorAll(".pager,.summary-row").forEach(el=>el.style.display=hidden?"none":"");
}
function syncViewQuery(){
  const url=new URL(window.location.href);
  if(active)url.searchParams.set("view","crossings");else url.searchParams.delete("view");
  history.replaceState(null,"",url);
}
function setCrossingsActive(nextActive,syncUrl=true){
  active=!!nextActive;
  layer.style.display=active?"block":"none";
  viewBtn.textContent=active?"← К объектам":"Пересечения";
  setHidden(active);
  if(syncUrl)syncViewQuery();
  if(active){if(!fromInput.value)fromInput.value=vlzToday();if(!toInput.value)toInput.value=vlzToday();loadCrossings()}
}
viewBtn.addEventListener("click",()=>setCrossingsActive(!active));
showBtn.addEventListener("click",loadCrossings);
async function loadCrossings(){
  const cam=camFor();
  out.textContent="Загрузка…";
  try{
    const q=new URLSearchParams({date_from:fromInput.value,date_to:toInput.value});
    const res=await fetch("/sea-speed/api/analytics/"+cam+"/crossings/summary?"+q.toString());
    if(!res.ok)throw Error("HTTP "+res.status);
    const s=await res.json();
    const rows=Object.entries(s.by_class||{}).map(function(kv){
      const v=kv[1];
      return "<tr><td>"+esc(kv[0])+"</td><td align=center>"+v.left_to_right+"</td><td align=center>"+v.right_to_left+"</td><td align=center><b>"+(v.left_to_right+v.right_to_left)+"</b></td></tr>";
    }).join("");
    out.innerHTML="<b>Пересечения "+esc(s.window.date_from||"…")+" … "+esc(s.window.date_to||"…")+" (Владивосток), камера "+esc(s.camera_id)+":</b> → "+s.totals.left_to_right+" · ← "+s.totals.right_to_left
    +'<table style="width:100%;border-collapse:collapse;margin-top:6px"><tr style="color:#93b8c5"><th align=left>класс</th><th>→</th><th>←</th><th>всего</th></tr>'+(rows||'<tr><td colspan=4 style="color:#93b8c5">нет данных за период</td></tr>')+"</table>";
  }catch(e){out.textContent="Ошибка загрузки: "+e.message}
}
if(requestedView==="crossings")setCrossingsActive(true,false);
}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",initCxLayer)}else{initCxLayer()}
})();
