const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(require('node:path').join(__dirname,'../fleet-backend/fleet-api.ts'),'utf8').replace(/^import[^\n]+\n/,'');
let handle,isOwner=true,targetOwner=false,updates=[],deletes=[],rpcCalls=[];
const db={rpc:async(name,p)=>{rpcCalls.push(name);return {data:name==='fleet_rate_limit'?true:['driver-id','company-admin-id']}},auth:{getUser:async()=>({data:{user:{id:'owner-id'}}}),admin:{deleteUser:async id=>{deletes.push(id);return {error:null}}}},from(table){if(table==='fleet_security_audit')return {insert:async()=>({error:null})};let filters={};const q={select(){return q},eq(k,v){filters[k]=v;return q},update(v){updates.push(v);return q},then(resolve){resolve({error:null})},async maybeSingle(){return {data:table==='fleet_companies'?{name:'Company A'}:filters.user_id==='owner-id'?{user_id:'owner-id',role:'super_admin',active:true,is_owner:isOwner}:{user_id:'assistant-id',role:'super_admin',is_owner:targetOwner}}}};return q;}};
vm.runInNewContext(stripTypeScriptTypes(source),{createClient:()=>db,Deno:{env:{get:()=>''},serve:f=>handle=f},Response,console,Date,TextEncoder,TextDecoder});
const req=body=>handle(new Request('https://test.local',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'application/json'},body:JSON.stringify(body)}));
(async()=>{
let r=await req({action:'setAdminActive',user_id:'assistant-id',active:false});assert.equal(r.status,200);assert.equal(updates[0].active,false);
r=await req({action:'setAdminActive',user_id:'assistant-id',active:true});assert.equal(r.status,200);assert.equal(updates[1].active,true);
targetOwner=true;r=await req({action:'setAdminActive',user_id:'assistant-id',active:false});assert.equal(r.status,403);targetOwner=false;
r=await req({action:'setAdminActive',user_id:'owner-id',active:false});assert.equal(r.status,403);
isOwner=false;for(const action of ['setAdminActive','deleteCompany']){r=await req({action,user_id:'assistant-id',active:false,company_id:'c',confirm_name:'Company A',is_owner:true});assert.equal(r.status,403)}assert.equal(updates.length,2);assert.equal(deletes.length,0);
isOwner=true;r=await req({action:'deleteCompany',company_id:'c',confirm_name:'wrong'});assert.equal(r.status,400);assert.ok(!rpcCalls.includes('fleet_delete_company'));
r=await req({action:'deleteCompany',company_id:'c',confirm_name:'Company A'});assert.equal(r.status,200);assert.deepEqual(deletes,['driver-id','company-admin-id']);
console.log('PASS: owner-only suspend/reactivate and deletion; owner/self protected; confirmation required; linked Auth accounts cleaned up');
})().catch(e=>{console.error(e);process.exit(1)});
