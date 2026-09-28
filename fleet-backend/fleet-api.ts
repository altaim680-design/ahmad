import { createClient } from 'npm:@supabase/supabase-js@2.117.2';
const cors={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,apikey,content-type,x-client-info','Access-Control-Allow-Methods':'POST,OPTIONS','Cache-Control':'no-store'};
const db=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false,autoRefreshToken:false}});
const states=['بانتظار التحميل','بالطريق','بانتظار التخليص','تم التسليم'];
const sha=async(s:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(x=>x.toString(16).padStart(2,'0')).join('');
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{...cors,'Content-Type':'application/json'}});
const str=(v:unknown,max=200)=>{if(typeof v!=='string'||!v.trim()||v.trim().length>max)throw new Error('تحقق من الحقول المطلوبة');return v.trim();};
const username=(v:unknown)=>{const x=str(v,40).toLowerCase();if(!/^[a-z][a-z0-9_.-]{2,39}$/.test(x))throw new Error('اسم المستخدم: أحرف إنكليزية وأرقام، ٣ أحرف على الأقل');return x;};
const password=(v:unknown)=>{const s=str(v,128);if(s.length<12)throw new Error('كلمة المرور يجب أن تكون ١٢ محرفاً على الأقل');return s;};
function check(error:any){if(error){console.error('Fleet operation failed',error.code||error.status);throw new Error(error.code==='23505'?'اسم المستخدم مستخدم مسبقاً':'تعذّر حفظ العملية، حاول مجدداً');}}
async function addUser(name:string,pass:string){const {data,error}=await db.auth.admin.createUser({email:name+'@nahda-fleet.invalid',password:pass,email_confirm:true});if(error)throw new Error('تعذّر إنشاء الحساب؛ تحقق من اسم المستخدم وكلمة المرور');return data.user!;}
Deno.serve(async(req:Request)=>{if(req.method==='OPTIONS')return new Response('ok',{headers:cors});if(req.method!=='POST')return response({error:'Method not allowed'},405);try{
 if(Number(req.headers.get('content-length')||0)>16000)return response({error:'Request too large'},413);
 const raw=await req.text();if(raw.length>16000)return response({error:'Request too large'},413);const b=JSON.parse(raw);const action=b.action;
 if(action==='bootstrap'){
  const hash=await sha(str(b.token,160));const {data:boot,error}=await db.from('fleet_bootstrap').delete().eq('token_hash',hash).select('id');check(error);if(!boot?.length)return response({error:'غير مسموح'},403);
  const name=username(b.username);const pass=password(b.password);const user=await addUser(name,pass);const {error:e}=await db.from('fleet_memberships').insert({user_id:user.id,username:name,role:'super_admin'});check(e);return response({ok:true});
 }
 const bearer=req.headers.get('Authorization')?.replace(/^Bearer\s+/i,'');if(!bearer)return response({error:'سجّل الدخول'},401);const {data:{user},error:ue}=await db.auth.getUser(bearer);if(ue||!user)return response({error:'انتهت الجلسة؛ سجّل الدخول مجدداً'},401);
 if(action==='driverInfo'||action==='driverUpdate'||action==='driverTrips'){
  const {data:driver}=await db.from('fleet_drivers').select('*').eq('user_id',user.id).eq('active',true).maybeSingle();
  if(!driver)return response({error:'هذا الحساب ليس حساب سائق فعّال'},403);
  const {data:company}=await db.from('fleet_companies').select('name,active').eq('id',driver.company_id).maybeSingle();
  if(!company?.active)return response({error:'الشركة متوقفة'},403);
  if(action==='driverTrips'){
   const {data,error}=await db.from('fleet_trips').select('id,plate,destination,status').eq('driver_user_id',user.id).eq('company_id',driver.company_id).eq('closed',false).order('created_at',{ascending:false});check(error);
   return response({trips:data,username:driver.username,company:company.name});
  }
  const {data:trip}=await db.from('fleet_trips').select('*').eq('id',str(b.trip_id,50)).eq('driver_user_id',user.id).eq('company_id',driver.company_id).eq('closed',false).maybeSingle();
  if(!trip)return response({error:'الرحلة غير متاحة لهذا الحساب'},403);
  if(action==='driverInfo')return response({plate:trip.plate,company:company.name,destination:trip.destination,status:trip.status});
  if(!states.includes(b.status))throw new Error('حالة الرحلة غير صحيحة');if(typeof b.latitude!=='number'||!Number.isFinite(b.latitude)||Math.abs(b.latitude)>90||typeof b.longitude!=='number'||!Number.isFinite(b.longitude)||Math.abs(b.longitude)>180||typeof b.accuracy!=='number'||!Number.isFinite(b.accuracy)||b.accuracy<0)throw new Error('حدّد موقعك أولاً');
  const {data:recent}=await db.from('fleet_updates').select('created_at').eq('trip_id',trip.id).order('created_at',{ascending:false}).limit(1);if(recent?.length&&Date.now()-new Date(recent[0].created_at).getTime()<15000)return response({error:'تم استلام تحديث حديث؛ انتظر ١٥ ثانية'},429);
  const {data,error}=await db.rpc('fleet_append_update',{p_trip:trip.id,p_place:str(b.place,200),p_status:b.status,p_note:typeof b.note==='string'?b.note.slice(0,500):'',p_source:'driver',p_lat:b.latitude,p_lon:b.longitude,p_accuracy:b.accuracy});check(error);return response({ok:true,time:data});
 }
 const {data:member}=await db.from('fleet_memberships').select('*').eq('user_id',user.id).eq('active',true).maybeSingle();if(!member)return response({error:'الحساب غير مخوّل'},403);const root=member.role==='super_admin';
 const can=async(cid:string)=>{if(!root&&member.company_id!==cid)throw new Error('لا تملك صلاحية لهذه الشركة');const {data:c}=await db.from('fleet_companies').select('*').eq('id',cid).maybeSingle();if(!c||(!root&&!c.active))throw new Error('الشركة غير متاحة');return c;};
 if(action==='createCompany'){
  if(!root)return response({error:'للمدير العام فقط'},403);const name=str(b.name,120),un=username(b.username),pw=password(b.password);const account=await addUser(un,pw);let cid:string|null=null;
  try{const {data:c,error}=await db.from('fleet_companies').insert({name}).select().single();check(error);cid=c.id;const {error:e}=await db.from('fleet_memberships').insert({user_id:account.id,username:un,role:'company_admin',company_id:cid});check(e);return response({ok:true,company:c,username:un});}catch(e){if(cid)await db.from('fleet_companies').delete().eq('id',cid);await db.auth.admin.deleteUser(account.id);throw e;}
 }
 if(action==='setCompanyActive'){if(!root)return response({error:'للمدير العام فقط'},403);if(typeof b.active!=='boolean')throw new Error('قيمة غير صحيحة');const {error}=await db.from('fleet_companies').update({active:b.active}).eq('id',str(b.company_id,50));check(error);return response({ok:true});}
 if(action==='resetCompanyPassword'){if(!root)return response({error:'للمدير العام فقط'},403);const {data:m}=await db.from('fleet_memberships').select('user_id').eq('company_id',str(b.company_id,50)).eq('role','company_admin').single();if(!m)throw new Error('الحساب غير موجود');const {error}=await db.auth.admin.updateUserById(m.user_id,{password:password(b.password)});check(error);return response({ok:true});}
 if(action==='createTrip'){
  const company=await can(str(b.company_id,50));if(!company.active)throw new Error('فعّل الشركة قبل إضافة رحلة');const {data,error}=await db.from('fleet_trips').insert({company_id:company.id,plate:str(b.plate,60),driver:String(b.driver||'').slice(0,100),phone:String(b.phone||'').slice(0,40),destination:String(b.destination||'').slice(0,140),declaration_no:String(b.declaration_no||'').slice(0,80)}).select().single();check(error);return response({ok:true,trip:data});
 }
 const {data:trip}=await db.from('fleet_trips').select('*').eq('id',str(b.trip_id,50)).maybeSingle();if(!trip)throw new Error('الرحلة غير موجودة');const company=await can(trip.company_id);
 if(action==='closeTrip'){const {error}=await db.from('fleet_trips').update({closed:true}).eq('id',trip.id);check(error);await db.from('fleet_driver_links').delete().eq('trip_id',trip.id);return response({ok:true});}
 if(trip.closed||!company.active)throw new Error('هذه الرحلة متوقفة');
 if(action==='driverAccountInfo'){
  const {data:drivers,error}=await db.from('fleet_drivers').select('user_id,username').eq('company_id',company.id).eq('active',true).order('username');check(error);
  return response({drivers,assigned:trip.driver_user_id});
 }
 if(action==='assignDriver'){
  const {data:d}=await db.from('fleet_drivers').select('user_id').eq('user_id',str(b.driver_id,50)).eq('company_id',company.id).eq('active',true).maybeSingle();
  if(!d)throw new Error('حساب السائق غير متاح لهذه الشركة');
  const {error}=await db.from('fleet_trips').update({driver_user_id:d.user_id}).eq('id',trip.id);check(error);return response({ok:true});
 }
 if(action==='createDriver'){
  const un=username(b.username),pw=password(b.password);const account=await addUser(un,pw);
  try{
   const {error}=await db.from('fleet_drivers').insert({user_id:account.id,company_id:company.id,username:un});check(error);
   const {error:e}=await db.from('fleet_trips').update({driver_user_id:account.id}).eq('id',trip.id);check(e);
   return response({ok:true,username:un});
  }catch(e){await db.auth.admin.deleteUser(account.id);throw e;}
 }
 if(action==='resetDriverPassword'){
  if(!trip.driver_user_id)throw new Error('لا يوجد سائق مرتبط');
  const {error}=await db.auth.admin.updateUserById(trip.driver_user_id,{password:password(b.password)});check(error);return response({ok:true});
 }
 if(action==='driverLink')return response({error:'استخدم حساب السائق بدلاً من الرابط القديم'},400);
 if(action==='officeUpdate'){if(!states.includes(b.status))throw new Error('حالة غير صحيحة');const {data,error}=await db.rpc('fleet_append_update',{p_trip:trip.id,p_place:str(b.place,200),p_status:b.status,p_note:String(b.note||'').slice(0,500),p_source:'office',p_lat:null,p_lon:null,p_accuracy:null});check(error);return response({ok:true,time:data});}
 return response({error:'طلب غير معروف'},400);
}catch(e){return response({error:e instanceof Error?e.message:'تعذّر تنفيذ الطلب'},400);}});
