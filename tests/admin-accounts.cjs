const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(require('node:path').join(__dirname,'../fleet-backend/fleet-api.ts'),'utf8').replace(/^import[^\n]+\n/,'');
let handle,role='super_admin',active=true,failInsert=false,duplicate=false,created=[],inserted=[],deleted=[],audits=[];
const db={rpc:async()=>({data:true}),auth:{getUser:async()=>({data:{user:{id:'root'}}}),admin:{async createUser(x){created.push(x);return duplicate?{error:{message:'duplicate'}}:{data:{user:{id:'new-admin'}}}},async deleteUser(id){deleted.push(id);return {error:null}}}},from(table){if(table==='fleet_security_audit')return {insert:async row=>{audits.push(row);return {error:null}}};assert.equal(table,'fleet_memberships');const q={select(){return q},eq(){return q},async maybeSingle(){return {data:active?{user_id:'root',active,role}:null}},async insert(x){inserted.push(x);return {error:failInsert?{code:'23505'}:null}}};return q;}};
vm.runInNewContext(stripTypeScriptTypes(source),{createClient:()=>db,Deno:{env:{get:()=>''},serve:f=>handle=f},Response,console:{error(){}},Date,TextEncoder,TextDecoder});
const request=body=>handle(new Request('https://test.local',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'application/json'},body:JSON.stringify({action:'createAdmin',username:'Assistant_1',password:'684293',...body})}));
(async()=>{
let r=await request({role:'company_admin',company_id:'untrusted'});assert.equal(r.status,200);assert.equal((await r.json()).username,'assistant_1');assert.equal(inserted[0].role,'super_admin');assert.equal(inserted[0].company_id,null);assert.equal(created[0].email,'assistant_1@nahda-fleet.invalid');assert.equal(created[0].email_confirm,true);assert.equal(audits[0].action,'createAdmin');assert.ok(!JSON.stringify(audits).includes('684293'));
for(const candidate of ['company_admin','driver']){role=candidate;r=await request();assert.equal(r.status,403)}
role='super_admin';active=false;r=await request();assert.equal(r.status,403);active=true;assert.equal(created.length,1);
r=await request({username:'a'});assert.equal(r.status,400);r=await request({password:'123'});assert.equal(r.status,400);assert.equal(created.length,1);
failInsert=true;r=await request();assert.equal(r.status,400);assert.deepEqual(deleted,['new-admin']);
failInsert=false;duplicate=true;const count=inserted.length;r=await request();assert.equal(r.status,400);assert.equal(inserted.length,count);
console.log('PASS: root creates full-access admin, enforced role, company/driver/inactive denial, validation, duplicate handling, rollback and password-free audit');
})().catch(e=>{console.error(e);process.exit(1)});
