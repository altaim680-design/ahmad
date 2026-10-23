begin;
create table public.fleet_trip_file_cleanup (
 id uuid primary key default gen_random_uuid(),
 trip_id uuid not null,
 bucket text not null check(bucket in ('fleet-trip-files','fleet-conversations','fleet-pod')),
 path text not null,
 created_at timestamptz not null default now(),
 unique(bucket,path)
);
create index fleet_trip_file_cleanup_trip on public.fleet_trip_file_cleanup(trip_id);
alter table public.fleet_trip_file_cleanup enable row level security;
revoke all on public.fleet_trip_file_cleanup from public,anon,authenticated;
grant all on public.fleet_trip_file_cleanup to service_role;
create function public.fleet_delete_trip(p_actor uuid,p_trip uuid,p_plate text)
returns integer language plpgsql security invoker set search_path='' as $$
declare t public.fleet_trips; pending integer;
begin
 perform 1 from public.fleet_memberships where user_id=p_actor and role='super_admin' and active for share;
 if not found then raise exception 'للمدير العام الفعّال فقط';end if;
 select * into t from public.fleet_trips where id=p_trip for update;
 if not found then raise exception 'الرحلة غير موجودة';end if;
 if p_plate is distinct from t.plate then raise exception 'اكتب رقم السيارة كما يظهر لتأكيد الحذف';end if;
 -- Record durable cleanup jobs before cascades remove the file metadata.
 -- Storage bytes are removed by the Storage API, never by SQL.
 insert into public.fleet_trip_file_cleanup(trip_id,bucket,path)
 select p_trip,objects.bucket_id,objects.name from storage.objects
 where (objects.bucket_id in ('fleet-trip-files','fleet-conversations') and objects.name like p_trip::text||'/%')
 or (objects.bucket_id='fleet-pod' and objects.name like t.company_id::text||'/'||p_trip::text||'/%')
 on conflict(bucket,path) do nothing;
 insert into public.fleet_trip_file_cleanup(trip_id,bucket,path)
 select p_trip,'fleet-trip-files',storage_path from public.fleet_trip_files where trip_id=p_trip and storage_path like p_trip::text||'/%'
 union select p_trip,'fleet-conversations',path from public.fleet_media where trip_id=p_trip and path like p_trip::text||'/%'
 union select p_trip,'fleet-pod',signature_path from public.fleet_proof_of_delivery where trip_id=p_trip and signature_path like t.company_id::text||'/'||p_trip::text||'/%'
 union select p_trip,'fleet-pod',photo_path from public.fleet_proof_of_delivery where trip_id=p_trip and photo_path like t.company_id::text||'/'||p_trip::text||'/%'
 on conflict(bucket,path) do nothing;
 delete from public.fleet_archive_entries where source_trip_id=p_trip;
 delete from public.fleet_trips where id=p_trip;
 insert into public.fleet_security_audit(actor,action,result_status,trip_id,company_id) values(p_actor,'deleteTrip',200,p_trip,t.company_id);
 select count(*)::integer into pending from public.fleet_trip_file_cleanup where trip_id=p_trip;
 return pending;
end $$;
revoke all on function public.fleet_delete_trip(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.fleet_delete_trip(uuid,uuid,text) to service_role;
commit;
