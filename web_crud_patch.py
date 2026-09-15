# -*- coding: utf-8 -*-
"""CRUD extension for Nahda Web V3.
Adds safe edit/delete controls without changing the original V3 source payload.
"""
import json
from datetime import date, datetime
from decimal import Decimal

import web_v3 as core
from flask import request, session, redirect, url_for, flash, render_template_string, Response
from markupsafe import escape
from sqlalchemy import Boolean, Date, DateTime, Integer, Float, Numeric
from werkzeug.security import generate_password_hash

app = core.app
db = core.db

User = core.User
Company = core.Company
CustomsDeclaration = core.CustomsDeclaration
DeclarationCharge = core.DeclarationCharge
TransportJob = core.TransportJob
TransportCost = core.TransportCost
TransportPayment = core.TransportPayment
TransportStage = core.TransportStage
TurkishVehicleInvoice = core.TurkishVehicleInvoice
InternalShipment = core.InternalShipment
SalesInvoice = core.SalesInvoice
InvoiceLine = core.InvoiceLine
CashTransaction = core.CashTransaction
Expense = core.Expense
Shareholder = core.Shareholder
CapitalMovement = core.CapitalMovement
JournalEntry = core.JournalEntry
JournalLine = core.JournalLine
V3Attachment = core.V3Attachment
ServiceCase = core.ServiceCase
ServiceCaseCharge = core.ServiceCaseCharge
ServiceCasePayment = core.ServiceCasePayment
AuditLog = core.AuditLog

ENTITY = {
    'company': (Company, 'الشركة', 'companies'),
    'declaration': (CustomsDeclaration, 'البيان', 'declarations'),
    'trip': (TransportJob, 'الرحلة', 'trips'),
    'internal': (InternalShipment, 'البيان الداخلي', 'internal_shipments'),
    'case': (ServiceCase, 'المعاملة', 'cases'),
    'invoice': (SalesInvoice, 'الفاتورة', 'invoices'),
    'cash': (CashTransaction, 'حركة الصندوق', 'cash'),
    'expense': (Expense, 'المصروف', 'expenses'),
    'shareholder': (Shareholder, 'الشريك', 'shareholders'),
    'attachment': (V3Attachment, 'المرفق', 'attachments'),
    'user': (User, 'المستخدم', 'users'),
}

PATH_ENTITY = {
    '/companies': 'company',
    '/declarations': 'declaration',
    '/trips': 'trip',
    '/internal-shipments': 'internal',
    '/cases': 'case',
    '/invoices': 'invoice',
    '/cash': 'cash',
    '/expenses': 'expense',
    '/shareholders': 'shareholder',
    '/attachments': 'attachment',
    '/users': 'user',
}

LABELS = {
    'name':'الاسم','company_id':'الشركة','declaration_id':'البيان','job_id':'الرحلة','transport_job_id':'الرحلة',
    'declaration_no':'رقم البيان','declaration_type':'نوع البيان','manifest_no':'رقم الملف / المانيفست',
    'date':'التاريخ','status':'الحالة','currency':'العملة','phone':'الهاتف','notes':'ملاحظات','note':'ملاحظات',
    'description':'البيان / الوصف','category':'التصنيف','amount':'المبلغ','direction':'نوع الحركة','reference':'المرجع',
    'opening_balance':'الرصيد الافتتاحي','office_fee':'رسوم المكتب','customs_fee':'الرسوم الجمركية',
    'syrian_transport':'أجور السيارة السورية','visa_fee':'الفيزا','crossing_fee':'العبور','insurance_fee':'التأمين',
    'extra_fee':'مصاريف إضافية','customer_total':'المطلوب من العميل','company_price':'سعر الشركة',
    'turkish_purchase_price':'تكلفة السيارة التركية','turkish_vehicle':'السيارة التركية','syrian_vehicle':'السيارة السورية',
    'vehicle_location':'موقع السيارة','vehicle_city':'مدينة السيارة','foreign_vehicle':'السيارة الأجنبية',
    'foreign_driver':'السائق الأجنبي','foreign_phone':'هاتف السائق','destination':'المقصد',
    'nassib_payment':'دفعة نصيب','nassib_due':'المتبقي نصيب','title':'العنوان','type':'النوع',
    'invoice_no':'رقم الفاتورة','payment_method':'طريقة الدفع','discount':'الخصم','username':'اسم المستخدم',
    'full_name':'الاسم الكامل','role':'الصلاحية','active':'فعال','original_name':'اسم الملف','source_type':'نوع المصدر',
    'source_id':'رقم المصدر','percentage':'النسبة','commitment':'المساهمة / الالتزام','share':'الحصة',
    'qty':'الكمية','unit_price':'سعر الوحدة','plate_no':'رقم السيارة','driver_name':'اسم السائق',
}

