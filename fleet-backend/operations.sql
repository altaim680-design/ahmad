begin;
alter table public.fleet_companies add column contact_name text not null default '' check(length(contact_name)<=100),add column contact_phone text not null default '' check(length(contact_phone)<=40),add column logo_data text not null default '' check(length(logo_data)<=360000);
create table public.fleet_groups(id uuid primary key default gen_random_uuid(),company_id uuid not null references public.fleet_companies(id) on delete cascade,name text not null check(length(name) between 1 and 120),created_at timestamptz not null default now(),unique(id,company_id),unique(company_id,name));
alter table public.fleet_trips add column group_id uuid,add column shipment_type text not null default 'custom';
alter table public.fleet_trips add constraint fleet_trip_group_fk foreign key(group_id,company_id) references public.fleet_groups(id,company_id);
create index fleet_trip_group_idx on public.fleet_trips(group_id);
create table public.fleet_trip_events(id bigint generated always as identity primary key,trip_id uuid not null references public.fleet_trips(id) on delete cascade,kind text not null,actor uuid not null,actor_name text not null,details jsonb not null default '{}',created_at timestamptz not null default now());
create table public.fleet_requirements(id uuid primary key default gen_random_uuid(),trip_id uuid not null references public.fleet_trips(id) on delete cascade,title text not null check(length(title) between 1 and 120),file_id uuid references public.fleet_trip_files(id) on delete set null,unique(trip_id,title));
create table public.fleet_media(id uuid primary key default gen_random_uuid(),trip_id uuid not null references public.fleet_trips(id) on delete cascade,actor uuid not null,path text not null unique,mime text not null,size_bytes bigint not null check(size_bytes between 1 and 10485760),created_at timestamptz not null default now(),unique(id,trip_id));
create table public.fleet_issues(id uuid primary key default gen_random_uuid(),trip_id uuid not null references public.fleet_trips(id) on delete cascade,category text not null check(category in('breakdown','border','documents','loading','other')),description text not null check(length(description) between 1 and 2000),actor_name text not null,status text not null default 'open' check(status in('open','resolved')),resolution text not null default '',created_at timestamptz not null default now(),resolved_at timestamptz,unique(id,trip_id));
create table public.fleet_messages(id bigint generated always as identity primary key,trip_id uuid not null references public.fleet_trips(id) on delete cascade,actor uuid not null,actor_name text not null,body text not null default '' check(length(body)<=2000),media_id uuid,issue_id uuid,created_at timestamptz not null default now(),foreign key(media_id,trip_id) references public.fleet_media(id,trip_id),foreign key(issue_id,trip_id) references public.fleet_issues(id,trip_id),unique(media_id));
create index fleet_messages_trip_idx on public.fleet_messages(trip_id,id desc);
create index fleet_events_trip_idx on public.fleet_trip_events(trip_id,id desc);
create index fleet_issues_trip_idx on public.fleet_issues(trip_id,status);
create index fleet_media_trip_idx on public.fleet_media(trip_id);
alter table public.fleet_groups enable row level security;
alter table public.fleet_trip_events enable row level security;
alter table public.fleet_requirements enable row level security;
alter table public.fleet_media enable row level security;
alter table public.fleet_issues enable row level security;
alter table public.fleet_messages enable row level security;
revoke all on public.fleet_groups,public.fleet_trip_events,public.fleet_requirements,public.fleet_media,public.fleet_issues,public.fleet_messages from public,anon,authenticated;
grant all on public.fleet_groups,public.fleet_trip_events,public.fleet_requirements,public.fleet_media,public.fleet_issues,public.fleet_messages to service_role;
grant usage,select on sequence public.fleet_messages_id_seq,public.fleet_trip_events_id_seq to service_role;
grant select on public.fleet_groups,public.fleet_trip_events,public.fleet_requirements,public.fleet_issues,public.fleet_messages to authenticated;
create policy groups_read on public.fleet_groups for select to authenticated using(fleet_private.is_root() or exists(select 1 from public.fleet_trips t where t.group_id=fleet_groups.id and fleet_private.can_trip(t.id)));
create policy events_read on public.fleet_trip_events for select to authenticated using(fleet_private.can_trip(trip_id));
create policy requirements_read on public.fleet_requirements for select to authenticated using(fleet_private.can_trip(trip_id));
create policy issues_read on public.fleet_issues for select to authenticated using(fleet_private.can_trip(trip_id));
create policy messages_read on public.fleet_messages for select to authenticated using(fleet_private.can_trip(trip_id));
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('fleet-conversations','fleet-conversations',false,10485760,array['image/jpeg','image/png','image/webp','audio/webm','audio/mp4','audio/ogg','audio/mpeg','audio/wav']);
create or replace view public.fleet_trip_status with(security_invoker=true) as select t.id,t.company_id,t.plate,t.driver,t.phone,t.destination,t.declaration_no,t.status,t.closed,t.created_at,u.place,u.latitude,u.longitude,u.accuracy,u.note,u.source,u.created_at as last_update,t.barcode,t.assigned_member_id,t.group_id,t.shipment_type from public.fleet_trips t left join lateral(select x.* from public.fleet_updates x where x.trip_id=t.id order by x.created_at desc limit 1)u on true;
-- One transaction locks the trip, checks the current assignment and records the change.
create function public.fleet_operate_trip(p_actor uuid,p_trip uuid,p_action text,p_data jsonb) returns void language plpgsql security invoker set search_path='' as $$
declare t public.fleet_trips; m public.fleet_memberships; target public.fleet_memberships; d public.fleet_drivers; gid uuid; did uuid; details jsonb;
begin
 select * into t from public.fleet_trips where id=p_trip for update;if not found then raise exception 'Trip unavailable';end if;
 select * into m from public.fleet_memberships where user_id=p_actor and active;if not found then raise exception 'Access denied';end if;
 if m.role<>'super_admin' and not(m.company_id=t.company_id and exists(select 1 from public.fleet_companies c where c.id=t.company_id and c.active) and (m.role='company_admin' or t.assigned_member_id=p_actor)) then raise exception 'Access denied';end if;
 if p_action='handoff' then
  if t.closed then raise exception 'Trip closed';end if;
  if nullif(btrim(p_data->>'note'),'') is null or length(p_data->>'note')>2000 then raise exception 'Summary required';end if;
  if coalesce(t.assigned_member_id::text,'') is distinct from coalesce(p_data->>'expected_member','') then raise exception 'Assignment changed; reload';end if;
  select * into target from public.fleet_memberships where user_id=(p_data->>'member_id')::uuid and company_id=t.company_id and active and role in('company_staff','company_admin');
  if not found or target.user_id=t.assigned_member_id then raise exception 'Select another active colleague';end if;
  details=jsonb_build_object('previous_member',t.assigned_member_id,'next_member',target.user_id,'next_name',target.username,'note',p_data->>'note');
  update public.fleet_trips set assigned_member_id=target.user_id where id=t.id;
 elsif p_action='vehicle' then
  if m.role<>'super_admin' or t.closed then raise exception 'Administrator only';end if;
  if length(coalesce(p_data->>'plate','')) not between 1 and 60 or length(coalesce(p_data->>'place','')) not between 1 and 200 or length(coalesce(p_data->>'driver',''))>100 or length(coalesce(p_data->>'phone',''))>40 or length(coalesce(p_data->>'note',''))>2000 then raise exception 'Invalid transfer';end if;
  did=nullif(p_data->>'driver_id','')::uuid;
  if did is not null then select * into d from public.fleet_drivers where user_id=did and company_id=t.company_id and active;if not found then raise exception 'Driver unavailable';end if;end if;
  details=jsonb_build_object('old_plate',t.plate,'old_driver',t.driver,'old_driver_id',t.driver_user_id,'new_plate',p_data->>'plate','new_driver',p_data->>'driver','new_driver_id',did,'place',p_data->>'place','note',p_data->>'note');
  update public.fleet_trips set plate=p_data->>'plate',driver=coalesce(p_data->>'driver',''),phone=coalesce(p_data->>'phone',''),driver_user_id=did where id=t.id;
 elsif p_action='group' then
  if m.role<>'super_admin' then raise exception 'Administrator only';end if;
  gid=nullif(p_data->>'group_id','')::uuid;
  if gid is not null and not exists(select 1 from public.fleet_groups where id=gid and company_id=t.company_id) then raise exception 'Group unavailable';end if;
  details=jsonb_build_object('old_group',t.group_id,'new_group',gid);update public.fleet_trips set group_id=gid where id=t.id;
 else raise exception 'Unknown operation';end if;
 insert into public.fleet_trip_events(trip_id,kind,actor,actor_name,details) values(t.id,p_action,p_actor,m.username,details);
