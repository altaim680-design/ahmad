const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{stripTypeScriptTypes}=require('node:module');
const src=fs.readFileSync('fleet-backend/fleet-push.ts','utf8').replace(/^import[^\n]+\n/gm,'');
let handler,role='company_admin',active=true,notifications=0,claimed=true,writes=[];
const db={auth:{getUser:async()=>({data:{user:{id:'user'}}})},rpc:async n=>({data:n==='fleet_due_reminders'?[]:n==='fleet_claim_reminder'?claimed:true}),from(table){const q={select(){return q},eq(){return q},limit:async()=>({data:[{endpoint:'https://fcm.googleapis.com/fcm/send/test',subscription:{},language:'en'}]}),single:async()=>({data:{public_key:'public',private_key:'private',cron_secret:'test-secret'}}),maybeSingle:async()=>({data:table==='fleet_memberships'?{role,active}:table==='fleet_trips'?{id:'trip',company_id:'company',driver_user_id:'driver',closed:false,reminder_minutes:60}:{active:true,company_id:'company'}}),update(x){writes.push(x);return q},insert:async()=>({error:null}),upsert:async x=>{writes.push(x);return {error:null}},delete(){return q},then(resolve){resolve({data:[],count:0,error:null})}};return q;}};
vm.runInNewContext(stripTypeScriptTypes(src),{createClient:()=>db,webpush:{sendNotification:async()=>{notifications++}},Deno:{env:{get:()=>''},serve:f=>handler=f},Response,TextDecoder,URL,console});
const call=(body,headers={Authorization:'Bearer test'})=>handler(new Request('https://test',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)}));
(async()=>{
assert.equal((await call({action:'remind',trip_id:'trip'},{})).status,401);
for(const action of ['status','settings','remind'])assert.equal((await call({action,trip_id:'trip',minutes:60})).status,403);
assert.equal((await call({action:'cron'},{})).status,401);assert.equal((await call({action:'cron'},{'x-cron-secret':'test-secret'})).status,200);assert.equal(notifications,0);
role='super_admin';assert.equal((await call({action:'settings',trip_id:'trip',minutes:1})).status,400);assert.equal((await call({action:'settings',trip_id:'trip',minutes:60})).status,200);assert.equal(writes[0].reminder_minutes,60);
assert.equal((await call({action:'remind',trip_id:'trip'})).status,200);assert.equal(notifications,1);claimed=false;assert.equal((await call({action:'remind',trip_id:'trip'})).status,409);assert.equal(notifications,1);
active=false;assert.equal((await call({action:'settings',trip_id:'trip',minutes:60})).status,403);active=true;
assert.equal((await call({action:'saveSubscription',subscription:{endpoint:'https://127.0.0.1/private',keys:{p256dh:'A'.repeat(87),auth:'A'.repeat(22)}}})).status,400);
assert.equal((await call({action:'saveSubscription',subscription:{endpoint:'https://evil.push.apple.com.attacker.test/a',keys:{p256dh:'A'.repeat(87),auth:'A'.repeat(22)}}})).status,400);
assert.equal((await call({action:'publicKey'})).status,200);
console.log('PASS: push auth/owner-role gating, disabled admin, cron secret, scheduling intervals, atomic cooldown and endpoint SSRF restrictions');
})().catch(e=>{console.error(e);process.exit(1)});