TECHNICAL = {'id','created_at','updated_at','created_by','updated_by','password_hash'}
CALCULATED = {
    'total','subtotal','grand_total','balance','remaining','due','paid','profit','total_cost','net','current_balance',
    'transport_job_id','invoice_no','declaration_id',
}
SAFE_FIELDS = {
    'invoice': {'date','company_id','declaration_id','job_id','payment_method','description','note','notes','discount'},
    'cash': {'category','description','note','notes','reference'},
    'expense': {'category','description','note','notes'},
    'attachment': {'original_name','category','note','notes'},
    'user': {'username','full_name','role','active'},
}
FK_MODELS = {'company_id':Company,'declaration_id':CustomsDeclaration,'job_id':TransportJob,'transport_job_id':TransportJob,'shareholder_id':Shareholder,'case_id':ServiceCase}

def _logged_in(): return bool(session.get('user_id'))
def _allowed(entity):
    if entity == 'user': return session.get('role') == 'admin'
    if entity in ('cash','expense','invoice'): return session.get('role') in ('admin','accountant')
    return core.can_edit()
def _go(endpoint):
    try: return redirect(url_for(endpoint))
    except Exception: return redirect('/')
def _label_for_obj(obj):
    for attr in ('name','declaration_no','manifest_no','invoice_no','title','username','original_name','description'):
        v=getattr(obj,attr,None)
        if v not in (None,''): return str(v)
    return f'#{getattr(obj,"id","")}'
def _field_list(entity,model):
    cols=[]; safe=SAFE_FIELDS.get(entity)
    for c in model.__table__.columns:
        n=c.name
        if n in TECHNICAL: continue
        if entity=='declaration': continue
        if safe is not None and n not in safe: continue
        if safe is None and (n in CALCULATED or any(x in n.lower() for x in ('total','balance','remaining'))): continue
        if entity=='trip' and n in ('declaration_id','transport_job_id'): continue
        cols.append(c)
    return cols
def _fk_options(col):
    m=FK_MODELS.get(col.name)
    if not m: return []
    try: rows=m.query.order_by(m.id.asc()).all()
    except Exception: rows=m.query.all()
    return [(x.id,_label_for_obj(x)) for x in rows]
def _parse_value(col,raw):
    if raw is None: return None
    if isinstance(col.type,Boolean): return str(raw).lower() in ('1','true','on','yes','نعم')
    raw=str(raw).strip()
    if raw=='' and col.nullable: return None
    if isinstance(col.type,Integer): return int(raw or 0)
    if isinstance(col.type,(Float,Numeric)): return float(raw or 0)
    if isinstance(col.type,DateTime):
        if not raw:return None
        try:return datetime.fromisoformat(raw)
        except Exception:return datetime.strptime(raw,'%Y-%m-%d')
    if isinstance(col.type,Date): return date.fromisoformat(raw[:10]) if raw else None
    return raw
def _value_for_input(obj,col):
    v=getattr(obj,col.name,'')
    if v is None:return ''
    if isinstance(v,datetime):return v.strftime('%Y-%m-%dT%H:%M')
    if isinstance(v,date):return v.isoformat()
    return v
def _audit(action,entity,rid,details=''):
    try: core.audit(action,entity,rid,details)
    except Exception: pass

