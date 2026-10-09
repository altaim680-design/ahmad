import {createClient} from 'npm:@supabase/supabase-js@2.117.2';
import webpush from 'npm:web-push@3.6.7';
const db=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false,autoRefreshToken:false}});
const origin='https://nahda-syria-fleet.onrender.com';
function fail(e:any){if(e)throw new Error('تعذّر تنفيذ طلب الإشعارات');}
function allowedEndpoint(value:string){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&(u.hostname==='fcm.googleapis.com'||u.hostname.endsWith('.push.services.mozilla.com')||u.hostname.endsWith('.push.apple.com')||u.hostname.endsWith('.notify.windows.com'));}catch{return false;}}
async function send(trip:any,config:any,gap:number){
 const {data:driver}=await db.from('fleet_drivers').select('active').eq('user_id',trip.driver_user_id).maybeSingle();
 const {data:company}=await db.from('fleet_companies').select('active').eq('id',trip.company_id).maybeSingle();
 if(!driver?.active||!company?.active||trip.closed)return {sent:0,reason:'الرحلة أو حساب السائق غير مفعّل'};
 const {data:subscriptions,error}=await db.from('fleet_push_subscriptions').select('*').eq('driver_user_id',trip.driver_user_id).limit(5);fail(error);
 if(!subscriptions?.length)return {sent:0,reason:'السائق لم يفعّل إشعارات الموقع على هاتفه بعد'};
 const {data:claimed,error:ce}=await db.rpc('fleet_claim_reminder',{p_trip:trip.id,p_gap:gap});fail(ce);
 if(!claimed)return {sent:0,reason:'تم إرسال تذكير حديث؛ انتظر ٥ دقائق على الأقل'};
 let sent=0;
 await Promise.all(subscriptions.map(async(s:any)=>{try{
  if(!allowedEndpoint(s.endpoint))return;
  const bodies:any={ar:'يرجى فتح خطواتي وتحديث موقع السيارة',en:'Please open Khotwati and update your vehicle location',tr:'Lütfen Khotwati uygulamasını açıp araç konumunu güncelleyin'};
  await webpush.sendNotification(s.subscription,JSON.stringify({title:'Khotwati | خطواتي',body:bodies[s.language]||bodies.ar,url:'/driver.html?notifyTrip='+encodeURIComponent(trip.id),tag:'trip-'+trip.id}),{TTL:3600,urgency:'normal',timeout:10000,vapidDetails:{subject:origin,publicKey:config.public_key,privateKey:config.private_key}});sent++;
 }catch(e){if([404,410].includes(e.statusCode))await db.from('fleet_push_subscriptions').delete().eq('endpoint',s.endpoint);}}));
 return {sent,reason:sent?'قُبل الإشعار للإرسال؛ وصوله يعتمد على الهاتف والإنترنت':'تعذّر إرسال الإشعار؛ قد يحتاج السائق إعادة تفعيل الإشعارات'};
}
Deno.serve(async req=>{
 const o=req.headers.get('Origin'),headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'POST,OPTIONS','Content-Type':'application/json','Cache-Control':'no-store','Vary':'Origin'};
 const response=(body:any,status=200)=>new Response(JSON.stringify(body),{status,headers});
 if(o&&o!==origin)return response({error:'Forbidden origin'},403);
 if(req.method==='OPTIONS')return new Response(null,{headers});if(req.method!=='POST')return response({error:'POST only'},405);
 try{
  if(!req.headers.get('content-type')?.startsWith('application/json'))return response({error:'JSON required'},415);
  const reader=req.body?.getReader();let chunks:Uint8Array[]=[],size=0;if(reader){while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>16000){await reader.cancel();return response({error:'Too large'},413);}chunks.push(value);}}
  const raw=new Uint8Array(size);let offset=0;for(const c of chunks){raw.set(c,offset);offset+=c.length;}const b=JSON.parse(new TextDecoder().decode(raw));
  const {data:config,error:cfgerr}=await db.from('fleet_push_config').select('*').single();fail(cfgerr);
  if(b.action==='cron'){
   if(req.headers.get('x-cron-secret')!==config.cron_secret)return response({error:'Unauthorized'},401);
   const {data:trips,error}=await db.rpc('fleet_due_reminders');fail(error);let sent=0;
   // Cap each cron batch and reuse per-trip atomic claims; no overlapping duplicates.
   for(let i=0;i<(trips||[]).length;i+=5){const results=await Promise.all(trips.slice(i,i+5).map((trip:any)=>send(trip,config,trip.reminder_minutes*60)));sent+=results.reduce((n,r)=>n+r.sent,0);}
   return response({sent});
  }
  const token=req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');if(!token)return response({error:'سجّل الدخول'},401);
  const {data:{user},error:ue}=await db.auth.getUser(token);if(ue||!user)return response({error:'سجّل الدخول'},401);
  const {data:rate,error:re}=await db.rpc('fleet_rate_limit',{p_actor:user.id});fail(re);if(!rate)return response({error:'محاولات كثيرة؛ حاول لاحقاً'},429);
  if(['publicKey','saveSubscription','removeSubscription'].includes(b.action)){
   const {data:driver}=await db.from('fleet_drivers').select('company_id,active').eq('user_id',user.id).maybeSingle();
   if(!driver?.active)return response({error:'حساب السائق غير مفعّل'},403);
   const {data:c}=await db.from('fleet_companies').select('active').eq('id',driver.company_id).maybeSingle();if(!c?.active)return response({error:'الشركة متوقفة'},403);
   if(b.action==='publicKey')return response({publicKey:config.public_key});
   if(b.action==='removeSubscription'){const {error}=await db.from('fleet_push_subscriptions').delete().eq('driver_user_id',user.id).eq('endpoint',String(b.endpoint||''));fail(error);return response({ok:true});}
   const s=b.subscription;if(!s||typeof s.endpoint!=='string'||s.endpoint.length>2000||!allowedEndpoint(s.endpoint)||!/^[\w-]{86,88}={0,2}$/.test(s.keys?.p256dh||'')||!/^[\w-]{22,24}={0,2}$/.test(s.keys?.auth||''))return response({error:'اشتراك إشعارات غير صالح'},400);
   const {data:old,error:oe}=await db.from('fleet_push_subscriptions').select('endpoint').eq('driver_user_id',user.id);fail(oe);if(old.length>=5&&!old.some(x=>x.endpoint===s.endpoint))return response({error:'وصلت للحد الأقصى: خمسة أجهزة'},400);
   const {error}=await db.from('fleet_push_subscriptions').upsert({endpoint:s.endpoint,driver_user_id:user.id,subscription:{endpoint:s.endpoint,keys:s.keys},language:['ar','en','tr'].includes(b.language)?b.language:'ar',updated_at:new Date().toISOString()});fail(error);return response({ok:true});
  }
  const {data:m}=await db.from('fleet_memberships').select('role,active').eq('user_id',user.id).maybeSingle();if(!m?.active||m.role!=='super_admin')return response({error:'للمدير العام فقط'},403);
  const {data:trip,error:te}=await db.from('fleet_trips').select('*').eq('id',b.trip_id).maybeSingle();fail(te);if(!trip)return response({error:'الرحلة غير موجودة'},404);
  if(b.action==='status'){const {count,error}=await db.from('fleet_push_subscriptions').select('endpoint',{count:'exact',head:true}).eq('driver_user_id',trip.driver_user_id);fail(error);return response({devices:count||0,minutes:trip.reminder_minutes,last_sent:trip.reminder_last_sent,assigned:!!trip.driver_user_id});}
  if(b.action==='settings'){if(![0,30,60,120].includes(b.minutes))return response({error:'قيمة غير صحيحة'},400);const {error}=await db.from('fleet_trips').update({reminder_minutes:b.minutes}).eq('id',trip.id);fail(error);return response({ok:true});}
  if(b.action==='remind'){const result=await send(trip,config,300);await db.from('fleet_security_audit').insert({actor:user.id,action:'remindDriver',trip_id:trip.id,company_id:trip.company_id,result_status:result.sent?200:409});return response(result,result.sent?200:409);}
  return response({error:'طلب غير معروف'},400);
 }catch(e){console.error('Push request failed',e?.name);return response({error:'تعذّر تنفيذ طلب الإشعارات'},400);}
});
