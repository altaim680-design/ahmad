begin;
insert into auth.users(id) values('fdc798d1-2b14-444f-b9e2-38dcd833f0b5'),('2650a72b-c122-44d7-b6c9-0478e2771249'),('cea72d61-4756-4c3e-9911-0774b5356983'),('2878c1cb-58bf-4982-956b-78b2b508cd82');
insert into public.fleet_companies(id,name) values('8d37b5b2-8a68-408b-b892-80894da11390','QA isolation'),('c4aaa4ef-5900-4b9f-adca-82e9f06c3669','QA other');
insert into public.fleet_memberships(user_id,username,role,company_id) values('fdc798d1-2b14-444f-b9e2-38dcd833f0b5','qa_fdc798d1','company_staff','8d37b5b2-8a68-408b-b892-80894da11390'),('2650a72b-c122-44d7-b6c9-0478e2771249','qa_2650a72b','company_staff','8d37b5b2-8a68-408b-b892-80894da11390'),('cea72d61-4756-4c3e-9911-0774b5356983','qa_cea72d61','company_admin','8d37b5b2-8a68-408b-b892-80894da11390'),('2878c1cb-58bf-4982-956b-78b2b508cd82','qa_2878c1cb','super_admin',null);
insert into public.fleet_trips(id,company_id,plate,assigned_member_id) values('087d8259-3da1-44f7-b1d2-58f1d49f1bde','8d37b5b2-8a68-408b-b892-80894da11390','QA A','fdc798d1-2b14-444f-b9e2-38dcd833f0b5'),('f426a8fc-14c7-440d-9670-1678756426fb','8d37b5b2-8a68-408b-b892-80894da11390','QA B','2650a72b-c122-44d7-b6c9-0478e2771249'),('140c88a8-17cf-43da-8c77-d81fc385658f','8d37b5b2-8a68-408b-b892-80894da11390','QA unassigned',null);
insert into public.fleet_updates(trip_id,company_id,place,status,source) select id,company_id,'QA','بالطريق','office' from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390';
insert into public.fleet_trip_files(id,trip_id,company_id,filename,size_bytes,storage_path,created_by) select id,id,company_id,'QA.pdf',20,id::text||'/'||id::text||'.pdf','2878c1cb-58bf-4982-956b-78b2b508cd82' from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390';
do $$ begin begin insert into public.fleet_trips(company_id,plate,assigned_member_id) values('c4aaa4ef-5900-4b9f-adca-82e9f06c3669','QA invalid','fdc798d1-2b14-444f-b9e2-38dcd833f0b5');raise exception 'cross-company assignment allowed';exception when foreign_key_violation then null;end;end $$;
select set_config('request.jwt.claim.sub','fdc798d1-2b14-444f-b9e2-38dcd833f0b5',true);set local role authenticated;
do $$ begin
 if (select count(*) from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'trip isolation';end if;
 if (select count(*) from public.fleet_trip_status where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'view isolation';end if;
 if (select count(*) from public.fleet_updates where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'updates isolation';end if;
 if (select count(*) from public.fleet_trip_files where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'files isolation';end if;
 if (select count(*) from public.fleet_report(current_date+1,'8d37b5b2-8a68-408b-b892-80894da11390'))<>1 then raise exception 'report isolation';end if;
if not exists(select 1 from public.fleet_trips where id='087d8259-3da1-44f7-b1d2-58f1d49f1bde') then raise exception 'wrong assignment';end if;end $$;reset role;
select set_config('request.jwt.claim.sub','2650a72b-c122-44d7-b6c9-0478e2771249',true);set local role authenticated;
do $$ begin
 if (select count(*) from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'trip isolation';end if;
 if (select count(*) from public.fleet_trip_status where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'view isolation';end if;
 if (select count(*) from public.fleet_updates where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'updates isolation';end if;
 if (select count(*) from public.fleet_trip_files where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>1 then raise exception 'files isolation';end if;
 if (select count(*) from public.fleet_report(current_date+1,'8d37b5b2-8a68-408b-b892-80894da11390'))<>1 then raise exception 'report isolation';end if;
if not exists(select 1 from public.fleet_trips where id='f426a8fc-14c7-440d-9670-1678756426fb') then raise exception 'wrong assignment';end if;end $$;reset role;
select set_config('request.jwt.claim.sub','cea72d61-4756-4c3e-9911-0774b5356983',true);set local role authenticated;
do $$ begin
 if (select count(*) from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'trip isolation';end if;
 if (select count(*) from public.fleet_trip_status where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'view isolation';end if;
 if (select count(*) from public.fleet_updates where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'updates isolation';end if;
 if (select count(*) from public.fleet_trip_files where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'files isolation';end if;
 if (select count(*) from public.fleet_report(current_date+1,'8d37b5b2-8a68-408b-b892-80894da11390'))<>3 then raise exception 'report isolation';end if;
end $$;reset role;
select set_config('request.jwt.claim.sub','2878c1cb-58bf-4982-956b-78b2b508cd82',true);set local role authenticated;
do $$ begin
 if (select count(*) from public.fleet_trips where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'trip isolation';end if;
 if (select count(*) from public.fleet_trip_status where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'view isolation';end if;
 if (select count(*) from public.fleet_updates where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'updates isolation';end if;
 if (select count(*) from public.fleet_trip_files where company_id='8d37b5b2-8a68-408b-b892-80894da11390')<>3 then raise exception 'files isolation';end if;
 if (select count(*) from public.fleet_report(current_date+1,'8d37b5b2-8a68-408b-b892-80894da11390'))<>3 then raise exception 'report isolation';end if;
end $$;reset role;
update public.fleet_memberships set active=false where user_id='fdc798d1-2b14-444f-b9e2-38dcd833f0b5';select set_config('request.jwt.claim.sub','fdc798d1-2b14-444f-b9e2-38dcd833f0b5',true);set local role authenticated;do $$ begin if exists(select 1 from public.fleet_trips) or exists(select 1 from public.fleet_trip_files) then raise exception 'inactive access';end if;end $$;reset role;rollback;select 'PASS: staff A/B isolation, manager/root all, report/view/update/file isolation, inactive denial, company FK' as result;