@app.route('/crud/edit/<entity>/<int:rid>',methods=['GET','POST'])
def crud_edit(entity,rid):
    if not _logged_in(): return redirect(url_for('login'))
    if entity not in ENTITY or not _allowed(entity): flash('ليس لديك صلاحية التعديل','error'); return redirect('/')
    model,title,back_ep=ENTITY[entity]; obj=model.query.get_or_404(rid)
    if entity=='declaration': return redirect(url_for('declaration_form',did=rid))
    fields=_field_list(entity,model)
    if request.method=='POST':
        try:
            changes=[]
            for col in fields:
                n=col.name; old=getattr(obj,n,None); raw=request.form.get(n)
                if raw is None: continue
                new=_parse_value(col,raw)
                if old!=new: changes.append(f'{n}: {old} -> {new}'); setattr(obj,n,new)
            if entity=='user':
                pw=request.form.get('new_password','').strip()
                if pw: obj.password_hash=generate_password_hash(pw)
            db.session.commit(); _audit('edit',entity,rid,'; '.join(changes)[:1500]); flash(f'تم تعديل {title} بنجاح','success'); return _go(back_ep)
        except Exception as e: db.session.rollback(); flash('تعذر حفظ التعديل: '+str(e),'error')
    meta=[]
    for col in fields:
        item={'name':col.name,'label':LABELS.get(col.name,col.name),'value':_value_for_input(obj,col),'options':_fk_options(col),'kind':'text'}
        if isinstance(col.type,Boolean):item['kind']='bool'
        elif isinstance(col.type,DateTime):item['kind']='datetime-local'
        elif isinstance(col.type,Date):item['kind']='date'
        elif isinstance(col.type,(Integer,Float,Numeric)):item['kind']='number'
        elif getattr(col.type,'length',0) is None or str(col.type).upper().startswith('TEXT'):item['kind']='textarea'
        if item['options']:item['kind']='select'
        meta.append(item)
    body='''<div class="page-head"><div><h1>تعديل {{title}}</h1><p class="muted">السجل رقم #{{obj.id}} — {{label}}</p></div></div><form method="post" class="card form-grid">{% for f in fields %}<label>{{f.label}}{% if f.kind == 'select' %}<select name="{{f.name}}"><option value="">—</option>{% for oid,txt in f.options %}<option value="{{oid}}" {% if (f.value|string)==(oid|string) %}selected{% endif %}>{{txt}}</option>{% endfor %}</select>{% elif f.kind == 'bool' %}<select name="{{f.name}}"><option value="1" {% if f.value %}selected{% endif %}>نعم</option><option value="0" {% if not f.value %}selected{% endif %}>لا</option></select>{% elif f.kind == 'textarea' %}<textarea name="{{f.name}}" rows="3">{{f.value}}</textarea>{% else %}<input name="{{f.name}}" type="{{f.kind}}" value="{{f.value}}" {% if f.kind=='number' %}step="any"{% endif %}>{% endif %}</label>{% endfor %}{% if entity == 'user' %}<label>كلمة مرور جديدة <input type="password" name="new_password" placeholder="اتركها فارغة بدون تغيير"></label>{% endif %}<div class="toolbar" style="grid-column:1/-1"><button class="btn green" type="submit">حفظ التعديل</button><a class="btn gray" href="{{back}}">رجوع</a></div></form>'''
    return core.layout('تعديل '+title,body,title=title,obj=obj,label=_label_for_obj(obj),fields=meta,entity=entity,back=url_for(back_ep))

def _delete_generic_rows(model,**filters):
    try:model.query.filter_by(**filters).delete(synchronize_session=False)
    except Exception:
        for row in model.query.filter_by(**filters).all():db.session.delete(row)
def _has(model,**filters):
    try:return model.query.filter_by(**filters).first() is not None
    except Exception:return False

