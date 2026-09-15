# -*- coding: utf-8 -*-
import os, io
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, send_file, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','nahda-web-change-me')
app.config['MAX_CONTENT_LENGTH'] = 12*1024*1024
url = os.environ.get('DATABASE_URL','sqlite:///nahda_web.db')
if url.startswith('postgres://'):
    url = url.replace('postgres://','postgresql://',1)
app.config['SQLALCHEMY_DATABASE_URI'] = url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),default='user'); active=db.Column(db.Boolean,default=True)
class Setting(db.Model):
    id=db.Column(db.Integer,primary_key=True); key=db.Column(db.String(80),unique=True,nullable=False); value=db.Column(db.Text,default='')
class Company(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(180),nullable=False); opening_balance=db.Column(db.Float,default=0); phone=db.Column(db.String(80),default=''); notes=db.Column(db.Text,default='')
class Partner(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(180),nullable=False); contribution=db.Column(db.Float,default=0); withdrawals=db.Column(db.Float,default=0); notes=db.Column(db.Text,default='')
class Declaration(db.Model):
    id=db.Column(db.Integer,primary_key=True); ref_no=db.Column(db.String(80),unique=True,nullable=False); decl_type=db.Column(db.String(80),nullable=False); company_id=db.Column(db.Integer,db.ForeignKey('company.id')); status=db.Column(db.String(40),default='مفتوح'); customs_fees=db.Column(db.Float,default=0); transport_fees=db.Column(db.Float,default=0); office_fees=db.Column(db.Float,default=0); extra_fees=db.Column(db.Float,default=0); visa_fees=db.Column(db.Float,default=0); transit_fees=db.Column(db.Float,default=0); insurance_fees=db.Column(db.Float,default=0); notes=db.Column(db.Text,default=''); created_at=db.Column(db.DateTime,default=datetime.utcnow); company=db.relationship('Company')
    @property
    def total(self): return sum([(self.customs_fees or 0),(self.transport_fees or 0),(self.office_fees or 0),(self.extra_fees or 0),(self.visa_fees or 0),(self.transit_fees or 0),(self.insurance_fees or 0)])
class CashTxn(db.Model):
    id=db.Column(db.Integer,primary_key=True); txn_date=db.Column(db.Date,default=date.today); direction=db.Column(db.String(20),nullable=False); category=db.Column(db.String(120),default='عام'); amount=db.Column(db.Float,nullable=False,default=0); company_id=db.Column(db.Integer,db.ForeignKey('company.id')); description=db.Column(db.Text,default=''); reference=db.Column(db.String(120),default=''); created_by=db.Column(db.String(80),default=''); company=db.relationship('Company')
class Attachment(db.Model):
    id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(180),nullable=False); entity_type=db.Column(db.String(80),default='عام'); entity_ref=db.Column(db.String(120),default=''); filename=db.Column(db.String(255),nullable=False); content_type=db.Column(db.String(120),default='application/octet-stream'); data=db.Column(db.LargeBinary,nullable=False); uploaded_at=db.Column(db.DateTime,default=datetime.utcnow)

def get_setting(k,d=''):
    r=Setting.query.filter_by(key=k).first(); return r.value if r else d
def put_setting(k,v):
    r=Setting.query.filter_by(key=k).first()
    if r:r.value=v
    else:db.session.add(Setting(key=k,value=v))
