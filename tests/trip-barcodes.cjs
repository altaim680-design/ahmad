const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const sandbox={window:{}};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/barcode-code128.js'),'utf8'),sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/trip-barcode.js'),'utf8'),sandbox);
const barcode=sandbox.window.KhotwatiBarcode;
assert.equal(barcode.normalize(' kw0000000001\r\n'),'KW0000000001');assert.ok(!barcode.valid('KW1'));assert.ok(!barcode.valid('<script>'));
for(const code of ['KW0000000001','KW0000098765','KW9999999999']){const svg=barcode.svg(code);assert.ok(svg.includes('>'+code+'</text>'));assert.ok(!svg.includes('style='));assert.ok(svg.includes('<rect x="20"'));}
const load=require('./i18n.cjs');
const els=new Proxy({},{get:(o,k)=>o[k]||(o[k]={value:'',hidden:false,innerHTML:'',textContent:'',addEventListener(){},showModal(){},close(){}})});
const ctx={window:{KhotwatiI18n:load('en').window.KhotwatiI18n,KhotwatiBarcode:barcode,addEventListener(){},supabase:{createClient:()=>({auth:{getSession:async()=>({data:{session:null}})}})}},document:{body:{classList:{add(){},remove(){}}},getElementById:id=>els[id],querySelectorAll:()=>[]},location:{hash:'',search:'',origin:'https://example.test'},URLSearchParams,Intl,Date,console,setTimeout:()=>0,setInterval:()=>0};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/office.js'),'utf8'),ctx);
vm.runInContext("me={role:'company_admin',company_id:'c'};companies=[{id:'c',name:'Company',active:true}];members=[];trips=[{id:'t',company_id:'c',plate:'ABC123',closed:true,barcode:'KW0000000001'}];",ctx);
els.companyFilter.value='c';els.tripFilter.value='open';els.search.value='';assert.equal(vm.runInContext('visibleTrips().length',ctx),0);
vm.runInContext("findBarcode(' kw0000000001\\r\\n')",ctx);assert.equal(vm.runInContext('visibleTrips().length',ctx),1);assert.equal(els.tripFilter.value,'all');assert.ok(els.tripsList.innerHTML.includes('data-op="barcode"'));
vm.runInContext("tripAction('barcode','t')",ctx);assert.ok(els.modalContent.innerHTML.includes('KW0000000001'));assert.ok(els.modalContent.innerHTML.includes('ABC123'));
vm.runInContext("findBarcode('KW0000000999')",ctx);assert.equal(vm.runInContext('visibleTrips().length',ctx),0);assert.ok(els.toast.textContent.includes('No trip'));
if(process.argv.includes('--svg'))process.stdout.write(barcode.svg('KW0000098765'));
else console.log('PASS: barcode generation, normalization, company-scoped lookup, closed-trip search and barcode display');
