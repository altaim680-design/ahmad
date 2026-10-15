begin;
create extension if not exists pg_net with schema extensions;

create table public.fleet_notifications(
 id bigint generated always as identity primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 trip_id uuid not null references public.fleet_trips(id) on delete cascade,
 message_id bigint not null references public.fleet_messages(id) on delete cascade,
 kind text not null check(kind in('message','issue')),
 title text not null check(length(title)<=180),
 body text not null default '' check(length(body)<=500),
 url text not null check(length(url)<=500),
 read_at timestamptz,
 push_sent_at timestamptz,
 created_at timestamptz not null default now(),
 unique(user_id,message_id)
);
create index fleet_notifications_user_idx on public.fleet_notifications(user_id,id desc);
create index fleet_notifications_unread_idx on public.fleet_notifications(user_id,read_at,id desc);
create index fleet_notifications_trip_idx on public.fleet_notifications(trip_id);
create index fleet_notifications_message_idx on public.fleet_notifications(message_id);

create table public.fleet_user_push_subscriptions(
 endpoint text primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 subscription jsonb not null,
 language text not null default 'ar' check(language in('ar','en','tr')),
 updated_at timestamptz not null default now()
);
create index fleet_user_push_user_idx on public.fleet_user_push_subscriptions(user_id);

alter table public.fleet_notifications enable row level security;
alter table public.fleet_user_push_subscriptions enable row level security;
revoke all on public.fleet_notifications,public.fleet_user_push_subscriptions from public,anon,authenticated;
grant all on public.fleet_notifications,public.fleet_user_push_subscriptions to service_role;
grant usage,select on sequence public.fleet_notifications_id_seq to service_role;

create or replace function fleet_private.create_message_notifications() returns trigger
language plpgsql security invoker set search_path='' as $$
declare t public.fleet_trips; v_title text; v_body text; v_section text;
begin
 select * into t from public.fleet_trips where id=new.trip_id;
 if not found then return new;end if;
 v_section:=case when new.issue_id is null then 'chat' else 'issues' end;
 v_title:=case when new.issue_id is null then 'رسالة جديدة • ' else 'بلاغ مشكلة • ' end||t.plate;
 v_body:=left(new.actor_name||': '||case when nullif(btrim(new.body),'') is not null then new.body when new.media_id is not null then 'مرفق جديد' else 'تحديث جديد' end,500);
 with recipient_ids as(
  select m.user_id from public.fleet_memberships m
  where m.active and (m.role='super_admin' or (m.company_id=t.company_id and (m.role='company_admin' or m.user_id=t.assigned_member_id)))
  union
  select d.user_id from public.fleet_drivers d where d.active and d.user_id=t.driver_user_id and d.company_id=t.company_id
 )
 insert into public.fleet_notifications(user_id,trip_id,message_id,kind,title,body,url,created_at)
 select r.user_id,t.id,new.id,case when new.issue_id is null then 'message' else 'issue' end,v_title,v_body,
  case when r.user_id=t.driver_user_id then '/driver.html?notifyTrip='||t.id::text||'&notifySection='||v_section else '/?notifyTrip='||t.id::text||'&notifySection='||v_section end,
  new.created_at
 from recipient_ids r where r.user_id<>new.actor
 on conflict(user_id,message_id) do nothing;
 return new;
end $$;
revoke all on function fleet_private.create_message_notifications() from public,anon,authenticated;

drop trigger if exists fleet_message_notifications on public.fleet_messages;
create trigger fleet_message_notifications after insert on public.fleet_messages for each row execute function fleet_private.create_message_notifications();

create or replace function fleet_private.queue_notification_push() returns trigger
language plpgsql security invoker set search_path='' as $$
declare secret text;
begin
 select cron_secret into secret from public.fleet_push_config where id=true;
 if secret is not null then
  perform net.http_post(
   url:='https://ymkzrzdmdrqllpvqdlfx.supabase.co/functions/v1/fleet-push',
   headers:=jsonb_build_object('Content-Type','application/json','x-cron-secret',secret),
   body:=jsonb_build_object('action','deliverNotification','notification_id',new.id),
   timeout_milliseconds:=10000
  );
 end if;
 return new;
end $$;
revoke all on function fleet_private.queue_notification_push() from public,anon,authenticated;

drop trigger if exists fleet_notification_push on public.fleet_notifications;
create trigger fleet_notification_push after insert on public.fleet_notifications for each row execute function fleet_private.queue_notification_push();
commit;
