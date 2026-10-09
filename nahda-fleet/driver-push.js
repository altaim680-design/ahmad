'use strict';
window.KhotwatiDriverPush=(()=>{
 let db,language='ar';const $=id=>document.getElementById(id),t=s=>window.KhotwatiI18n.t(s);
 const supported=()=>('serviceWorker' in navigator)&&('PushManager' in window)&&('Notification' in window);
 async function call(action,body={}){const {data:{session}}=await db.auth.getSession();if(!session)throw new Error(t('سجّل الدخول أولاً'));const r=await fetch('https://ymkzrzdmdrqllpvqdlfx.supabase.co/functions/v1/fleet-push',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+session.access_token},body:JSON.stringify({action,...body})});const x=await r.json();if(!r.ok)throw new Error(t(x.error||'تعذّر تنفيذ طلب الإشعارات'));return x;}
 async function registration(){await navigator.serviceWorker.register('/driver-sw.js',{scope:'/'});return navigator.serviceWorker.ready;}
 function keyBytes(s){const binary=atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4));return Uint8Array.from(binary,c=>c.charCodeAt(0));}
 async function refresh(){if(!supported()){$('pushStatus').textContent=t('لتفعيل الإشعارات على الآيفون: أضف الموقع للشاشة الرئيسية ثم افتحه من أيقونته.');return;}try{const reg=await registration(),sub=await reg.pushManager.getSubscription();if(sub&&Notification.permission==='granted'){await call('saveSubscription',{subscription:sub.toJSON(),language});$('pushStatus').textContent=t('إشعارات التذكير مفعّلة على هذا الجهاز');}else $('pushStatus').textContent=t('فعّل الإشعارات لتصلك تذكيرات تحديث الموقع');}catch(e){$('pushStatus').textContent=e.message;}}
 async function disable(){if(!supported())return;const reg=await navigator.serviceWorker.getRegistration('/'),sub=await reg?.pushManager.getSubscription();if(sub){try{await call('removeSubscription',{endpoint:sub.endpoint});}finally{await sub.unsubscribe();}}}
 function bind(client,lang){db=client;language=lang;
 $('enablePush').onclick=async()=>{const b=$('enablePush');b.disabled=true;try{if(!supported())throw new Error(t('لتفعيل الإشعارات على الآيفون: أضف الموقع للشاشة الرئيسية ثم افتحه من أيقونته.'));const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error(t('اسمح بالإشعارات من إعدادات المتصفح ثم حاول مجدداً'));const [reg,config]=await Promise.all([registration(),call('publicKey')]);const sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(config.publicKey)});await call('saveSubscription',{subscription:sub.toJSON(),language});$('pushStatus').textContent=t('إشعارات التذكير مفعّلة على هذا الجهاز');}catch(e){$('pushStatus').textContent=e.message;}finally{b.disabled=false;}};
 $('disablePush').onclick=async()=>{try{await disable();$('pushStatus').textContent=t('تم إيقاف إشعارات هذا الجهاز');}catch(e){$('pushStatus').textContent=e.message;}};
 }
 return {bind,refresh,disable};
})();
