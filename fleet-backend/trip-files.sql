begin;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('fleet-trip-files','fleet-trip-files',false,10485760,array['application/pdf']);
create table public.fleet_trip_files(
 id uuid primary key,
 trip_id uuid not null,
 company_id uuid not null,
 filename text not null check(length(filename) between 1 and 200),
 size_bytes bigint not null check(size_bytes between 5 and 10485760),
 storage_path text not null unique,
 created_by uuid not null default auth.uid(),
 created_at timestamptz not null default now(),
 foreign key(trip_id,company_id) references public.fleet_trips(id,company_id) on delete cascade,
 check(storage_path=trip_id::text||'/'||id::text||'.pdf')
);
create index fleet_trip_files_trip_idx on public.fleet_trip_files(trip_id,created_at);
alter table public.fleet_trip_files enable row level security;
revoke all on public.fleet_trip_files from public,anon,authenticated;
grant select,insert,delete on public.fleet_trip_files to authenticated;
grant all on public.fleet_trip_files to service_role;
create policy trip_files_read on public.fleet_trip_files for select to authenticated using(fleet_private.can_company(company_id));
create policy trip_files_insert on public.fleet_trip_files for insert to authenticated with check(fleet_private.is_root() and created_by=auth.uid());
create policy trip_files_delete on public.fleet_trip_files for delete to authenticated using(fleet_private.is_root());
create policy trip_pdf_read on storage.objects for select to authenticated using(bucket_id='fleet-trip-files' and (
 exists(select 1 from public.fleet_trip_files f where f.storage_path=name and fleet_private.can_company(f.company_id))
 or (fleet_private.is_root() and exists(select 1 from public.fleet_trips t where t.id::text=split_part(name,'/',1)))
));
create policy trip_pdf_insert on storage.objects for insert to authenticated with check(bucket_id='fleet-trip-files' and fleet_private.is_root() and name ~ '^[a-f0-9-]{36}/[a-f0-9-]{36}[.]pdf$' and exists(select 1 from public.fleet_trips t where t.id::text=split_part(name,'/',1)));
create policy trip_pdf_delete on storage.objects for delete to authenticated using(bucket_id='fleet-trip-files' and fleet_private.is_root());
commit;
