begin;
insert into auth.users(id) values('d30187f2-2cb9-4984-884f-bd735fa5cc80'),('49ca20ac-84df-44a2-9267-593599258b00'),('31728c5d-e930-461d-92cb-d8ef9d83897a'),('4176a1cc-269a-4ded-82d3-11b6de2f0753'),('4c36ea25-3d04-4720-b2cf-e40b0fc09c6b'),('fcee63d0-3908-4b59-97e5-abf14dfb2a90');
insert into public.fleet_companies(id,name) values('6ca5b8e0-c9f1-4fea-b15a-3997577afc7a','Operations QA'),('6aae7f3f-00f7-4678-a608-eab40bca718f','Other QA');
insert into public.fleet_memberships(user_id,username,role,company_id) values('d30187f2-2cb9-4984-884f-bd735fa5cc80','qa_d30187f2','super_admin',null),('49ca20ac-84df-44a2-9267-593599258b00','qa_49ca20ac','company_staff','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a'),('31728c5d-e930-461d-92cb-d8ef9d83897a','qa_31728c5d','company_staff','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a'),('fcee63d0-3908-4b59-97e5-abf14dfb2a90','qa_fcee63d0','company_staff','6aae7f3f-00f7-4678-a608-eab40bca718f');
insert into public.fleet_drivers(user_id,username,company_id) values('4176a1cc-269a-4ded-82d3-11b6de2f0753','qa_4176a1cc','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a'),('4c36ea25-3d04-4720-b2cf-e40b0fc09c6b','qa_4c36ea25','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a');
insert into public.fleet_groups(id,company_id,name) values('071921fc-32e2-4271-9945-b743f04569f6','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a','Group QA'),('c82aac20-0f5f-4266-830b-c0e1e2e71684','6aae7f3f-00f7-4678-a608-eab40bca718f','Other group');
insert into public.fleet_trips(id,company_id,plate,assigned_member_id,driver_user_id,group_id) values('e83d339b-f162-4400-9009-19d148bd24e8','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a','Original truck','49ca20ac-84df-44a2-9267-593599258b00','4176a1cc-269a-4ded-82d3-11b6de2f0753','071921fc-32e2-4271-9945-b743f04569f6'),('946ab72f-9345-4cfd-a9a8-671606c195c0','6ca5b8e0-c9f1-4fea-b15a-3997577afc7a','Other truck','31728c5d-e930-461d-92cb-d8ef9d83897a',null,'071921fc-32e2-4271-9945-b743f04569f6'),('300707fa-fb4f-4975-aa88-4304bbb0f28d','6aae7f3f-00f7-4678-a608-eab40bca718f','Other company','fcee63d0-3908-4b59-97e5-abf14dfb2a90',null,'c82aac20-0f5f-4266-830b-c0e1e2e71684');
insert into public.fleet_requirements(trip_id,title) values('e83d339b-f162-4400-9009-19d148bd24e8','Invoice'),('946ab72f-9345-4cfd-a9a8-671606c195c0','CMR'),('300707fa-fb4f-4975-aa88-4304bbb0f28d','Other');
select public.fleet_post_message('49ca20ac-84df-44a2-9267-593599258b00','FORGED NAME','e83d339b-f162-4400-9009-19d148bd24e8','Private A',null,null);
select public.fleet_post_message('31728c5d-e930-461d-92cb-d8ef9d83897a','FORGED NAME','946ab72f-9345-4cfd-a9a8-671606c195c0','Private B',null,null);
select public.fleet_post_message('4176a1cc-269a-4ded-82d3-11b6de2f0753','FORGED NAME','e83d339b-f162-4400-9009-19d148bd24e8','Driver issue',null,'breakdown');
select set_config('request.jwt.claim.sub','49ca20ac-84df-44a2-9267-593599258b00',true);set local role authenticated;
do $$ begin
 if (select count(*) from public.fleet_messages)<>2 then raise exception 'message isolation';end if;
 if (select count(*) from public.fleet_requirements)<>1 then raise exception 'document isolation';end if;
 if (select count(*) from public.fleet_groups)<>1 then raise exception 'group isolation';end if;
 if exists(select 1 from public.fleet_messages where actor_name='FORGED NAME') then raise exception 'sender spoof';end if;
 if has_function_privilege('authenticated','public.fleet_operate_trip(uuid,uuid,text,jsonb)','execute') then raise exception 'RPC exposed';end if;
 if has_table_privilege('authenticated','public.fleet_media','select') then raise exception 'media exposed';end if;
