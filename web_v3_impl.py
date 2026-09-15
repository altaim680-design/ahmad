# -*- coding: utf-8 -*-
import os, io, json
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, send_file, render_template_string, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','nahda-web-v3-change-me')
app.config['MAX_CONTENT_LENGTH'] = 20*1024*1024
_db_url = os.environ.get('DATABASE_URL','sqlite:///nahda_web.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://','postgresql://',1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -------------------- existing shared tables --------------------
class User(db.Model):
    __tablename__='user'
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(20),default='user')
    active=db.Column(db.Boolean,default=True)

class Setting(db.Model):
    __tablename__='setting'
    id=db.Column(db.Integer,primary_key=True)
    key=db.Column(db.String(80),unique=True,nullable=False)
    value=db.Column(db.Text,default='')

class Company(db.Model):
    __tablename__='company'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(180),nullable=False)
    opening_balance=db.Column(db.Float,default=0)
    phone=db.Column(db.String(80),default='')
    notes=db.Column(db.Text,default='')

# -------------------- customs V3 tables --------------------
class CustomsDeclaration(db.Model):
    __tablename__='v3_customs_declarations'
    id=db.Column(db.Integer,primary_key=True)
    declaration_no=db.Column(db.String(100),unique=True,nullable=False)
    manifest_no=db.Column(db.String(100),default='')
    declaration_date=db.Column(db.String(20),default='')
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    customer_name=db.Column(db.String(180),default='')
    vehicle_no=db.Column(db.String(120),default='')
    trailer_no=db.Column(db.String(120),default='')
    driver=db.Column(db.String(180),default='')
    origin=db.Column(db.String(180),default='')
    destination=db.Column(db.String(180),default='')
    cargo_description=db.Column(db.Text,default='')
    quantity=db.Column(db.Float,default=0)
    weight=db.Column(db.Float,default=0)
    origin_country=db.Column(db.String(120),default='')
    declaration_type=db.Column(db.String(100),default='بيان داخلي')
    customs_office=db.Column(db.String(180),default='')
    exporter_name=db.Column(db.String(180),default='')
    importer_name=db.Column(db.String(180),default='')
    consignee_name=db.Column(db.String(180),default='')
    broker_name=db.Column(db.String(180),default='')
    declarant_name=db.Column(db.String(180),default='')
    border_point=db.Column(db.String(180),default='باب الهوى')
    transport_mode=db.Column(db.String(120),default='بري')
    country_destination=db.Column(db.String(120),default='')
    package_count=db.Column(db.Float,default=0)
    package_type=db.Column(db.String(100),default='')
    gross_weight=db.Column(db.Float,default=0)
    net_weight=db.Column(db.Float,default=0)
    goods_value=db.Column(db.Float,default=0)
    currency=db.Column(db.String(20),default='USD')
    invoice_no=db.Column(db.String(100),default='')
    shipping_doc_no=db.Column(db.String(100),default='')
    container_no=db.Column(db.String(100),default='')
    seal_no=db.Column(db.String(100),default='')
    loading_date=db.Column(db.String(20),default='')
    expected_arrival_date=db.Column(db.String(20),default='')
    customs_reference=db.Column(db.String(120),default='')
    transport_job_id=db.Column(db.Integer)
    status=db.Column(db.String(40),default='مسودة')
    note=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    company=db.relationship('Company')

class DeclarationCharge(db.Model):
    __tablename__='v3_declaration_charges'
    id=db.Column(db.Integer,primary_key=True)
    declaration_id=db.Column(db.Integer,db.ForeignKey('v3_customs_declarations.id',ondelete='CASCADE'),nullable=False)
    charge_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    charge_type=db.Column(db.String(100),nullable=False)
    description=db.Column(db.Text,default='')
    amount=db.Column(db.Float,default=0)
    required=db.Column(db.Boolean,default=True)
    paid=db.Column(db.Float,default=0)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    declaration=db.relationship('CustomsDeclaration',backref=db.backref('charges',lazy=True,cascade='all, delete-orphan'))

class TransportJob(db.Model):
    __tablename__='v3_transport_jobs'
    id=db.Column(db.Integer,primary_key=True)
    declaration_id=db.Column(db.Integer,db.ForeignKey('v3_customs_declarations.id'))
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    manifest_no=db.Column(db.String(120),default='')
    turkish_vehicle=db.Column(db.String(120),default='')
    vehicle_location=db.Column(db.String(180),default='')
    vehicle_city=db.Column(db.String(180),default='')
    company_price=db.Column(db.Float,default=0)
    turkish_purchase_price=db.Column(db.Float,default=0)
    syrian_vehicle=db.Column(db.String(120),default='')
    foreign_vehicle=db.Column(db.String(120),default='')
    foreign_driver=db.Column(db.String(180),default='')
    foreign_phone=db.Column(db.String(80),default='')
    destination=db.Column(db.String(180),default='')
    cargo_description=db.Column(db.Text,default='')
    nassib_payment=db.Column(db.Float,default=0)
    nassib_due=db.Column(db.Float,default=0)
    nassib_balance=db.Column(db.Float,default=0)
    total_cost=db.Column(db.Float,default=0)
    profit=db.Column(db.Float,default=0)
    status=db.Column(db.String(40),default='مفتوحة')
    note=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    declaration=db.relationship('CustomsDeclaration',foreign_keys=[declaration_id])
    company=db.relationship('Company')

class TransportCost(db.Model):
    __tablename__='v3_transport_costs'
    id=db.Column(db.Integer,primary_key=True)
    job_id=db.Column(db.Integer,db.ForeignKey('v3_transport_jobs.id',ondelete='CASCADE'),nullable=False)
    stage=db.Column(db.String(120),nullable=False)
    description=db.Column(db.Text,default='')
    amount=db.Column(db.Float,default=0)
    vehicle_no=db.Column(db.String(120),default='')
    driver=db.Column(db.String(180),default='')
    phone=db.Column(db.String(80),default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    job=db.relationship('TransportJob',backref=db.backref('costs',lazy=True,cascade='all, delete-orphan'))

class TransportPayment(db.Model):
    __tablename__='v3_transport_payments'
    id=db.Column(db.Integer,primary_key=True)
    job_id=db.Column(db.Integer,db.ForeignKey('v3_transport_jobs.id',ondelete='CASCADE'),nullable=False)
    payment_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    beneficiary=db.Column(db.String(180),default='')
    amount=db.Column(db.Float,default=0)
    description=db.Column(db.Text,default='')
    payment_party=db.Column(db.String(100),default='أخرى')
    direction=db.Column(db.String(10),default='out')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    job=db.relationship('TransportJob',backref=db.backref('payments',lazy=True,cascade='all, delete-orphan'))

class TransportStage(db.Model):
    __tablename__='v3_transport_stage_log'
    id=db.Column(db.Integer,primary_key=True)
    job_id=db.Column(db.Integer,db.ForeignKey('v3_transport_jobs.id',ondelete='CASCADE'),nullable=False)
    stage=db.Column(db.String(120),nullable=False)
    status=db.Column(db.String(40),default='مفتوحة')
    started_at=db.Column(db.String(30),default='')
    completed_at=db.Column(db.String(30),default='')
    note=db.Column(db.Text,default='')
    location=db.Column(db.String(180),default='')
    job=db.relationship('TransportJob',backref=db.backref('stages',lazy=True,cascade='all, delete-orphan'))
    __table_args__=(db.UniqueConstraint('job_id','stage',name='uq_v3_job_stage'),)

class TurkishVehicleInvoice(db.Model):
    __tablename__='v3_turkish_vehicle_invoices'
    id=db.Column(db.Integer,primary_key=True)
    job_id=db.Column(db.Integer,db.ForeignKey('v3_transport_jobs.id',ondelete='CASCADE'),nullable=False)
    invoice_no=db.Column(db.String(120),unique=True,nullable=False)
    invoice_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    amount=db.Column(db.Float,default=0)
    manifest_no=db.Column(db.String(120),default='')
    vehicle_no=db.Column(db.String(120),default='')
    cargo_description=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    job=db.relationship('TransportJob',backref=db.backref('turkish_invoices',lazy=True,cascade='all, delete-orphan'))

class InternalShipment(db.Model):
    __tablename__='v3_internal_shipments'
    id=db.Column(db.Integer,primary_key=True)
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    shipment_no=db.Column(db.String(120),unique=True,nullable=False)
    shipment_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    customer_name=db.Column(db.String(180),default='')
    phone=db.Column(db.String(80),default='')
    origin=db.Column(db.String(180),default='')
    destination=db.Column(db.String(180),default='')
    vehicle_no=db.Column(db.String(120),default='')
    driver=db.Column(db.String(180),default='')
    description=db.Column(db.Text,default='')
    revenue=db.Column(db.Float,default=0)
    cost=db.Column(db.Float,default=0)
    profit=db.Column(db.Float,default=0)
    status=db.Column(db.String(40),default='مفتوحة')
    cash_received=db.Column(db.Float,default=0)
    cash_paid=db.Column(db.Float,default=0)
    transport_job_id=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    company=db.relationship('Company')

class SalesInvoice(db.Model):
    __tablename__='v3_sales_invoices'
    id=db.Column(db.Integer,primary_key=True)
    invoice_no=db.Column(db.String(100),unique=True,nullable=False)
    invoice_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    declaration_id=db.Column(db.Integer,db.ForeignKey('v3_customs_declarations.id'))
    job_id=db.Column(db.Integer,db.ForeignKey('v3_transport_jobs.id'))
    description=db.Column(db.Text,default='')
    subtotal=db.Column(db.Float,default=0)
    discount=db.Column(db.Float,default=0)
    total=db.Column(db.Float,default=0)
    paid=db.Column(db.Float,default=0)
    payment_method=db.Column(db.String(60),default='نقدي')
    status=db.Column(db.String(30),default='غير مسددة')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    company=db.relationship('Company')
    declaration=db.relationship('CustomsDeclaration')
    job=db.relationship('TransportJob')
    @property
    def remaining(self): return max(0,float(self.total or 0)-float(self.paid or 0))

class InvoiceLine(db.Model):
    __tablename__='v3_invoice_lines'
    id=db.Column(db.Integer,primary_key=True)
    invoice_id=db.Column(db.Integer,db.ForeignKey('v3_sales_invoices.id',ondelete='CASCADE'),nullable=False)
    description=db.Column(db.Text,default='')
    qty=db.Column(db.Float,default=1)
    unit_price=db.Column(db.Float,default=0)
    amount=db.Column(db.Float,default=0)
    invoice=db.relationship('SalesInvoice',backref=db.backref('lines',lazy=True,cascade='all, delete-orphan'))

class CashTransaction(db.Model):
    __tablename__='v3_cash_transactions'
    id=db.Column(db.Integer,primary_key=True)
    txn_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    direction=db.Column(db.String(10),nullable=False) # in/out
    category=db.Column(db.String(120),default='عام')
    amount=db.Column(db.Float,default=0)
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    description=db.Column(db.Text,default='')
    reference=db.Column(db.String(120),default='')
    created_by=db.Column(db.String(80),default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    company=db.relationship('Company')

class Expense(db.Model):
    __tablename__='v3_expenses'
    id=db.Column(db.Integer,primary_key=True)
    expense_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    category=db.Column(db.String(120),default='مصاريف عامة')
    amount=db.Column(db.Float,default=0)
    description=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class Shareholder(db.Model):
    __tablename__='v3_shareholders'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(180),unique=True,nullable=False)
    phone=db.Column(db.String(80),default='')
    capital_commitment=db.Column(db.Float,default=0)
    capital_percentage=db.Column(db.Float,default=0)
    note=db.Column(db.Text,default='')

class CapitalMovement(db.Model):
    __tablename__='v3_capital_movements'
    id=db.Column(db.Integer,primary_key=True)
    shareholder_id=db.Column(db.Integer,db.ForeignKey('v3_shareholders.id',ondelete='CASCADE'),nullable=False)
    amount=db.Column(db.Float,default=0)
    txn_type=db.Column(db.String(20),nullable=False) # capital/additional/draw
    txn_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    note=db.Column(db.Text,default='')
    shareholder=db.relationship('Shareholder',backref=db.backref('movements',lazy=True,cascade='all, delete-orphan'))

class Account(db.Model):
    __tablename__='v3_accounts'
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(20),unique=True,nullable=False)
    name=db.Column(db.String(180),nullable=False)
    type=db.Column(db.String(30),nullable=False)
    active=db.Column(db.Boolean,default=True)

class JournalEntry(db.Model):
    __tablename__='v3_journal_entries'
    id=db.Column(db.Integer,primary_key=True)
    entry_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    description=db.Column(db.Text,nullable=False)
    ref_type=db.Column(db.String(80),default='')
    ref_id=db.Column(db.Integer)
    posted=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class JournalLine(db.Model):
    __tablename__='v3_journal_lines'
    id=db.Column(db.Integer,primary_key=True)
    entry_id=db.Column(db.Integer,db.ForeignKey('v3_journal_entries.id',ondelete='CASCADE'),nullable=False)
    account_id=db.Column(db.Integer,db.ForeignKey('v3_accounts.id'),nullable=False)
    debit=db.Column(db.Float,default=0)
    credit=db.Column(db.Float,default=0)
    note=db.Column(db.Text,default='')
    entry=db.relationship('JournalEntry',backref=db.backref('lines',lazy=True,cascade='all, delete-orphan'))
    account=db.relationship('Account')

class V3Attachment(db.Model):
    __tablename__='v3_attachments'
    id=db.Column(db.Integer,primary_key=True)
    source_type=db.Column(db.String(60),default='عام')
    source_id=db.Column(db.Integer)
    category=db.Column(db.String(100),default='أخرى')
    original_name=db.Column(db.String(255),nullable=False)
    mime_type=db.Column(db.String(120),default='application/octet-stream')
    data=db.Column(db.LargeBinary,nullable=False)
    note=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class ServiceCase(db.Model):
    __tablename__='v3_service_cases'
    id=db.Column(db.Integer,primary_key=True)
    case_no=db.Column(db.String(120),unique=True,nullable=False)
    case_type=db.Column(db.String(100),nullable=False)
    company_id=db.Column(db.Integer,db.ForeignKey('company.id'))
    case_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    declaration_no=db.Column(db.String(120),default='')
    manifest_no=db.Column(db.String(120),default='')
    customer_name=db.Column(db.String(180),default='')
    vehicle_no=db.Column(db.String(120),default='')
    driver=db.Column(db.String(180),default='')
    origin=db.Column(db.String(180),default='')
    destination=db.Column(db.String(180),default='')
    cargo_description=db.Column(db.Text,default='')
    status=db.Column(db.String(40),default='مفتوحة')
    note=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    company=db.relationship('Company')

