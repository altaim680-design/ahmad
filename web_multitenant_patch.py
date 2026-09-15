# -*- coding: utf-8 -*-
"""Multi-company layer for Nahda Web.

Each office/company using the system is a tenant. Existing data is migrated to
NAHDA. Business rows are automatically scoped by tenant_id on every ORM SELECT,
and new rows inherit the current tenant automatically.
"""
import io
import re
from datetime import datetime

import web_admin_mobile_patch as base
import web_invoice_collector_patch as invoice_brand
from flask import request, session, redirect, url_for, flash, render_template_string, Response, has_request_context
from sqlalchemy import event, text
from sqlalchemy.orm import Session as SASession, with_loader_criteria
from werkzeug.security import generate_password_hash, check_password_hash

app = base.app
core = base.core
db = core.db
User = core.User


class Tenant(db.Model):
    __tablename__ = 'system_tenant'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    address = db.Column(db.String(250), default='')
    phone = db.Column(db.String(100), default='')
    currency = db.Column(db.String(20), default='USD')
    active = db.Column(db.Boolean, default=True)
    logo_data = db.Column(db.LargeBinary)
    logo_mime = db.Column(db.String(100), default='image/jpeg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TenantSetting(db.Model):
    __tablename__ = 'system_tenant_setting'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('system_tenant.id', ondelete='CASCADE'), nullable=False)
    key = db.Column(db.String(80), nullable=False)
    value = db.Column(db.Text, default='')
    __table_args__ = (db.UniqueConstraint('tenant_id', 'key', name='uq_tenant_setting_key'),)


SCOPED_NAMES = [
    'User', 'Company', 'CustomsDeclaration', 'DeclarationCharge',
    'TransportJob', 'TransportCost', 'TransportPayment', 'TransportStage',
    'TurkishVehicleInvoice', 'InternalShipment', 'SalesInvoice', 'InvoiceLine',
    'CashTransaction', 'Expense', 'Shareholder', 'CapitalMovement',
    'JournalEntry', 'JournalLine', 'V3Attachment', 'ServiceCase',
    'ServiceCaseCharge', 'ServiceCasePayment', 'AuditLog'
]
SCOPED_MODELS = [getattr(core, n) for n in SCOPED_NAMES if getattr(core, n, None) is not None]

# Add mapped columns to existing ORM classes. Physical DB columns are added below.
for model in SCOPED_MODELS:
    if 'tenant_id' not in model.__table__.c:
        setattr(model, 'tenant_id', db.Column(db.Integer, nullable=True))
if 'login_name' not in User.__table__.c:
    User.login_name = db.Column(db.String(80), nullable=True)
if 'system_owner' not in User.__table__.c:
    User.system_owner = db.Column(db.Boolean, default=False)


def _qident(name):
    return db.engine.dialect.identifier_preparer.quote(name)


def _ensure_db_column(model, name, ddl):
    table = model.__tablename__
    insp = db.inspect(db.engine)
    names = {c['name'] for c in insp.get_columns(table)}
    if name in names:
        return
    with db.engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {_qident(table)} ADD COLUMN {_qident(name)} {ddl}'))


def _global_setting(key, default=''):
    try:
        row = core.Setting.query.filter_by(key=key).first()
        return row.value if row and row.value not in (None, '') else default
    except Exception:
        return default


