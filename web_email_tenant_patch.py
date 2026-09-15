# -*- coding: utf-8 -*-
"""Email-based authentication on top of the multi-tenant Nahda system.

Login uses email + password only. A user whose email/password is linked to more
than one tenant chooses the company after authentication. Tenant codes remain
internal (invoice namespace / administration) and are no longer required at
login.
"""
import hashlib
import re
import secrets

import web_multitenant_patch as mt
from flask import request, session, redirect, url_for, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = mt.app
core = mt.core
db = mt.db
User = mt.User
Tenant = mt.Tenant
TenantSetting = mt.TenantSetting

PRIMARY_OWNER_EMAIL = 'ahmadwkas704@gmail.com'
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
ROLE_LABELS = {
    'admin': 'مدير',
    'accountant': 'محاسب',
    'transport': 'نقل وترانزيت',
    'user': 'موظف',
    'viewer': 'مشاهدة فقط',
    'collector': 'محصل ديون فقط',
}

# Add email to the existing User model/table without rebuilding the database.
if 'email' not in User.__table__.c:
    User.email = db.Column(db.String(255), nullable=True)

with app.app_context():
    mt._ensure_db_column(User, 'email', 'VARCHAR(255)')
    owner = User.query.execution_options(tenant_bypass=True).filter_by(system_owner=True).order_by(User.id.asc()).first()
    if owner:
        owner.email = PRIMARY_OWNER_EMAIL
        db.session.commit()


def _norm_email(value):
    return (value or '').strip().lower()


def _activate_user(u):
    t = Tenant.query.get(u.tenant_id)
    if not t or not t.active or not u.active:
        flash('الحساب أو الشركة موقوفة', 'error')
        return redirect(url_for('login'))
    session.clear()
    session['uid'] = u.id
    session['user_id'] = u.id
    session['username'] = u.login_name or u.email or u.username
    session['email'] = u.email or ''
    session['role'] = u.role
    session['tenant_id'] = t.id
    session['tenant_code'] = t.code
    session['tenant_name'] = t.name
    session['system_owner'] = bool(u.system_owner)
    return redirect(url_for('debts') if u.role == 'collector' else url_for('index'))


