create table public.fleet_drivers (
 user_id uuid primary key references auth.users(id) on delete cascade,
 company_id uuid not null references public.fleet_companies(id) on delete cascade,
 username text not null unique,
 active boolean not null default true,
 unique(user_id,company_id)
);
create index fleet_drivers_company_idx on public.fleet_drivers(company_id);
alter table public.fleet_drivers enable row level security;
revoke all on public.fleet_drivers from public,anon,authenticated;
grant all on public.fleet_drivers to service_role;
alter table public.fleet_trips add column driver_user_id uuid;
alter table public.fleet_trips add constraint fleet_trip_driver_company_fk foreign key(driver_user_id,company_id) references public.fleet_drivers(user_id,company_id);
create index fleet_trips_driver_idx on public.fleet_trips(driver_user_id,company_id);
