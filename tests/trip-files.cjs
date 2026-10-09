const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const els=new Proxy({},{get:(o,k)=>o[k]||(o[k]={value:'',hidden:false,innerHTML:'',textContent:'',open:false,addEventListener(){},showModal(){this.open=true},close(){this.open=false}})});
let rows=[],uploads=[],removed=[],failInsert=false;
const db={auth:{getSession:async()=>({data:{session:null}})},from(){const q={select(){return q},eq(){return q},order:async()=>({data:rows}),insert:async r=>{if(failInsert)return {error:new Error('insert failed')};rows.push({...r,created_at:new Date().toISOString()});return {data:r}}};return q;},storage:{from:()=>({upload:async(p,f,options)=>{uploads.push({p,f,options});return {data:{path:p}}},remove:async p=>{removed.push(...p);return {data:[]}}})}};
const ctx={window:{KhotwatiI18n:{t:s=>s,locale:'en'},supabase:{createClient:()=>db},addEventListener(){}},document:{body:{classList:{add(){},remove(){}}},getElementById:id=>els[id],querySelectorAll:()=>[],addEventListener(){}},location:{hash:'',search:''},URLSearchParams,Intl,Date,console,setTimeout:()=>0,setInterval:()=>0,FormData:class{},crypto:require('node:crypto').webcrypto,TextDecoder};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('nahda-fleet/office.js','utf8'),ctx);
(async()=>{await new Promise(r=>setImmediate(r));vm.runInContext("me={role:'super_admin'};",ctx);await vm.runInContext("tripFiles({id:'trip',company_id:'company',plate:'ABC'})",ctx);assert.ok(els.modalContent.innerHTML.includes('uploadTripFile'));
els.tripPdfInput.files=[Object.assign(new Blob(['%PDF-1.4 test']),{name:'بيان.pdf'})];await els.uploadTripFile.onsubmit({preventDefault(){},submitter:{}});assert.equal(uploads.length,1);assert.equal(rows[0].filename,'بيان.pdf');assert.equal(uploads[0].options.contentType,'application/pdf');assert.ok(els.modalContent.innerHTML.includes('بيان.pdf'));
els.tripPdfInput.files=[Object.assign(new Blob(['not a pdf']),{name:'fake.pdf'})];await els.uploadTripFile.onsubmit({preventDefault(){},submitter:{}});assert.equal(uploads.length,1);assert.ok(els.modalError.textContent.includes('PDF'));
failInsert=true;els.tripPdfInput.files=[Object.assign(new Blob(['%PDF-1.4 test']),{name:'new.pdf'})];await els.uploadTripFile.onsubmit({preventDefault(){},submitter:{}});assert.equal(removed.length,1);
vm.runInContext("me={role:'company_admin'}",ctx);await vm.runInContext("tripFiles({id:'trip',company_id:'company',plate:'ABC'})",ctx);assert.ok(!els.modalContent.innerHTML.includes('uploadTripFile'));assert.ok(!els.modalContent.innerHTML.includes('data-file-op="delete"'));assert.ok(els.modalContent.innerHTML.includes('data-file-op="open"'));
let sounds=0;
class AudioMock {
 constructor(){this.state='running';this.currentTime=0;this.destination={};}
 createOscillator(){return {frequency:{setValueAtTime(){}},connect(){},start(){sounds++},stop(){}};}
 createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}
}
const audio={window:{AudioContext:AudioMock}};
vm.runInNewContext(fs.readFileSync('nahda-fleet/scan-sound.js','utf8'),audio);audio.window.KhotwatiScanSound.unlock();audio.window.KhotwatiScanSound.play();assert.equal(sounds,1);
console.log('PASS: PDF upload, original Arabic filename, invalid-file rejection, failed-save cleanup, read-only company UI and barcode confirmation sound');
})().catch(e=>{console.error(e);process.exit(1)});
