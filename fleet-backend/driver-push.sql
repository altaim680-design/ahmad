begin;
create table public.fleet_push_config(id boolean primary key default true check(id),public_key text not null,private_key text not null,cron_secret text not null);
create table public.fleet_push_subscriptions(endpoint text primary key,driver_user_id uuid not null references public.fleet_drivers(user_id) on delete cascade,subscription jsonb not null,language text not null default 'ar',updated_at timestamptz not null default now());
create index fleet_push_driver_idx on public.fleet_push_subscriptions(driver_user_id);
alter table public.fleet_trips add column reminder_minutes integer not null default 0 check(reminder_minutes in(0,30,60,120)),add column reminder_last_sent timestamptz;
alter table public.fleet_push_config enable row level security;
alter table public.fleet_push_subscriptions enable row level security;
revoke all on public.fleet_push_config,public.fleet_push_subscriptions from public,anon,authenticated;
grant all on public.fleet_push_config,public.fleet_push_subscriptions to service_role;
create function public.fleet_claim_reminder(p_trip uuid,p_gap integer) returns boolean language plpgsql security invoker set search_path='' as $$
begin
 update public.fleet_trips set reminder_last_sent=now() where id=p_trip and not closed and (reminder_last_sent is null or reminder_last_sent<now()-make_interval(secs=>greatest(p_gap,300)));
 return found;
end $$;
revoke all on function public.fleet_claim_reminder(uuid,integer) from public,anon,authenticated;
grant execute on function public.fleet_claim_reminder(uuid,integer) to service_role;
create function public.fleet_due_reminders() returns setof public.fleet_trips language sql security invoker set search_path='' as $$
 select t.* from public.fleet_trips t join public.fleet_companies c on c.id=t.company_id join public.fleet_drivers d on d.user_id=t.driver_user_id
 where t.reminder_minutes>0 and not t.closed and c.active and d.active
 and extract(hour from now() at time zone 'Asia/Damascus') between 8 and 19
 and coalesce((select max(u.created_at) from public.fleet_updates u where u.trip_id=t.id and u.source='driver'),t.created_at)<now()-make_interval(mins=>t.reminder_minutes)
 and (t.reminder_last_sent is null or t.reminder_last_sent<now()-make_interval(mins=>t.reminder_minutes))
 order by t.reminder_last_sent nulls first,t.created_at limit 25;
$$;
revoke all on function public.fleet_due_reminders() from public,anon,authenticated;
grant execute on function public.fleet_due_reminders() to service_role;
commit;

-- After installing fleet-push and provisioning private VAPID keys plus a random
-- cron_secret in fleet_push_config, enable the recurring check (all trips default OFF).
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
select cron.schedule('fleet-driver-location-reminders','*/15 * * * *',$job$
 select net.http_post(url:='https://ymkzrzdmdrqllpvqdlfx.supabase.co/functions/v1/fleet-push',headers:=jsonb_build_object('Content-Type','application/json','x-cron-secret',(select cron_secret from public.fleet_push_config where id)),body:='{"action":"cron"}'::jsonb,timeout_milliseconds:=60000);
$job$);
