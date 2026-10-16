'use strict';
(()=>{
 const STORAGE_KEY='khotwati-driver-session';
 let allowUntil=0,firstClient=null,recoveryBox=null;
 const allow=(ms=8000)=>{allowUntil=Date.now()+ms;};
 const hasStoredSession=()=>{try{return !!localStorage.getItem(STORAGE_KEY);}catch{return false;}};
 function ensureRecoveryBox(){
  if(recoveryBox||!document.body)return recoveryBox;
  recoveryBox=document.createElement('div');
  recoveryBox.id='khotwatiSessionRecovery';
  recoveryBox.hidden=true;
  recoveryBox.setAttribute('role','status');
  recoveryBox.style.cssText='position:fixed;inset:auto 14px 14px 14px;z-index:99999;padding:14px 16px;border:1px solid #d7e1e8;border-radius:14px;background:Canvas;color:CanvasText;box-shadow:0 12px 30px #0002;font:inherit';
  recoveryBox.innerHTML='<b>الجلسة ما زالت محفوظة</b><p style="margin:6px 0 10px">تعذّر تحميل البيانات مؤقتًا. لا تحتاج لتسجيل الدخول من جديد.</p><button type="button" style="padding:8px 12px;border-radius:10px;border:0;cursor:pointer">إعادة المحاولة</button>';
  recoveryBox.querySelector('button').onclick=()=>location.reload();
  document.body.append(recoveryBox);
  return recoveryBox;
 }
 function showRecovery(){const b=ensureRecoveryBox();if(b)b.hidden=false;}
 function hideRecovery(){if(recoveryBox)recoveryBox.hidden=true;}
 function allowIfExplicit(event){
  if(event.target?.closest?.('#logout,#driverLogout,[data-explicit-logout]'))allow();
 }
 document.addEventListener('click',allowIfExplicit,true);
 document.addEventListener('submit',event=>{if(['loginForm','driverLoginForm'].includes(event.target?.id))allow(12000);},true);
 const supabase=window.supabase;
 if(!supabase?.createClient)return;
 const originalCreate=supabase.createClient.bind(supabase);
 supabase.createClient=(...args)=>{
  const client=originalCreate(...args);
  if(!firstClient)firstClient=client;
  if(client?.auth&&!client.auth.__khotwatiGuarded){
   const realSignOut=client.auth.signOut.bind(client.auth);
   Object.defineProperty(client.auth,'__khotwatiGuarded',{value:true});
   client.auth.signOut=async(options)=>{
    const msg=(document.getElementById('loginError')?.textContent||'')+' '+(document.getElementById('driverAccountStatus')?.textContent||'');
    const accountBlocked=/غير مفعّل|موقوف|disabled|inactive|suspended/i.test(msg);
    if(Date.now()<allowUntil||accountBlocked)return realSignOut(options);
    showRecovery();
    const err=new Error('تعذّر تحميل البيانات مؤقتًا؛ بقي تسجيل الدخول محفوظًا');
    err.code='KHOTWATI_SESSION_PRESERVED';
    throw err;
   };
  }
  return client;
 };
 document.addEventListener('DOMContentLoaded',async()=>{
  const login=document.getElementById('login'),office=document.getElementById('office');
  if(login&&hasStoredSession())login.hidden=true;
  if(!firstClient)return;
  try{
   const {data:{session}}=await firstClient.auth.getSession();
   if(!session){if(login)login.hidden=false;hideRecovery();return;}
   const observer=new MutationObserver(()=>{if(office&&!office.hidden){hideRecovery();observer.disconnect();}});
   if(office)observer.observe(office,{attributes:true,attributeFilter:['hidden']});
   setTimeout(()=>{
    if(office&&!office.hidden)return;
    if(login&&login.hidden)showRecovery();
   },4500);
  }catch{if(login)login.hidden=false;}
 });
 window.KhotwatiSession={allowSignOut:allow,storageKey:STORAGE_KEY};
})();
