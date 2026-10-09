begin;
create sequence public.fleet_trip_barcode_seq minvalue 1 maxvalue 9999999999 no cycle;
revoke all on sequence public.fleet_trip_barcode_seq from public,anon,authenticated;
grant usage on sequence public.fleet_trip_barcode_seq to service_role;
alter table public.fleet_trips add column barcode text not null default ('KW'||lpad(nextval('public.fleet_trip_barcode_seq')::text,10,'0'));
alter table public.fleet_trips add constraint fleet_trips_barcode_key unique(barcode),add constraint fleet_trips_barcode_format check(barcode ~ '^KW[0-9]{10}$');
create or replace view public.fleet_trip_status with (security_invoker=true) as
 select t.id,t.company_id,t.plate,t.driver,t.phone,t.destination,t.declaration_no,t.status,t.closed,t.created_at,
 u.place,u.latitude,u.longitude,u.accuracy,u.note,u.source,u.created_at as last_update,t.barcode
 from public.fleet_trips t left join lateral
 (select x.* from public.fleet_updates x where x.trip_id=t.id order by x.created_at desc limit 1) u on true;
commit;
