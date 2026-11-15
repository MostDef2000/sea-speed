(function(){
  "use strict";
  var popup=null,pollTimer=null,pollAttempts=0;
  function loginUrl(){
    var target=location.pathname.indexOf("/sea-speed/")===0?location.pathname+location.search+location.hash:"/sea-speed/";
    return "/outpost.goauthentik.io/start?rd="+encodeURIComponent(target);
  }
  function closePopup(){if(popup){try{popup.close()}catch(_error){}popup=null}}
  function stopPolling(){if(pollTimer){clearInterval(pollTimer);pollTimer=null}}
  function openLogin(){
    stopPolling();
    pollAttempts=0;
    popup=window.open(loginUrl(),"sea-speed-login","width=520,height=680");
    pollTimer=setInterval(function(){
      pollAttempts++;
      if(pollAttempts>200){stopPolling();return}
      fetch("/sea-speed/api/session",{cache:"no-store",credentials:"same-origin"}).then(function(response){return response.json()}).then(function(body){
        if(body&&body.username){
          stopPolling();
          closePopup();
          if(location.pathname.indexOf("/sea-speed/")===0)location.reload();
          else location.href="/sea-speed/";
        }
      }).catch(function(){})
    },1500)
  }
  function showOverlay(){
    if(document.getElementById("seaSpeedLoginOverlay"))return;
    var overlay=document.createElement("div");
    overlay.id="seaSpeedLoginOverlay";
    overlay.setAttribute("role","dialog");
    overlay.setAttribute("aria-modal","true");
    overlay.style.cssText="position:fixed;inset:0;z-index:2147483000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;background:rgba(3,17,29,.92);color:#f1fbff;font:16px/1.5 Inter,system-ui,sans-serif;text-align:center;padding:24px";
    var title=document.createElement("p");
    title.textContent="Сессия истекла";
    title.style.cssText="margin:0;font-size:1.15rem;font-weight:700";
    var note=document.createElement("p");
    note.textContent="Войдите, чтобы продолжить работу.";
    note.style.cssText="margin:0;color:#a7c4cf";
    var button=document.createElement("button");
    button.id="seaSpeedLoginBtn";
    button.setAttribute("type","button");
    button.textContent="Войти";
    button.style.cssText="min-height:44px;padding:0 22px;border:0;border-radius:12px;background:linear-gradient(135deg,#6fe0d6,#35beb6);color:#022027;font-size:1rem;font-weight:700;cursor:pointer";
    button.addEventListener("click",openLogin);
    overlay.appendChild(title);
    overlay.appendChild(note);
    overlay.appendChild(button);
    document.body.appendChild(overlay);
  }
  function wireLoginButton(){
    var button=document.getElementById("loginBtn");
    if(button)button.addEventListener("click",openLogin);
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",wireLoginButton);
  else wireLoginButton();
  window.SeaSpeedAuth={openLogin:openLogin,showOverlay:showOverlay,loginUrl:loginUrl};
})();
