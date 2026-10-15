'use strict';
(()=>{
 const BASE='https://ymkzrzdmdrqllpvqdlfx.supabase.co',KEY='sb_publishable_NnABPXhnEsU9-jVgp6DhRQ_Fl-c1xRH';
 const lang=()=>window.KhotwatiI18n?.language||document.documentElement.lang||'ar';
 const words={
  ar:{title:'الإشعارات',empty:'لا توجد إشعارات بعد',all:'تعليم الكل كمقروء',enable:'تفعيل إشعارات الهاتف',enabled:'إشعارات الهاتف مفعّلة',hint:'يصل الإشعار بصوت الجهاز إذا كانت أصوات الإشعارات مفعّلة.',unsupported:'الإشعارات غير مدعومة هنا. على الآيفون أضف الموقع للشاشة الرئيسية وافتحه من الأيقونة.',blocked:'الإشعارات مرفوضة من إعدادات المتصفح.',error:'تعذّر تحميل الإشعارات',new:'إشعار جديد'},
  en:{title:'Notifications',empty:'No notifications yet',all:'Mark all as read',enable:'Enable phone notifications',enabled:'Phone notifications enabled',hint:'Notifications use your phone’s system sound when notification sounds are enabled.',unsupported:'Notifications are not supported here. On iPhone, add the site to the Home Screen and open it from the icon.',blocked:'Notifications are blocked in browser settings.',error:'Could not load notifications',new:'New notification'},
  tr:{title:'Bildirimler',empty:'Henüz bildirim yok',all:'Tümünü okundu işaretle',enable:'Telefon bildirimlerini aç',enabled:'Telefon bildirimleri açık',hint:'Bildirim sesleri açıksa telefonun sistem bildirim sesi kullanılır.',unsupported:'Bildirimler burada desteklenmiyor. iPhone’da siteyi Ana Ekrana ekleyip simgeden açın.',blocked:'Bildirimler tarayıcı ayarlarında engellenmiş.',error:'Bildirimler yüklenemedi',new:'Yeni bildirim'}
 };
 const W=()=>words[lang()]||words.ar;
 let db,sessionUser=null,timer=null,lastTop=null,firstFeed=true,audio=null,panelOpen=false,deepLinked=false;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const style=document.createElement('style');style.textContent=`
 .notify-wrap{position:relative;display:inline-flex;align-items:center;z-index:80}.notify-bell{position:relative;min-width:42px;height:38px;border:1px solid var(--line,#d7e0e7);border-radius:12px;background:var(--card,#fff);color:inherit;font-size:20px;cursor:pointer}.notify-badge{position:absolute;inset-inline-start:-6px;top:-7px;min-width:20px;height:20px;padding:0 5px;border-radius:999px;background:#c92a2a;color:#fff;font:700 12px/20px system-ui;text-align:center;box-shadow:0 0 0 2px var(--card,#fff)}.notify-badge[hidden]{display:none}.notify-panel{position:fixed;top:72px;inset-inline-end:18px;width:min(390px,calc(100vw - 24px));max-height:min(620px,76vh);overflow:auto;background:var(--card,#fff);color:var(--text,#16212a);border:1px solid var(--line,#d7e0e7);border-radius:18px;box-shadow:0 20px 55px #0003;padding:14px;z-index:9999}.notify-panel[hidden]{display:none}.notify-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.notify-head h3{margin:0;font-size:18px}.notify-actions{display:flex;gap:8px;flex-wrap:wrap}.notify-small{font-size:12px;padding:7px 9px}.notify-list{display:grid;gap:8px;margin-top:10px}.notify-item{width:100%;text-align:start;border:1px solid var(--line,#d7e0e7);background:transparent;color:inherit;border-radius:14px;padding:11px;cursor:pointer}.notify-item.unread{background:color-mix(in srgb,var(--accent,#2c8c7d) 10%,transparent);border-color:color-mix(in srgb,var(--accent,#2c8c7d) 42%,var(--line,#d7e0e7))}.notify-item b,.notify-item span,.notify-item time{display:block}.notify-item span{margin-top:4px;line-height:1.55}.notify-item time{margin-top:6px;font-size:11px;opacity:.65}.notify-status{font-size:12px;opacity:.75;margin:8px 0 0}.notify-empty{padding:18px;text-align:center;opacity:.65}.notify-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#dc3545;margin-inline-end:6px}.notify-enable{border:1px solid var(--line,#d7e0e7);border-radius:10px;background:transparent;color:inherit;cursor:pointer;padding:7px 9px}.notify-enable.primary{background:var(--accent,#2c8c7d);color:#fff;border-color:transparent}@media(max-width:640px){.notify-panel{top:66px;inset-inline:12px;width:auto}}
 `;document.head.append(style);
 function stamp(v){try{return new Intl.DateTimeFormat(lang(),{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Damascus'}).format(new Date(v));}catch{return ''}}
 function supported(){return 'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window;}
 function api(action,body={}){return db.auth.getSession().then(async({data:{session}})=>{if(!session)throw Error('no-session');const r=await fetch(BASE+'/functions/v1/fleet-push',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+session.access_token},body:JSON.stringify({action,...body})});const x=await r.json();if(!r.ok)throw Error(x.error||W().error);return x;});}
 function keyBytes(s){const binary=atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4));return Uint8Array.from(binary,c=>c.charCodeAt(0));}
 async function registration(){await navigator.serviceWorker.register('/notify-sw.js',{scope:'/'});return navigator.serviceWorker.ready;}
 async function ensurePush(prompt=false){
  const status=document.getElementById('notifyPushStatus');if(!status)return;
  if(!supported()){status.textContent=W().unsupported;return;}
  try{
   let permission=Notification.permission;if(prompt&&permission==='default')permission=await Notification.requestPermission();
   if(permission==='denied'){status.textContent=W().blocked;return;}
   if(permission!=='granted'){status.textContent=W().hint;return;}
   const [reg,cfg]=await Promise.all([registration(),api('notificationPublicKey')]);
   const sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(cfg.publicKey)});
   await api('saveUserSubscription',{subscription:sub.toJSON(),language:lang()});status.textContent=W().enabled+' · '+W().hint;
  }catch(e){status.textContent=e.message||W().error;}
 }
 function unlockAudio(){if(audio)return;try{const C=window.AudioContext||window.webkitAudioContext;if(!C)return;audio=new C();if(audio.state==='suspended')audio.resume().catch(()=>{});}catch{}}
 function beep(){if(document.hidden||!audio)return;try{if(audio.state==='suspended')audio.resume().catch(()=>{});const now=audio.currentTime;[0,.16].forEach((offset,i)=>{const o=audio.createOscillator(),g=audio.createGain();o.frequency.value=i?720:880;g.gain.setValueAtTime(.0001,now+offset);g.gain.exponentialRampToValueAtTime(.12,now+offset+.015);g.gain.exponentialRampToValueAtTime(.0001,now+offset+.12);o.connect(g);g.connect(audio.destination);o.start(now+offset);o.stop(now+offset+.14);});}catch{}}
 function build(){
  if(document.getElementById('notifyWrap'))return;
  const wrap=document.createElement('div');wrap.id='notifyWrap';wrap.className='notify-wrap';wrap.hidden=true;wrap.setAttribute('data-no-i18n','');
  wrap.innerHTML='<button id="notifyBell" class="notify-bell" type="button" aria-label="'+esc(W().title)+'">🔔<span id="notifyBadge" class="notify-badge" hidden>0</span></button>';
  const header=document.querySelector('body>header');const langBox=header?.querySelector('.language-control');if(header)header.insertBefore(wrap,langBox||null);else document.body.prepend(wrap);
  const panel=document.createElement('aside');panel.id='notifyPanel';panel.className='notify-panel';panel.hidden=true;panel.setAttribute('data-no-i18n','');
  panel.innerHTML='<div class="notify-head"><h3>'+esc(W().title)+'</h3><button id="notifyClose" class="secondary notify-small" type="button">×</button></div><div class="notify-actions"><button id="notifyReadAll" class="secondary notify-small" type="button">'+esc(W().all)+'</button><button id="notifyEnablePush" class="notify-enable primary" type="button">'+esc(W().enable)+'</button></div><p id="notifyPushStatus" class="notify-status"></p><div id="notifyList" class="notify-list"></div>';
  document.body.append(panel);
  document.getElementById('notifyBell').onclick=()=>toggle();document.getElementById('notifyClose').onclick=()=>toggle(false);
  document.getElementById('notifyEnablePush').onclick=()=>ensurePush(true);
  document.getElementById('notifyReadAll').onclick=async()=>{try{await api('readAllNotifications');await refresh();}catch{}};
  panel.onclick=async e=>{const item=e.target.closest('[data-notification-id]');if(!item)return;try{await api('readNotification',{id:item.dataset.notificationId});}catch{}openTarget(item.dataset.url);refresh().catch(()=>{});};
  document.addEventListener('pointerdown',unlockAudio,{once:true,capture:true});document.addEventListener('keydown',unlockAudio,{once:true,capture:true});
 }
 function toggle(value=!panelOpen){panelOpen=!!value;const p=document.getElementById('notifyPanel');if(p)p.hidden=!panelOpen;if(panelOpen)refresh().catch(()=>{});}
 function openTarget(raw){
  try{const u=new URL(raw||'/',location.origin);if(u.origin!==location.origin)return;const trip=u.searchParams.get('notifyTrip'),section=u.searchParams.get('notifySection')||'chat';toggle(false);if(trip&&window.KhotwatiOps?.openTrip){window.KhotwatiOps.openTrip(trip,section);return;}location.assign(u.pathname+u.search);}catch{}
 }
 async function refresh(){
  if(!sessionUser)return;const data=await api('notificationFeed');const list=data.notifications||[],unread=Number(data.unread||0),top=Number(list[0]?.id||0);
  const badge=document.getElementById('notifyBadge');badge.hidden=unread===0;badge.textContent=unread>99?'99+':String(unread);
  const box=document.getElementById('notifyList');box.innerHTML=list.length?list.map(n=>'<button type="button" class="notify-item '+(n.read_at?'':'unread')+'" data-notification-id="'+esc(n.id)+'" data-url="'+esc(n.url||'/')+'"><b>'+(n.read_at?'':'<span class="notify-dot"></span>')+esc(n.title||W().new)+'</b><span>'+esc(n.body||'')+'</span><time>'+esc(stamp(n.created_at))+'</time></button>').join(''):'<div class="notify-empty">'+esc(W().empty)+'</div>';
  if(!firstFeed&&top&&lastTop&&top>lastTop)beep();firstFeed=false;if(top)lastTop=top;
 }
 async function syncSession(){
  try{const {data:{session}}=await db.auth.getSession();const uid=session?.user?.id||null;if(uid===sessionUser)return;sessionUser=uid;firstFeed=true;lastTop=null;document.getElementById('notifyWrap').hidden=!uid;if(!uid){toggle(false);clearInterval(timer);timer=null;return;}await refresh();ensurePush(false);clearInterval(timer);timer=setInterval(()=>{if(!document.hidden)refresh().catch(()=>{});},15000);maybeDeepLink();}catch{}
 }
 function maybeDeepLink(){if(deepLinked)return;const q=new URLSearchParams(location.search),trip=q.get('notifyTrip');if(!trip)return;deepLinked=true;setTimeout(()=>{if(window.KhotwatiOps?.openTrip)window.KhotwatiOps.openTrip(trip,q.get('notifySection')||'chat');},1200);}
 function start(){if(!window.supabase)return;build();db=window.supabase.createClient(BASE,KEY,{auth:{persistSession:true,autoRefreshToken:false,detectSessionInUrl:false,storageKey:'khotwati-driver-session'}});syncSession();db.auth.onAuthStateChange(()=>setTimeout(syncSession,50));setInterval(syncSession,10000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh().catch(()=>{});});}
 start();
})();
