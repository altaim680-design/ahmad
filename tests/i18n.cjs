const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.join(__dirname,'../nahda-fleet');
function load(language){const sandbox={window:{},localStorage:{getItem:()=>language},document:{documentElement:{},createTreeWalker:()=>({nextNode:()=>null}),querySelectorAll:()=>[],getElementById:()=>({addEventListener(){}})},NodeFilter:{SHOW_TEXT:4},URLSearchParams,location:{search:''}};vm.runInNewContext(fs.readFileSync(path.join(root,'i18n.js'),'utf8'),sandbox);return sandbox;}
for(const [lang,label] of [['en','Start live tracking'],['tr','Canlı takibi başlat'],['ar','بدء التتبّع المباشر']]){
 const s=load(lang),i=s.window.KhotwatiI18n;assert.equal(i.t('بدء التتبّع المباشر'),label);assert.equal(s.document.documentElement.dir,lang==='ar'?'rtl':'ltr');assert.equal(i.t('سرمدا — شركة أحمد'),lang==='ar'?'سرمدا — شركة أحمد':'سرمدا — '+(lang==='en'?'Company':'Şirket')+' أحمد');
 if(lang!=='ar')assert.ok(!/[\u0600-\u06ff]/.test(i.t('كلمة المرور (٦ خانات أو أكثر — أرقام أو أحرف)')));
 for(const file of ['index.html','driver.html']){const html=fs.readFileSync(path.join(root,file),'utf8').replace(/<script[\s\S]*?<\/script>/g,'').replace(/<[^>]*>/g,'\n');for(const line of html.split('\n')){const left=i.t(line);if(lang!=='ar'&&/[\u0600-\u06ff]/.test(left)&&!['خ','العربية'].includes(left.trim()))console.log('UNTRANSLATED',lang,file,left);}}
}
const office=fs.readFileSync(path.join(root,'office.js'),'utf8');assert.ok(office.includes("'<option value=\"'+esc(v)+'\" '"));assert.ok(office.includes("const states=['بانتظار التحميل','بالطريق','بانتظار التخليص','تم التسليم']"));
console.log('PASS: AR/EN/TR dictionary, direction, labels, and stable backend status values');
module.exports=load;