with app.app_context():
    # Create only the new system tables; create_all never alters existing tables.
    db.create_all()
    default_tenant = Tenant.query.filter_by(code='NAHDA').first()
    if not default_tenant:
        default_tenant = Tenant(
            code='NAHDA',
            name=_global_setting('company_name', 'نهضة سوريا للتخليص الجمركي والنقل'),
            address=_global_setting('address', ''),
            phone=_global_setting('phone', ''),
            currency=_global_setting('currency', 'USD') or 'USD',
            active=True,
        )
        db.session.add(default_tenant)
        db.session.commit()

    # Physical migration: all old records belong to the first tenant.
    for model in SCOPED_MODELS:
        _ensure_db_column(model, 'tenant_id', 'INTEGER')
    _ensure_db_column(User, 'login_name', 'VARCHAR(80)')
    _ensure_db_column(User, 'system_owner', 'INTEGER DEFAULT 0')

    with db.engine.begin() as conn:
        for model in SCOPED_MODELS:
            t = _qident(model.__tablename__)
            conn.execute(text(f'UPDATE {t} SET tenant_id=:tid WHERE tenant_id IS NULL'), {'tid': default_tenant.id})
        ut = _qident(User.__tablename__)
        conn.execute(text(f"UPDATE {ut} SET login_name=username WHERE login_name IS NULL OR login_name=''"))

    # First existing administrator becomes the platform owner who can create tenants.
    owner = User.query.filter_by(tenant_id=default_tenant.id, role='admin').order_by(User.id.asc()).first()
    if owner and not owner.system_owner:
        owner.system_owner = True
        db.session.commit()

    # Copy old company settings into NAHDA once.
    for key, fallback in [
        ('company_name', default_tenant.name), ('address', default_tenant.address),
        ('phone', default_tenant.phone), ('currency', default_tenant.currency),
        ('report_footer', _global_setting('report_footer', '')),
    ]:
        if not TenantSetting.query.filter_by(tenant_id=default_tenant.id, key=key).first():
            db.session.add(TenantSetting(tenant_id=default_tenant.id, key=key, value=_global_setting(key, fallback)))
    db.session.commit()


# -------------------- tenant isolation --------------------
@event.listens_for(SASession, 'do_orm_execute')
def _tenant_select_filter(execute_state):
    if not execute_state.is_select or execute_state.execution_options.get('tenant_bypass'):
        return
    if not has_request_context():
        return
    tid = session.get('tenant_id')
    if not tid:
        return
    stmt = execute_state.statement
    for model in SCOPED_MODELS:
        stmt = stmt.options(with_loader_criteria(
            model,
            lambda cls, tid=tid: cls.tenant_id == tid,
            include_aliases=True,
        ))
    execute_state.statement = stmt


@event.listens_for(SASession, 'before_flush')
def _tenant_before_flush(db_session, flush_context, instances):
    if not has_request_context():
        return
    tid = session.get('tenant_id')
    if not tid:
        return
    scoped = tuple(SCOPED_MODELS)
    for obj in list(db_session.new):
        if isinstance(obj, scoped) and hasattr(obj, 'tenant_id') and not getattr(obj, 'tenant_id', None):
            obj.tenant_id = tid
    # Prevent a normal request from mutating/deleting a row that belongs to another tenant.
    for obj in list(db_session.dirty) + list(db_session.deleted):
        if isinstance(obj, scoped) and hasattr(obj, 'tenant_id'):
            otid = getattr(obj, 'tenant_id', None)
            if otid not in (None, tid):
                raise PermissionError('محاولة الوصول إلى بيانات شركة أخرى مرفوضة')


# -------------------- tenant settings --------------------
_original_get_setting = core.get_setting
_original_put_setting = core.put_setting


def tenant_get_setting(key, default=''):
    if has_request_context() and session.get('tenant_id'):
        tid = session['tenant_id']
        row = TenantSetting.query.filter_by(tenant_id=tid, key=key).first()
        if row is not None and row.value not in (None, ''):
            return row.value
        t = Tenant.query.get(tid)
        if t:
            direct = {'company_name': t.name, 'address': t.address, 'phone': t.phone, 'currency': t.currency}
            if key in direct and direct[key] not in (None, ''):
                return direct[key]
    return _original_get_setting(key, default)


def tenant_put_setting(key, value):
    if has_request_context() and session.get('tenant_id'):
        tid = session['tenant_id']
        row = TenantSetting.query.filter_by(tenant_id=tid, key=key).first()
        if not row:
            row = TenantSetting(tenant_id=tid, key=key)
            db.session.add(row)
        row.value = '' if value is None else str(value)
        return row
    return _original_put_setting(key, value)