end $$;reset role;
do $$ begin
 begin perform public.fleet_operate_trip('49ca20ac-84df-44a2-9267-593599258b00','946ab72f-9345-4cfd-a9a8-671606c195c0','handoff',jsonb_build_object('member_id','49ca20ac-84df-44a2-9267-593599258b00','expected_member','31728c5d-e930-461d-92cb-d8ef9d83897a','note','wrong trip'));raise exception 'unauthorized handoff allowed';exception when others then if sqlerrm='unauthorized handoff allowed' then raise;end if;end;
 begin perform public.fleet_operate_trip('49ca20ac-84df-44a2-9267-593599258b00','e83d339b-f162-4400-9009-19d148bd24e8','handoff',jsonb_build_object('member_id','fcee63d0-3908-4b59-97e5-abf14dfb2a90','expected_member','49ca20ac-84df-44a2-9267-593599258b00','note','wrong company'));raise exception 'cross-company handoff allowed';exception when others then if sqlerrm='cross-company handoff allowed' then raise;end if;end;
end $$;
select public.fleet_operate_trip('49ca20ac-84df-44a2-9267-593599258b00','e83d339b-f162-4400-9009-19d148bd24e8','handoff',jsonb_build_object('member_id','31728c5d-e930-461d-92cb-d8ef9d83897a','expected_member','49ca20ac-84df-44a2-9267-593599258b00','note','Documents reviewed; await border clearance'));
select set_config('request.jwt.claim.sub','49ca20ac-84df-44a2-9267-593599258b00',true);set local role authenticated;
do $$ begin if exists(select 1 from public.fleet_messages) or exists(select 1 from public.fleet_groups) then raise exception 'old assignee retains access';end if;end $$;reset role;
select set_config('request.jwt.claim.sub','31728c5d-e930-461d-92cb-d8ef9d83897a',true);set local role authenticated;
do $$ begin if (select count(*) from public.fleet_messages)<>3 or (select count(*) from public.fleet_trip_events)<>1 then raise exception 'new assignee missing history';end if;end $$;reset role;
do $$ begin
 begin perform public.fleet_post_message('49ca20ac-84df-44a2-9267-593599258b00','ignored','e83d339b-f162-4400-9009-19d148bd24e8','Late unauthorized post',null,null);raise exception 'revoked post accepted';exception when others then if sqlerrm='revoked post accepted' then raise;end if;end;
 begin perform public.fleet_operate_trip('31728c5d-e930-461d-92cb-d8ef9d83897a','e83d339b-f162-4400-9009-19d148bd24e8','vehicle',jsonb_build_object('plate','wrong','place','wrong'));raise exception 'staff changed vehicle';exception when others then if sqlerrm='staff changed vehicle' then raise;end if;end;
end $$;
select public.fleet_operate_trip('d30187f2-2cb9-4984-884f-bd735fa5cc80','e83d339b-f162-4400-9009-19d148bd24e8','vehicle',jsonb_build_object('plate','Replacement truck','driver','New driver','phone','123456','place','Border','driver_id','4c36ea25-3d04-4720-b2cf-e40b0fc09c6b','note','Transfer complete'));
do $$ begin
 if (select driver_user_id from public.fleet_trips where id='e83d339b-f162-4400-9009-19d148bd24e8')<>'4c36ea25-3d04-4720-b2cf-e40b0fc09c6b' then raise exception 'driver not replaced';end if;
 if not exists(select 1 from public.fleet_trip_events where trip_id='e83d339b-f162-4400-9009-19d148bd24e8' and kind='vehicle' and details->>'old_plate'='Original truck') then raise exception 'old vehicle lost';end if;
 begin perform public.fleet_post_message('4176a1cc-269a-4ded-82d3-11b6de2f0753','ignored','e83d339b-f162-4400-9009-19d148bd24e8','Old driver post',null,null);raise exception 'old driver access';exception when others then if sqlerrm='old driver access' then raise;end if;end;
end $$;
select public.fleet_post_message('4c36ea25-3d04-4720-b2cf-e40b0fc09c6b','ignored','e83d339b-f162-4400-9009-19d148bd24e8','New driver ready',null,null);
rollback;
select 'PASS: private messages/docs/groups, handover, old access revoked, driver replacement, history, RPC restrictions, sender identity' as result;
