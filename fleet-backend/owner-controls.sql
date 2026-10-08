begin;
alter table public.fleet_memberships add column if not exists is_owner boolean not null default false;
create unique index if not exists fleet_single_owner on public.fleet_memberships(is_owner) where is_owner;
update public.fleet_memberships set is_owner=true where user_id='2b96c19c-315a-402a-bbcc-7d72a0611ada' and role='super_admin';
create or replace function public.fleet_delete_company(p_actor uuid,p_company uuid,p_name text)
returns uuid[] language plpgsql security invoker set search_path='' as $$
declare company_name text; accounts uuid[];
begin
 if not exists(select 1 from public.fleet_memberships where user_id=p_actor and is_owner and active and role='super_admin') then raise exception 'Owner only'; end if;
 select name into company_name from public.fleet_companies where id=p_company for update;
 if not found then raise exception 'Company not found'; end if;
 if p_name is distinct from company_name then raise exception 'Company name does not match'; end if;
 select array_agg(user_id) into accounts from (select user_id from public.fleet_memberships where company_id=p_company union select user_id from public.fleet_drivers where company_id=p_company) a;
 delete from public.fleet_trips where company_id=p_company;
 delete from public.fleet_companies where id=p_company;
 return coalesce(accounts,array[]::uuid[]);
end $$;
revoke all on function public.fleet_delete_company(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.fleet_delete_company(uuid,uuid,text) to service_role;
commit;