end $$;
revoke all on function public.fleet_operate_trip(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.fleet_operate_trip(uuid,uuid,text,jsonb) to service_role;
create function public.fleet_post_message(p_actor uuid,p_name text,p_trip uuid,p_body text,p_media uuid,p_category text) returns bigint language plpgsql security invoker set search_path='' as $$
declare mid bigint; iid uuid; a public.fleet_media; t public.fleet_trips; m public.fleet_memberships; d public.fleet_drivers; sender text;
begin
 select * into t from public.fleet_trips where id=p_trip for update;
 if not found or t.closed then raise exception 'Trip unavailable';end if;
 select * into m from public.fleet_memberships where user_id=p_actor and active;
 if found then
  if m.role<>'super_admin' and not(m.company_id=t.company_id and exists(select 1 from public.fleet_companies c where c.id=t.company_id and c.active) and (m.role='company_admin' or t.assigned_member_id=p_actor)) then raise exception 'Access denied';end if;
  sender=m.username;
 else
  select * into d from public.fleet_drivers where user_id=p_actor and active and company_id=t.company_id;
  if not found or t.driver_user_id is distinct from p_actor or not exists(select 1 from public.fleet_companies where id=t.company_id and active) then raise exception 'Access denied';end if;
  sender=d.username;
 end if;
 if length(coalesce(p_body,''))>2000 or (nullif(btrim(p_body),'') is null and p_media is null) then raise exception 'Message required';end if;
 if p_media is not null then select * into a from public.fleet_media where id=p_media for update;if not found or a.trip_id<>p_trip or a.actor<>p_actor or exists(select 1 from public.fleet_messages where media_id=p_media) then raise exception 'Media unavailable';end if;end if;
 if p_category is not null then insert into public.fleet_issues(trip_id,category,description,actor_name) values(p_trip,p_category,p_body,sender) returning id into iid;end if;
 insert into public.fleet_messages(trip_id,actor,actor_name,body,media_id,issue_id) values(p_trip,p_actor,sender,coalesce(p_body,''),p_media,iid) returning id into mid;return mid;
end $$;
revoke all on function public.fleet_post_message(uuid,text,uuid,text,uuid,text) from public,anon,authenticated;
grant execute on function public.fleet_post_message(uuid,text,uuid,text,uuid,text) to service_role;
commit;