@app.route('/crud/delete/<entity>/<int:rid>',methods=['POST'])
def crud_delete(entity,rid):
    if not _logged_in():return redirect(url_for('login'))
    if entity not in ENTITY or not _allowed(entity):flash('ليس لديك صلاحية الحذف','error');return redirect('/')
    model,title,back_ep=ENTITY[entity];obj=model.query.get_or_404(rid)
    try:
        if entity=='company':
            linked=False
            for m in (CustomsDeclaration,TransportJob,SalesInvoice,CashTransaction,ServiceCase,InternalShipment):
                if hasattr(m,'company_id') and _has(m,company_id=rid):linked=True;break
            if linked:flash('لا يمكن حذف الشركة لأنها مرتبطة ببيانات أو حركات. عدّلها بدلاً من الحذف.','error');return _go(back_ep)
        elif entity=='declaration':
            if _has(TransportJob,declaration_id=rid) or _has(SalesInvoice,declaration_id=rid):flash('لا يمكن حذف البيان لأنه مرتبط برحلة أو فاتورة. احذف/ألغِ الارتباط أولاً.','error');return _go(back_ep)
            _delete_generic_rows(DeclarationCharge,declaration_id=rid);_delete_generic_rows(V3Attachment,source_type='declaration',source_id=rid)
        elif entity=='trip':
            if _has(TransportPayment,job_id=rid) or _has(SalesInvoice,job_id=rid):flash('لا يمكن حذف الرحلة لأنها تحتوي دفعات أو فاتورة. حفاظاً على الحسابات يجب إلغاء الدفعات أولاً.','error');return _go(back_ep)
            _delete_generic_rows(TransportCost,job_id=rid);_delete_generic_rows(TransportStage,job_id=rid);_delete_generic_rows(TurkishVehicleInvoice,job_id=rid);_delete_generic_rows(V3Attachment,source_type='trip',source_id=rid)
            try:
                dec=CustomsDeclaration.query.filter_by(transport_job_id=rid).first()
                if dec: dec.transport_job_id=None; dec.status='مفتوح' if hasattr(dec,'status') else getattr(dec,'status',None)
            except Exception:pass
        elif entity=='case':
            if _has(ServiceCasePayment,case_id=rid):flash('لا يمكن حذف المعاملة لأنها تحتوي دفعات مالية. يمكن تعديل بياناتها فقط.','error');return _go(back_ep)
            _delete_generic_rows(ServiceCaseCharge,case_id=rid);_delete_generic_rows(V3Attachment,source_type='case',source_id=rid)
        elif entity=='invoice':
            paid=float(getattr(obj,'paid',0) or 0)
            if paid>0:flash('لا يمكن حذف فاتورة عليها دفعات. استخدم التصحيح المحاسبي حفاظاً على الرصيد.','error');return _go(back_ep)
            try:
                for je in JournalEntry.query.filter_by(ref_type='invoice',ref_id=rid).all():_delete_generic_rows(JournalLine,entry_id=je.id);db.session.delete(je)
            except Exception:pass
            _delete_generic_rows(InvoiceLine,invoice_id=rid)
        elif entity in ('cash','expense'):
            flash('الحركات المالية لا تُحذف مباشرة لأنها مرتبطة بقيود محاسبية. عدّل الوصف/التصنيف، والتصحيح المالي يكون بقيد عكسي.','error');return _go(back_ep)
        elif entity=='shareholder':
            if _has(CapitalMovement,shareholder_id=rid):flash('لا يمكن حذف الشريك لوجود حركات رأس مال مرتبطة به. يمكن تعديل بياناته.','error');return _go(back_ep)
        elif entity=='user':
            if rid==session.get('user_id'):flash('لا يمكنك حذف المستخدم الذي تعمل به حالياً.','error');return _go(back_ep)
            if getattr(obj,'role','')=='admin' and User.query.filter_by(role='admin').count()<=1:flash('لا يمكن حذف آخر مدير في النظام.','error');return _go(back_ep)
        elif entity=='internal':
            _delete_generic_rows(V3Attachment,source_type='internal',source_id=rid);_delete_generic_rows(V3Attachment,source_type='internal_shipment',source_id=rid)
        label=_label_for_obj(obj);db.session.delete(obj);db.session.commit();_audit('delete',entity,rid,label);flash(f'تم حذف {title} بنجاح','success')
    except Exception as e:db.session.rollback();flash('تعذر الحذف: '+str(e),'error')
    return _go(back_ep)

@app.route('/crud/health')
def crud_health():return {'ok':True,'crud':True,'version':'V3.1','entities':sorted(ENTITY.keys())}

def _ids_for_entity(entity):
    try:
        model=ENTITY[entity][0];return [x.id for x in model.query.order_by(model.id.desc()).limit(500).all()]
    except Exception:return []
