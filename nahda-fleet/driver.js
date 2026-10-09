'use strict';
(()=>{
const t=window.KhotwatiI18n.t,locale=window.KhotwatiI18n.locale;
const $=id=>document.getElementById(id),states=['بانتظار التحميل','بالطريق','بانتظار التخليص','تم التسليم'];
let tripId=new URLSearchParams(location.search).get('notifyTrip')||'',gps=null,ready=false,epoch=0;
const db=window.supabase.createClient('https://ymkzrzdmdrqllpvqdlfx.supabase.co','sb_publishable_NnABPXhnEsU9-jVgp6DhRQ_Fl-c1xRH',{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false,storageKey:'khotwati-driver-session'}});
window.KhotwatiDriverPush?.bind(db,window.KhotwatiI18n.language);
const stamp=t=>new Intl.DateTimeFormat(locale,{timeZone:'Asia/Damascus',dateStyle:'short',timeStyle:'short'}).format(new Date(t));
function errorText(e){return e.name==='AbortError'?window.KhotwatiI18n.t('الاتصال تأخر. تحقق من الإنترنت واضغط إعادة المحاولة.'):/fetch|network|load failed/i.test(e.message)?window.KhotwatiI18n.t('تعذّر الاتصال بخدمة الرحلات. تحقق من الإنترنت وحاول مجدداً.'):window.KhotwatiI18n.t(e.message||'تعذّر فتح الرحلة');}
async function api(action,body={},signal){const c=new AbortController(),timer=setTimeout(()=>c.abort(),25000);const abort=()=>c.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)c.abort();try{const {data:{session}}=await db.auth.getSession();if(!session){showLogin();throw new Error(window.KhotwatiI18n.t('سجّل الدخول أولاً'));}const r=await fetch('https://ymkzrzdmdrqllpvqdlfx.supabase.co/functions/v1/fleet-api',{method:'POST',headers:{Authorization:'Bearer '+session.access_token,'Content-Type':'application/json',apikey:'sb_publishable_NnABPXhnEsU9-jVgp6DhRQ_Fl-c1xRH'},body:JSON.stringify({action,trip_id:tripId,...body}),signal:c.signal});let data;try{data=await r.json();}catch{throw new Error(window.KhotwatiI18n.t('تعذّر قراءة رد خدمة الرحلات؛ أعد المحاولة'));}if(r.status===401)showLogin();if(!r.ok||data.error){const error=new Error(data.error||window.KhotwatiI18n.t('تعذّر تنفيذ الطلب'));error.status=r.status;throw error;}return data;}finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}}
async function loadTrip(){stopLive();$('startTracking').disabled=true;const version=++epoch;gps=null;ready=false;$('locateDriver').disabled=true;$('sendDriver').disabled=true;$('retryDriver').hidden=true;$('driverResult').textContent='';if(!tripId)return;try{const info=await api('driverInfo');if(version!==epoch)return;$('driverPlate').textContent=window.KhotwatiI18n.t('السيارة ')+info.plate;$('driverCompany').textContent=info.company;$('driverDestination').textContent=window.KhotwatiI18n.t('الوجهة: ')+(info.destination||window.KhotwatiI18n.t('غير محدّدة'));$('driverState').replaceChildren(...states.map(s=>{const o=document.createElement('option');o.value=s;o.textContent=window.KhotwatiI18n.t(s);return o;}));$('driverState').value=info.status;ready=true;$('locateDriver').disabled=false;$('startTracking').disabled=false;}catch(e){$('driverPlate').textContent=window.KhotwatiI18n.t('تعذّر فتح الرحلة');$('driverResult').textContent=errorText(e);$('retryDriver').hidden=false;}}
let wakeLock=null;
function releaseWake(){const lock=wakeLock;wakeLock=null;lock?.release().catch(()=>{});$('wakeStatus').textContent='';}
async function keepAwake(){
 if(!live.active||document.hidden)return;
 if(!navigator.wakeLock){$('wakeStatus').textContent=window.KhotwatiI18n.t('أبقِ الشاشة مفتوحة؛ منع القفل التلقائي غير متاح بهذا المتصفح.');return;}
 try{const lock=await navigator.wakeLock.request('screen');if(!live.active||document.hidden){await lock.release();return;}wakeLock=lock;$('wakeStatus').textContent=window.KhotwatiI18n.t('إبقاء الشاشة مضاءة أثناء التتبّع مفعّل.');lock.addEventListener('release',()=>{if(wakeLock===lock){wakeLock=null;$('wakeStatus').textContent=live.active?window.KhotwatiI18n.t('تم تحرير الشاشة؛ أبقِ الموقع ظاهراً لاستمرار التتبّع.'):'';}});}catch{$('wakeStatus').textContent=window.KhotwatiI18n.t('تعذّر منع قفل الشاشة؛ أبقِ الموقع ظاهراً.');}
}
function liveButtons(){const active=live.active;$('startTracking').hidden=active;$('stopTracking').hidden=!active;$('locateDriver').disabled=active||!ready;$('sendDriver').disabled=active||!gps;$('driverPlace').readOnly=active;}
function stopLive(){live.stop();releaseWake();liveButtons();}
const live=new window.FleetLiveTracker({geo:navigator.geolocation,
 onPosition:p=>{$('gpsStatus').textContent=window.KhotwatiI18n.t('إشارة الموقع: دقة تقارب ')+Math.round(p.accuracy)+window.KhotwatiI18n.t(' متر');},
 onState:(state,data)=>{
  const messages={waiting:window.KhotwatiI18n.t('التتبّع مفعّل — بانتظار إشارة الموقع…'),sending:window.KhotwatiI18n.t('التتبّع مفعّل — جارٍ إرسال الموقع…'),sent:window.KhotwatiI18n.t('● التتبّع مفعّل — آخر إرسال: ')+(data?.time?stamp(data.time):''),stopped:window.KhotwatiI18n.t('التتبّع متوقف'),paused:window.KhotwatiI18n.t('التتبّع معلّق لأن الصفحة بالخلفية؛ يعود عند فتحها.'),denied:window.KhotwatiI18n.t('توقف التتبّع: اسمح بالوصول للموقع من إعدادات المتصفح.'),blocked:window.KhotwatiI18n.t('توقف التتبّع: ')+(window.KhotwatiI18n.t(data?.message||'الرحلة غير متاحة')),'gps-error':window.KhotwatiI18n.t('بانتظار إشارة GPS جديدة؛ لا يُرسل موقع قديم.'),'network-error':window.KhotwatiI18n.t('تعذّر الإرسال؛ ستتم محاولة إرسال موقع جديد تلقائياً.')};
  $('trackingStatus').textContent=messages[state]||state;
  if(state==='sent'){$('driverResult').textContent=window.KhotwatiI18n.t('✓ وصل الموقع تلقائياً إلى المكتب');}
  if(!live.active)releaseWake();liveButtons();
 },
 send:async(point,id,signal)=>{
  let place=window.KhotwatiI18n.t('إحداثيات: ')+point.latitude.toFixed(5)+', '+point.longitude.toFixed(5);
  const controller=new AbortController(),abort=()=>controller.abort(),timer=setTimeout(abort,8000);signal.addEventListener('abort',abort,{once:true});
  try{if(signal.aborted)throw new Error('stopped');const response=await fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude='+point.latitude+'&longitude='+point.longitude+'&localityLanguage='+window.KhotwatiI18n.language,{signal:controller.signal});if(response.ok){const d=await response.json();place=[...new Set([d.locality||d.city,d.principalSubdivision,d.countryName].filter(Boolean))].join(' — ')||place;}}catch{}finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
  if(signal.aborted)throw new Error('stopped');
  $('driverPlace').value=place;
  return api('driverUpdate',{trip_id:id,latitude:point.latitude,longitude:point.longitude,accuracy:point.accuracy,place,status:$('driverState').value,note:$('driverNote').value},signal);
 }
});
$('startTracking').onclick=()=>{if(!ready)return;if(!navigator.geolocation){$('trackingStatus').textContent=window.KhotwatiI18n.t('المتصفح لا يدعم تحديد الموقع');return;}epoch++;gps=null;live.start(tripId);liveButtons();keepAwake();};
$('stopTracking').onclick=stopLive;
document.addEventListener('visibilitychange',()=>{if(!live.active)return;if(document.hidden){live.pause();releaseWake();}else{live.resume();keepAwake();}});
window.addEventListener('online',()=>{if(live.active&&!document.hidden)live.resume();});
window.addEventListener('pagehide',()=>stopLive());
$('retryDriver').onclick=loadTrip;
$('locateDriver').onclick=()=>{if(!ready)return;const version=epoch;if(!navigator.geolocation){$('gpsStatus').textContent=window.KhotwatiI18n.t('افتح الرابط في Safari أو Chrome لتحديد الموقع');return;}gps=null;$('sendDriver').disabled=true;$('locateDriver').disabled=true;$('driverResult').textContent='';$('driverPlace').value='';$('gpsStatus').textContent=window.KhotwatiI18n.t('وافق على إذن الموقع؛ جارٍ تحديد مكانك…');navigator.geolocation.getCurrentPosition(async p=>{if(version!==epoch)return;const current={latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy,time:Date.now()};gps=current;$('gpsStatus').textContent=window.KhotwatiI18n.t('تم تحديد الموقع بدقة تقارب ')+Math.round(current.accuracy)+window.KhotwatiI18n.t(' متر. جارٍ معرفة اسم البلدة…');const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);try{const r=await fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude='+current.latitude+'&longitude='+current.longitude+'&localityLanguage='+window.KhotwatiI18n.language,{signal:controller.signal});if(!r.ok)throw new Error();const d=await r.json();if(version!==epoch)return;const place=[...new Set([d.locality||d.city,d.principalSubdivision,d.countryName].filter(Boolean))].join(' — ');if(!place)throw new Error();$('driverPlace').value=place;$('gpsStatus').textContent=window.KhotwatiI18n.t('موقعك جاهز. راجع اسم البلدة ثم أرسل التحديث.');}catch{if(version!==epoch)return;$('gpsStatus').textContent=window.KhotwatiI18n.t('تم تحديد الإحداثيات؛ اكتب اسم البلدة قبل الإرسال.');}finally{clearTimeout(timer);if(version!==epoch)return;$('locateDriver').disabled=false;$('sendDriver').disabled=false;}},e=>{if(version!==epoch)return;$('gpsStatus').textContent=e.code===1?window.KhotwatiI18n.t('إذن الموقع مرفوض. فعّله للموقع من إعدادات المتصفح، ثم حاول مجدداً.'):window.KhotwatiI18n.t('تعذّر تحديد الموقع؛ فعّل خدمة الموقع وحاول مجدداً.');$('locateDriver').disabled=false;},{enableHighAccuracy:true,timeout:20000,maximumAge:0});};
$('sendDriver').onclick=async()=>{if(!ready||!gps||Date.now()-gps.time>300000){$('driverResult').textContent=window.KhotwatiI18n.t('حدّد موقعك من جديد قبل الإرسال');return;}const place=$('driverPlace').value.trim();if(!place){$('driverResult').textContent=window.KhotwatiI18n.t('اكتب اسم المكان أولاً');return;}$('sendDriver').disabled=true;try{const r=await api('driverUpdate',{latitude:gps.latitude,longitude:gps.longitude,accuracy:gps.accuracy,place,status:$('driverState').value,note:$('driverNote').value});$('driverResult').textContent=window.KhotwatiI18n.t('✓ وصل التحديث إلى المكتب — ')+stamp(r.time);gps=null;$('gpsStatus').textContent=window.KhotwatiI18n.t('تم الإرسال. حدّد موقعك من جديد عندما تريد إرسال تحديث آخر.');}catch(e){$('driverResult').textContent=errorText(e);$('sendDriver').disabled=false;}};
function showLogin(){stopLive();epoch++;ready=false;gps=null;$('driverLogin').hidden=false;$('driverPage').hidden=true;$('driverChooser').hidden=true;$('driverLogout').hidden=true;}
async function loadAccount(){
 stopLive();
 const {data:{session}}=await db.auth.getSession();if(!session){showLogin();return;}
 $('driverLogin').hidden=true;$('driverLogout').hidden=false;$('driverChooser').hidden=false;
 $('driverAccountStatus').textContent=window.KhotwatiI18n.t('جارٍ تحميل رحلاتك…');$('driverPage').hidden=true;ready=false;gps=null;
 try{
  const data=await api('driverTrips');
  window.KhotwatiDriverPush?.refresh();
  $('driverTrips').replaceChildren(...data.trips.map(t=>{const o=document.createElement('option');o.value=t.id;o.textContent=t.plate+' — '+(t.destination||window.KhotwatiI18n.t('بدون وجهة'));return o;}));
  $('driverAccountStatus').textContent=data.company+' · '+data.username+(data.trips.length?'':window.KhotwatiI18n.t(' — لا توجد رحلات مفتوحة مرتبطة بحسابك. تواصل مع المكتب.'));
  tripId=data.trips.some(t=>t.id===tripId)?tripId:(data.trips[0]?.id||'');$('driverTrips').value=tripId;
  if(tripId){$('driverPage').hidden=false;await loadTrip();}
 }catch(e){$('driverAccountStatus').textContent=errorText(e);throw e;}
}
$('driverLoginForm').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('driverLoginError').textContent='';try{
 const {error}=await db.auth.signInWithPassword({email:$('driverUsername').value.trim().toLowerCase()+'@nahda-fleet.invalid',password:$('driverPassword').value});if(error)throw error;
 $('driverPassword').value='';await loadAccount();
}catch(e){if(!$('driverLogin').hidden){$('driverLoginError').textContent=/Invalid login/i.test(e.message)?window.KhotwatiI18n.t('اسم المستخدم أو كلمة المرور غير صحيحة'):errorText(e);}}finally{button.disabled=false;}};
$('driverLogout').onclick=async()=>{stopLive();try{await window.KhotwatiDriverPush?.disable();}catch{}const {error}=await db.auth.signOut({scope:'local'});if(error){$('driverAccountStatus').textContent=errorText(error);return;}tripId='';showLogin();};
$('reloadTrips').onclick=()=>loadAccount().catch(()=>{});
$('driverTrips').onchange=()=>{tripId=$('driverTrips').value;gps=null;$('driverPlace').value='';$('driverNote').value='';$('gpsStatus').textContent='';loadTrip();};
loadAccount().catch(()=>{});
})();
