begin;
alter table public.fleet_memberships drop constraint fleet_memberships_check,drop constraint fleet_memberships_role_check;
alter table public.fleet_memberships add constraint fleet_memberships_role_check check(role in('super_admin','company_admin','company_staff')),add constraint fleet_memberships_check check((role='super_admin' and company_id is null) or (role in('company_admin','company_staff') and company_id is not null)),add constraint fleet_memberships_user_company_key unique(user_id,company_id);
alter table public.fleet_trips add column assigned_member_id uuid;
alter table public.fleet_trips add constraint fleet_trip_responsible_fk foreign key(assigned_member_id,company_id) references public.fleet_memberships(user_id,company_id);
create index fleet_trip_assigned_idx on public.fleet_trips(assigned_member_id);
create function fleet_private.can_trip(tid uuid) returns boolean language sql stable security definer set search_path='' as $$
 select auth.uid() is not null and (fleet_private.is_root() or exists(
 select 1 from public.fleet_trips t join public.fleet_memberships m on m.company_id=t.company_id join public.fleet_companies c on c.id=t.company_id
 where t.id=tid and m.user_id=auth.uid() and m.active and c.active and (m.role='company_admin' or (m.role='company_staff' and t.assigned_member_id=m.user_id))));
$$;
revoke all on function fleet_private.can_trip(uuid) from public,anon;
grant execute on function fleet_private.can_trip(uuid) to authenticated,service_role;
alter policy trips_read on public.fleet_trips using(fleet_private.can_trip(id));
alter policy updates_read on public.fleet_updates using(fleet_private.can_trip(trip_id));
alter policy trip_files_read on public.fleet_trip_files using(fleet_private.can_trip(trip_id));
alter policy trip_pdf_read on storage.objects using(bucket_id='fleet-trip-files' and (
 exists(select 1 from public.fleet_trip_files f where f.storage_path=name and fleet_private.can_trip(f.trip_id))
 or (fleet_private.is_root() and exists(select 1 from public.fleet_trips t where t.id::text=split_part(name,'/',1)))
));
create or replace view public.fleet_trip_status with (security_invoker=true) as
 select t.id,t.company_id,t.plate,t.driver,t.phone,t.destination,t.declaration_no,t.status,t.closed,t.created_at,
 u.place,u.latitude,u.longitude,u.accuracy,u.note,u.source,u.created_at as last_update,t.barcode,t.assigned_member_id
 from public.fleet_trips t left join lateral (select x.* from public.fleet_updates x where x.trip_id=t.id order by x.created_at desc limit 1) u on true;
commit;
