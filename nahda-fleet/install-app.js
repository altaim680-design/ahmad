'use strict';
(()=>{
 const words={ar:['ثبّت خطواتي على هاتفك','افتح خطواتي من أيقونته على الشاشة الرئيسية.','تثبيت التطبيق','طريقة التثبيت','لاحقاً','في Safari اضغط «مشاركة»، ثم «إضافة إلى الشاشة الرئيسية»، ثم «إضافة». إذا ظهر خيار «فتح كتطبيق ويب» فعّله. إذا فتحت الرابط داخل واتساب، افتحه أولاً في Safari.','من قائمة المتصفح اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية». إذا لم يظهر الخيار، افتح الرابط في Chrome أو Safari.','إضافة خطواتي للشاشة الرئيسية','تعذّر فتح نافذة التثبيت. جرّب من قائمة المتصفح.'],en:['Install Khotwati on your phone','Open Khotwati from its Home Screen icon.','Install app','How to install','Later','In Safari, tap Share, then Add to Home Screen, then Add. Enable Open as Web App if shown. If you opened this link inside WhatsApp, open it in Safari first.','In the browser menu, choose Install app or Add to Home Screen. If unavailable, open this link in Chrome or Safari.','Add Khotwati to Home Screen','Could not open the install prompt. Try the browser menu.'],tr:['Khotwati’yi telefonunuza ekleyin','Khotwati’yi Ana Ekrandaki simgesinden açın.','Uygulamayı yükle','Nasıl yüklenir','Daha sonra','Safari’de Paylaş, Ana Ekrana Ekle ve Ekle seçeneklerine dokunun. Görünüyorsa Web Uygulaması Olarak Aç seçeneğini etkinleştirin. Bağlantıyı WhatsApp içinde açtıysanız önce Safari’de açın.','Tarayıcı menüsünden Uygulamayı yükle veya Ana Ekrana Ekle seçeneğini seçin. Yoksa bağlantıyı Chrome veya Safari’de açın.','Khotwati’yi Ana Ekrana ekle','Yükleme penceresi açılamadı. Tarayıcı menüsünü deneyin.']};
 const w=words[window.KhotwatiI18n?.language]||words.ar;
 const ios=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const mobile=ios||/Android/.test(navigator.userAgent);
 const mode=window.matchMedia('(display-mode: standalone)');
 let installed=mode.matches||navigator.standalone===true,promptEvent=null;
 if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('/driver-sw.js',{scope:'/'}).catch(()=>{});
 if(installed)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 const box=el('aside');box.className='install-card';box.hidden=true;box.setAttribute('aria-label',w[0]);
 const title=el('h2',w[0]),description=el('p',w[1]),help=el('p');help.hidden=true;help.id='installHelp';help.setAttribute('role','status');
 const actions=el('div');actions.className='actions';
 const install=el('button',w[3]);install.type='button';install.className='primary';
 const later=el('button',w[4]);later.type='button';later.className='secondary';actions.append(install,later);box.append(title,description,help,actions);document.body.append(box);
 const reopen=el('button',w[7]);reopen.type='button';reopen.className='secondary install-link';reopen.hidden=!mobile;document.querySelector('.developer-credit')?.append(reopen);
 const key='khotwati-install-dismissed';
 function dismissed(){try{return Date.now()-Number(localStorage.getItem(key)||0)<7*86400000;}catch{return false;}}
 function hide(){box.hidden=true;try{localStorage.setItem(key,String(Date.now()));}catch{}}
 function show(){if(installed)return;box.hidden=false;help.hidden=true;install.textContent=promptEvent?w[2]:w[3];}
 later.onclick=()=>{hide();reopen.focus();};reopen.onclick=show;
 install.onclick=async()=>{
  if(!promptEvent){help.textContent=ios?w[5]:w[6];help.hidden=false;return;}
  const event=promptEvent;promptEvent=null;install.disabled=true;
  try{await event.prompt();const choice=await event.userChoice;if(choice.outcome==='accepted'){installed=true;reopen.hidden=true;}hide();}catch{help.textContent=w[8];help.hidden=false;}finally{install.disabled=false;install.textContent=w[3];}
 };
 window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();promptEvent=event;reopen.hidden=installed;if(!installed&&!dismissed())show();else install.textContent=w[2];});
 function finish(){installed=true;promptEvent=null;box.hidden=true;reopen.hidden=true;}
 window.addEventListener('appinstalled',finish);mode.addEventListener?.('change',e=>{if(e.matches)finish();});
 if(mobile&&!dismissed())show();
})();
