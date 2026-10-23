'use strict';
(()=>{
const button=document.getElementById('toggleLoginPassword'),password=document.getElementById('password'),hint=document.getElementById('capsLockHint'),form=document.getElementById('loginForm');if(!button||!password||!form)return;
const labels={ar:['إظهار كلمة المرور','إخفاء كلمة المرور'],en:['Show password','Hide password'],tr:['Şifreyi göster','Şifreyi gizle']},words=labels[window.KhotwatiI18n?.language||'ar']||labels.ar;
button.setAttribute('aria-label',words[0]);button.addEventListener('click',()=>{const shown=password.type==='password';password.type=shown?'text':'password';button.setAttribute('aria-pressed',String(shown));button.setAttribute('aria-label',words[shown?1:0]);});
const hide=()=>{password.type='password';button.setAttribute('aria-pressed','false');button.setAttribute('aria-label',words[0]);hint.hidden=true;};password.addEventListener('keydown',e=>hint.hidden=!e.getModifierState?.('CapsLock'));password.addEventListener('keyup',e=>hint.hidden=!e.getModifierState?.('CapsLock'));password.addEventListener('blur',()=>hint.hidden=true);form.addEventListener('submit',hide);window.addEventListener('pagehide',hide);
})();