def _action_html(entity,rid):
    if not rid:return ''
    edit=f'/declarations/form/{rid}' if entity=='declaration' else f'/crud/edit/{entity}/{rid}'
    dl='إلغاء' if entity in ('cash','expense') else 'حذف'
    return f'<span class="crud-actions no-print" style="display:inline-flex;gap:6px;align-items:center;white-space:nowrap"><a class="btn small blue" href="{edit}">تعديل</a><form method="post" action="/crud/delete/{entity}/{rid}" style="display:inline;margin:0" onsubmit="return confirm(\'هل أنت متأكد من {dl} هذا السجل؟\')"><button class="btn small red" type="submit">{dl}</button></form></span>'

@app.after_request
def crud_ui_inject(response):
    try:
        if not _logged_in() or not core.can_edit():return response
        if 'text/html' not in response.headers.get('Content-Type',''):return response
        html=response.get_data(as_text=True);path=request.path.rstrip('/') or '/';entity=PATH_ENTITY.get(path)
        if entity and _allowed(entity):
            ids=_ids_for_entity(entity);cfg=json.dumps({'entity':entity,'ids':ids},ensure_ascii=False)
            script=f'''<script>(function(){{const cfg={cfg};function ridFromRow(row,idx){{const hrefs=[...row.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')||'');const pats={{declaration:/\\/declarations\\/(?:form\\/)?(\\d+)/,trip:/\\/trips\\/(\\d+)/,case:/\\/cases\\/(\\d+)/,invoice:/\\/invoices\\/(\\d+)/,attachment:/\\/attachment\\/(\\d+)/}};if(pats[cfg.entity]){{for(const h of hrefs){{const m=h.match(pats[cfg.entity]);if(m)return m[1];}}}}const first=row.querySelector('td');if(first){{const t=(first.textContent||'').trim();if(/^\\d+$/.test(t))return t;}}return cfg.ids[idx]||null;}}function buttons(id){{if(!id)return '';const edit=cfg.entity==='declaration'?`/declarations/form/${{id}}`:`/crud/edit/${{cfg.entity}}/${{id}}`;const dl=(cfg.entity==='cash'||cfg.entity==='expense')?'إلغاء':'حذف';return `<span class="crud-actions no-print" style="display:inline-flex;gap:6px;white-space:nowrap"><a class="btn small blue" href="${{edit}}">تعديل</a><form method="post" action="/crud/delete/${{cfg.entity}}/${{id}}" style="display:inline;margin:0" onsubmit="return confirm('هل أنت متأكد من ${{dl}} هذا السجل؟')"><button class="btn small red" type="submit">${{dl}}</button></form></span>`;}}const tables=[...document.querySelectorAll('table')];for(const table of tables){{const rows=[...table.querySelectorAll('tbody tr')];if(!rows.length)continue;let hits=0;rows.forEach((r,i)=>{{if(ridFromRow(r,i))hits++;}});if(!hits)continue;const hr=table.querySelector('thead tr');if(hr&&![...hr.children].some(x=>(x.textContent||'').includes('إجراءات'))){{const th=document.createElement('th');th.textContent='إجراءات';hr.appendChild(th);}}rows.forEach((r,i)=>{{const id=ridFromRow(r,i);if(!id)return;const td=document.createElement('td');td.innerHTML=buttons(id);r.appendChild(td);}});break;}}}})();</script>'''
            html=html.replace('</body>',script+'</body>')
        detail=None
        import re
        for ent,pat in [('declaration',r'^/declarations/(\d+)$'),('trip',r'^/trips/(\d+)$'),('case',r'^/cases/(\d+)$'),('invoice',r'^/invoices/(\d+)$')]:
            m=re.match(pat,path)
            if m and _allowed(ent):detail=(ent,int(m.group(1)));break
        if detail:
            ent,rid=detail;controls=_action_html(ent,rid);marker='<div class="toolbar no-print">'
            html=html.replace(marker,marker+controls,1) if marker in html else html.replace('</h1>','</h1>'+controls,1)
        response.set_data(html);response.headers['Content-Length']=str(len(response.get_data()))
    except Exception as e:print('[crud-ui]',type(e).__name__,str(e))
    return response
