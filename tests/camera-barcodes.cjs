const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
global.ZXing=require('../nahda-fleet/barcode-reader.js');
const camera=require('../nahda-fleet/camera-barcode.js');
const vendor={window:{}};vm.createContext(vendor,{codeGeneration:{strings:false,wasm:false}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/barcode-reader.js'),'utf8'),vendor);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/barcode-code128.js'),'utf8'),vendor);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nahda-fleet/trip-barcode.js'),'utf8'),vendor);
const svg=vendor.window.KhotwatiBarcode.svg('KW0000098765'),width=Number(svg.match(/width="(\d+)"/)[1]),height=124;
const pixels=new Uint8ClampedArray(width*height*4);pixels.fill(255);
for(const match of svg.matchAll(/<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"/g)){
 const [x,y,w,h]=match.slice(1).map(Number);for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++){const p=(j*width+i)*4;pixels[p]=pixels[p+1]=pixels[p+2]=0;}
}
assert.equal(camera.decodeCanvas({width,height,getContext:()=>({getImageData:()=>({data:pixels})})}),'KW0000098765');
let stopped=0,found=[],errors=[],tasks=[];
const media={getTracks:()=>[{stop(){stopped++}}]};
const video={srcObject:null,readyState:2,videoWidth:1280,videoHeight:720,play:async()=>{},pause(){}};
const canvas={getContext:()=>({drawImage(){}})};
const opts={video,canvas,onResult:c=>found.push(c),onError:e=>errors.push(e),getUserMedia:async()=>media,decode:()=> 'KW0000098765',setTimeout:f=>{tasks.push(f);return tasks.length},clearTimeout(){}};
(async()=>{
 const scanner=camera.create(opts);await scanner.start();assert.equal(found.length,0);await tasks.shift()();assert.deepEqual(found,['KW0000098765']);assert.equal(stopped,1);assert.equal(video.srcObject,null);
 let resolve;const pending=camera.create({...opts,getUserMedia:()=>new Promise(r=>resolve=r)});const work=pending.start();pending.stop();resolve(media);await work;assert.equal(stopped,2);assert.equal(found.length,1);
 const denied=camera.create({...opts,getUserMedia:async()=>{throw Object.assign(new Error(),{name:'NotAllowedError'})}});await denied.start();assert.equal(errors[0].name,'NotAllowedError');assert.equal(video.srcObject,null);
 tasks=[];const ignore=camera.create({...opts,decode:()=> '123456789012'});await ignore.start();await tasks.shift()();assert.equal(found.length,1);ignore.stop();
 let finish;tasks=[];const late=camera.create({...opts,decode:()=>new Promise(r=>finish=r)});const running=late.start();await new Promise(r=>setImmediate(r));late.stop();finish('KW0000098765');await running;assert.equal(found.length,1);
 console.log('PASS: real CODE128 decoding; CSP without eval; two-read confirmation; stream release; permission denial; invalid-code filtering; cancellation during permission/decode');
})().catch(e=>{console.error(e);process.exit(1)});
