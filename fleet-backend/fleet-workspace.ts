import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.57.4';
const db=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const ORIGIN='https://nahda-syria-fleet.onrender.com';
const mimeExt:Record<string,string>={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','audio/webm':'webm','audio/mp4':'m4a','audio/ogg':'ogg','audio/mpeg':'mp3','audio/wav':'wav'};
const templates:Record<string,string[]>={import:['فاتورة تجارية','بيان جمركي','شهادة منشأ','قائمة تعبئة'],transit:['بيان ترانزيت','CMR','فاتورة تجارية'],transfer:['بيان مناقلة','CMR'],custom:[]};
const uuid=(v:any)=>{if(typeof v!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(v))throw Error('Invalid ID');return v;};
const str=(v:any,max=2000,required=false)=>{if(typeof v!=='string'||v.length>max||(required&&!v.trim()))throw Error('Invalid text');return v.trim();};
const checked=async(q:any)=>{const r=await q;if(r.error)throw Error(r.error.message);return r.data;};
async function all(table:string,configure:(q:any)=>any){let rows:any[]=[];for(let start=0;;start+=500){const batch=await checked(configure(db.from(table).select('*')).order('id').range(start,start+499));rows.push(...batch);if(batch.length<500)return rows;}}
Deno.serve(async req=>{
 const headers={'Content-Type':'application/json','Access-Control-Allow-Origin':ORIGIN,'Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'POST,OPTIONS','Vary':'Origin','Cache-Control':'no-store'};
 const reply=(v:any,status=200)=>new Response(JSON.stringify(v),{status,headers});
 if(req.headers.get('origin')&&req.headers.get('origin')!==ORIGIN)return reply({error:'Origin denied'},403);
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers});
 if(req.method!=='POST')return reply({error:'POST required'},405);
 let action='',actor='';
 try{
 if(!req.headers.get('content-type')?.includes('application/json'))return reply({error:'JSON required'},415);
 const reader=req.body?.getReader();if(!reader)return reply({error:'Empty request'},400);let size=0;const chunks:Uint8Array[]=[];while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>400000){await reader.cancel();return reply({error:'Request too large'},413);}chunks.push(value);}const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length;}const b=JSON.parse(new TextDecoder().decode(bytes));action=b.action;
 const token=req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');if(!token)return reply({error:'Sign in required'},401);
 const {data:{user},error}=await db.auth.getUser(token);if(error||!user)return reply({error:'Sign in required'},401);actor=user.id;
 const allowed=await checked(db.rpc('fleet_rate_limit',{p_actor:actor}));if(!allowed)return reply({error:'Too many requests'},429);
 const member=await checked(db.from('fleet_memberships').select('*').eq('user_id',actor).maybeSingle());
 const driver=member?null:await checked(db.from('fleet_drivers').select('*').eq('user_id',actor).maybeSingle());
 const account=member||driver;if(!account?.active)return reply({error:'Access denied'},403);
 const root=member?.role==='super_admin',isDriver=!member;
 const company=account.company_id?await checked(db.from('fleet_companies').select('*').eq('id',account.company_id).maybeSingle()):null;
 if(!root&&!company?.active)return reply({error:'Company inactive'},403);
 const deny=()=>reply({error:'Access denied'},403);
 const scope=(q:any)=>root?q:isDriver?q.eq('company_id',account.company_id).eq('driver_user_id',actor).eq('closed',false):member.role==='company_admin'?q.eq('company_id',account.company_id):q.eq('company_id',account.company_id).eq('assigned_member_id',actor);
 const canRead=(trip:any)=>trip&&(root||(trip.company_id===account.company_id&&(isDriver?trip.driver_user_id===actor&&!trip.closed:member.role==='company_admin'||trip.assigned_member_id===actor)));
 if(action==='branding')return reply({company:company?{id:company.id,name:company.name,contact_name:company.contact_name,contact_phone:company.contact_phone,logo_data:company.logo_data}:null});
 if(action==='saveBranding'){
  if(!root)return deny();const cid=uuid(b.company_id),logo=str(b.logo_data||'',360000);
  if(logo){if(!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(logo))throw Error('Invalid logo');const raw=atob(logo.split(',')[1]);if(!(raw.startsWith('\x89PNG')||raw.startsWith('\xff\xd8\xff')||(raw.startsWith('RIFF')&&raw.slice(8,12)==='WEBP')))throw Error('Invalid logo');}
  await checked(db.from('fleet_companies').update({contact_name:str(b.contact_name||'',100),contact_phone:str(b.contact_phone||'',40),logo_data:logo}).eq('id',cid));return reply({ok:true});
 }
 if(action==='overview'){
  const trips=await all('fleet_trips',scope);const ids=new Set(trips.map(t=>t.id));
  const groups=await all('fleet_groups',q=>root?q:q.eq('company_id',account.company_id));
  const issues:any[]=[];const missing:Record<string,number>={};
  for(let i=0;i<trips.length;i+=100){const batch=trips.slice(i,i+100).map(t=>t.id);if(!batch.length)continue;
   issues.push(...await all('fleet_issues',q=>q.in('trip_id',batch).eq('status','open')));
   const docs=await all('fleet_requirements',q=>q.in('trip_id',batch).is('file_id',null));for(const d of docs)missing[d.trip_id]=(missing[d.trip_id]||0)+1;
  }
  return reply({groups:groups.filter(g=>root||trips.some(t=>t.group_id===g.id)).map(g=>({...g,trips:trips.filter(t=>t.group_id===g.id).map(t=>({id:t.id,plate:t.plate,status:t.status,closed:t.closed}))})),issues:issues.filter(i=>ids.has(i.trip_id)),missing});
 }
 if(action==='createGroup'){
  if(!root)return deny();const group=await checked(db.from('fleet_groups').insert({company_id:uuid(b.company_id),name:str(b.name,120,true)}).select().single());return reply({group});
 }
 const trip=await checked(db.from('fleet_trips').select('*').eq('id',uuid(b.trip_id)).maybeSingle());if(!canRead(trip))return deny();
 if(action==='details'){
  const [docs,events,issues,files]=await Promise.all([
   checked(db.from('fleet_requirements').select('*').eq('trip_id',trip.id).order('title')),
   checked(db.from('fleet_trip_events').select('*').eq('trip_id',trip.id).order('id',{ascending:false}).limit(100)),
   checked(db.from('fleet_issues').select('*').eq('trip_id',trip.id).order('created_at',{ascending:false}).limit(100)),
   checked(db.from('fleet_trip_files').select('id,filename').eq('trip_id',trip.id).order('created_at',{ascending:false}))]);
  const peers=!isDriver?await checked(db.from('fleet_memberships').select('user_id,username,role').eq('company_id',trip.company_id).eq('active',true).in('role',['company_admin','company_staff']).order('username')):[];
  const groups=root?await checked(db.from('fleet_groups').select('id,name').eq('company_id',trip.company_id).order('name')):[];
  const drivers=root?await checked(db.from('fleet_drivers').select('user_id,username').eq('company_id',trip.company_id).eq('active',true).order('username')):[];
  const group=trip.group_id?await checked(db.from('fleet_groups').select('name').eq('id',trip.group_id).maybeSingle()):null;
  return reply({trip,docs,events,issues,files,peers,groups,drivers,group,role:root?'root':isDriver?'driver':'office'});
 }
 if(action==='messages'){
  let q=db.from('fleet_messages').select('*').eq('trip_id',trip.id).order('id',{ascending:false}).limit(51);
  if(b.before!=null){if(!/^\d{1,16}$/.test(String(b.before)))throw Error('Invalid cursor');q=q.lt('id',b.before);}
  const rows=await checked(q);return reply({messages:rows.slice(0,50),more:rows.length>50});
 }
 if(action==='prepareMedia'){
  if(trip.closed)throw Error('Trip closed');const mime=str(b.mime,80).split(';')[0],ext=mimeExt[mime];if(!ext||!Number.isInteger(b.size)||b.size<1||b.size>10485760)throw Error('Use an image or audio file up to 10 MB');
  const id=crypto.randomUUID(),path=trip.id+'/'+id+'.'+ext;
  await checked(db.from('fleet_media').insert({id,trip_id:trip.id,actor,path,mime,size_bytes:b.size}));
  const data=await checked(db.storage.from('fleet-conversations').createSignedUploadUrl(path));return reply({id,path,token:data.token,mime});
 }
 if(action==='send'){
  if(trip.closed)throw Error('Trip closed');const body=str(b.body||'',2000),category=b.category||null;
  if(category&&!['breakdown','border','documents','loading','other'].includes(category))throw Error('Invalid category');if(category&&!body)throw Error('Describe the problem');
  const mediaId=b.media_id?uuid(b.media_id):null;
  if(mediaId){const file=await checked(db.from('fleet_media').select('*').eq('id',mediaId).eq('trip_id',trip.id).eq('actor',actor).maybeSingle());if(!file)throw Error('Media unavailable');const objects=await checked(db.storage.from('fleet-conversations').list(trip.id,{search:file.path.split('/')[1],limit:5}));const found=objects.find((o:any)=>o.name===file.path.split('/')[1]);if(!found||Number(found.metadata?.size)!==file.size_bytes||found.metadata?.mimetype?.split(';')[0]!==file.mime)throw Error('Upload incomplete');}
  const id=await checked(db.rpc('fleet_post_message',{p_actor:actor,p_name:account.username,p_trip:trip.id,p_body:body,p_media:mediaId,p_category:category}));return reply({ok:true,id});
 }
 if(action==='mediaUrl'){
  const file=await checked(db.from('fleet_media').select('*').eq('id',uuid(b.media_id)).eq('trip_id',trip.id).maybeSingle());if(!file)return deny();const message=await checked(db.from('fleet_messages').select('id').eq('media_id',file.id).eq('trip_id',trip.id).maybeSingle());if(!message)return deny();const data=await checked(db.storage.from('fleet-conversations').createSignedUrl(file.path,120));return reply({url:data.signedUrl,mime:file.mime});
 }
 if(action==='handoff'||action==='vehicle'||action==='group'){
  if(isDriver||(!root&&action!=='handoff'))return deny();
  await checked(db.rpc('fleet_operate_trip',{p_actor:actor,p_trip:trip.id,p_action:action,p_data:b.data||{}}));return reply({ok:true});
 }
 if(action==='resolveIssue'){
  if(isDriver)return deny();await checked(db.from('fleet_issues').update({status:'resolved',resolution:str(b.resolution,2000,true),resolved_at:new Date().toISOString()}).eq('id',uuid(b.issue_id)).eq('trip_id',trip.id));return reply({ok:true});
 }
 if(action==='requirements'){
  if(!root)return deny();const type=str(b.type,20);if(!Object.hasOwn(templates,type))throw Error('Invalid shipment type');const titles=[...templates[type],...(b.title?[str(b.title,120,true)]:[])];
  if(titles.length)await checked(db.from('fleet_requirements').upsert(titles.map(title=>({trip_id:trip.id,title})),{onConflict:'trip_id,title',ignoreDuplicates:true}));
  await checked(db.from('fleet_trips').update({shipment_type:type}).eq('id',trip.id));return reply({ok:true});
 }
 if(action==='linkDocument'){
  if(!root)return deny();const fileId=b.file_id?uuid(b.file_id):null;
  if(fileId&&!await checked(db.from('fleet_trip_files').select('id').eq('id',fileId).eq('trip_id',trip.id).maybeSingle()))return deny();
  await checked(db.from('fleet_requirements').update({file_id:fileId}).eq('id',uuid(b.requirement_id)).eq('trip_id',trip.id));return reply({ok:true});
 }
 return reply({error:'Unknown action'},400);
 }catch(e){return reply({error:e instanceof Error?e.message:'Request failed'},400);}
});
