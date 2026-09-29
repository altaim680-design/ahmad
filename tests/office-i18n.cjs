const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const load=require('./i18n.cjs'),src=fs.readFileSync(path.join(__dirname,'../nahda-fleet/office.js'),'utf8');
(async()=>{for(const lang of ['en','tr']){
const els=new Proxy({},{get:(o,k)=>o[k]||(o[k]={value:'',hidden:false,innerHTML:'',textContent:'',showModal(){},close(){}})});
const sandbox={window:{KhotwatiI18n:load(lang).window.KhotwatiI18n,addEventListener(){},sessionStorage:{},supabase:{createClient:()=>({auth:{getSession:async()=>({data:{session:null}})}})}},document:{getElementById:id=>els[id],querySelectorAll:()=>[],querySelector:()=>({classList:{toggle(){}}})},location:{hash:'',search:'',origin:'https://example.test'},URLSearchParams,Intl,Date,console,setTimeout:()=>0,setInterval:()=>0};
vm.createContext(sandbox);vm.runInContext(src,sandbox);await new Promise(r=>setImmediate(r));
vm.runInContext("me={role:'super_admin'};companies=[{id:'c',name:'شركة أحمد',active:true}];trips=[{id:'a',company_id:'c',plate:'ABC-123',driver:'محمد',place:'سرمدا',note:'ملاحظة خاصة',status:'بالطريق',closed:false}];members=[];render();",sandbox);
assert.ok(els.tripsList.innerHTML.includes('شركة أحمد'));assert.ok(els.tripsList.innerHTML.includes('ملاحظة خاصة'));assert.ok(els.tripsList.innerHTML.includes(lang==='en'?'On the road':'Yolda'));
vm.runInContext("me={role:'company_admin',company_id:'c'};render();",sandbox);assert.ok(!els.tripsList.innerHTML.includes('data-op="link"'));assert.ok(!els.tripsList.innerHTML.includes('data-op="update"'));assert.ok(!els.tripsList.innerHTML.includes('data-op="close"'));assert.ok(els.tripsList.innerHTML.includes('data-op="history"'));
const option=vm.runInContext("options(states,'بالطريق')",sandbox);assert.ok(option.includes('value="بالطريق" selected'));assert.ok(option.includes(lang==='en'?'On the road':'Yolda'));
const msg=vm.runInContext('singleMessage(trips[0])',sandbox);assert.ok(msg.includes('سرمدا'));assert.ok(msg.includes(lang==='en'?'Vehicle number':'Araç plakası'));
}
console.log('PASS: EN/TR office rendering, report message labels, original company/location/note data, unchanged status values');})().catch(e=>{console.error(e);process.exit(1)});