def email_login():
    if request.method == 'POST':
        email = _norm_email(request.form.get('email'))
        password = request.form.get('password') or ''
        session.clear()
        if not EMAIL_RE.match(email):
            flash('اكتب بريد إلكتروني صحيح', 'error')
        else:
            candidates = User.query.execution_options(tenant_bypass=True).filter(
                db.func.lower(User.email) == email,
                User.active.is_(True),
            ).order_by(User.id.asc()).all()
            matches = []
            for u in candidates:
                try:
                    if check_password_hash(u.password_hash, password):
                        t = Tenant.query.get(u.tenant_id)
                        if t and t.active:
                            matches.append(u)
                except Exception:
                    pass
            if len(matches) == 1:
                return _activate_user(matches[0])
            if len(matches) > 1:
                session['pending_email'] = email
                session['pending_user_ids'] = [u.id for u in matches]
                return redirect(url_for('select_company'))
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')

    if session.get('uid'):
        return redirect(url_for('index'))

    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الدخول</title><style>
    *{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial;background:linear-gradient(135deg,#071827,#0b3344 55%,#0f766e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#0f172a;padding:18px}.box{width:min(94vw,440px);background:#fff;border-radius:24px;padding:30px;box-shadow:0 28px 80px #0006}.brand{text-align:center;margin-bottom:24px}.logo{width:70px;height:70px;margin:auto;border-radius:20px;background:linear-gradient(145deg,#0f766e,#102a43);display:flex;align-items:center;justify-content:center;color:#fff;font-size:32px;box-shadow:0 10px 30px #0f766e55}.brand h1{margin:12px 0 6px;color:#0f766e;font-size:24px}.brand p{color:#64748b;margin:0;line-height:1.7}.field{margin:14px 0}.field label{display:block;font-weight:800;margin-bottom:7px}.field input{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:13px;font-size:16px;outline:none}.field input:focus{border-color:#0f766e;box-shadow:0 0 0 3px #0f766e1c}.btn{width:100%;padding:14px;border:0;border-radius:13px;background:#0f766e;color:#fff;font-size:17px;font-weight:900;margin-top:10px;cursor:pointer}.flash{padding:11px 13px;border-radius:11px;background:#fee2e2;color:#991b1b;margin:10px 0}.hint{font-size:13px;color:#64748b;text-align:center;margin-top:16px;line-height:1.7}</style></head><body><div class="box"><div class="brand"><div class="logo">⚓</div><h1>نظام التخليص الجمركي</h1><p>دخول آمن للشركات المتعددة</p></div>{% with ms=get_flashed_messages(with_categories=true) %}{% for c,m in ms %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}<form method="post"><div class="field"><label>البريد الإلكتروني</label><input type="email" name="email" value="{{request.form.get('email','')}}" autocomplete="email" placeholder="name@example.com" required></div><div class="field"><label>كلمة المرور</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn">تسجيل الدخول</button></form><div class="hint">لا تحتاج رمز شركة. النظام يحدد شركتك تلقائياً من حسابك.</div></div></body></html>'''
    return render_template_string(html)


app.view_functions['login'] = email_login


@app.route('/select-company', methods=['GET', 'POST'])
def select_company():
    ids = session.get('pending_user_ids') or []
    if not ids:
        return redirect(url_for('login'))
    users = User.query.execution_options(tenant_bypass=True).filter(User.id.in_(ids), User.active.is_(True)).all()
    options = []
    for u in users:
        t = Tenant.query.get(u.tenant_id)
        if t and t.active:
            options.append((u, t))
    if not options:
        session.clear()
        flash('لا توجد شركة فعالة مرتبطة بالحساب', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        uid = request.form.get('user_id', type=int)
        allowed = {u.id: u for u, _ in options}
        if uid not in allowed:
            flash('اختيار غير صالح', 'error')
        else:
            return _activate_user(allowed[uid])
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>اختيار الشركة</title><style>body{font-family:Tahoma,Arial;background:#eef4f6;margin:0;padding:25px;color:#0f172a}.box{max-width:600px;margin:6vh auto;background:#fff;border-radius:20px;padding:25px;box-shadow:0 15px 50px #0002}h1{color:#0f766e}.company{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:16px;border:1px solid #dbe4ea;border-radius:14px;margin:10px 0}.company b{font-size:17px}.company small{display:block;color:#64748b;margin-top:5px}.btn{border:0;background:#0f766e;color:#fff;padding:11px 16px;border-radius:10px;font-weight:800;cursor:pointer}</style></head><body><div class="box"><h1>اختر الشركة</h1><p>هذا البريد مرتبط بأكثر من شركة. اختر الشركة التي تريد فتحها.</p>{% for u,t in options %}<form method="post" class="company"><div><b>{{t.name}}</b><small>{{u.role}} • {{u.email}}</small></div><input type="hidden" name="user_id" value="{{u.id}}"><button class="btn">فتح</button></form>{% endfor %}</div></body></html>'''
    return render_template_string(html, options=options)


def email_users_page():
    if not session.get('uid'):
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('إدارة المستخدمين للمدير فقط', 'error')
        return redirect(url_for('index'))
    tid = session.get('tenant_id')
    if request.method == 'POST':
        email = _norm_email(request.form.get('email'))
        name = (request.form.get('name') or '').strip() or email.split('@')[0]
        password = request.form.get('password') or ''
        role = (request.form.get('role') or 'viewer').strip()
        exists = User.query.execution_options(tenant_bypass=True).filter(
            User.tenant_id == tid,
            db.func.lower(User.email) == email,
        ).first() if email else None
        if not EMAIL_RE.match(email):
            flash('البريد الإلكتروني غير صحيح', 'error')
        elif len(password) < 6:
            flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'error')
        elif role not in ROLE_LABELS:
            flash('الصلاحية غير صحيحة', 'error')
        elif exists:
            flash('هذا البريد موجود مسبقاً داخل الشركة', 'error')
        else:
            digest = hashlib.sha1(email.encode('utf-8')).hexdigest()[:20]
            internal = f't{tid}__{digest}'[:80]
            u = User(
                username=internal,
                login_name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                active=True,
                tenant_id=tid,
                system_owner=False,
            )
            db.session.add(u)
            db.session.commit()
            try:
                core.audit('إضافة مستخدم', 'user', u.id, f'{email} - {role}')
            except Exception:
                pass
            flash('تمت إضافة المستخدم بنجاح', 'success')
        return redirect(url_for('users'))

    rows = User.query.execution_options(tenant_bypass=True).filter_by(tenant_id=tid).order_by(User.id.asc()).all()
    body = '''<div class="hero"><h1>المستخدمون والصلاحيات</h1><p>كل مستخدم يدخل بالبريد الإلكتروني وكلمة المرور، ويشاهد بيانات هذه الشركة فقط.</p></div><div class="card no-print"><div class="section-title">إضافة مستخدم</div><form method="post"><div class="formgrid"><div class="field"><label>الاسم</label><input name="name" placeholder="اسم الموظف"></div><div class="field"><label>البريد الإلكتروني</label><input type="email" name="email" required></div><div class="field"><label>كلمة المرور</label><input type="password" name="password" minlength="6" required></div><div class="field"><label>الصلاحية</label><select name="role">{% for key,label in roles.items() %}<option value="{{key}}">{{label}}</option>{% endfor %}</select></div></div><button class="btn green">إضافة المستخدم</button></form></div><div class="card"><div class="tablewrap"><table><thead><tr><th>ID</th><th>الاسم</th><th>الإيميل</th><th>الصلاحية</th><th>الحالة</th></tr></thead><tbody>{% for x in rows %}<tr><td>{{x.id}}</td><td>{{x.login_name or '—'}}</td><td>{{x.email or '—'}}</td><td>{{roles.get(x.role,x.role)}}</td><td>{{'فعال' if x.active else 'موقوف'}}</td></tr>{% endfor %}</tbody></table></div></div>'''
    return core.layout('المستخدمون والصلاحيات', body, rows=rows, roles=ROLE_LABELS)


app.view_functions['users'] = email_users_page


def _internal_tenant_code():
    while True:
        code = 'C' + secrets.token_hex(3).upper()
        if not Tenant.query.filter_by(code=code).first():
            return code


def email_system_tenants():
    if not (session.get('uid') and session.get('system_owner')):
        flash('هذه الصفحة لمالك النظام فقط', 'error')
        return redirect(url_for('index') if session.get('uid') else url_for('login'))
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        admin_email = _norm_email(request.form.get('admin_email'))
        admin_name = (request.form.get('admin_name') or '').strip() or 'مدير الشركة'
        admin_password = request.form.get('admin_password') or ''
        if not name:
            flash('اسم الشركة مطلوب', 'error')
        elif not EMAIL_RE.match(admin_email):
            flash('إيميل مدير الشركة غير صحيح', 'error')
        elif len(admin_password) < 6:
            flash('كلمة مرور المدير يجب أن تكون 6 أحرف على الأقل', 'error')
        else:
            t = Tenant(
                code=_internal_tenant_code(),
                name=name,
                address=(request.form.get('address') or '').strip(),
                phone=(request.form.get('phone') or '').strip(),
                currency=(request.form.get('currency') or 'USD').strip(),
                active=True,
            )
            db.session.add(t)
            db.session.flush()
            for k, v in [('company_name', name), ('address', t.address), ('phone', t.phone), ('currency', t.currency), ('report_footer', '')]:
                db.session.add(TenantSetting(tenant_id=t.id, key=k, value=v))
            digest = hashlib.sha1(admin_email.encode('utf-8')).hexdigest()[:20]
            internal = f't{t.id}__{digest}'[:80]
            db.session.add(User(
                username=internal,
                login_name=admin_name,
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role='admin', active=True, tenant_id=t.id, system_owner=False,
            ))
            db.session.commit()
            flash(f'تم إنشاء شركة {name}. المدير يدخل مباشرة بإيميله: {admin_email}', 'success')
        return redirect(url_for('system_tenants'))

    tenants = Tenant.query.order_by(Tenant.id.asc()).all()
    admins = {}
    for t in tenants:
        u = User.query.execution_options(tenant_bypass=True).filter_by(tenant_id=t.id, role='admin').order_by(User.id.asc()).first()
        admins[t.id] = u.email if u else ''
    body = '''<div class="hero"><h1>إدارة الشركات</h1><p>أضف شركة وحدد إيميل مديرها. لا يحتاج أي مستخدم إلى رمز شركة عند تسجيل الدخول.</p></div><div class="card no-print"><div class="section-title">إضافة شركة جديدة</div><form method="post"><div class="formgrid"><div class="field"><label>اسم الشركة</label><input name="name" required></div><div class="field"><label>العنوان</label><input name="address"></div><div class="field"><label>الهاتف</label><input name="phone"></div><div class="field"><label>العملة</label><input name="currency" value="USD"></div><div class="field"><label>اسم مدير الشركة</label><input name="admin_name" value="مدير الشركة"></div><div class="field"><label>إيميل مدير الشركة</label><input type="email" name="admin_email" required></div><div class="field"><label>كلمة مرور المدير</label><input type="password" name="admin_password" minlength="6" required></div></div><button class="btn green">إنشاء الشركة</button></form></div><div class="card"><div class="tablewrap"><table><thead><tr><th>#</th><th>الشركة</th><th>مدير الشركة</th><th>الهاتف</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>{% for t in tenants %}<tr><td>{{t.id}}</td><td><b>{{t.name}}</b></td><td>{{admins.get(t.id) or '—'}}</td><td>{{t.phone}}</td><td>{{'فعالة' if t.active else 'موقوفة'}}</td><td>{% if t.id != session.get('tenant_id') %}<form method="post" action="{{url_for('system_tenant_toggle',tid=t.id)}}"><button class="btn small {{'red' if t.active else 'green'}}">{{'إيقاف' if t.active else 'تفعيل'}}</button></form>{% else %}<span class="muted">الشركة الحالية</span>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div>'''
    return core.layout('إدارة الشركات', body, tenants=tenants, admins=admins)


app.view_functions['system_tenants'] = email_system_tenants


@app.route('/email-tenant-health')
def email_tenant_health():
    return {
        'ok': True,
        'email_login': True,
        'multi_company': True,
        'company_selector': True,
        'primary_owner_email': PRIMARY_OWNER_EMAIL,
    }