class ServiceCaseCharge(db.Model):
    __tablename__='v3_service_case_charges'
    id=db.Column(db.Integer,primary_key=True)
    case_id=db.Column(db.Integer,db.ForeignKey('v3_service_cases.id',ondelete='CASCADE'),nullable=False)
    charge_type=db.Column(db.String(120),nullable=False)
    description=db.Column(db.Text,default='')
    amount=db.Column(db.Float,default=0)
    required=db.Column(db.Boolean,default=True)
    billable=db.Column(db.Boolean,default=True)
    paid=db.Column(db.Float,default=0)
    case=db.relationship('ServiceCase',backref=db.backref('charges',lazy=True,cascade='all, delete-orphan'))

class ServiceCasePayment(db.Model):
    __tablename__='v3_service_case_payments'
    id=db.Column(db.Integer,primary_key=True)
    case_id=db.Column(db.Integer,db.ForeignKey('v3_service_cases.id',ondelete='CASCADE'),nullable=False)
    payment_date=db.Column(db.String(20),default=lambda:date.today().isoformat())
    amount=db.Column(db.Float,default=0)
    direction=db.Column(db.String(20),default='receipt')
    description=db.Column(db.Text,default='')
    case=db.relationship('ServiceCase',backref=db.backref('payments',lazy=True,cascade='all, delete-orphan'))

class AuditLog(db.Model):
    __tablename__='v3_audit_log'
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),default='')
    action=db.Column(db.String(180),nullable=False)
    entity=db.Column(db.String(80),default='')
    entity_id=db.Column(db.Integer)
    details=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

# -------------------- helpers --------------------
def fnum(x):
    try: return float(str(x or '0').replace(',','').replace('$','').strip() or 0)
    except Exception: return 0.0

def sval(x): return (x or '').strip() if isinstance(x,str) else (x or '')

def get_setting(k,d=''):
    r=Setting.query.filter_by(key=k).first()
    return r.value if r and r.value is not None else d

def put_setting(k,v):
    r=Setting.query.filter_by(key=k).first()
    if r: r.value=v
    else: db.session.add(Setting(key=k,value=v))

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get('uid'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return w

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def w(*a,**kw):
            if session.get('role') not in roles:
                flash('ليس لديك صلاحية لهذه العملية','error'); return redirect(request.referrer or url_for('home'))
            return fn(*a,**kw)
        return w
    return deco

def can_edit(): return session.get('role') in ('admin','user','transport','accountant')
def can_finance(): return session.get('role') in ('admin','accountant')

def audit(action,entity='',entity_id=None,details=''):
    try:
        db.session.add(AuditLog(username=session.get('username','system'),action=action,entity=entity,entity_id=entity_id,details=details)); db.session.commit()
    except Exception:
        db.session.rollback()

def next_invoice_no():
    last=SalesInvoice.query.order_by(SalesInvoice.id.desc()).first()
    n=(last.id+1) if last else 1
    return f'INV-{date.today().year}-{n:05d}'

def next_case_no():
    last=ServiceCase.query.order_by(ServiceCase.id.desc()).first(); n=(last.id+1 if last else 1)
    return f'CASE-{date.today().year}-{n:05d}'

def account(code): return Account.query.filter_by(code=code).first()

def journal(desc,lines,ref_type='',ref_id=None,entry_date=None):
    e=JournalEntry(entry_date=entry_date or date.today().isoformat(),description=desc,ref_type=ref_type,ref_id=ref_id,posted=True)
    db.session.add(e); db.session.flush()
    for code,debit,credit,note in lines:
        a=account(code)
        if a: db.session.add(JournalLine(entry_id=e.id,account_id=a.id,debit=fnum(debit),credit=fnum(credit),note=note or ''))
    return e

def company_balance(company_id):
    c=Company.query.get(company_id)
    if not c:return 0
    inv=sum(float(x.total or 0) for x in SalesInvoice.query.filter_by(company_id=company_id).all())
    paid=sum(float(x.paid or 0) for x in SalesInvoice.query.filter_by(company_id=company_id).all())
    return float(c.opening_balance or 0)+inv-paid

def recompute_job(job):
    costs=sum(float(x.amount or 0) for x in job.costs)
    pay_out=sum(float(x.amount or 0) for x in job.payments if x.direction=='out')
    job.total_cost=costs+pay_out
    job.nassib_balance=float(job.nassib_due or 0)-float(job.nassib_payment or 0)
    job.profit=float(job.company_price or 0)-float(job.turkish_purchase_price or 0)-float(job.total_cost or 0)

DEFAULT_ACCOUNTS=[
('1000','الصندوق','asset'),('1010','البنك','asset'),('1100','ذمم العملاء','asset'),('1200','عهد وسلف','asset'),
('2000','ذمم الموردين','liability'),('2100','ديون أخرى','liability'),('3000','رأس المال','equity'),('3100','أرباح محتجزة','equity'),
('4000','إيرادات التخليص','revenue'),('4010','إيرادات الترانزيت','revenue'),('4020','إيرادات السيارات','revenue'),
('4030','إيرادات الطوابع','revenue'),('4040','رسوم وعمولات البيانات','revenue'),('4050','أتعاب ومعاملات المكتب','revenue'),
('4060','إيرادات إضافية / سيارة سورية','revenue'),('5000','مصاريف تشغيل','expense'),('5010','رواتب وأجور','expense'),
('5020','مصاريف سيارات ونقل','expense'),('5030','رسوم وعبور وفيزا','expense'),('5040','مصاريف إدارية','expense')]

# -------------------- UI --------------------
CSS=r'''*{box-sizing:border-box}html{direction:rtl}body{margin:0;background:#f4f7fb;font-family:Tahoma,Arial,sans-serif;color:#172033}.layout{display:flex;min-height:100vh}.side{width:255px;background:linear-gradient(180deg,#0b1f33,#102a43 55%,#0c3b3a);color:#fff;padding:16px 12px;position:sticky;top:0;height:100vh;overflow:auto}.brand{padding:10px 10px 18px;border-bottom:1px solid #ffffff20;margin-bottom:10px}.brand h2{font-size:17px;margin:0 0 5px}.brand small{color:#b7c7d8}.side a{display:flex;gap:8px;align-items:center;color:#eaf1f8;text-decoration:none;padding:10px 11px;margin:3px 0;border-radius:10px;font-size:14px}.side a:hover,.side a.active{background:#ffffff16}.main{flex:1;min-width:0}.top{height:64px;background:#fff;border-bottom:1px solid #e4eaf0;display:flex;align-items:center;padding:0 22px;position:sticky;top:0;z-index:3}.top .title{font-weight:700;color:#102a43}.top .user{margin-right:auto;color:#64748b;font-size:13px}.content{padding:22px;max-width:1600px;margin:auto}.hero{background:linear-gradient(135deg,#0f766e,#123b5d);color:#fff;border-radius:18px;padding:20px 22px;margin-bottom:18px;box-shadow:0 10px 30px #102a4320}.hero h1{margin:0 0 7px;font-size:25px}.hero p{margin:0;color:#d8f3ef}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:13px}.card{background:#fff;border:1px solid #e3e9ef;border-radius:15px;padding:15px;box-shadow:0 4px 14px #0f172a08;margin-bottom:14px}.stat{border-top:4px solid #0f766e}.stat .n{font-size:28px;font-weight:800;color:#0f766e;margin-top:7px}.stat .label{color:#64748b;font-size:13px}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.toolbar h2{margin:0 auto 0 0}.btn{display:inline-block;border:0;background:#0f766e;color:#fff;text-decoration:none;padding:9px 13px;border-radius:9px;cursor:pointer;font-family:inherit;font-size:13px}.btn:hover{filter:brightness(.96)}.blue{background:#2563eb}.dark{background:#334155}.amber{background:#d97706}.red{background:#b91c1c}.gray{background:#64748b}.green{background:#15803d}.small{padding:6px 9px;font-size:12px}.tablewrap{overflow:auto;border:1px solid #e2e8f0;border-radius:12px;background:white}table{width:100%;border-collapse:collapse;min-width:800px}th,td{padding:9px 10px;border-bottom:1px solid #edf1f5;text-align:right;white-space:nowrap;font-size:13px}th{background:#f1f5f9;color:#334155;position:sticky;top:0}.formgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.field label{display:block;font-size:12px;color:#475569;font-weight:700;margin-bottom:5px}.field input,.field select,.field textarea,.search input,.search select{width:100%;padding:9px 10px;border:1px solid #cfd8e3;border-radius:9px;background:#fff;font-family:inherit}.field textarea{min-height:80px;resize:vertical}.full{grid-column:1/-1}.section-title{font-weight:800;color:#0f3a55;margin:2px 0 12px}.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#e6f6f3;color:#0f766e;font-size:11px;font-weight:700}.badge.warn{background:#fff1d6;color:#a16207}.badge.danger{background:#fee2e2;color:#991b1b}.flash{padding:11px 13px;border-radius:10px;margin-bottom:10px;background:#e8f7f4;color:#0f5f59}.flash.error{background:#fee2e2;color:#991b1b}.flash.warn{background:#fff7dc;color:#92400e}.muted{color:#64748b;font-size:12px}.search{display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:8px}.split{display:grid;grid-template-columns:1.2fr .8fr;gap:14px}.tabs{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.tabs a{padding:7px 10px;border-radius:8px;text-decoration:none;background:#e8eef4;color:#334155}.loginbg{min-height:100vh;background:radial-gradient(circle at top right,#1f6f67,#0b1f33 55%);display:grid;place-items:center;padding:20px}.login{width:min(430px,100%);background:#fff;border-radius:20px;padding:26px;box-shadow:0 30px 80px #0006}.login h1{font-size:22px;color:#102a43;margin:0 0 6px}.login .logo{width:54px;height:54px;border-radius:16px;background:#0f766e;color:white;display:grid;place-items:center;font-size:27px;margin-bottom:14px}.kpi{font-size:12px;color:#64748b}.amount{font-weight:800;color:#0f766e}.mobilebar{display:none}@media(max-width:900px){.side{display:none}.mobilebar{display:flex;overflow:auto;gap:6px;padding:8px;background:#102a43;position:sticky;top:64px;z-index:2}.mobilebar a{color:#fff;text-decoration:none;white-space:nowrap;background:#ffffff16;padding:7px 9px;border-radius:8px;font-size:12px}.content{padding:12px}.split{grid-template-columns:1fr}.search{grid-template-columns:1fr}.top{padding:0 12px}.hero h1{font-size:20px}}@media print{.side,.top,.mobilebar,.no-print,.toolbar form,.btn{display:none!important}.layout{display:block}.content{padding:0;max-width:none}.card,.hero{box-shadow:none;border:0}.hero{color:#000;background:#fff;padding:0}.hero p{color:#444}body{background:#fff}table{min-width:0}th{position:static}}'''
NAV_ITEMS=[
('⌂','الرئيسية','home'),('🗂','مركز المعاملات','case_center'),('▦','البيانات الجمركية','declarations'),('🚛','الترانزيت والرحلات','trips'),('↔','البيانات الداخلية','internal_shipments'),('▣','الفواتير','invoices'),('💼','المحاسبة','accounting'),('📒','القيود اليومية','journal_page'),('📚','دليل الحسابات','accounts_page'),('💵','الصندوق','cash'),('👥','الشركات والذمم','companies'),('🤝','الشركاء ورأس المال','shareholders'),('💸','المصروفات','expenses'),('📎','المرفقات','attachments'),('📊','التقارير والجرد','reports')]

def layout(title,body,**ctx):
    nav=''.join([f'<a href="{{{{url_for(\'{ep}\')}}}}"><span>{ic}</span>{tx}</a>' for ic,tx,ep in NAV_ITEMS])
    admin='''{% if session.get('role')=='admin' %}<a href="{{url_for('users')}}">👤 المستخدمون</a><a href="{{url_for('settings')}}">⚙ الإعدادات</a><a href="{{url_for('audit_page')}}">🛡 سجل التدقيق</a>{% endif %}<a href="{{url_for('logout')}}">↩ خروج</a>'''
    mobile=''.join([f'<a href="{{{{url_for(\'{ep}\')}}}}">{tx}</a>' for _,tx,ep in NAV_ITEMS[:9]])
    html=f'''<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body><div class="layout"><aside class="side"><div class="brand"><h2>{{{{company_name}}}}</h2><small>التخليص الجمركي • الترانزيت • المحاسبة</small></div>{nav}{admin}</aside><main class="main"><div class="top"><div class="title">{title}</div><div class="user">{{{{session.get('username')}}}} • {{{{session.get('role')}}}}</div></div><div class="mobilebar">{mobile}</div><div class="content">{{% with ms=get_flashed_messages(with_categories=true) %}}{{% for c,m in ms %}}<div class="flash {{{{c}}}}">{{{{m}}}}</div>{{% endfor %}}{{% endwith %}}{body}</div></main></div></body></html>'''
    return render_template_string(html,company_name=get_setting('company_name','نهضة سوريا للتخليص الجمركي والنقل'),**ctx)

def badge_status(s):
    s=s or ''
    cls='danger' if s in ('مغلق','مغلقة','ملغاة') else ('warn' if s in ('مسودة','بانتظار الدفع','قيد المعالجة') else '')
    return f'<span class="badge {cls}">{s}</span>'

app.jinja_env.globals['badge_status']=badge_status
app.jinja_env.globals['company_balance']=company_balance
app.jinja_env.globals['fnum']=fnum

# -------------------- auth --------------------
@app.route('/health')
def health(): return {'ok':True,'app':'nahda-web-v3','version':3}

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=sval(request.form.get('username')),active=True).first()
        if u and check_password_hash(u.password_hash,request.form.get('password','')):
            session.clear(); session.update(uid=u.id,username=u.username,role=u.role); return redirect(url_for('home'))
        flash('بيانات الدخول غير صحيحة','error')
    html=f'''<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head><body><div class="loginbg"><div class="login"><div class="logo">ن</div><h1>{{{{company}}}}</h1><div class="muted">نظام الجمارك والترانزيت والمحاسبة — Web V3</div>{{% with ms=get_flashed_messages(with_categories=true) %}}{{% for c,m in ms %}}<div class="flash {{{{c}}}}" style="margin-top:12px">{{{{m}}}}</div>{{% endfor %}}{{% endwith %}}<form method="post" style="margin-top:18px"><div class="field"><label>اسم المستخدم</label><input name="username" autocomplete="username" required></div><div class="field" style="margin-top:10px"><label>كلمة المرور</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn" style="width:100%;margin-top:16px;padding:11px">تسجيل الدخول</button></form></div></div></body></html>'''
    return render_template_string(html,company=get_setting('company_name','نهضة سوريا للتخليص الجمركي والنقل'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

# -------------------- dashboard --------------------
@app.route('/')
@login_required
def home():
    cash_in=db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount),0)).filter_by(direction='in').scalar() or 0
    cash_out=db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount),0)).filter_by(direction='out').scalar() or 0
    capital=0
    for s in Shareholder.query.all():
        capital+=sum((m.amount if m.txn_type in ('capital','additional') else -m.amount) for m in s.movements)
    due=sum(x.remaining for x in SalesInvoice.query.all())
    body='''<div class="hero"><h1>لوحة التحكم الرئيسية</h1><p>متابعة البيانات الجمركية والرحلات والفواتير والذمم والصندوق من مكان واحد.</p></div><div class="grid"><div class="card stat"><div class="label">البيانات المفتوحة</div><div class="n">{{open_decl}}</div></div><div class="card stat"><div class="label">الرحلات المفتوحة</div><div class="n">{{open_trips}}</div></div><div class="card stat"><div class="label">ذمم الفواتير</div><div class="n">{{'%.2f'|format(due)}}</div></div><div class="card stat"><div class="label">رصيد الصندوق</div><div class="n">{{'%.2f'|format(cash_in-cash_out)}}</div></div><div class="card stat"><div class="label">رأس المال المدور</div><div class="n">{{'%.2f'|format(capital)}}</div></div><div class="card stat"><div class="label">الشركات</div><div class="n">{{companies}}</div></div></div><div class="split"><div class="card"><div class="section-title">آخر البيانات</div><div class="tablewrap"><table><tr><th>البيان</th><th>النوع</th><th>الشركة</th><th>المنافيست</th><th>الحالة</th></tr>{% for x in decls %}<tr><td><a href="{{url_for('declaration_detail',did=x.id)}}">{{x.declaration_no}}</a></td><td>{{x.declaration_type}}</td><td>{{x.company.name if x.company else x.customer_name}}</td><td>{{x.manifest_no}}</td><td>{{x.status}}</td></tr>{% endfor %}</table></div></div><div class="card"><div class="section-title">آخر الرحلات</div><div class="tablewrap"><table><tr><th>#</th><th>المنافيست</th><th>المقصد</th><th>الربح</th><th>الحالة</th></tr>{% for x in trips %}<tr><td><a href="{{url_for('trip_detail',jid=x.id)}}">{{x.id}}</a></td><td>{{x.manifest_no}}</td><td>{{x.destination}}</td><td>{{'%.2f'|format(x.profit or 0)}}</td><td>{{x.status}}</td></tr>{% endfor %}</table></div></div></div>'''
    return layout('لوحة التحكم',body,open_decl=CustomsDeclaration.query.filter(CustomsDeclaration.status!='مغلق').count(),open_trips=TransportJob.query.filter(TransportJob.status!='مغلقة').count(),due=due,cash_in=cash_in,cash_out=cash_out,capital=capital,companies=Company.query.count(),decls=CustomsDeclaration.query.order_by(CustomsDeclaration.id.desc()).limit(8).all(),trips=TransportJob.query.order_by(TransportJob.id.desc()).limit(8).all())