core.get_setting = tenant_get_setting
core.put_setting = tenant_put_setting


# Invoice numbers are namespaced to avoid clashes between tenants while keeping one DB.
def tenant_next_invoice_no():
    code = (session.get('tenant_code') or 'NAHDA').upper()
    rows = core.SalesInvoice.query.order_by(core.SalesInvoice.id.desc()).limit(500).all()
    mx = 0
    for x in rows:
        m = re.search(r'(\d+)$', str(x.invoice_no or ''))
        if m:
            mx = max(mx, int(m.group(1)))
    return f'{code}-INV-{mx + 1:06d}'


core.next_invoice_no = tenant_next_invoice_no


# -------------------- session and login --------------------
@app.before_request
def tenant_session_context():
    if not session.get('uid'):
        return None
    # Existing sessions from the pre-multitenant version are upgraded automatically.
    if not session.get('tenant_id'):
        u = User.query.execution_options(tenant_bypass=True).filter_by(id=session.get('uid')).first()
        if u and u.tenant_id:
            session['tenant_id'] = u.tenant_id
            session['system_owner'] = bool(u.system_owner)
            session['username'] = u.login_name or u.username
    tid = session.get('tenant_id')
    if tid:
        t = Tenant.query.get(tid)
        if not t or not t.active:
            session.clear()
            if request.endpoint != 'login':
                flash('هذه الشركة موقوفة أو غير موجودة', 'error')
                return redirect(url_for('login'))
        else:
            session['tenant_code'] = t.code
            session['tenant_name'] = t.name
    return None