def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get('uid'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return w
def admin_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if session.get('role')!='admin': flash('هذه العملية للمدير فقط','error'); return redirect(url_for('home'))
        return fn(*a,**kw)
    return w
def editable(): return session.get('role') in ('admin','user')

def num(x):
    try:return float(x or 0)
    except:return 0

CSS='''*{box-sizing:border-box}body{margin:0;background:#f3f6f9;font-family:Tahoma,Arial;direction:rtl;color:#162234}.top{background:#102a43;color:white;padding:13px 18px;display:flex;gap:15px;align-items:center;position:sticky;top:0}.brand{font-weight:bold;font-size:18px;margin-left:auto}.top a{color:white;text-decoration:none;padding:8px;border-radius:8px}.top a:hover{background:#ffffff1a}.wrap{max-width:1450px;margin:18px auto;padding:0 15px}.card{background:#fff;border:1px solid #dce4ea;border-radius:13px;padding:15px;margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.stat b{display:block;font-size:25px;color:#0f766e;margin-top:8px}.btn{border:0;background:#0f766e;color:#fff;padding:9px 13px;border-radius:8px;cursor:pointer}.alt{background:#475569}.danger{background:#b91c1c}input,select,textarea{width:100%;padding:9px;border:1px solid #ccd8e0;border-radius:8px}.formgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.full{grid-column:1/-1}.tablewrap{overflow:auto;border:1px solid #dce4ea;border-radius:11px}table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border-bottom:1px solid #e5e9ed;text-align:right;white-space:nowrap}th{background:#eef4f8}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.flash{padding:10px;border-radius:8px;background:#e7f7f3;margin-bottom:8px}.flash.error{background:#fdeaea;color:#8b1b1b}.muted{color:#64748b;font-size:13px}.login{max-width:420px;margin:11vh auto}.badge{background:#e7f7f3;color:#0f766e;padding:4px 8px;border-radius:99px;font-size:12px}@media print{.top,.no-print,.toolbar{display:none!important}.wrap{margin:0;max-width:none}.card{border:0}}'''
NAV='''<div class="top"><div class="brand">{{company_name}}</div><a href="{{url_for('home')}}">الرئيسية</a><a href="{{url_for('declarations')}}">البيانات</a><a href="{{url_for('companies')}}">الشركات</a><a href="{{url_for('cash')}}">الصندوق</a><a href="{{url_for('partners')}}">الشركاء</a><a href="{{url_for('attachments')}}">المرفقات</a><a href="{{url_for('reports')}}">التقارير</a>{% if session.get('role')=='admin' %}<a href="{{url_for('settings')}}">الإعدادات</a><a href="{{url_for('users')}}">المستخدمون</a>{% endif %}<a href="{{url_for('logout')}}">خروج</a></div>'''
def page(title,body,**ctx):
    return render_template_string('<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+CSS+'</style></head><body>'+NAV+'<div class="wrap">{% with ms=get_flashed_messages(with_categories=true) %}{% for c,m in ms %}<div class="flash {{c}}">{{m}}</div>{% endfor %}{% endwith %}'+body+'</div></body></html>',company_name=get_setting('company_name','نهضة سوريا للتخليص الجمركي'),**ctx)

@app.route('/health')
def health(): return {'ok':True,'app':'nahda-web'}
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip(),active=True).first()
        if u and check_password_hash(u.password_hash,request.form.get('password','')):
            session.clear(); session.update(uid=u.id,username=u.username,role=u.role); return redirect(url_for('home'))
        flash('بيانات الدخول غير صحيحة','error')
    html='''<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'''+CSS+'''</style></head><body><div class="login card"><h1>{{company}}</h1><p class="muted">نظام التخليص الجمركي والمحاسبة</p>{% with ms=get_flashed_messages(with_categories=true) %}{% for c,m in ms %}<div class="flash {{c}}">{{m}}</div>{% endfor %}{% endwith %}<form method="post"><label>اسم المستخدم</label><input name="username" required><br><br><label>كلمة المرور</label><input type="password" name="password" required><br><br><button class="btn" style="width:100%">دخول</button></form></div></body></html>'''
    return render_template_string(html,company=get_setting('company_name','نهضة سوريا للتخليص الجمركي'))
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    incoming=db.session.query(db.func.coalesce(db.func.sum(CashTxn.amount),0)).filter(CashTxn.direction=='وارد').scalar() or 0; outgoing=db.session.query(db.func.coalesce(db.func.sum(CashTxn.amount),0)).filter(CashTxn.direction=='صادر').scalar() or 0; capital=sum((p.contribution or 0)-(p.withdrawals or 0) for p in Partner.query.all())
    body='''<h1>لوحة التحكم</h1><div class="grid"><div class="card stat">رصيد الصندوق<b>{{(incoming-outgoing)|round(2)}}</b></div><div class="card stat">رأس المال<b>{{capital|round(2)}}</b></div><div class="card stat">الوارد<b>{{incoming|round(2)}}</b></div><div class="card stat">الصادر<b>{{outgoing|round(2)}}</b></div><div class="card stat">الشركات<b>{{companies}}</b></div><div class="card stat">البيانات المفتوحة<b>{{open_decl}}</b></div></div><div class="card"><h2>آخر حركات الصندوق</h2><div class="tablewrap"><table><tr><th>التاريخ</th><th>الحركة</th><th>التصنيف</th><th>المبلغ</th><th>البيان</th></tr>{% for x in rows %}<tr><td>{{x.txn_date}}</td><td>{{x.direction}}</td><td>{{x.category}}</td><td>{{x.amount}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div></div>'''
    return page('الرئيسية',body,incoming=incoming,outgoing=outgoing,capital=capital,companies=Company.query.count(),open_decl=Declaration.query.filter(Declaration.status!='مغلق').count(),rows=CashTxn.query.order_by(CashTxn.id.desc()).limit(10).all())

@app.route('/companies',methods=['GET','POST'])
@login_required
def companies():
    if request.method=='POST' and editable(): db.session.add(Company(name=request.form['name'],opening_balance=num(request.form.get('opening_balance')),phone=request.form.get('phone',''),notes=request.form.get('notes',''))); db.session.commit(); return redirect(url_for('companies'))
    body='''<h1>الشركات</h1>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div><label>اسم الشركة</label><input name="name" required></div><div><label>رصيد افتتاحي</label><input type="number" step="0.01" name="opening_balance"></div><div><label>الهاتف</label><input name="phone"></div><div><label>ملاحظات</label><input name="notes"></div></div><br><button class="btn">إضافة شركة</button></form></div>{% endif %}<div class="tablewrap"><table><tr><th>ID</th><th>الاسم</th><th>الرصيد الافتتاحي</th><th>الهاتف</th><th>ملاحظات</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.name}}</td><td>{{x.opening_balance}}</td><td>{{x.phone}}</td><td>{{x.notes}}</td></tr>{% endfor %}</table></div>'''
    return page('الشركات',body,rows=Company.query.order_by(Company.id.desc()).all(),edit=editable())

@app.route('/declarations',methods=['GET','POST'])
@login_required
def declarations():
    if request.method=='POST' and editable():
        ref=request.form['ref_no'].strip()
        if Declaration.query.filter_by(ref_no=ref).first(): flash('رقم البيان موجود مسبقاً','error')
        else:
            db.session.add(Declaration(ref_no=ref,decl_type=request.form['decl_type'],company_id=request.form.get('company_id') or None,status=request.form.get('status','مفتوح'),customs_fees=num(request.form.get('customs_fees')),transport_fees=num(request.form.get('transport_fees')),office_fees=num(request.form.get('office_fees')),extra_fees=num(request.form.get('extra_fees')),visa_fees=num(request.form.get('visa_fees')),transit_fees=num(request.form.get('transit_fees')),insurance_fees=num(request.form.get('insurance_fees')),notes=request.form.get('notes',''))); db.session.commit(); return redirect(url_for('declarations'))
    comps=Company.query.order_by(Company.name).all(); rows=Declaration.query.order_by(Declaration.id.desc()).all()
    body='''<div class="toolbar"><h1 style="margin-left:auto">البيانات الجمركية</h1><button class="btn alt" onclick="window.print()">حفظ PDF</button></div>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div><label>رقم البيان</label><input name="ref_no" required></div><div><label>النوع</label><select name="decl_type"><option>بيان داخلي</option><option>ترانزيت</option><option>مناقلة</option><option>ترانزيت بيان داخلي</option></select></div><div><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div><div><label>الحالة</label><select name="status"><option>مفتوح</option><option>مسودة</option><option>قيد المعالجة</option><option>بانتظار الدفع</option><option>مغلق</option></select></div><div><label>رسوم جمركية</label><input type="number" step="0.01" name="customs_fees"></div><div><label>النقل</label><input type="number" step="0.01" name="transport_fees"></div><div><label>رسوم المكتب</label><input type="number" step="0.01" name="office_fees"></div><div><label>فيزا</label><input type="number" step="0.01" name="visa_fees"></div><div><label>عبور</label><input type="number" step="0.01" name="transit_fees"></div><div><label>تأمين</label><input type="number" step="0.01" name="insurance_fees"></div><div><label>إضافي</label><input type="number" step="0.01" name="extra_fees"></div><div class="full"><label>ملاحظات</label><input name="notes"></div></div><br><button class="btn">حفظ البيان</button></form></div>{% endif %}<div class="tablewrap"><table><tr><th>ID</th><th>الرقم</th><th>النوع</th><th>الشركة</th><th>الحالة</th><th>الإجمالي</th><th>التاريخ</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.ref_no}}</td><td>{{x.decl_type}}</td><td>{{x.company.name if x.company else ''}}</td><td><span class="badge">{{x.status}}</span></td><td>{{x.total|round(2)}}</td><td>{{x.created_at.strftime('%Y-%m-%d')}}</td></tr>{% endfor %}</table></div>'''
    return page('البيانات',body,rows=rows,comps=comps,edit=editable())

@app.route('/cash',methods=['GET','POST'])
@login_required
def cash():
    if request.method=='POST' and editable(): db.session.add(CashTxn(txn_date=datetime.strptime(request.form.get('txn_date') or str(date.today()),'%Y-%m-%d').date(),direction=request.form['direction'],category=request.form.get('category','عام'),amount=num(request.form.get('amount')),company_id=request.form.get('company_id') or None,description=request.form.get('description',''),reference=request.form.get('reference',''),created_by=session.get('username',''))); db.session.commit(); return redirect(url_for('cash'))
    rows=CashTxn.query.order_by(CashTxn.id.desc()).limit(500).all(); incoming=sum(x.amount for x in rows if x.direction=='وارد'); outgoing=sum(x.amount for x in rows if x.direction=='صادر'); comps=Company.query.order_by(Company.name).all()
    body='''<div class="toolbar"><h1 style="margin-left:auto">الصندوق</h1><button class="btn alt" onclick="window.print()">حفظ PDF</button></div><div class="grid"><div class="card stat">الوارد<b>{{incoming|round(2)}}</b></div><div class="card stat">الصادر<b>{{outgoing|round(2)}}</b></div><div class="card stat">الرصيد<b>{{(incoming-outgoing)|round(2)}}</b></div></div>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div><label>التاريخ</label><input type="date" name="txn_date" value="{{today}}"></div><div><label>الحركة</label><select name="direction"><option>وارد</option><option>صادر</option></select></div><div><label>التصنيف</label><input name="category" value="عام"></div><div><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div><div><label>المرجع</label><input name="reference"></div><div class="full"><label>البيان</label><input name="description"></div></div><br><button class="btn">تسجيل</button></form></div>{% endif %}<div class="tablewrap"><table><tr><th>التاريخ</th><th>الحركة</th><th>التصنيف</th><th>الشركة</th><th>المبلغ</th><th>المرجع</th><th>البيان</th></tr>{% for x in rows %}<tr><td>{{x.txn_date}}</td><td>{{x.direction}}</td><td>{{x.category}}</td><td>{{x.company.name if x.company else ''}}</td><td>{{x.amount}}</td><td>{{x.reference}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div>'''
    return page('الصندوق',body,rows=rows,comps=comps,incoming=incoming,outgoing=outgoing,edit=editable(),today=str(date.today()))

@app.route('/partners',methods=['GET','POST'])
@login_required
def partners():
    if request.method=='POST' and editable(): db.session.add(Partner(name=request.form['name'],contribution=num(request.form.get('contribution')),withdrawals=num(request.form.get('withdrawals')),notes=request.form.get('notes',''))); db.session.commit(); return redirect(url_for('partners'))
    rows=Partner.query.order_by(Partner.id).all(); total=sum((x.contribution or 0)-(x.withdrawals or 0) for x in rows)
    body='''<h1>الشركاء ورأس المال</h1><div class="card stat">إجمالي رأس المال المدور<b>{{total|round(2)}}</b></div>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div><label>اسم الشريك</label><input name="name" required></div><div><label>المساهمة</label><input type="number" step="0.01" name="contribution"></div><div><label>السحوبات</label><input type="number" step="0.01" name="withdrawals"></div><div><label>ملاحظات</label><input name="notes"></div></div><br><button class="btn">إضافة</button></form></div>{% endif %}<div class="tablewrap"><table><tr><th>الشريك</th><th>المساهمة</th><th>السحوبات</th><th>الرصيد</th></tr>{% for x in rows %}<tr><td>{{x.name}}</td><td>{{x.contribution}}</td><td>{{x.withdrawals}}</td><td>{{(x.contribution-x.withdrawals)|round(2)}}</td></tr>{% endfor %}</table></div>'''
    return page('الشركاء',body,rows=rows,total=total,edit=editable())

@app.route('/attachments',methods=['GET','POST'])
@login_required
def attachments():
    if request.method=='POST' and editable():
        f=request.files.get('file')
        if f and f.filename: db.session.add(Attachment(title=request.form.get('title') or f.filename,entity_type=request.form.get('entity_type','عام'),entity_ref=request.form.get('entity_ref',''),filename=f.filename,content_type=f.mimetype or 'application/octet-stream',data=f.read())); db.session.commit(); return redirect(url_for('attachments'))
    rows=Attachment.query.order_by(Attachment.id.desc()).all()
    body='''<h1>المرفقات</h1>{% if edit %}<div class="card no-print"><form method="post" enctype="multipart/form-data"><div class="formgrid"><div><label>العنوان</label><input name="title"></div><div><label>القسم</label><select name="entity_type"><option>بيان</option><option>فاتورة</option><option>رحلة</option><option>عام</option></select></div><div><label>المرجع</label><input name="entity_ref"></div><div><label>الملف</label><input type="file" name="file" required></div></div><br><button class="btn">رفع</button></form></div>{% endif %}<div class="tablewrap"><table><tr><th>العنوان</th><th>القسم</th><th>المرجع</th><th>الملف</th><th></th></tr>{% for x in rows %}<tr><td>{{x.title}}</td><td>{{x.entity_type}}</td><td>{{x.entity_ref}}</td><td>{{x.filename}}</td><td><a class="btn alt" href="{{url_for('attachment',aid=x.id)}}">فتح</a></td></tr>{% endfor %}</table></div>'''
    return page('المرفقات',body,rows=rows,edit=editable())
@app.route('/attachment/<int:aid>')
@login_required
def attachment(aid):
    a=Attachment.query.get_or_404(aid); return send_file(io.BytesIO(a.data),mimetype=a.content_type,download_name=a.filename,as_attachment=False)

@app.route('/reports')
@login_required
def reports():
    rows=CashTxn.query.order_by(CashTxn.txn_date,CashTxn.id).all(); incoming=sum(x.amount for x in rows if x.direction=='وارد'); outgoing=sum(x.amount for x in rows if x.direction=='صادر')
    body='''<div class="toolbar"><h1 style="margin-left:auto">الجرد والتقارير</h1><button class="btn alt" onclick="window.print()">حفظ PDF / طباعة</button></div><div class="grid"><div class="card stat">الوارد<b>{{incoming|round(2)}}</b></div><div class="card stat">الصادر<b>{{outgoing|round(2)}}</b></div><div class="card stat">الصافي<b>{{(incoming-outgoing)|round(2)}}</b></div></div><div class="tablewrap"><table><tr><th>التاريخ</th><th>الحركة</th><th>التصنيف</th><th>الشركة</th><th>المبلغ</th><th>المرجع</th><th>البيان</th></tr>{% for x in rows %}<tr><td>{{x.txn_date}}</td><td>{{x.direction}}</td><td>{{x.category}}</td><td>{{x.company.name if x.company else ''}}</td><td>{{x.amount}}</td><td>{{x.reference}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div>'''
    return page('التقارير',body,rows=rows,incoming=incoming,outgoing=outgoing)

@app.route('/settings',methods=['GET','POST'])
@login_required
@admin_required
def settings():
    if request.method=='POST':
        for k in ('company_name','address','phone','currency','report_footer'): put_setting(k,request.form.get(k,''))
        db.session.commit(); return redirect(url_for('settings'))
    vals={k:get_setting(k,'') for k in ('company_name','address','phone','currency','report_footer')}
    body='''<h1>إعدادات الشركة</h1><div class="card"><form method="post"><div class="formgrid"><div class="full"><label>اسم الشركة</label><input name="company_name" value="{{v.company_name}}"></div><div><label>العنوان</label><input name="address" value="{{v.address}}"></div><div><label>الهاتف</label><input name="phone" value="{{v.phone}}"></div><div><label>العملة</label><input name="currency" value="{{v.currency}}"></div><div class="full"><label>تذييل التقارير</label><input name="report_footer" value="{{v.report_footer}}"></div></div><br><button class="btn">حفظ</button></form></div>'''
    return page('الإعدادات',body,v=vals)

@app.route('/users',methods=['GET','POST'])
@login_required
@admin_required
def users():
    if request.method=='POST':
        u=request.form['username'].strip()
        if User.query.filter_by(username=u).first(): flash('اسم المستخدم موجود','error')
        else: db.session.add(User(username=u,password_hash=generate_password_hash(request.form['password']),role=request.form.get('role','user'))); db.session.commit()
        return redirect(url_for('users'))
    body='''<h1>المستخدمون والصلاحيات</h1><div class="card no-print"><form method="post"><div class="formgrid"><div><label>اسم المستخدم</label><input name="username" required></div><div><label>كلمة المرور</label><input type="password" name="password" required></div><div><label>الصلاحية</label><select name="role"><option value="admin">مدير</option><option value="user">موظف</option><option value="viewer">مشاهدة فقط</option></select></div></div><br><button class="btn">إضافة</button></form></div><div class="tablewrap"><table><tr><th>المستخدم</th><th>الصلاحية</th><th>الحالة</th></tr>{% for x in rows %}<tr><td>{{x.username}}</td><td>{{x.role}}</td><td>{{'فعال' if x.active else 'موقوف'}}</td></tr>{% endfor %}</table></div>'''
    return page('المستخدمون',body,rows=User.query.order_by(User.id).all())

with app.app_context():
    db.create_all()
    if not User.query.first(): db.session.add(User(username=os.environ.get('ADMIN_USER','admin'),password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD','Nahda2026!')),role='admin'))
    if not Setting.query.filter_by(key='company_name').first(): db.session.add(Setting(key='company_name',value='نهضة سوريا للتخليص الجمركي والنقل')); db.session.add(Setting(key='currency',value='USD'))
    db.session.commit()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
