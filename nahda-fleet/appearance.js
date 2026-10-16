'use strict';
(()=>{
 const html=document.documentElement,media=window.matchMedia('(prefers-color-scheme: dark)');
 const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
 const save=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
 let mode=read('khotwati-appearance','system'),large=read('khotwati-large-text','false')==='true';
 if(!['light','dark','system'].includes(mode))mode='system';
 function apply(){html.dataset.appearance=mode==='system'?(media.matches?'dark':'light'):mode;html.classList.toggle('large-text',large);}
 apply();media.addEventListener?.('change',apply);
 document.addEventListener('DOMContentLoaded',()=>{
 const lang=window.KhotwatiI18n?.language||'ar';
 const w=({ar:['المظهر','نهاري','ليلي','حسب الجهاز','تكبير الخط','حجم الخط العادي','الرجوع للأعلى','الإنترنت مقطوع؛ تحديث البيانات وإرسال الموقع يحتاجان اتصالاً.','غرفة العمليات','Enterprise'],en:['Appearance','Light','Dark','Device setting','Larger text','Normal text size','Back to top','You are offline. Updating data and sending location require an internet connection.','Command Center','Enterprise'],tr:['Görünüm','Açık','Koyu','Cihaz ayarı','Yazıyı büyüt','Normal yazı boyutu','Yukarı dön','İnternet bağlantısı yok. Veri güncelleme ve konum gönderme için bağlantı gerekir.','Operasyon Merkezi','Enterprise']})[lang];
 const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 const bar=el('div');bar.className='appearance-bar';bar.setAttribute('data-no-i18n','');
 const label=el('label',w[0]);label.htmlFor='appearanceMode';const select=el('select');select.id='appearanceMode';
 ['light','dark','system'].forEach((v,i)=>{const option=el('option',w[i+1]);option.value=v;select.append(option);});select.value=mode;
 const font=el('button');font.type='button';font.className='secondary';
 function fontLabel(){font.textContent=large?w[5]:w[4];font.setAttribute('aria-pressed',String(large));}fontLabel();
 select.onchange=()=>{mode=select.value;save('khotwati-appearance',mode);apply();};
 font.onclick=()=>{large=!large;save('khotwati-large-text',String(large));apply();fontLabel();};
 bar.append(label,select,font);
 if(location.pathname==='/'||location.pathname==='/index.html'){const ops=el('a','◉ '+w[8]);ops.href='/command-center.html';ops.className='secondary';ops.style.textDecoration='none';bar.append(ops);const ent=el('a','◆ '+w[9]);ent.href='/enterprise.html';ent.className='secondary';ent.style.textDecoration='none';bar.append(ent);}
 document.querySelector('body>header')?.after(bar);
 const offline=el('p',w[7]);offline.className='connection-warning';offline.setAttribute('role','status');offline.setAttribute('aria-live','polite');bar.after(offline);
 const connection=()=>{offline.hidden=navigator.onLine!==false;};connection();window.addEventListener('online',connection);window.addEventListener('offline',connection);
 const top=el('button','↑');top.type='button';top.className='back-to-top';top.setAttribute('aria-label',w[6]);top.title=w[6];top.hidden=true;document.body.append(top);
 const scroll=()=>{top.hidden=window.scrollY<450;};window.addEventListener('scroll',scroll,{passive:true});scroll();top.onclick=()=>window.scrollTo({top:0,behavior:'auto'});
 window.addEventListener('storage',e=>{if(e.key==='khotwati-appearance'){mode=['light','dark','system'].includes(e.newValue)?e.newValue:'system';select.value=mode;apply();}if(e.key==='khotwati-large-text'){large=e.newValue==='true';apply();fontLabel();}});
 if(!['/notifications.html','/enterprise.html'].includes(location.pathname)&&!document.querySelector('script[data-khotwati-notifications]')){const s=document.createElement('script');s.src='/notifications.js?v=2';s.dataset.khotwatiNotifications='1';document.head.append(s);}
 });
})();