def tenant_login():
    if request.method == 'POST':
        code = (request.form.get('company_code') or '').strip().upper()
        login_name = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        session.clear()
        t = Tenant.query.filter(db.func.upper(Tenant.code) == code).first()
        if not t or not t.active:
            flash('رمز الشركة غير صحيح أو الشركة موقوفة', 'error')
        else:
            u = User.query.execution_options(tenant_bypass=True).filter_by(tenant_id=t.id, login_name=login_name).first()
            # Backward-compatible fallback for the original NAHDA users.
            if not u:
                u = User.query.execution_options(tenant_bypass=True).filter_by(tenant_id=t.id, username=login_name).first()
            if u and u.active and check_password_hash(u.password_hash, password):
                session['uid'] = u.id
                session['user_id'] = u.id
                session['username'] = u.login_name or login_name
                session['role'] = u.role
                session['tenant_id'] = t.id
                session['tenant_code'] = t.code
                session['tenant_name'] = t.name
                session['system_owner'] = bool(u.system_owner)
                return redirect(url_for('debts') if u.role == 'collector' else url_for('index'))
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    if session.get('uid'):
        return redirect(url_for('index'))
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الدخول</title><style>
    body{margin:0;font-family:Tahoma,Arial;background:linear-gradient(135deg,#0b1f33,#0f766e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#0f172a}.box{width:min(92%,430px);background:#fff;border-radius:22px;padding:28px;box-shadow:0 24px 70px #0005}.brand{text-align:center;margin-bottom:22px}.brand h1{margin:5px 0;color:#0f766e}.brand p{color:#64748b;margin:0}.field{margin:12px 0}.field label{display:block;font-weight:700;margin-bottom:6px}.field input{width:100%;box-sizing:border-box;padding:13px;border:1px solid #cbd5e1;border-radius:12px;font-size:16px}.btn{width:100%;padding:13px;border:0;border-radius:12px;background:#0f766e;color:#fff;font-size:17px;font-weight:800;margin-top:10px}.flash{padding:10px;border-radius:10px;background:#fee2e2;color:#991b1b;margin:8px 0}.hint{font-size:13px;color:#64748b;text-align:center;margin-top:14px}</style></head><body><div class="box"><div class="brand"><h1>نظام التخليص الجمركي</h1><p>دخول الشركات المتعددة</p></div>{% with ms=get_flashed_messages(with_categories=true) %}{% for c,m in ms %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}<form method="post"><div class="field"><label>رمز الشركة</label><input name="company_code" value="{{request.form.get('company_code','NAHDA')}}" autocomplete="organization" required></div><div class="field"><label>اسم المستخدم</label><input name="username" value="{{request.form.get('username','')}}" autocomplete="username" required></div><div class="field"><label>كلمة المرور</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn">دخول</button></form><div class="hint">كل شركة ترى بياناتها ومستخدميها فقط.</div></div></body></html>'''
    return render_template_string(html)


app.view_functions['login'] = tenant_login


# -------------------- users inside each tenant --------------------
ROLE_LABELS = {
    'admin': 'مدير', 'accountant': 'محاسب', 'transport': 'نقل وترانزيت',
    'user': 'موظف', 'viewer': 'مشاهدة فقط', 'collector': 'محصل ديون فقط'
}


def tenant_users():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('إدارة المستخدمين للمدير فقط', 'error')
        return redirect(url_for('index'))
    tid = session['tenant_id']
    t = Tenant.query.get(tid)
    if request.method == 'POST':
        login_name = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or 'viewer').strip()
        if not login_name or not password:
            flash('اسم المستخدم وكلمة المرور مطلوبان', 'error')
        elif User.query.filter_by(login_name=login_name).first():
            flash('اسم المستخدم موجود داخل هذه الشركة', 'error')
        elif role not in ROLE_LABELS:
            flash('الصلاحية غير صحيحة', 'error')
        else:
            internal = f't{tid}__{login_name}'[:80]
            u = User(username=internal, login_name=login_name, password_hash=generate_password_hash(password), role=role, active=True, tenant_id=tid, system_owner=False)
            db.session.add(u)
            db.session.commit()
            flash('تمت إضافة المستخدم', 'success')
        return redirect(url_for('users'))
    rows = User.query.order_by(User.id.asc()).all()
    body = '''<div class="hero"><h1>المستخدمون والصلاحيات</h1><p>{{tenant.name}} — رمز الشركة: <b>{{tenant.code}}</b></p></div><div class="card no-print"><form method="post"><div class="formgrid"><div class="field"><label>اسم المستخدم</label><input name="username" required></div><div class="field"><label>كلمة المرور</label><input type="password" name="password" required></div><div class="field"><label>الصلاحية</label><select name="role">{% for k,v in roles.items() %}<option value="{{k}}">{{v}}</option>{% endfor %}</select></div></div><button class="btn green">إضافة مستخدم</button></form></div><div class="card"><div class="tablewrap"><table><thead><tr><th>#</th><th>المستخدم</th><th>الصلاحية</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.login_name or x.username}}</td><td>{{roles.get(x.role,x.role)}}</td><td>{{'فعال' if x.active else 'موقوف'}}</td><td>{% if x.id != session.get('uid') %}<form method="post" action="{{url_for('tenant_user_toggle',uid=x.id)}}"><button class="btn small {{'red' if x.active else 'green'}}">{{'إيقاف' if x.active else 'تفعيل'}}</button></form>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div>'''
    return core.layout('المستخدمون والصلاحيات', body, rows=rows, tenant=t, roles=ROLE_LABELS)


app.view_functions['users'] = tenant_users


@app.route('/users/<int:uid>/toggle', methods=['POST'])
def tenant_user_toggle(uid):
    if not session.get('uid') or session.get('role') != 'admin':
        return redirect(url_for('login'))
    u = User.query.get_or_404(uid)
    if u.id == session.get('uid'):
        flash('لا يمكنك إيقاف حسابك الحالي', 'error')
    else:
        u.active = not bool(u.active)
        db.session.commit()
        flash('تم تحديث حالة المستخدم', 'success')
    return redirect(url_for('users'))


# -------------------- tenant company settings + logo --------------------
def tenant_settings_page():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('الإعدادات للمدير فقط', 'error')
        return redirect(url_for('index'))
    t = Tenant.query.get_or_404(session['tenant_id'])
    keys = ['company_name', 'address', 'phone', 'currency', 'report_footer']
    if request.method == 'POST':
        for k in keys:
            tenant_put_setting(k, request.form.get(k, ''))
        t.name = (request.form.get('company_name') or t.name).strip()
        t.address = (request.form.get('address') or '').strip()
        t.phone = (request.form.get('phone') or '').strip()
        t.currency = (request.form.get('currency') or 'USD').strip()
        f = request.files.get('logo')
        if f and f.filename:
            data = f.read()
            if len(data) > 5 * 1024 * 1024:
                db.session.rollback()
                flash('حجم الشعار أكبر من 5MB', 'error')
                return redirect(url_for('settings'))
            t.logo_data = data
            t.logo_mime = f.mimetype or 'image/png'
        db.session.commit()
        session['tenant_name'] = t.name
        flash('تم حفظ إعدادات الشركة', 'success')
        return redirect(url_for('settings'))
    values = {k: tenant_get_setting(k, '') for k in keys}
    body = '''<div class="hero"><h1>إعدادات الشركة</h1><p>هذه الإعدادات تخص {{tenant.name}} فقط.</p></div><div class="card"><form method="post" enctype="multipart/form-data"><div class="formgrid"><div class="field full"><label>اسم الشركة</label><input name="company_name" value="{{v.company_name}}"></div><div class="field"><label>العنوان</label><input name="address" value="{{v.address}}"></div><div class="field"><label>الهاتف</label><input name="phone" value="{{v.phone}}"></div><div class="field"><label>العملة</label><input name="currency" value="{{v.currency or 'USD'}}"></div><div class="field"><label>لوغو الشركة</label><input type="file" name="logo" accept="image/*"></div><div class="field full"><label>تذييل التقارير</label><input name="report_footer" value="{{v.report_footer}}"></div></div><button class="btn green">حفظ الإعدادات</button></form></div>'''
    return core.layout('إعدادات الشركة', body, tenant=t, v=values)


app.view_functions['settings'] = tenant_settings_page


def tenant_company_logo():
    tid = session.get('tenant_id') if has_request_context() else None
    if tid:
        t = Tenant.query.get(tid)
        if t and t.logo_data:
            return Response(bytes(t.logo_data), mimetype=t.logo_mime or 'image/png', headers={'Cache-Control': 'private, max-age=300'})
    return invoice_brand.company_logo()


app.view_functions['company_logo'] = tenant_company_logo


# -------------------- platform owner: create/manage tenants --------------------
def _owner_only():
    return bool(session.get('uid') and session.get('system_owner'))


@app.route('/system/tenants', methods=['GET', 'POST'])
def system_tenants():
    if not _owner_only():
        flash('هذه الصفحة لمالك النظام فقط', 'error')
        return redirect(url_for('index') if session.get('uid') else url_for('login'))
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        name = (request.form.get('name') or '').strip()
        admin_login = (request.form.get('admin_login') or 'admin').strip()
        admin_password = request.form.get('admin_password') or ''
        if not re.fullmatch(r'[A-Z0-9_-]{2,20}', code):
            flash('رمز الشركة يجب أن يكون أحرف إنكليزية/أرقام من 2 إلى 20', 'error')
        elif not name or not admin_login or len(admin_password) < 6:
            flash('اسم الشركة وبيانات المدير مطلوبة، وكلمة المرور 6 أحرف على الأقل', 'error')
        elif Tenant.query.filter_by(code=code).first():
            flash('رمز الشركة مستخدم مسبقاً', 'error')
        else:
            t = Tenant(code=code, name=name, address=(request.form.get('address') or '').strip(), phone=(request.form.get('phone') or '').strip(), currency=(request.form.get('currency') or 'USD').strip(), active=True)
            db.session.add(t)
            db.session.flush()
            for k, v in [('company_name', name), ('address', t.address), ('phone', t.phone), ('currency', t.currency), ('report_footer', '')]:
                db.session.add(TenantSetting(tenant_id=t.id, key=k, value=v))
            internal = f't{t.id}__{admin_login}'[:80]
            db.session.add(User(username=internal, login_name=admin_login, password_hash=generate_password_hash(admin_password), role='admin', active=True, tenant_id=t.id, system_owner=False))
            db.session.commit()
            flash(f'تم إنشاء الشركة {name}. رمز الدخول: {code}', 'success')
        return redirect(url_for('system_tenants'))
    tenants = Tenant.query.order_by(Tenant.id.asc()).all()
    body = '''<div class="hero"><h1>الشركات المستخدمة للنظام</h1><p>كل شركة مستقلة ببياناتها ومستخدميها وفواتيرها.</p></div><div class="card no-print"><div class="section-title">إضافة شركة جديدة</div><form method="post"><div class="formgrid"><div class="field"><label>رمز الشركة</label><input name="code" placeholder="مثال ABC" required></div><div class="field"><label>اسم الشركة</label><input name="name" required></div><div class="field"><label>العنوان</label><input name="address"></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field"><label>العملة</label><input name="currency" value="USD"></div><div class="field"><label>اسم مستخدم مدير الشركة</label><input name="admin_login" value="admin" required></div><div class="field"><label>كلمة مرور المدير</label><input type="password" name="admin_password" minlength="6" required></div></div><button class="btn green">إنشاء الشركة</button></form></div><div class="card"><div class="tablewrap"><table><thead><tr><th>#</th><th>الرمز</th><th>الشركة</th><th>الهاتف</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>{% for t in tenants %}<tr><td>{{t.id}}</td><td><b>{{t.code}}</b></td><td>{{t.name}}</td><td>{{t.phone}}</td><td>{{'فعالة' if t.active else 'موقوفة'}}</td><td>{% if t.id != session.get('tenant_id') %}<form method="post" action="{{url_for('system_tenant_toggle',tid=t.id)}}"><button class="btn small {{'red' if t.active else 'green'}}">{{'إيقاف' if t.active else 'تفعيل'}}</button></form>{% else %}<span class="muted">الشركة الحالية</span>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div>'''
    return core.layout('إدارة الشركات', body, tenants=tenants)


@app.route('/system/tenants/<int:tid>/toggle', methods=['POST'])
def system_tenant_toggle(tid):
    if not _owner_only():
        return redirect(url_for('login'))
    if tid == session.get('tenant_id'):
        flash('لا يمكن إيقاف الشركة التي تعمل عليها حالياً', 'error')
    else:
        t = Tenant.query.get_or_404(tid)
        t.active = not bool(t.active)
        db.session.commit()
        flash('تم تحديث حالة الشركة', 'success')
    return redirect(url_for('system_tenants'))


# Put a clear tenant badge and owner shortcut on all normal pages.
_previous_layout = core.layout


def multitenant_layout(page_title, body, **ctx):
    if session.get('tenant_id'):
        badge = f'''<div class="toolbar no-print" style="justify-content:space-between"><span class="btn gray" style="pointer-events:none">🏢 {session.get('tenant_name','')} — {session.get('tenant_code','')}</span>'''
        if session.get('system_owner'):
            badge += f'<a class="btn amber" href="{url_for("system_tenants")}">🏢 إدارة الشركات</a>'
        badge += '</div>'
        body = badge + body
    return _previous_layout(page_title, body, **ctx)


core.layout = multitenant_layout


@app.route('/multitenant-health')
def multitenant_health():
    return {
        'ok': True,
        'multi_tenant': True,
        'tenant_login': True,
        'tenant_isolation': True,
        'tenant_settings': True,
        'tenant_users': True,
        'owner_company_management': True,
    }
