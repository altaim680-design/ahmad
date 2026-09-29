create table public.fleet_request_limits(actor uuid primary key,window_start timestamptz not null,requests integer not null check(requests>0));
create table public.fleet_security_audit(id bigint generated always as identity primary key,actor uuid not null,action text not null,result_status integer not null,trip_id uuid,company_id uuid,created_at timestamptz not null default now());
create index fleet_security_audit_time_idx on public.fleet_security_audit(created_at desc);
alter table public.fleet_request_limits enable row level security;
alter table public.fleet_security_audit enable row level security;
revoke all on public.fleet_request_limits,public.fleet_security_audit from public,anon,authenticated;
grant select,insert,update,delete on public.fleet_request_limits to service_role;
grant select,insert on public.fleet_security_audit to service_role;
grant usage,select on sequence public.fleet_security_audit_id_seq to service_role;
create function public.fleet_rate_limit(p_actor uuid) returns boolean language plpgsql security invoker set search_path='' as $$
declare n integer; w timestamptz := date_trunc('minute',clock_timestamp());
begin
 insert into public.fleet_request_limits(actor,window_start,requests) values(p_actor,w,1)
 on conflict(actor) do update set window_start=excluded.window_start,requests=case when fleet_request_limits.window_start=excluded.window_start then least(fleet_request_limits.requests+1,121) else 1 end
 returning requests into n;
 return n<=120;
end $$;
revoke all on function public.fleet_rate_limit(uuid) from public,anon,authenticated;
grant execute on function public.fleet_rate_limit(uuid) to service_role;
