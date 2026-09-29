const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const src=fs.readFileSync(path.join(__dirname,'../fleet-backend/fleet-api.ts'),'utf8').replace(/^import[^\n]+\n/,'');let handle,authCalls=0;
const db={auth:{getUser:async()=>{authCalls++;return {data:{user:null},error:{}}}}};
vm.runInNewContext(stripTypeScriptTypes(src),{createClient:()=>db,Deno:{env:{get:()=>''},serve:f=>handle=f},Response,TextEncoder,TextDecoder,console,Date});
(async()=>{
const request=(body,headers={},method='POST')=>handle(new Request('https://test.local',{method,headers:{'Content-Type':'application/json',...headers},...(method==='OPTIONS'?{}:{body})}));
let r=await request('{"action":"driverTrips"}',{Origin:'https://evil.example'});assert.equal(r.status,403);assert.equal(authCalls,0);assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
r=await request('',{Origin:'https://nahda-syria-fleet.onrender.com'},'OPTIONS');assert.equal(r.status,200);assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://nahda-syria-fleet.onrender.com');
for(const [body,status,headers] of [['{}',400,{}],['bad json',400,{}],['x'.repeat(16001),413,{}],['{"action":"bootstrap"}',400,{}],['{"action":"driverTrips"}',401,{}],['{}',415,{'Content-Type':'text/plain'}]])assert.equal((await request(body,headers)).status,status);
for(const page of ['index.html','driver.html']){const html=fs.readFileSync(path.join(__dirname,'../nahda-fleet',page),'utf8');assert.ok(html.includes('Content-Security-Policy'));assert.ok(html.includes("script-src 'self'"));assert.ok(!/<script(?![^>]*src=)[^>]*>/.test(html));assert.ok(!/\son\w+=/.test(html));}
console.log('PASS: origin allowlist, preflight, anonymous denial, removed bootstrap, content type, malformed and oversized body, external-only scripts and CSP');
})().catch(e=>{console.error(e);process.exit(1)});