# -------------------- companies --------------------
@app.route('/companies',methods=['GET','POST'])
@login_required
def companies():
    if request.method=='POST' and can_edit():
        name=sval(request.form.get('name'))
        if name: db.session.add(Company(name=name,opening_balance=fnum(request.form.get('opening_balance')),phone=sval(request.form.get('phone')),notes=sval(request.form.get('notes')))); db.session.commit(); audit('إضافة شركة','company',None,name)
        return redirect(url_for('companies'))
    rows=Company.query.order_by(Company.id.asc()).all()
    body='''<div class="hero"><h1>الشركات والذمم</h1><p>لكل شركة حساب مستقل، رصيد افتتاحي، وفواتير وذمم خاصة بها.</p></div>{% if edit %}<div class="card no-print"><div class="section-title">إضافة شركة</div><form method="post"><div class="formgrid"><div class="field"><label>اسم الشركة</label><input name="name" required></div><div class="field"><label>الرصيد الافتتاحي</label><input name="opening_balance" type="number" step="0.01"></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field full"><label>ملاحظات</label><input name="notes"></div></div><button class="btn" style="margin-top:10px">حفظ الشركة</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>الشركة</th><th>رصيد افتتاحي</th><th>ذمة حالية</th><th>الهاتف</th><th>ملاحظات</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.name}}</td><td>{{'%.2f'|format(x.opening_balance or 0)}}</td><td class="amount">{{'%.2f'|format(company_balance(x.id))}}</td><td>{{x.phone}}</td><td>{{x.notes}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('الشركات والذمم',body,rows=rows,edit=can_edit())

# -------------------- declarations --------------------
DECL_TYPES=['بيان داخلي','ترانزيت','مناقلة','ترانزيت بيان داخلي']
STATUSES=['مسودة','مفتوح','قيد المعالجة','بانتظار الدفع','مغلق']

@app.route('/declarations')
@login_required
def declarations():
    q=sval(request.args.get('q')); typ=sval(request.args.get('type')); st=sval(request.args.get('status'))
    query=CustomsDeclaration.query
    if q:
        like=f'%{q}%'; query=query.filter(db.or_(CustomsDeclaration.declaration_no.ilike(like),CustomsDeclaration.manifest_no.ilike(like),CustomsDeclaration.customer_name.ilike(like),CustomsDeclaration.vehicle_no.ilike(like),CustomsDeclaration.importer_name.ilike(like),CustomsDeclaration.cargo_description.ilike(like)))
    if typ and typ!='الكل': query=query.filter_by(declaration_type=typ)
    if st and st!='الكل': query=query.filter_by(status=st)
    rows=query.order_by(CustomsDeclaration.id.asc()).all()
    body='''<div class="hero"><h1>البيانات الجمركية</h1><p>كل تفاصيل البيان السوري والمنافيست والشركات والسيارات والمستندات والحساب المالي.</p></div><div class="toolbar no-print"><a class="btn" href="{{url_for('declaration_form')}}">＋ إضافة بيان</a><a class="btn blue" href="{{url_for('trip_select_declaration')}}">🚛 استيراد بيان لإنشاء رحلة</a><button class="btn dark" onclick="window.print()">حفظ PDF / طباعة</button></div><div class="card no-print"><form class="search"><input name="q" placeholder="بحث شامل: بيان، منافيست، شركة، سيارة، بضاعة..." value="{{q}}"><select name="type"><option>الكل</option>{% for x in types %}<option {% if x==typ %}selected{% endif %}>{{x}}</option>{% endfor %}</select><select name="status"><option>الكل</option>{% for x in statuses %}<option {% if x==st %}selected{% endif %}>{{x}}</option>{% endfor %}</select><button class="btn">بحث</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>رقم البيان</th><th>النوع</th><th>المنافيست</th><th>التاريخ</th><th>الشركة</th><th>السيارة</th><th>المقصد</th><th>الحالة</th><th>الرحلة</th><th>إجراء</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.declaration_no}}</td><td>{{x.declaration_type}}</td><td>{{x.manifest_no}}</td><td>{{x.declaration_date}}</td><td>{{x.company.name if x.company else x.customer_name}}</td><td>{{x.vehicle_no}}</td><td>{{x.destination}}</td><td>{{x.status}}</td><td>{{x.transport_job_id or '—'}}</td><td><a class="btn small dark" href="{{url_for('declaration_detail',did=x.id)}}">فتح</a> <a class="btn small blue" href="{{url_for('declaration_form',did=x.id)}}">تعديل</a></td></tr>{% endfor %}</table></div></div>'''
    return layout('البيانات الجمركية',body,rows=rows,q=q,typ=typ,st=st,types=DECL_TYPES,statuses=STATUSES)

@app.route('/declarations/form',methods=['GET','POST'])
@app.route('/declarations/form/<int:did>',methods=['GET','POST'])
@login_required
def declaration_form(did=None):
    if not can_edit(): flash('لا تملك صلاحية التعديل','error'); return redirect(url_for('declarations'))
    d=CustomsDeclaration.query.get(did) if did else None
    if request.method=='POST':
        no=sval(request.form.get('declaration_no'))
        other=CustomsDeclaration.query.filter_by(declaration_no=no).first()
        if other and (not d or other.id!=d.id): flash('رقم البيان مستخدم مسبقاً','error')
        else:
            if not d: d=CustomsDeclaration(declaration_no=no); db.session.add(d)
            d.declaration_no=no; d.manifest_no=sval(request.form.get('manifest_no')); d.declaration_date=sval(request.form.get('declaration_date'))
            d.company_id=request.form.get('company_id') or None; d.customer_name=sval(request.form.get('customer_name')); d.vehicle_no=sval(request.form.get('vehicle_no')); d.trailer_no=sval(request.form.get('trailer_no')); d.driver=sval(request.form.get('driver')); d.origin=sval(request.form.get('origin')); d.destination=sval(request.form.get('destination')); d.cargo_description=sval(request.form.get('cargo_description')); d.quantity=fnum(request.form.get('quantity')); d.weight=fnum(request.form.get('weight')); d.origin_country=sval(request.form.get('origin_country')); d.declaration_type=sval(request.form.get('declaration_type')) or 'بيان داخلي'; d.customs_office=sval(request.form.get('customs_office')); d.exporter_name=sval(request.form.get('exporter_name')); d.importer_name=sval(request.form.get('importer_name')); d.consignee_name=sval(request.form.get('consignee_name')); d.broker_name=sval(request.form.get('broker_name')); d.declarant_name=sval(request.form.get('declarant_name')); d.border_point=sval(request.form.get('border_point')); d.transport_mode=sval(request.form.get('transport_mode')); d.country_destination=sval(request.form.get('country_destination')); d.package_count=fnum(request.form.get('package_count')); d.package_type=sval(request.form.get('package_type')); d.gross_weight=fnum(request.form.get('gross_weight')); d.net_weight=fnum(request.form.get('net_weight')); d.goods_value=fnum(request.form.get('goods_value')); d.currency=sval(request.form.get('currency')) or 'USD'; d.invoice_no=sval(request.form.get('invoice_no')); d.shipping_doc_no=sval(request.form.get('shipping_doc_no')); d.container_no=sval(request.form.get('container_no')); d.seal_no=sval(request.form.get('seal_no')); d.loading_date=sval(request.form.get('loading_date')); d.expected_arrival_date=sval(request.form.get('expected_arrival_date')); d.customs_reference=sval(request.form.get('customs_reference')); d.status=sval(request.form.get('status')) or 'مسودة'; d.note=sval(request.form.get('note')); d.updated_at=datetime.utcnow()
            db.session.commit(); audit('حفظ بيان جمركي','declaration',d.id,d.declaration_no); flash('تم حفظ البيان'); return redirect(url_for('declaration_detail',did=d.id))
    comps=Company.query.order_by(Company.name).all(); today=date.today().isoformat()
    body='''<div class="hero"><h1>{{'تعديل' if d else 'إضافة'}} بيان جمركي</h1><p>نفس حقول البيان الأساسية المستخدمة في برنامج سطح المكتب.</p></div><form method="post"><div class="card"><div class="section-title">بيانات البيان الأساسية</div><div class="formgrid"><div class="field"><label>رقم البيان السوري *</label><input name="declaration_no" required value="{{d.declaration_no if d else ''}}"></div><div class="field"><label>رقم المنافيست</label><input name="manifest_no" value="{{d.manifest_no if d else ''}}"></div><div class="field"><label>تاريخ البيان</label><input type="date" name="declaration_date" value="{{d.declaration_date if d and d.declaration_date else today}}"></div><div class="field"><label>نوع البيان</label><select name="declaration_type">{% for x in types %}<option {% if d and d.declaration_type==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select></div><div class="field"><label>الحالة</label><select name="status">{% for x in statuses %}<option {% if d and d.status==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select></div><div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}" {% if d and d.company_id==c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select></div><div class="field"><label>اسم العميل / الشركة</label><input name="customer_name" value="{{d.customer_name if d else ''}}"></div><div class="field"><label>الشركة الموردة</label><input name="exporter_name" value="{{d.exporter_name if d else ''}}"></div><div class="field"><label>الشركة المستوردة</label><input name="importer_name" value="{{d.importer_name if d else ''}}"></div><div class="field"><label>المستلم</label><input name="consignee_name" value="{{d.consignee_name if d else ''}}"></div><div class="field"><label>المخلص الجمركي</label><input name="broker_name" value="{{d.broker_name if d else ''}}"></div><div class="field"><label>اسم المصرح</label><input name="declarant_name" value="{{d.declarant_name if d else ''}}"></div></div></div><div class="card"><div class="section-title">النقل والبضاعة</div><div class="formgrid"><div class="field"><label>السيارة السورية</label><input name="vehicle_no" value="{{d.vehicle_no if d else ''}}"></div><div class="field"><label>المقطورة</label><input name="trailer_no" value="{{d.trailer_no if d else ''}}"></div><div class="field"><label>السائق</label><input name="driver" value="{{d.driver if d else ''}}"></div><div class="field"><label>من</label><input name="origin" value="{{d.origin if d else ''}}"></div><div class="field"><label>إلى / المقصد</label><input name="destination" value="{{d.destination if d else ''}}"></div><div class="field"><label>بلد المنشأ</label><input name="origin_country" value="{{d.origin_country if d else ''}}"></div><div class="field"><label>بلد المقصد</label><input name="country_destination" value="{{d.country_destination if d else ''}}"></div><div class="field"><label>نقطة الحدود</label><input name="border_point" value="{{d.border_point if d else 'باب الهوى'}}"></div><div class="field"><label>وسيلة النقل</label><input name="transport_mode" value="{{d.transport_mode if d else 'بري'}}"></div><div class="field full"><label>وصف البضاعة</label><textarea name="cargo_description">{{d.cargo_description if d else ''}}</textarea></div><div class="field"><label>الكمية</label><input type="number" step="0.01" name="quantity" value="{{d.quantity if d else 0}}"></div><div class="field"><label>الوزن</label><input type="number" step="0.01" name="weight" value="{{d.weight if d else 0}}"></div><div class="field"><label>عدد الطرود</label><input type="number" step="0.01" name="package_count" value="{{d.package_count if d else 0}}"></div><div class="field"><label>نوع الطرود</label><input name="package_type" value="{{d.package_type if d else ''}}"></div><div class="field"><label>الوزن الإجمالي</label><input type="number" step="0.01" name="gross_weight" value="{{d.gross_weight if d else 0}}"></div><div class="field"><label>الوزن الصافي</label><input type="number" step="0.01" name="net_weight" value="{{d.net_weight if d else 0}}"></div></div></div><div class="card"><div class="section-title">المراجع والمستندات</div><div class="formgrid"><div class="field"><label>المكتب الجمركي</label><input name="customs_office" value="{{d.customs_office if d else ''}}"></div><div class="field"><label>المرجع الجمركي</label><input name="customs_reference" value="{{d.customs_reference if d else ''}}"></div><div class="field"><label>رقم الفاتورة</label><input name="invoice_no" value="{{d.invoice_no if d else ''}}"></div><div class="field"><label>وثيقة الشحن</label><input name="shipping_doc_no" value="{{d.shipping_doc_no if d else ''}}"></div><div class="field"><label>رقم الحاوية</label><input name="container_no" value="{{d.container_no if d else ''}}"></div><div class="field"><label>رقم الختم</label><input name="seal_no" value="{{d.seal_no if d else ''}}"></div><div class="field"><label>تاريخ التحميل</label><input type="date" name="loading_date" value="{{d.loading_date if d else ''}}"></div><div class="field"><label>الوصول المتوقع</label><input type="date" name="expected_arrival_date" value="{{d.expected_arrival_date if d else ''}}"></div><div class="field"><label>قيمة البضاعة</label><input type="number" step="0.01" name="goods_value" value="{{d.goods_value if d else 0}}"></div><div class="field"><label>العملة</label><input name="currency" value="{{d.currency if d else 'USD'}}"></div><div class="field full"><label>ملاحظات</label><textarea name="note">{{d.note if d else ''}}</textarea></div></div></div><div class="toolbar"><button class="btn green">حفظ البيان</button><a class="btn gray" href="{{url_for('declarations')}}">إلغاء</a></div></form>'''
    return layout('بيان جمركي',body,d=d,comps=comps,types=DECL_TYPES,statuses=STATUSES,today=today)

@app.route('/declarations/<int:did>')
@login_required
def declaration_detail(did):
    d=CustomsDeclaration.query.get_or_404(did)
    total=sum(float(x.amount or 0) for x in d.charges); paid=sum(float(x.paid or 0) for x in d.charges)
    body='''<div class="hero"><h1>البيان {{d.declaration_no}}</h1><p>{{d.declaration_type}} • {{d.company.name if d.company else d.customer_name}} • {{d.status}}</p></div><div class="toolbar no-print"><a class="btn blue" href="{{url_for('declaration_form',did=d.id)}}">تعديل البيان</a><a class="btn" href="{{url_for('declaration_finance',did=d.id)}}">💰 الحساب المالي</a><a class="btn amber" href="{{url_for('entity_attachments',source_type='declaration',source_id=d.id)}}">📎 المستندات</a>{% if not d.transport_job_id %}<a class="btn green" href="{{url_for('trip_import',did=d.id)}}">🚛 استيراد وإنشاء رحلة</a>{% endif %}<button class="btn dark" onclick="window.print()">📄 PDF / طباعة</button></div><div class="split"><div class="card"><div class="section-title">تفاصيل البيان</div><div class="tablewrap"><table><tr><th>الحقل</th><th>القيمة</th></tr><tr><td>المنافيست</td><td>{{d.manifest_no}}</td></tr><tr><td>التاريخ</td><td>{{d.declaration_date}}</td></tr><tr><td>الشركة الموردة</td><td>{{d.exporter_name}}</td></tr><tr><td>الشركة المستوردة</td><td>{{d.importer_name}}</td></tr><tr><td>السيارة / السائق</td><td>{{d.vehicle_no}} / {{d.driver}}</td></tr><tr><td>المسار</td><td>{{d.origin}} ← {{d.destination}}</td></tr><tr><td>البضاعة</td><td style="white-space:normal">{{d.cargo_description}}</td></tr><tr><td>الوزن الإجمالي / الصافي</td><td>{{d.gross_weight}} / {{d.net_weight}}</td></tr><tr><td>قيمة البضاعة</td><td>{{d.goods_value}} {{d.currency}}</td></tr><tr><td>المكتب / المرجع</td><td>{{d.customs_office}} / {{d.customs_reference}}</td></tr><tr><td>وثيقة الشحن / الفاتورة</td><td>{{d.shipping_doc_no}} / {{d.invoice_no}}</td></tr><tr><td>الحاوية / الختم</td><td>{{d.container_no}} / {{d.seal_no}}</td></tr><tr><td>ملاحظات</td><td style="white-space:normal">{{d.note}}</td></tr></table></div></div><div><div class="card"><div class="section-title">الحساب المالي</div><div class="grid"><div><div class="kpi">إجمالي الرسوم</div><div class="amount">{{'%.2f'|format(total)}}</div></div><div><div class="kpi">المدفوع</div><div class="amount">{{'%.2f'|format(paid)}}</div></div><div><div class="kpi">المتبقي</div><div class="amount">{{'%.2f'|format(total-paid)}}</div></div></div></div><div class="card"><div class="section-title">الربط</div><p>الرحلة: <b>{{d.transport_job_id or 'غير مرتبطة'}}</b></p><p>الحالة: {{d.status}}</p></div></div></div>'''
    return layout('تفاصيل البيان',body,d=d,total=total,paid=paid)

@app.route('/declarations/<int:did>/finance',methods=['GET','POST'])
@login_required
def declaration_finance(did):
    d=CustomsDeclaration.query.get_or_404(did)
    if request.method=='POST' and can_finance():
        db.session.add(DeclarationCharge(declaration_id=did,charge_date=sval(request.form.get('charge_date')) or date.today().isoformat(),charge_type=sval(request.form.get('charge_type')),description=sval(request.form.get('description')),amount=fnum(request.form.get('amount')),required=bool(request.form.get('required')),paid=fnum(request.form.get('paid')))); db.session.commit(); audit('إضافة رسم للبيان','declaration_charge',did); return redirect(url_for('declaration_finance',did=did))
    rows=DeclarationCharge.query.filter_by(declaration_id=did).order_by(DeclarationCharge.id.asc()).all(); total=sum(x.amount or 0 for x in rows); paid=sum(x.paid or 0 for x in rows)
    body='''<div class="hero"><h1>الحساب المالي — {{d.declaration_no}}</h1><p>رسوم جمركية، فيزا، عبور، تأمين، معاملة المكتب، سيارة سورية، ومصاريف إضافية.</p></div>{% if finance %}<div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="charge_date" value="{{today}}"></div><div class="field"><label>نوع الرسم</label><select name="charge_type"><option>رسوم جمركية</option><option>فيزا</option><option>عبور</option><option>تأمين</option><option>معاملة المكتب</option><option>سيارة سورية</option><option>مصاريف إضافية</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div class="field"><label>المدفوع منه</label><input type="number" step="0.01" name="paid" value="0"></div><div class="field full"><label>الوصف</label><input name="description"></div><label><input type="checkbox" name="required" checked style="width:auto"> مطلوب لهذه المعاملة</label></div><button class="btn" style="margin-top:10px">إضافة الرسم</button></form></div>{% endif %}<div class="grid"><div class="card stat"><div class="label">الإجمالي</div><div class="n">{{'%.2f'|format(total)}}</div></div><div class="card stat"><div class="label">المدفوع</div><div class="n">{{'%.2f'|format(paid)}}</div></div><div class="card stat"><div class="label">المتبقي</div><div class="n">{{'%.2f'|format(total-paid)}}</div></div></div><div class="card"><div class="tablewrap"><table><tr><th>التاريخ</th><th>النوع</th><th>الوصف</th><th>المبلغ</th><th>المدفوع</th><th>المتبقي</th></tr>{% for x in rows %}<tr><td>{{x.charge_date}}</td><td>{{x.charge_type}}</td><td>{{x.description}}</td><td>{{'%.2f'|format(x.amount or 0)}}</td><td>{{'%.2f'|format(x.paid or 0)}}</td><td>{{'%.2f'|format((x.amount or 0)-(x.paid or 0))}}</td></tr>{% endfor %}</table></div></div><div class="toolbar"><a class="btn gray" href="{{url_for('declaration_detail',did=d.id)}}">رجوع للبيان</a><a class="btn blue" href="{{url_for('invoice_new',declaration_id=d.id)}}">إنشاء فاتورة من البيان</a></div>'''
    return layout('الحساب المالي للبيان',body,d=d,rows=rows,total=total,paid=paid,today=date.today().isoformat(),finance=can_finance())

# -------------------- trip import + trips --------------------
@app.route('/trips/select')
@login_required
def trip_select_declaration():
    q=sval(request.args.get('q')); st=sval(request.args.get('status'))
    query=CustomsDeclaration.query.filter(CustomsDeclaration.transport_job_id.is_(None))
    if q:
        like=f'%{q}%'; query=query.filter(db.or_(CustomsDeclaration.declaration_no.ilike(like),CustomsDeclaration.manifest_no.ilike(like),CustomsDeclaration.customer_name.ilike(like),CustomsDeclaration.vehicle_no.ilike(like),CustomsDeclaration.cargo_description.ilike(like)))
    if st and st!='الكل': query=query.filter_by(status=st)
    rows=query.order_by(CustomsDeclaration.id.asc()).all()
    body='''<div class="hero"><h1>إنشاء رحلة — استيراد من البيانات الموجودة فقط</h1><p>لا يمكن إنشاء رحلة فارغة. اختر بياناً موجوداً ثم أكمل بيانات النقل.</p></div><div class="card no-print"><form class="search"><input name="q" placeholder="بحث شامل" value="{{q}}"><select name="status"><option>الكل</option>{% for x in statuses %}<option {% if st==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select><span></span><button class="btn">بحث</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>البيان</th><th>المنافيست</th><th>التاريخ</th><th>الشركة</th><th>السيارة</th><th>المقصد</th><th>البضاعة</th><th>الحالة</th><th></th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.declaration_no}}</td><td>{{x.manifest_no}}</td><td>{{x.declaration_date}}</td><td>{{x.company.name if x.company else x.customer_name}}</td><td>{{x.vehicle_no}}</td><td>{{x.destination}}</td><td>{{x.cargo_description}}</td><td>{{x.status}}</td><td><a class="btn small green" href="{{url_for('trip_import',did=x.id)}}">استيراد وإنشاء رحلة</a></td></tr>{% endfor %}</table></div></div>'''
    return layout('استيراد بيان للرحلة',body,rows=rows,q=q,st=st,statuses=STATUSES)

@app.route('/trips/import/<int:did>',methods=['GET','POST'])
@login_required
def trip_import(did):
    if not can_edit(): flash('لا تملك صلاحية','error'); return redirect(url_for('trips'))
    d=CustomsDeclaration.query.get_or_404(did)
    if d.transport_job_id: flash('هذا البيان مرتبط مسبقاً برحلة','warn'); return redirect(url_for('trip_detail',jid=d.transport_job_id))
    if request.method=='POST':
        j=TransportJob(declaration_id=d.id,company_id=d.company_id,manifest_no=sval(request.form.get('manifest_no')) or d.manifest_no,turkish_vehicle=sval(request.form.get('turkish_vehicle')),vehicle_location=sval(request.form.get('vehicle_location')),vehicle_city=sval(request.form.get('vehicle_city')),company_price=fnum(request.form.get('company_price')),turkish_purchase_price=fnum(request.form.get('turkish_purchase_price')),syrian_vehicle=sval(request.form.get('syrian_vehicle')) or d.vehicle_no,foreign_vehicle=sval(request.form.get('foreign_vehicle')),foreign_driver=sval(request.form.get('foreign_driver')),foreign_phone=sval(request.form.get('foreign_phone')),destination=sval(request.form.get('destination')) or d.destination,cargo_description=d.cargo_description,nassib_payment=fnum(request.form.get('nassib_payment')),nassib_due=fnum(request.form.get('nassib_due')),status='مفتوحة',note=sval(request.form.get('note')))
        db.session.add(j); db.session.flush(); recompute_job(j); d.transport_job_id=j.id; d.status='مغلق'; db.session.commit(); audit('إنشاء رحلة من بيان','transport_job',j.id,d.declaration_no); return redirect(url_for('trip_detail',jid=j.id))
    body='''<div class="hero"><h1>إنشاء رحلة من البيان {{d.declaration_no}}</h1><p>البيانات الأساسية مستوردة من البيان ولا تحتاج لإعادة كتابتها.</p></div><div class="card"><div class="grid"><div><div class="kpi">الشركة</div><b>{{d.company.name if d.company else d.customer_name}}</b></div><div><div class="kpi">المنافيست</div><b>{{d.manifest_no}}</b></div><div><div class="kpi">السيارة السورية</div><b>{{d.vehicle_no}}</b></div><div><div class="kpi">المقصد</div><b>{{d.destination}}</b></div></div></div><form method="post"><div class="card"><div class="section-title">بيانات الرحلة</div><div class="formgrid"><div class="field"><label>رقم المنافيست</label><input name="manifest_no" value="{{d.manifest_no}}"></div><div class="field"><label>السيارة التركية</label><input name="turkish_vehicle"></div><div class="field"><label>مكان السيارة</label><input name="vehicle_location"></div><div class="field"><label>المدينة</label><input name="vehicle_city"></div><div class="field"><label>سعر الشركة</label><input type="number" step="0.01" name="company_price"></div><div class="field"><label>شراء السيارة من التركي</label><input type="number" step="0.01" name="turkish_purchase_price"></div><div class="field"><label>السيارة السورية</label><input name="syrian_vehicle" value="{{d.vehicle_no}}"></div><div class="field"><label>السيارة الأجنبية</label><input name="foreign_vehicle"></div><div class="field"><label>السائق الأجنبي</label><input name="foreign_driver"></div><div class="field"><label>هاتف السائق</label><input name="foreign_phone"></div><div class="field"><label>المقصد</label><input name="destination" value="{{d.destination}}"></div><div class="field"><label>دفعة نصيب</label><input type="number" step="0.01" name="nassib_payment"></div><div class="field"><label>المستحق في نصيب</label><input type="number" step="0.01" name="nassib_due"></div><div class="field full"><label>ملاحظات</label><textarea name="note"></textarea></div></div></div><button class="btn green">إنشاء الرحلة</button></form>'''
    return layout('إنشاء رحلة',body,d=d)

@app.route('/trips')
@login_required
def trips():
    q=sval(request.args.get('q')); st=sval(request.args.get('status'))
    query=TransportJob.query
    if q:
        like=f'%{q}%'; query=query.filter(db.or_(TransportJob.manifest_no.ilike(like),TransportJob.turkish_vehicle.ilike(like),TransportJob.syrian_vehicle.ilike(like),TransportJob.foreign_driver.ilike(like),TransportJob.destination.ilike(like)))
    if st and st!='الكل': query=query.filter_by(status=st)
    rows=query.order_by(TransportJob.id.desc()).all()
    body='''<div class="hero"><h1>الترانزيت والرحلات</h1><p>ملف الرحلة الكامل: المراحل، التكاليف، الدفعات، السيارات، CMR، والفاتورة التركية.</p></div><div class="toolbar no-print"><a class="btn green" href="{{url_for('trip_select_declaration')}}">＋ إنشاء رحلة من بيان</a><button class="btn dark" onclick="window.print()">PDF / طباعة</button></div><div class="card no-print"><form class="search"><input name="q" placeholder="منافيست، سيارة، سائق، مقصد" value="{{q}}"><select name="status"><option>الكل</option><option {% if st=='مفتوحة' %}selected{% endif %}>مفتوحة</option><option {% if st=='مغلقة' %}selected{% endif %}>مغلقة</option></select><span></span><button class="btn">بحث</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>#</th><th>البيان</th><th>المنافيست</th><th>الشركة</th><th>التركية</th><th>السورية</th><th>المقصد</th><th>التكلفة</th><th>الربح</th><th>الحالة</th><th></th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.declaration.declaration_no if x.declaration else '—'}}</td><td>{{x.manifest_no}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.turkish_vehicle}}</td><td>{{x.syrian_vehicle}}</td><td>{{x.destination}}</td><td>{{'%.2f'|format(x.total_cost or 0)}}</td><td class="amount">{{'%.2f'|format(x.profit or 0)}}</td><td>{{x.status}}</td><td><a class="btn small dark" href="{{url_for('trip_detail',jid=x.id)}}">فتح الملف</a></td></tr>{% endfor %}</table></div></div>'''
    return layout('الرحلات',body,rows=rows,q=q,st=st)

@app.route('/trips/<int:jid>',methods=['GET','POST'])
@login_required
def trip_detail(jid):
    j=TransportJob.query.get_or_404(jid); recompute_job(j); db.session.commit()
    body='''<div class="hero"><h1>ملف الرحلة #{{j.id}}</h1><p>بيان {{j.declaration.declaration_no if j.declaration else '—'}} • منافيست {{j.manifest_no}} • {{j.status}}</p></div><div class="toolbar no-print"><a class="btn" href="{{url_for('trip_cost_new',jid=j.id)}}">＋ تكلفة</a><a class="btn blue" href="{{url_for('trip_payment_new',jid=j.id)}}">＋ دفعة</a><a class="btn amber" href="{{url_for('trip_stage_new',jid=j.id)}}">＋ مرحلة</a><a class="btn green" href="{{url_for('turkish_invoice_new',jid=j.id)}}">🇹🇷 فاتورة السيارة التركية</a><a class="btn dark" href="{{url_for('entity_attachments',source_type='trip',source_id=j.id)}}">📎 مرفقات الرحلة</a><a class="btn gray" href="{{url_for('trip_toggle',jid=j.id)}}">{{'إعادة فتح' if j.status=='مغلقة' else 'إغلاق الرحلة'}}</a><button class="btn dark" onclick="window.print()">PDF / طباعة</button></div><div class="grid"><div class="card stat"><div class="label">سعر الشركة</div><div class="n">{{'%.2f'|format(j.company_price or 0)}}</div></div><div class="card stat"><div class="label">شراء التركي</div><div class="n">{{'%.2f'|format(j.turkish_purchase_price or 0)}}</div></div><div class="card stat"><div class="label">إجمالي التكاليف والدفعات</div><div class="n">{{'%.2f'|format(j.total_cost or 0)}}</div></div><div class="card stat"><div class="label">الربح</div><div class="n">{{'%.2f'|format(j.profit or 0)}}</div></div><div class="card stat"><div class="label">رصيد نصيب</div><div class="n">{{'%.2f'|format(j.nassib_balance or 0)}}</div></div></div><div class="card"><div class="section-title">بيانات الرحلة</div><div class="tablewrap"><table><tr><th>المنافيست</th><th>السيارة التركية</th><th>مكانها</th><th>السورية</th><th>الأجنبية</th><th>السائق</th><th>الهاتف</th><th>المقصد</th></tr><tr><td>{{j.manifest_no}}</td><td>{{j.turkish_vehicle}}</td><td>{{j.vehicle_location}} / {{j.vehicle_city}}</td><td>{{j.syrian_vehicle}}</td><td>{{j.foreign_vehicle}}</td><td>{{j.foreign_driver}}</td><td>{{j.foreign_phone}}</td><td>{{j.destination}}</td></tr></table></div></div><div class="split"><div class="card"><div class="section-title">المراحل</div><div class="tablewrap"><table><tr><th>المرحلة</th><th>الحالة</th><th>الموقع</th><th>البدء</th><th>الإكمال</th></tr>{% for x in j.stages %}<tr><td>{{x.stage}}</td><td>{{x.status}}</td><td>{{x.location}}</td><td>{{x.started_at}}</td><td>{{x.completed_at}}</td></tr>{% endfor %}</table></div></div><div class="card"><div class="section-title">التكاليف</div><div class="tablewrap"><table><tr><th>المرحلة</th><th>الوصف</th><th>المبلغ</th><th>السيارة</th><th>السائق</th></tr>{% for x in j.costs %}<tr><td>{{x.stage}}</td><td>{{x.description}}</td><td>{{'%.2f'|format(x.amount or 0)}}</td><td>{{x.vehicle_no}}</td><td>{{x.driver}}</td></tr>{% endfor %}</table></div></div></div><div class="card"><div class="section-title">الدفعات</div><div class="tablewrap"><table><tr><th>التاريخ</th><th>المستفيد</th><th>الجهة</th><th>الاتجاه</th><th>المبلغ</th><th>الوصف</th></tr>{% for x in j.payments %}<tr><td>{{x.payment_date}}</td><td>{{x.beneficiary}}</td><td>{{x.payment_party}}</td><td>{{'وارد' if x.direction=='in' else 'صادر'}}</td><td>{{'%.2f'|format(x.amount or 0)}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div></div><div class="card"><div class="section-title">فواتير السيارة التركية</div><div class="tablewrap"><table><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>المبلغ</th><th>المنافيست</th><th>السيارة</th></tr>{% for x in j.turkish_invoices %}<tr><td>{{x.invoice_no}}</td><td>{{x.invoice_date}}</td><td>{{'%.2f'|format(x.amount or 0)}}</td><td>{{x.manifest_no}}</td><td>{{x.vehicle_no}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('ملف الرحلة',body,j=j)

@app.route('/trips/<int:jid>/cost',methods=['GET','POST'])
@login_required
def trip_cost_new(jid):
    j=TransportJob.query.get_or_404(jid)
    if request.method=='POST' and can_edit():
        db.session.add(TransportCost(job_id=jid,stage=sval(request.form.get('stage')),description=sval(request.form.get('description')),amount=fnum(request.form.get('amount')),vehicle_no=sval(request.form.get('vehicle_no')),driver=sval(request.form.get('driver')),phone=sval(request.form.get('phone')))); db.session.commit(); recompute_job(j); db.session.commit(); audit('إضافة تكلفة رحلة','transport_cost',jid); return redirect(url_for('trip_detail',jid=jid))
    body='''<div class="hero"><h1>إضافة تكلفة للرحلة #{{j.id}}</h1></div><div class="card"><form method="post"><div class="formgrid"><div class="field"><label>المرحلة</label><select name="stage"><option>تركيا</option><option>باب الهوى</option><option>المناقلة</option><option>سوريا</option><option>المقصد</option><option>أخرى</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div class="field"><label>السيارة</label><input name="vehicle_no"></div><div class="field"><label>السائق</label><input name="driver"></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn">حفظ التكلفة</button></form></div>'''
    return layout('تكلفة رحلة',body,j=j)

@app.route('/trips/<int:jid>/payment',methods=['GET','POST'])
@login_required
def trip_payment_new(jid):
    j=TransportJob.query.get_or_404(jid)
    if request.method=='POST' and can_finance():
        amt=fnum(request.form.get('amount')); direction=sval(request.form.get('direction')) or 'out'
        p=TransportPayment(job_id=jid,payment_date=sval(request.form.get('payment_date')) or date.today().isoformat(),beneficiary=sval(request.form.get('beneficiary')),amount=amt,description=sval(request.form.get('description')),payment_party=sval(request.form.get('payment_party')),direction=direction); db.session.add(p)
        db.session.add(CashTransaction(txn_date=p.payment_date,direction=direction,category='دفعة رحلة',amount=amt,company_id=j.company_id,description=p.description or p.beneficiary,reference=f'TRIP-{jid}',created_by=session.get('username','')))
        if direction=='out': journal('دفعة رحلة', [('5020',amt,0,p.description),('1000',0,amt,p.description)],'trip_payment',jid,p.payment_date)
        else: journal('تحصيل رحلة', [('1000',amt,0,p.description),('4010',0,amt,p.description)],'trip_receipt',jid,p.payment_date)
        db.session.commit(); recompute_job(j); db.session.commit(); audit('دفعة رحلة','transport_payment',jid); return redirect(url_for('trip_detail',jid=jid))
    body='''<div class="hero"><h1>إضافة دفعة للرحلة #{{j.id}}</h1></div><div class="card"><form method="post"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="payment_date" value="{{today}}"></div><div class="field"><label>المستفيد</label><input name="beneficiary"></div><div class="field"><label>الجهة</label><select name="payment_party"><option>الشركة التركية</option><option>السائق</option><option>نصيب</option><option>المكتب</option><option>أخرى</option></select></div><div class="field"><label>الاتجاه</label><select name="direction"><option value="out">صادر</option><option value="in">وارد</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn blue">حفظ الدفعة</button></form></div>'''
    return layout('دفعة رحلة',body,j=j,today=date.today().isoformat())

@app.route('/trips/<int:jid>/stage',methods=['GET','POST'])
@login_required
def trip_stage_new(jid):
    j=TransportJob.query.get_or_404(jid)
    if request.method=='POST' and can_edit():
        stage=sval(request.form.get('stage')); x=TransportStage.query.filter_by(job_id=jid,stage=stage).first()
        if not x: x=TransportStage(job_id=jid,stage=stage); db.session.add(x)
        x.status=sval(request.form.get('status')); x.location=sval(request.form.get('location')); x.note=sval(request.form.get('note'))
        if not x.started_at: x.started_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        if x.status=='مكتملة': x.completed_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        db.session.commit(); audit('تحديث مرحلة رحلة','transport_stage',jid,stage); return redirect(url_for('trip_detail',jid=jid))
    body='''<div class="hero"><h1>مرحلة الرحلة #{{j.id}}</h1></div><div class="card"><form method="post"><div class="formgrid"><div class="field"><label>المرحلة</label><select name="stage"><option>استلام البيان</option><option>السيارة التركية</option><option>الوصول للحدود</option><option>المناقلة</option><option>السيارة السورية</option><option>نصيب</option><option>الوصول للمقصد</option></select></div><div class="field"><label>الحالة</label><select name="status"><option>مفتوحة</option><option>قيد التنفيذ</option><option>مكتملة</option></select></div><div class="field"><label>الموقع</label><input name="location"></div><div class="field full"><label>ملاحظة</label><input name="note"></div></div><button class="btn amber">حفظ المرحلة</button></form></div>'''
    return layout('مرحلة رحلة',body,j=j)

@app.route('/trips/<int:jid>/toggle')
@login_required
def trip_toggle(jid):
    j=TransportJob.query.get_or_404(jid); j.status='مفتوحة' if j.status=='مغلقة' else 'مغلقة'; db.session.commit(); audit('تغيير حالة رحلة','transport_job',jid,j.status); return redirect(url_for('trip_detail',jid=jid))

@app.route('/trips/<int:jid>/turkish-invoice',methods=['GET','POST'])
@login_required
def turkish_invoice_new(jid):
    j=TransportJob.query.get_or_404(jid)
    if request.method=='POST' and can_finance():
        no=sval(request.form.get('invoice_no'))
        if TurkishVehicleInvoice.query.filter_by(invoice_no=no).first(): flash('رقم الفاتورة مستخدم','error')
        else:
            db.session.add(TurkishVehicleInvoice(job_id=jid,invoice_no=no,invoice_date=sval(request.form.get('invoice_date')) or date.today().isoformat(),amount=fnum(request.form.get('amount')),manifest_no=sval(request.form.get('manifest_no')),vehicle_no=sval(request.form.get('vehicle_no')),cargo_description=sval(request.form.get('cargo_description')))); db.session.commit(); audit('فاتورة سيارة تركية','turkish_invoice',jid,no); return redirect(url_for('trip_detail',jid=jid))
    no=f'TR-{jid}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
    body='''<div class="hero"><h1>فاتورة السيارة للشركة التركية</h1><p>تسوية قيمة السيارة فقط، مع رقم المنافيست والسيارة ووصف البضاعة.</p></div><div class="card"><form method="post"><div class="formgrid"><div class="field"><label>رقم الفاتورة</label><input name="invoice_no" value="{{no}}"></div><div class="field"><label>التاريخ</label><input type="date" name="invoice_date" value="{{today}}"></div><div class="field"><label>قيمة السيارة</label><input type="number" step="0.01" name="amount" value="{{j.turkish_purchase_price or 0}}"></div><div class="field"><label>المنافيست</label><input name="manifest_no" value="{{j.manifest_no}}"></div><div class="field"><label>السيارة التركية</label><input name="vehicle_no" value="{{j.turkish_vehicle}}"></div><div class="field full"><label>وصف البضاعة</label><textarea name="cargo_description">{{j.cargo_description}}</textarea></div></div><button class="btn green">إنشاء الفاتورة</button></form></div>'''
    return layout('فاتورة السيارة التركية',body,j=j,no=no,today=date.today().isoformat())

# -------------------- internal shipments --------------------
@app.route('/internal-shipments',methods=['GET','POST'])
@login_required
def internal_shipments():
    if request.method=='POST' and can_edit():
        no=sval(request.form.get('shipment_no'))
        if InternalShipment.query.filter_by(shipment_no=no).first(): flash('رقم البيان الداخلي موجود','error')
        else:
            rev=fnum(request.form.get('revenue')); cost=fnum(request.form.get('cost'))
            db.session.add(InternalShipment(company_id=request.form.get('company_id') or None,shipment_no=no,shipment_date=sval(request.form.get('shipment_date')),customer_name=sval(request.form.get('customer_name')),phone=sval(request.form.get('phone')),origin=sval(request.form.get('origin')),destination=sval(request.form.get('destination')),vehicle_no=sval(request.form.get('vehicle_no')),driver=sval(request.form.get('driver')),description=sval(request.form.get('description')),revenue=rev,cost=cost,profit=rev-cost,status=sval(request.form.get('status')),cash_received=fnum(request.form.get('cash_received')),cash_paid=fnum(request.form.get('cash_paid')))); db.session.commit(); audit('إضافة بيان داخلي','internal_shipment',None,no)
        return redirect(url_for('internal_shipments'))
    rows=InternalShipment.query.order_by(InternalShipment.id.desc()).all(); comps=Company.query.order_by(Company.name).all()
    body='''<div class="hero"><h1>البيانات الداخلية</h1><p>ملف مستقل للنقل الداخلي من باب الهوى إلى المقصد مع الإيراد والتكلفة والربح.</p></div>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>رقم البيان الداخلي</label><input name="shipment_no" required></div><div class="field"><label>التاريخ</label><input type="date" name="shipment_date" value="{{today}}"></div><div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div><div class="field"><label>اسم العميل</label><input name="customer_name"></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field"><label>من</label><input name="origin" value="باب الهوى"></div><div class="field"><label>إلى</label><input name="destination"></div><div class="field"><label>السيارة السورية</label><input name="vehicle_no"></div><div class="field"><label>السائق</label><input name="driver"></div><div class="field"><label>الإيراد</label><input type="number" step="0.01" name="revenue"></div><div class="field"><label>التكلفة</label><input type="number" step="0.01" name="cost"></div><div class="field"><label>المقبوض</label><input type="number" step="0.01" name="cash_received"></div><div class="field"><label>المدفوع</label><input type="number" step="0.01" name="cash_paid"></div><div class="field"><label>الحالة</label><select name="status"><option>مفتوحة</option><option>مغلقة</option></select></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn" style="margin-top:10px">حفظ البيان الداخلي</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>#</th><th>الرقم</th><th>التاريخ</th><th>الشركة</th><th>العميل</th><th>المسار</th><th>السيارة</th><th>الإيراد</th><th>التكلفة</th><th>الربح</th><th>الحالة</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.shipment_no}}</td><td>{{x.shipment_date}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.customer_name}}</td><td>{{x.origin}} ← {{x.destination}}</td><td>{{x.vehicle_no}}</td><td>{{'%.2f'|format(x.revenue or 0)}}</td><td>{{'%.2f'|format(x.cost or 0)}}</td><td class="amount">{{'%.2f'|format(x.profit or 0)}}</td><td>{{x.status}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('البيانات الداخلية',body,rows=rows,comps=comps,today=date.today().isoformat(),edit=can_edit())

# -------------------- service case center --------------------
@app.route('/cases',methods=['GET','POST'])
@login_required
def case_center():
    if request.method=='POST' and can_edit():
        no=sval(request.form.get('case_no')) or next_case_no()
        if ServiceCase.query.filter_by(case_no=no).first(): flash('رقم المعاملة مستخدم','error')
        else:
            db.session.add(ServiceCase(case_no=no,case_type=sval(request.form.get('case_type')),company_id=request.form.get('company_id') or None,case_date=sval(request.form.get('case_date')),declaration_no=sval(request.form.get('declaration_no')),manifest_no=sval(request.form.get('manifest_no')),customer_name=sval(request.form.get('customer_name')),vehicle_no=sval(request.form.get('vehicle_no')),driver=sval(request.form.get('driver')),origin=sval(request.form.get('origin')),destination=sval(request.form.get('destination')),cargo_description=sval(request.form.get('cargo_description')),status='مفتوحة',note=sval(request.form.get('note')))); db.session.commit(); audit('إضافة معاملة','service_case',None,no)
        return redirect(url_for('case_center'))
    rows=ServiceCase.query.order_by(ServiceCase.id.desc()).all(); comps=Company.query.order_by(Company.name).all()
    body='''<div class="hero"><h1>مركز المعاملات</h1><p>تجميع كل أنواع العمل في ملف واحد: داخلي، ترانزيت، مناقلة، وترانزيت البيان الداخلي.</p></div>{% if edit %}<div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>رقم المعاملة</label><input name="case_no" value="{{next_no}}"></div><div class="field"><label>النوع</label><select name="case_type">{% for x in types %}<option>{{x}}</option>{% endfor %}</select></div><div class="field"><label>التاريخ</label><input type="date" name="case_date" value="{{today}}"></div><div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div><div class="field"><label>رقم البيان</label><input name="declaration_no"></div><div class="field"><label>المنافيست</label><input name="manifest_no"></div><div class="field"><label>العميل</label><input name="customer_name"></div><div class="field"><label>السيارة</label><input name="vehicle_no"></div><div class="field"><label>السائق</label><input name="driver"></div><div class="field"><label>من</label><input name="origin"></div><div class="field"><label>إلى</label><input name="destination"></div><div class="field full"><label>البضاعة</label><input name="cargo_description"></div><div class="field full"><label>ملاحظات</label><input name="note"></div></div><button class="btn" style="margin-top:10px">حفظ المعاملة</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>#</th><th>رقم الملف</th><th>النوع</th><th>الشركة</th><th>البيان</th><th>المنافيست</th><th>السيارة</th><th>الحالة</th><th></th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.case_no}}</td><td>{{x.case_type}}</td><td>{{x.company.name if x.company else x.customer_name}}</td><td>{{x.declaration_no}}</td><td>{{x.manifest_no}}</td><td>{{x.vehicle_no}}</td><td>{{x.status}}</td><td><a class="btn small dark" href="{{url_for('case_detail',cid=x.id)}}">فتح</a></td></tr>{% endfor %}</table></div></div>'''
    return layout('مركز المعاملات',body,rows=rows,comps=comps,next_no=next_case_no(),today=date.today().isoformat(),types=DECL_TYPES,edit=can_edit())

@app.route('/cases/<int:cid>',methods=['GET','POST'])
@login_required
def case_detail(cid):
    c=ServiceCase.query.get_or_404(cid)
    if request.method=='POST' and can_finance():
        action=request.form.get('action')
        if action=='charge': db.session.add(ServiceCaseCharge(case_id=cid,charge_type=sval(request.form.get('charge_type')),description=sval(request.form.get('description')),amount=fnum(request.form.get('amount')),required=bool(request.form.get('required')),billable=bool(request.form.get('billable')),paid=fnum(request.form.get('paid'))))
        elif action=='payment':
            amt=fnum(request.form.get('amount')); direction=sval(request.form.get('direction')) or 'receipt'; db.session.add(ServiceCasePayment(case_id=cid,payment_date=sval(request.form.get('payment_date')) or date.today().isoformat(),amount=amt,direction=direction,description=sval(request.form.get('description')))); db.session.add(CashTransaction(txn_date=sval(request.form.get('payment_date')) or date.today().isoformat(),direction='in' if direction=='receipt' else 'out',category='مركز المعاملات',amount=amt,company_id=c.company_id,description=sval(request.form.get('description')),reference=c.case_no,created_by=session.get('username','')))
        db.session.commit(); return redirect(url_for('case_detail',cid=cid))
    total=sum(x.amount or 0 for x in c.charges if x.billable); paid=sum(x.paid or 0 for x in c.charges)+sum(x.amount or 0 for x in c.payments if x.direction=='receipt')
    body='''<div class="hero"><h1>المعاملة {{c.case_no}}</h1><p>{{c.case_type}} • {{c.company.name if c.company else c.customer_name}} • {{c.status}}</p></div><div class="grid"><div class="card stat"><div class="label">تكاليف قابلة للفوترة</div><div class="n">{{'%.2f'|format(total)}}</div></div><div class="card stat"><div class="label">المقبوض</div><div class="n">{{'%.2f'|format(paid)}}</div></div><div class="card stat"><div class="label">المتبقي</div><div class="n">{{'%.2f'|format(total-paid)}}</div></div></div>{% if finance %}<div class="split no-print"><div class="card"><div class="section-title">إضافة تكلفة</div><form method="post"><input type="hidden" name="action" value="charge"><div class="formgrid"><div class="field"><label>النوع</label><select name="charge_type"><option>رسوم جمركية</option><option>فيزا</option><option>عبور</option><option>تأمين</option><option>معاملة المكتب</option><option>سيارة سورية</option><option>مصاريف إضافية</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount"></div><div class="field"><label>المدفوع</label><input type="number" step="0.01" name="paid"></div><div class="field full"><label>الوصف</label><input name="description"></div><label><input type="checkbox" name="required" checked style="width:auto"> مطلوب</label><label><input type="checkbox" name="billable" checked style="width:auto"> على حساب العميل</label></div><button class="btn">إضافة</button></form></div><div class="card"><div class="section-title">إضافة قبض / دفع</div><form method="post"><input type="hidden" name="action" value="payment"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="payment_date" value="{{today}}"></div><div class="field"><label>النوع</label><select name="direction"><option value="receipt">قبض</option><option value="payment">دفع</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount"></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn blue">حفظ</button></form></div></div>{% endif %}<div class="split"><div class="card"><div class="section-title">التكاليف</div><div class="tablewrap"><table><tr><th>النوع</th><th>الوصف</th><th>المبلغ</th><th>المدفوع</th><th>على العميل</th></tr>{% for x in c.charges %}<tr><td>{{x.charge_type}}</td><td>{{x.description}}</td><td>{{x.amount}}</td><td>{{x.paid}}</td><td>{{'نعم' if x.billable else 'لا'}}</td></tr>{% endfor %}</table></div></div><div class="card"><div class="section-title">الدفعات</div><div class="tablewrap"><table><tr><th>التاريخ</th><th>النوع</th><th>المبلغ</th><th>الوصف</th></tr>{% for x in c.payments %}<tr><td>{{x.payment_date}}</td><td>{{'قبض' if x.direction=='receipt' else 'دفع'}}</td><td>{{x.amount}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div></div></div>'''
    return layout('ملف المعاملة',body,c=c,total=total,paid=paid,finance=can_finance(),today=date.today().isoformat())

# -------------------- invoices --------------------
@app.route('/invoices')
@login_required
def invoices():
    rows=SalesInvoice.query.order_by(SalesInvoice.id.desc()).all()
    body='''<div class="hero"><h1>الفواتير</h1><p>فاتورة مرتبطة بالشركة والبيان أو الرحلة، مع المدفوع والمتبقي وطريقة الدفع.</p></div><div class="toolbar no-print"><a class="btn" href="{{url_for('invoice_new')}}">＋ فاتورة جديدة</a><button class="btn dark" onclick="window.print()">PDF / طباعة</button></div><div class="card"><div class="tablewrap"><table><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>الشركة</th><th>البيان</th><th>الرحلة</th><th>الإجمالي</th><th>المدفوع</th><th>المتبقي</th><th>الطريقة</th><th>الحالة</th><th></th></tr>{% for x in rows %}<tr><td>{{x.invoice_no}}</td><td>{{x.invoice_date}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.declaration.declaration_no if x.declaration else '—'}}</td><td>{{x.job_id or '—'}}</td><td>{{'%.2f'|format(x.total or 0)}}</td><td>{{'%.2f'|format(x.paid or 0)}}</td><td class="amount">{{'%.2f'|format(x.remaining)}}</td><td>{{x.payment_method}}</td><td>{{x.status}}</td><td><a class="btn small dark" href="{{url_for('invoice_detail',iid=x.id)}}">فتح</a></td></tr>{% endfor %}</table></div></div>'''
    return layout('الفواتير',body,rows=rows)

@app.route('/invoices/new',methods=['GET','POST'])
@login_required
def invoice_new():
    if not can_finance(): flash('هذه العملية للمحاسبة','error'); return redirect(url_for('invoices'))
    declaration_id=request.args.get('declaration_id',type=int); job_id=request.args.get('job_id',type=int)
    d=CustomsDeclaration.query.get(declaration_id) if declaration_id else None; j=TransportJob.query.get(job_id) if job_id else None
    if request.method=='POST':
        desc=sval(request.form.get('line_desc')); qty=fnum(request.form.get('qty')) or 1; unit=fnum(request.form.get('unit_price')); subtotal=qty*unit; discount=fnum(request.form.get('discount')); total=max(0,subtotal-discount); paid=min(total,fnum(request.form.get('paid'))); status='مسددة' if paid>=total and total>0 else ('جزئية' if paid>0 else 'غير مسددة')
        inv=SalesInvoice(invoice_no=sval(request.form.get('invoice_no')) or next_invoice_no(),invoice_date=sval(request.form.get('invoice_date')) or date.today().isoformat(),company_id=request.form.get('company_id') or None,declaration_id=request.form.get('declaration_id') or None,job_id=request.form.get('job_id') or None,description=sval(request.form.get('description')),subtotal=subtotal,discount=discount,total=total,paid=paid,payment_method=sval(request.form.get('payment_method')),status=status); db.session.add(inv); db.session.flush(); db.session.add(InvoiceLine(invoice_id=inv.id,description=desc,qty=qty,unit_price=unit,amount=subtotal))
        journal('فاتورة مبيعات', [('1100',total,0,desc),('4000',0,total,desc)],'invoice',inv.id,inv.invoice_date)
        if paid>0:
            db.session.add(CashTransaction(txn_date=inv.invoice_date,direction='in',category='تحصيل فاتورة',amount=paid,company_id=inv.company_id,description=f'دفعة فاتورة {inv.invoice_no}',reference=inv.invoice_no,created_by=session.get('username',''))); journal('تحصيل فاتورة',[('1000',paid,0,inv.invoice_no),('1100',0,paid,inv.invoice_no)],'invoice_payment',inv.id,inv.invoice_date)
        db.session.commit(); audit('إنشاء فاتورة','invoice',inv.id,inv.invoice_no); return redirect(url_for('invoice_detail',iid=inv.id))
    comps=Company.query.order_by(Company.name).all(); decls=CustomsDeclaration.query.order_by(CustomsDeclaration.id.desc()).all(); trips_=TransportJob.query.order_by(TransportJob.id.desc()).all(); default_price=0; default_desc=''
    if d: default_price=sum(x.amount or 0 for x in d.charges); default_desc=f'رسوم وخدمات البيان {d.declaration_no}'
    elif j: default_price=j.company_price or 0; default_desc=f'خدمات الرحلة #{j.id} - منافيست {j.manifest_no}'
    body='''<div class="hero"><h1>فاتورة جديدة</h1><p>ترقيم تلقائي وربط بالبيان أو الرحلة مع حساب المتبقي.</p></div><div class="card"><form method="post"><div class="formgrid"><div class="field"><label>رقم الفاتورة</label><input name="invoice_no" value="{{inv_no}}"></div><div class="field"><label>التاريخ</label><input type="date" name="invoice_date" value="{{today}}"></div><div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}" {% if d and d.company_id==c.id or j and j.company_id==c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select></div><div class="field"><label>البيان</label><select name="declaration_id"><option value="">—</option>{% for x in decls %}<option value="{{x.id}}" {% if d and d.id==x.id %}selected{% endif %}>{{x.declaration_no}}</option>{% endfor %}</select></div><div class="field"><label>الرحلة</label><select name="job_id"><option value="">—</option>{% for x in trips %}<option value="{{x.id}}" {% if j and j.id==x.id %}selected{% endif %}>#{{x.id}} - {{x.manifest_no}}</option>{% endfor %}</select></div><div class="field"><label>طريقة الدفع</label><select name="payment_method"><option>نقدي</option><option>تحويل</option><option>آجل</option></select></div><div class="field full"><label>بيان الفاتورة</label><input name="description" value="{{default_desc}}"></div></div><hr style="border:0;border-top:1px solid #eee;margin:15px 0"><div class="formgrid"><div class="field full"><label>وصف البند</label><input name="line_desc" value="{{default_desc}}"></div><div class="field"><label>الكمية</label><input type="number" step="0.01" name="qty" value="1"></div><div class="field"><label>سعر الوحدة</label><input type="number" step="0.01" name="unit_price" value="{{default_price}}"></div><div class="field"><label>الخصم</label><input type="number" step="0.01" name="discount" value="0"></div><div class="field"><label>المدفوع</label><input type="number" step="0.01" name="paid" value="0"></div></div><button class="btn green" style="margin-top:12px">حفظ الفاتورة</button></form></div>'''
    return layout('فاتورة جديدة',body,inv_no=next_invoice_no(),today=date.today().isoformat(),comps=comps,decls=decls,trips=trips_,d=d,j=j,default_price=default_price,default_desc=default_desc)

@app.route('/invoices/<int:iid>',methods=['GET','POST'])
@login_required
def invoice_detail(iid):
    x=SalesInvoice.query.get_or_404(iid)
    if request.method=='POST' and can_finance():
        amt=fnum(request.form.get('amount'))
        if amt>0:
            x.paid=min(float(x.total or 0),float(x.paid or 0)+amt); x.status='مسددة' if x.paid>=x.total else 'جزئية'; db.session.add(CashTransaction(txn_date=sval(request.form.get('date')) or date.today().isoformat(),direction='in',category='تحصيل فاتورة',amount=amt,company_id=x.company_id,description=sval(request.form.get('description')) or f'دفعة {x.invoice_no}',reference=x.invoice_no,created_by=session.get('username',''))); journal('تحصيل فاتورة',[('1000',amt,0,x.invoice_no),('1100',0,amt,x.invoice_no)],'invoice_payment',x.id,sval(request.form.get('date')) or date.today().isoformat()); db.session.commit(); audit('دفعة فاتورة','invoice',x.id,str(amt))
        return redirect(url_for('invoice_detail',iid=iid))
    body='''<div class="hero"><h1>الفاتورة {{x.invoice_no}}</h1><p>{{x.company.name if x.company else '—'}} • {{x.invoice_date}} • {{x.status}}</p></div><div class="toolbar no-print"><button class="btn dark" onclick="window.print()">📄 حفظ PDF / طباعة</button><a class="btn amber" href="{{url_for('entity_attachments',source_type='invoice',source_id=x.id)}}">📎 المرفقات</a></div><div class="grid"><div class="card stat"><div class="label">الإجمالي</div><div class="n">{{'%.2f'|format(x.total or 0)}}</div></div><div class="card stat"><div class="label">المدفوع</div><div class="n">{{'%.2f'|format(x.paid or 0)}}</div></div><div class="card stat"><div class="label">المتبقي</div><div class="n">{{'%.2f'|format(x.remaining)}}</div></div></div><div class="card"><div class="tablewrap"><table><tr><th>الوصف</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr>{% for l in x.lines %}<tr><td>{{l.description}}</td><td>{{l.qty}}</td><td>{{l.unit_price}}</td><td>{{l.amount}}</td></tr>{% endfor %}</table></div><p>الخصم: {{x.discount}} | طريقة الدفع: {{x.payment_method}}</p></div>{% if finance and x.remaining>0 %}<div class="card no-print"><div class="section-title">تسجيل دفعة جديدة</div><form method="post"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="date" value="{{today}}"></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" max="{{x.remaining}}" name="amount" required></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn blue">تسجيل الدفعة</button></form></div>{% endif %}'''
    return layout('الفاتورة',body,x=x,finance=can_finance(),today=date.today().isoformat())

# -------------------- cash, expenses, accounting --------------------
@app.route('/cash',methods=['GET','POST'])
@login_required
def cash():
    if request.method=='POST' and can_finance():
        amt=fnum(request.form.get('amount')); direction=sval(request.form.get('direction')); dt=sval(request.form.get('txn_date')) or date.today().isoformat(); desc=sval(request.form.get('description')); cat=sval(request.form.get('category'))
        db.session.add(CashTransaction(txn_date=dt,direction=direction,category=cat,amount=amt,company_id=request.form.get('company_id') or None,description=desc,reference=sval(request.form.get('reference')),created_by=session.get('username','')))
        if direction=='in': journal(desc or 'وارد صندوق',[('1000',amt,0,desc),('4000',0,amt,desc)],'cash',None,dt)
        else: journal(desc or 'صادر صندوق',[('5000',amt,0,desc),('1000',0,amt,desc)],'cash',None,dt)
        db.session.commit(); audit('حركة صندوق','cash',None,desc); return redirect(url_for('cash'))
    rows=CashTransaction.query.order_by(CashTransaction.id.desc()).all(); incoming=sum(x.amount or 0 for x in rows if x.direction=='in'); outgoing=sum(x.amount or 0 for x in rows if x.direction=='out'); comps=Company.query.order_by(Company.name).all()
    body='''<div class="hero"><h1>الصندوق — وارد / صادر</h1><p>كل حركة مرتبطة بالمرجع والشركة والمستخدم.</p></div><div class="grid"><div class="card stat"><div class="label">الوارد</div><div class="n">{{'%.2f'|format(incoming)}}</div></div><div class="card stat"><div class="label">الصادر</div><div class="n">{{'%.2f'|format(outgoing)}}</div></div><div class="card stat"><div class="label">الرصيد</div><div class="n">{{'%.2f'|format(incoming-outgoing)}}</div></div></div>{% if finance %}<div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="txn_date" value="{{today}}"></div><div class="field"><label>الحركة</label><select name="direction"><option value="in">وارد</option><option value="out">صادر</option></select></div><div class="field"><label>التصنيف</label><input name="category" value="عام"></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div class="field"><label>الشركة</label><select name="company_id"><option value="">—</option>{% for c in comps %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div><div class="field"><label>المرجع</label><input name="reference"></div><div class="field full"><label>البيان</label><input name="description"></div></div><button class="btn" style="margin-top:10px">حفظ الحركة</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>التاريخ</th><th>الحركة</th><th>التصنيف</th><th>المبلغ</th><th>الشركة</th><th>المرجع</th><th>الوصف</th><th>المستخدم</th></tr>{% for x in rows %}<tr><td>{{x.txn_date}}</td><td>{{'وارد' if x.direction=='in' else 'صادر'}}</td><td>{{x.category}}</td><td>{{'%.2f'|format(x.amount or 0)}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.reference}}</td><td>{{x.description}}</td><td>{{x.created_by}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('الصندوق',body,rows=rows,incoming=incoming,outgoing=outgoing,finance=can_finance(),today=date.today().isoformat(),comps=comps)

@app.route('/expenses',methods=['GET','POST'])
@login_required
def expenses():
    if request.method=='POST' and can_finance():
        amt=fnum(request.form.get('amount')); dt=sval(request.form.get('expense_date')) or date.today().isoformat(); desc=sval(request.form.get('description')); cat=sval(request.form.get('category'))
        db.session.add(Expense(expense_date=dt,category=cat,amount=amt,description=desc)); db.session.add(CashTransaction(txn_date=dt,direction='out',category=cat,amount=amt,description=desc,created_by=session.get('username',''))); journal(desc or cat,[('5000',amt,0,desc),('1000',0,amt,desc)],'expense',None,dt); db.session.commit(); audit('مصروف','expense',None,desc); return redirect(url_for('expenses'))
    rows=Expense.query.order_by(Expense.id.desc()).all(); total=sum(x.amount or 0 for x in rows)
    body='''<div class="hero"><h1>المصروفات</h1><p>رواتب، تشغيل، نقل، رسوم، ومصاريف إدارية.</p></div><div class="card stat"><div class="label">إجمالي المصروفات</div><div class="n">{{'%.2f'|format(total)}}</div></div>{% if finance %}<div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>التاريخ</label><input type="date" name="expense_date" value="{{today}}"></div><div class="field"><label>التصنيف</label><select name="category"><option>رواتب وأجور</option><option>مصاريف تشغيل</option><option>نقل وسيارات</option><option>رسوم وعبور وفيزا</option><option>مصاريف إدارية</option><option>أخرى</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount" required></div><div class="field full"><label>الوصف</label><input name="description"></div></div><button class="btn red" style="margin-top:10px">تسجيل المصروف</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>التاريخ</th><th>التصنيف</th><th>المبلغ</th><th>الوصف</th></tr>{% for x in rows %}<tr><td>{{x.expense_date}}</td><td>{{x.category}}</td><td>{{x.amount}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('المصروفات',body,rows=rows,total=total,finance=can_finance(),today=date.today().isoformat())

@app.route('/accounting')
@login_required
def accounting():
    cash_in=sum(x.amount or 0 for x in CashTransaction.query.filter_by(direction='in').all()); cash_out=sum(x.amount or 0 for x in CashTransaction.query.filter_by(direction='out').all()); revenue=sum(x.total or 0 for x in SalesInvoice.query.all()); exp=sum(x.amount or 0 for x in Expense.query.all()); recv=sum(x.remaining for x in SalesInvoice.query.all()); cap=0
    for s in Shareholder.query.all(): cap+=sum((m.amount if m.txn_type in ('capital','additional') else -m.amount) for m in s.movements)
    body='''<div class="hero"><h1>المحاسبة</h1><p>لوحة محاسبية موحدة: الصندوق، الإيرادات، المصروفات، الذمم، رأس المال، والقيود.</p></div><div class="grid"><div class="card stat"><div class="label">رصيد الصندوق</div><div class="n">{{'%.2f'|format(cash_in-cash_out)}}</div></div><div class="card stat"><div class="label">إجمالي الفواتير</div><div class="n">{{'%.2f'|format(revenue)}}</div></div><div class="card stat"><div class="label">المصروفات</div><div class="n">{{'%.2f'|format(exp)}}</div></div><div class="card stat"><div class="label">الذمم</div><div class="n">{{'%.2f'|format(recv)}}</div></div><div class="card stat"><div class="label">رأس المال</div><div class="n">{{'%.2f'|format(cap)}}</div></div><div class="card stat"><div class="label">صافي تقريبي</div><div class="n">{{'%.2f'|format(revenue-exp)}}</div></div></div><div class="grid"><a class="card" href="{{url_for('journal_page')}}"><b>📒 القيود اليومية</b><p class="muted">عرض وترحيل القيود</p></a><a class="card" href="{{url_for('accounts_page')}}"><b>📚 دليل الحسابات</b><p class="muted">الأصول، الخصوم، الإيرادات والمصروفات</p></a><a class="card" href="{{url_for('shareholders')}}"><b>🤝 الشركاء ورأس المال</b><p class="muted">المساهمات والسحوبات</p></a><a class="card" href="{{url_for('reports')}}"><b>📊 الجرد والتقارير</b><p class="muted">شهري، ربع سنوي، نصف سنوي، سنوي</p></a></div>'''
    return layout('المحاسبة',body,cash_in=cash_in,cash_out=cash_out,revenue=revenue,exp=exp,recv=recv,cap=cap)

@app.route('/accounts')
@login_required
def accounts_page():
    rows=Account.query.order_by(Account.code.asc()).all(); body='''<div class="hero"><h1>دليل الحسابات</h1><p>الحسابات الأساسية المستخدمة في القيود والترحيل.</p></div><div class="card"><div class="tablewrap"><table><tr><th>الكود</th><th>اسم الحساب</th><th>النوع</th><th>الحالة</th></tr>{% for x in rows %}<tr><td>{{x.code}}</td><td>{{x.name}}</td><td>{{x.type}}</td><td>{{'فعال' if x.active else 'موقوف'}}</td></tr>{% endfor %}</table></div></div>'''; return layout('دليل الحسابات',body,rows=rows)

@app.route('/journal')
@login_required
def journal_page():
    rows=JournalEntry.query.order_by(JournalEntry.id.desc()).limit(300).all(); body='''<div class="hero"><h1>القيود اليومية والترحيل</h1><p>كل حركة مالية آلية تظهر بقيدها المدين والدائن.</p></div><div class="card"><div class="tablewrap"><table><tr><th>#</th><th>التاريخ</th><th>البيان</th><th>المرجع</th><th>مدين</th><th>دائن</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.entry_date}}</td><td>{{x.description}}</td><td>{{x.ref_type}} {{x.ref_id or ''}}</td><td>{{'%.2f'|format(x.lines|sum(attribute='debit'))}}</td><td>{{'%.2f'|format(x.lines|sum(attribute='credit'))}}</td></tr>{% endfor %}</table></div></div>'''; return layout('القيود اليومية',body,rows=rows)

# -------------------- shareholders --------------------
@app.route('/shareholders',methods=['GET','POST'])
@login_required
def shareholders():
    if request.method=='POST' and can_finance():
        action=request.form.get('action','new')
        if action=='new':
            name=sval(request.form.get('name')); s=Shareholder(name=name,phone=sval(request.form.get('phone')),capital_commitment=fnum(request.form.get('capital_commitment')),capital_percentage=fnum(request.form.get('capital_percentage')),note=sval(request.form.get('note'))); db.session.add(s); db.session.flush(); amt=fnum(request.form.get('amount')); 
            if amt>0: db.session.add(CapitalMovement(shareholder_id=s.id,amount=amt,txn_type='capital',txn_date=sval(request.form.get('txn_date')) or date.today().isoformat(),note='رأس مال مدفوع')); journal('رأس مال مدفوع',[('1000',amt,0,name),('3000',0,amt,name)],'capital',s.id,sval(request.form.get('txn_date')) or date.today().isoformat())
        else:
            sid=int(request.form.get('shareholder_id')); s=Shareholder.query.get_or_404(sid); amt=fnum(request.form.get('amount')); typ=sval(request.form.get('txn_type')); current=sum((m.amount if m.txn_type in ('capital','additional') else -m.amount) for m in s.movements)
            if typ=='draw' and amt>current: flash('السحب أكبر من رصيد الشريك','error'); return redirect(url_for('shareholders'))
            db.session.add(CapitalMovement(shareholder_id=sid,amount=amt,txn_type=typ,txn_date=sval(request.form.get('txn_date')) or date.today().isoformat(),note=sval(request.form.get('note'))));
            if typ=='draw': journal('سحب شريك',[('3000',amt,0,s.name),('1000',0,amt,s.name)],'capital',sid,sval(request.form.get('txn_date')) or date.today().isoformat())
            else: journal('زيادة رأس مال',[('1000',amt,0,s.name),('3000',0,amt,s.name)],'capital',sid,sval(request.form.get('txn_date')) or date.today().isoformat())
        db.session.commit(); return redirect(url_for('shareholders'))
    rows=Shareholder.query.order_by(Shareholder.id.asc()).all()
    body='''<div class="hero"><h1>الشركاء ورأس المال</h1><p>أسماء الشركاء، رأس المال المتفق عليه، النسبة، المساهمات، الإضافات والسحوبات.</p></div>{% if finance %}<div class="split no-print"><div class="card"><div class="section-title">إضافة شريك</div><form method="post"><input type="hidden" name="action" value="new"><div class="formgrid"><div class="field"><label>اسم الشريك</label><input name="name" required></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field"><label>رأس المال المتفق</label><input type="number" step="0.01" name="capital_commitment"></div><div class="field"><label>النسبة %</label><input type="number" step="0.01" name="capital_percentage"></div><div class="field"><label>المبلغ المدفوع</label><input type="number" step="0.01" name="amount"></div><div class="field"><label>التاريخ</label><input type="date" name="txn_date" value="{{today}}"></div></div><button class="btn green">إضافة</button></form></div><div class="card"><div class="section-title">حركة رأس مال</div><form method="post"><input type="hidden" name="action" value="move"><div class="formgrid"><div class="field"><label>الشريك</label><select name="shareholder_id">{% for x in rows %}<option value="{{x.id}}">{{x.name}}</option>{% endfor %}</select></div><div class="field"><label>الحركة</label><select name="txn_type"><option value="additional">مساهمة إضافية</option><option value="draw">سحب من رأس المال</option></select></div><div class="field"><label>المبلغ</label><input type="number" step="0.01" name="amount"></div><div class="field"><label>التاريخ</label><input type="date" name="txn_date" value="{{today}}"></div><div class="field full"><label>البيان</label><input name="note"></div></div><button class="btn blue">حفظ الحركة</button></form></div></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>الشريك</th><th>المتفق عليه</th><th>النسبة</th><th>المدفوع</th><th>الإضافات</th><th>السحوبات</th><th>صافي المساهمة</th><th>المتبقي</th></tr>{% for x in rows %}{% set cap=x.movements|selectattr('txn_type','equalto','capital')|sum(attribute='amount') %}{% set add=x.movements|selectattr('txn_type','equalto','additional')|sum(attribute='amount') %}{% set draw=x.movements|selectattr('txn_type','equalto','draw')|sum(attribute='amount') %}{% set net=cap+add-draw %}<tr><td>{{x.name}}</td><td>{{'%.2f'|format(x.capital_commitment or 0)}}</td><td>{{'%.2f'|format(x.capital_percentage or 0)}}%</td><td>{{'%.2f'|format(cap)}}</td><td>{{'%.2f'|format(add)}}</td><td>{{'%.2f'|format(draw)}}</td><td class="amount">{{'%.2f'|format(net)}}</td><td>{{'%.2f'|format([0,(x.capital_commitment or 0)-net]|max)}}</td></tr>{% endfor %}</table></div></div>'''
    return layout('الشركاء ورأس المال',body,rows=rows,finance=can_finance(),today=date.today().isoformat())

# -------------------- attachments --------------------
@app.route('/attachments')
@login_required
def attachments():
    rows=V3Attachment.query.order_by(V3Attachment.id.desc()).limit(500).all(); body='''<div class="hero"><h1>مركز المرفقات</h1><p>كل مرفقات البيانات والرحلات والفواتير والمعاملات في مكان واحد.</p></div><div class="card"><div class="tablewrap"><table><tr><th>#</th><th>المصدر</th><th>ID</th><th>التصنيف</th><th>الملف</th><th>التاريخ</th><th></th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.source_type}}</td><td>{{x.source_id}}</td><td>{{x.category}}</td><td>{{x.original_name}}</td><td>{{x.created_at.strftime('%Y-%m-%d %H:%M') if x.created_at else ''}}</td><td><a class="btn small blue" href="{{url_for('attachment_download',aid=x.id)}}">فتح</a></td></tr>{% endfor %}</table></div></div>'''; return layout('المرفقات',body,rows=rows)

@app.route('/attachments/<source_type>/<int:source_id>',methods=['GET','POST'])
@login_required
def entity_attachments(source_type,source_id):
    if request.method=='POST' and can_edit():
        f=request.files.get('file')
        if f and f.filename:
            db.session.add(V3Attachment(source_type=source_type,source_id=source_id,category=sval(request.form.get('category')) or 'أخرى',original_name=f.filename,mime_type=f.mimetype or 'application/octet-stream',data=f.read(),note=sval(request.form.get('note')))); db.session.commit(); audit('رفع مرفق','attachment',source_id,f.filename)
        return redirect(url_for('entity_attachments',source_type=source_type,source_id=source_id))
    rows=V3Attachment.query.filter_by(source_type=source_type,source_id=source_id).order_by(V3Attachment.id.desc()).all(); body='''<div class="hero"><h1>المرفقات — {{source_type}} #{{source_id}}</h1></div>{% if edit %}<div class="card no-print"><form method="post" enctype="multipart/form-data"><div class="formgrid"><div class="field"><label>الملف</label><input type="file" name="file" required></div><div class="field"><label>التصنيف</label><select name="category"><option>CMR</option><option>فاتورة</option><option>بيان</option><option>هوية / وثيقة</option><option>صورة</option><option>أخرى</option></select></div><div class="field full"><label>ملاحظة</label><input name="note"></div></div><button class="btn amber">رفع المرفق</button></form></div>{% endif %}<div class="card"><div class="tablewrap"><table><tr><th>التصنيف</th><th>الملف</th><th>ملاحظة</th><th>التاريخ</th><th></th></tr>{% for x in rows %}<tr><td>{{x.category}}</td><td>{{x.original_name}}</td><td>{{x.note}}</td><td>{{x.created_at.strftime('%Y-%m-%d %H:%M')}}</td><td><a class="btn small blue" href="{{url_for('attachment_download',aid=x.id)}}">فتح / تحميل</a></td></tr>{% endfor %}</table></div></div>'''; return layout('المرفقات',body,rows=rows,source_type=source_type,source_id=source_id,edit=can_edit())

@app.route('/attachment/<int:aid>')
@login_required
def attachment_download(aid):
    x=V3Attachment.query.get_or_404(aid); return send_file(io.BytesIO(x.data),mimetype=x.mime_type,download_name=x.original_name,as_attachment=False)

# -------------------- reports --------------------
@app.route('/reports')
@login_required
def reports():
    period=sval(request.args.get('period')) or 'monthly'; y=request.args.get('year',type=int) or date.today().year; m=request.args.get('month',type=int) or date.today().month
    if period=='monthly': start=f'{y:04d}-{m:02d}-01'; end=f'{y:04d}-{m:02d}-31'; title='شهري'
    elif period=='quarter':
        q=((m-1)//3)*3+1; start=f'{y:04d}-{q:02d}-01'; end=f'{y:04d}-{q+2:02d}-31'; title='ربع سنوي'
    elif period=='half': start=f'{y:04d}-{1 if m<=6 else 7:02d}-01'; end=f'{y:04d}-{6 if m<=6 else 12:02d}-31'; title='نصف سنوي'
    else: start=f'{y:04d}-01-01'; end=f'{y:04d}-12-31'; title='سنوي'
    cash_rows=CashTransaction.query.filter(CashTransaction.txn_date>=start,CashTransaction.txn_date<=end).all(); invs=SalesInvoice.query.filter(SalesInvoice.invoice_date>=start,SalesInvoice.invoice_date<=end).all(); exps=Expense.query.filter(Expense.expense_date>=start,Expense.expense_date<=end).all(); incoming=sum(x.amount or 0 for x in cash_rows if x.direction=='in'); outgoing=sum(x.amount or 0 for x in cash_rows if x.direction=='out'); revenue=sum(x.total or 0 for x in invs); exp=sum(x.amount or 0 for x in exps); recv=sum(x.remaining for x in invs)
    body='''<div class="hero"><h1>الجرد والتقارير — {{title}}</h1><p>{{start}} إلى {{end}}</p></div><div class="card no-print"><form class="search"><select name="period"><option value="monthly" {% if period=='monthly' %}selected{% endif %}>شهري</option><option value="quarter" {% if period=='quarter' %}selected{% endif %}>ربع سنوي</option><option value="half" {% if period=='half' %}selected{% endif %}>نصف سنوي</option><option value="year" {% if period=='year' %}selected{% endif %}>سنوي</option></select><input type="number" name="year" value="{{year}}"><input type="number" min="1" max="12" name="month" value="{{month}}"><button class="btn">عرض</button></form></div><div class="toolbar no-print"><button class="btn dark" onclick="window.print()">📄 حفظ PDF / طباعة التقرير</button></div><div class="grid"><div class="card stat"><div class="label">الوارد</div><div class="n">{{'%.2f'|format(incoming)}}</div></div><div class="card stat"><div class="label">الصادر</div><div class="n">{{'%.2f'|format(outgoing)}}</div></div><div class="card stat"><div class="label">الفواتير</div><div class="n">{{'%.2f'|format(revenue)}}</div></div><div class="card stat"><div class="label">المصروفات</div><div class="n">{{'%.2f'|format(exp)}}</div></div><div class="card stat"><div class="label">صافي تقريبي</div><div class="n">{{'%.2f'|format(revenue-exp)}}</div></div><div class="card stat"><div class="label">ذمم الفترة</div><div class="n">{{'%.2f'|format(recv)}}</div></div></div><div class="split"><div class="card"><div class="section-title">الفواتير</div><div class="tablewrap"><table><tr><th>الرقم</th><th>الشركة</th><th>الإجمالي</th><th>المدفوع</th><th>المتبقي</th></tr>{% for x in invs %}<tr><td>{{x.invoice_no}}</td><td>{{x.company.name if x.company else '—'}}</td><td>{{x.total}}</td><td>{{x.paid}}</td><td>{{x.remaining}}</td></tr>{% endfor %}</table></div></div><div class="card"><div class="section-title">حركة الصندوق</div><div class="tablewrap"><table><tr><th>التاريخ</th><th>الحركة</th><th>المبلغ</th><th>البيان</th></tr>{% for x in cash_rows %}<tr><td>{{x.txn_date}}</td><td>{{'وارد' if x.direction=='in' else 'صادر'}}</td><td>{{x.amount}}</td><td>{{x.description}}</td></tr>{% endfor %}</table></div></div></div>'''
    return layout('الجرد والتقارير',body,period=period,year=y,month=m,title=title,start=start,end=end,incoming=incoming,outgoing=outgoing,revenue=revenue,exp=exp,recv=recv,invs=invs,cash_rows=cash_rows)

# -------------------- settings/users/audit --------------------
@app.route('/settings',methods=['GET','POST'])
@login_required
@role_required('admin')
def settings():
    keys=['company_name','address','phone','currency','report_footer']
    if request.method=='POST':
        for k in keys: put_setting(k,sval(request.form.get(k)))
        db.session.commit(); return redirect(url_for('settings'))
    v={k:get_setting(k,'') for k in keys}; body='''<div class="hero"><h1>إعدادات الشركة</h1><p>الاسم والعنوان والهاتف والعملة وتذييل التقارير.</p></div><div class="card"><form method="post"><div class="formgrid"><div class="field full"><label>اسم الشركة</label><input name="company_name" value="{{v.company_name}}"></div><div class="field"><label>العنوان</label><input name="address" value="{{v.address}}"></div><div class="field"><label>الهاتف</label><input name="phone" value="{{v.phone}}"></div><div class="field"><label>العملة</label><input name="currency" value="{{v.currency}}"></div><div class="field full"><label>تذييل التقارير</label><input name="report_footer" value="{{v.report_footer}}"></div></div><button class="btn">حفظ</button></form></div>'''; return layout('الإعدادات',body,v=v)

@app.route('/users',methods=['GET','POST'])
@login_required
@role_required('admin')
def users():
    if request.method=='POST':
        name=sval(request.form.get('username'))
        if User.query.filter_by(username=name).first(): flash('اسم المستخدم موجود','error')
        else: db.session.add(User(username=name,password_hash=generate_password_hash(request.form.get('password','')),role=sval(request.form.get('role')) or 'viewer',active=True)); db.session.commit()
        return redirect(url_for('users'))
    rows=User.query.order_by(User.id.asc()).all(); body='''<div class="hero"><h1>المستخدمون والصلاحيات</h1><p>مدير، محاسب، نقل، موظف، مشاهدة فقط.</p></div><div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>اسم المستخدم</label><input name="username" required></div><div class="field"><label>كلمة المرور</label><input type="password" name="password" required></div><div class="field"><label>الصلاحية</label><select name="role"><option value="admin">مدير</option><option value="accountant">محاسب</option><option value="transport">نقل وترانزيت</option><option value="user">موظف</option><option value="viewer">مشاهدة فقط</option></select></div></div><button class="btn">إضافة المستخدم</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>المستخدم</th><th>الصلاحية</th><th>الحالة</th></tr>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.username}}</td><td>{{x.role}}</td><td>{{'فعال' if x.active else 'موقوف'}}</td></tr>{% endfor %}</table></div></div>'''; return layout('المستخدمون',body,rows=rows)

@app.route('/audit')
@login_required
@role_required('admin')
def audit_page():
    rows=AuditLog.query.order_by(AuditLog.id.desc()).limit(500).all(); body='''<div class="hero"><h1>سجل التدقيق</h1><p>من قام بأي عملية ومتى وعلى أي ملف.</p></div><div class="card"><div class="tablewrap"><table><tr><th>التاريخ</th><th>المستخدم</th><th>العملية</th><th>الكيان</th><th>ID</th><th>التفاصيل</th></tr>{% for x in rows %}<tr><td>{{x.created_at.strftime('%Y-%m-%d %H:%M:%S')}}</td><td>{{x.username}}</td><td>{{x.action}}</td><td>{{x.entity}}</td><td>{{x.entity_id}}</td><td>{{x.details}}</td></tr>{% endfor %}</table></div></div>'''; return layout('سجل التدقيق',body,rows=rows)

# -------------------- initialization --------------------
def migrate_v2_data():
    # Best-effort migration from the temporary V2 declaration table if it exists.
    try:
        insp=db.inspect(db.engine)
        if 'declaration' in insp.get_table_names() and CustomsDeclaration.query.count()==0:
            rows=db.session.execute(db.text('SELECT * FROM declaration ORDER BY id')).mappings().all()
            for r in rows:
                no=str(r.get('ref_no') or '').strip()
                if not no: continue
                d=CustomsDeclaration(declaration_no=no,declaration_type=r.get('decl_type') or 'بيان داخلي',company_id=r.get('company_id'),status=r.get('status') or 'مفتوح',note=r.get('notes') or '',declaration_date=date.today().isoformat())
                db.session.add(d); db.session.flush()
                mapping=[('رسوم جمركية',r.get('customs_fees')),('سيارة سورية',r.get('transport_fees')),('معاملة المكتب',r.get('office_fees')),('مصاريف إضافية',r.get('extra_fees')),('فيزا',r.get('visa_fees')),('عبور',r.get('transit_fees')),('تأمين',r.get('insurance_fees'))]
                for t,a in mapping:
                    if fnum(a): db.session.add(DeclarationCharge(declaration_id=d.id,charge_type=t,amount=fnum(a),required=True,paid=0))
            db.session.commit()
    except Exception:
        db.session.rollback()

with app.app_context():
    db.create_all()
    if not User.query.first(): db.session.add(User(username=os.environ.get('ADMIN_USER','admin'),password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD','Nahda2026!')),role='admin',active=True))
    if not Setting.query.filter_by(key='company_name').first(): db.session.add(Setting(key='company_name',value='نهضة سوريا للتخليص الجمركي والنقل بالترانزيت العربي والدولي')); db.session.add(Setting(key='currency',value='USD'))
    for code,name,typ in DEFAULT_ACCOUNTS:
        if not Account.query.filter_by(code=code).first(): db.session.add(Account(code=code,name=name,type=typ,active=True))
    db.session.commit(); migrate_v2_data()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
