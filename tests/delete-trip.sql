begin;
insert into auth.users(id) values('d71e0d47-cbe4-457e-b602-ed60862dccee'),('3d460111-32fd-4cad-aedb-ae799eac1b97'),('285fe56e-36cf-4aaf-8d5b-5032e2ae1c06');
insert into public.fleet_companies(id,name) values('4160f0d0-38c8-45b2-9aa2-465cba24dc75','Delete trip QA');
insert into public.fleet_memberships(user_id,username,role,company_id) values('d71e0d47-cbe4-457e-b602-ed60862dccee','qa_delete_root','super_admin',null),('3d460111-32fd-4cad-aedb-ae799eac1b97','qa_delete_staff','company_staff','4160f0d0-38c8-45b2-9aa2-465cba24dc75');
insert into public.fleet_drivers(user_id,username,company_id) values('285fe56e-36cf-4aaf-8d5b-5032e2ae1c06','qa_delete_driver','4160f0d0-38c8-45b2-9aa2-465cba24dc75');
insert into public.fleet_trips(id,company_id,plate,driver_user_id,closed) values('588c71ad-9489-495f-8f5c-c44957fe5204','4160f0d0-38c8-45b2-9aa2-465cba24dc75','DELETE QA','285fe56e-36cf-4aaf-8d5b-5032e2ae1c06',false),('10e552b4-84c1-400a-8e94-df3ee2a3867f','4160f0d0-38c8-45b2-9aa2-465cba24dc75','KEEP QA','285fe56e-36cf-4aaf-8d5b-5032e2ae1c06',true);
insert into public.fleet_trip_files(id,trip_id,company_id,filename,size_bytes,created_by,storage_path) values('f6abff8a-e8c1-4af5-92de-b4b056f43b97','588c71ad-9489-495f-8f5c-c44957fe5204','4160f0d0-38c8-45b2-9aa2-465cba24dc75','QA.pdf',100,'d71e0d47-cbe4-457e-b602-ed60862dccee','588c71ad-9489-495f-8f5c-c44957fe5204/f6abff8a-e8c1-4af5-92de-b4b056f43b97.pdf');
insert into public.fleet_requirements(trip_id,title,file_id) values('588c71ad-9489-495f-8f5c-c44957fe5204','Invoice','f6abff8a-e8c1-4af5-92de-b4b056f43b97');
insert into public.fleet_media(id,trip_id,actor,path,mime,size_bytes) values('1831a61a-e058-401b-8c3b-42751caefcd2','588c71ad-9489-495f-8f5c-c44957fe5204','d71e0d47-cbe4-457e-b602-ed60862dccee','588c71ad-9489-495f-8f5c-c44957fe5204/qa.jpg','image/jpeg',100);
select public.fleet_post_message('d71e0d47-cbe4-457e-b602-ed60862dccee','QA','588c71ad-9489-495f-8f5c-c44957fe5204','test issue','1831a61a-e058-401b-8c3b-42751caefcd2','other');
do $$begin
 if has_function_privilege('authenticated','public.fleet_delete_trip(uuid,uuid,text)','execute') or has_function_privilege('anon','public.fleet_delete_trip(uuid,uuid,text)','execute') then raise exception 'RPC exposed';end if;
 if has_table_privilege('authenticated','public.fleet_trip_file_cleanup','select') then raise exception 'queue exposed';end if;
 begin perform public.fleet_delete_trip('3d460111-32fd-4cad-aedb-ae799eac1b97','588c71ad-9489-495f-8f5c-c44957fe5204','DELETE QA');raise exception 'staff allowed';exception when others then if sqlerrm='staff allowed' then raise;end if;end;
 begin perform public.fleet_delete_trip('d71e0d47-cbe4-457e-b602-ed60862dccee','588c71ad-9489-495f-8f5c-c44957fe5204','wrong');raise exception 'wrong confirmation allowed';exception when others then if sqlerrm='wrong confirmation allowed' then raise;end if;end;
 if not exists(select 1 from public.fleet_trips where id='588c71ad-9489-495f-8f5c-c44957fe5204') then raise exception 'rejected deletion mutated trip';end if;
end $$;
select public.fleet_delete_trip('d71e0d47-cbe4-457e-b602-ed60862dccee','588c71ad-9489-495f-8f5c-c44957fe5204','DELETE QA');
do $$begin
 if exists(select 1 from public.fleet_trips where id='588c71ad-9489-495f-8f5c-c44957fe5204') or exists(select 1 from public.fleet_messages where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204') or exists(select 1 from public.fleet_requirements where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204') or exists(select 1 from public.fleet_media where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204') or exists(select 1 from public.fleet_trip_files where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204') then raise exception 'cascade failed';end if;
 if (select count(*) from public.fleet_trip_file_cleanup where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204')<>2 then raise exception 'cleanup jobs missing';end if;
 if not exists(select 1 from public.fleet_trips where id='10e552b4-84c1-400a-8e94-df3ee2a3867f') or not exists(select 1 from public.fleet_drivers where user_id='285fe56e-36cf-4aaf-8d5b-5032e2ae1c06') then raise exception 'unrelated trip/driver removed';end if;
 if not exists(select 1 from public.fleet_security_audit where trip_id='588c71ad-9489-495f-8f5c-c44957fe5204' and action='deleteTrip') then raise exception 'missing audit';end if;
end $$;
select public.fleet_delete_trip('d71e0d47-cbe4-457e-b602-ed60862dccee','10e552b4-84c1-400a-8e94-df3ee2a3867f','KEEP QA');
rollback;
