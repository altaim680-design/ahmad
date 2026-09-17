# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import request, session, redirect, render_template_string, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

import web_sporthub_access_v4 as access
import web_sporthub_admin_v2 as admin2
import web_sporthub_admin_patch as admin1
import web_sporthub_patch as core

app = access.app
db = core.db
SportClub = core.SportClub
SportProduct = core.SportProduct
SportOrder = core.SportOrder
SportOrderItem = core.SportOrderItem
SportPayment = core.SportPayment


class SportClubAccount(db.Model):
    __tablename__ = 'sporthub_club_account'
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('sporthub_club.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    username = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(300), nullable=False)
    commission_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    club = db.relationship('SportClub', backref=db.backref('market_account', uselist=False, lazy=True))


class SportCommissionLedger(db.Model):
    __tablename__ = 'sporthub_commission_ledger'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('sporthub_payment.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey('sporthub_club.id', ondelete='CASCADE'), nullable=False, index=True)
    gross_syp = db.Column(db.BigInteger, nullable=False, default=0)
    commission_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    commission_syp = db.Column(db.BigInteger, nullable=False, default=0)
    club_net_syp = db.Column(db.BigInteger, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


with app.app_context():
    db.create_all()


def _role():
    role = session.get('sporthub_role')
    if role:
        return role
    if session.get('sporthub_admin') and not session.get('sporthub_club_id'):
        return 'super'
    return ''


def _super_ok():
    return _role() == 'super'


def _club_ok():
    return _role() == 'club' and bool(session.get('sporthub_club_id'))


def _any_admin():
    return _super_ok() or _club_ok()


def _club_id():
    try:
        return int(session.get('sporthub_club_id')) if _club_ok() else None
    except Exception:
        return None


def _guard():
    if not _any_admin():
        return redirect('/sporthub/admin/login')
    return None


def _commission_value(value):
    try:
        x = Decimal(str(value or '0'))
    except (InvalidOperation, ValueError):
        x = Decimal('0')
    if x < 0:
        x = Decimal('0')
    if x > 100:
        x = Decimal('100')
    return x.quantize(Decimal('0.01'))


def _account_for_club(cid):
    return SportClubAccount.query.filter_by(club_id=cid).first()


def _rate_for_club(cid):
    a = _account_for_club(cid)
    return _commission_value(a.commission_pct if a else 0)


def _money(n):
    return f"{int(n or 0):,}"


def _ensure_ledger(payment):
    if payment.status not in ('verified', 'paid'):
        return None
    row = SportCommissionLedger.query.filter_by(payment_id=payment.id).first()
    if row:
        return row
    pct = _rate_for_club(payment.club_id)
    gross = int(payment.amount_syp or 0)
    commission = int((Decimal(gross) * pct / Decimal('100')).quantize(Decimal('1')))
    row = SportCommissionLedger(
        payment_id=payment.id,
        club_id=payment.club_id,
        gross_syp=gross,
        commission_pct=pct,
        commission_syp=commission,
        club_net_syp=max(0, gross - commission),
    )
    db.session.add(row)
    return row


def _backfill_ledgers():
    missing = SportPayment.query.filter(SportPayment.status.in_(['verified', 'paid'])).all()
    changed = False
    for p in missing:
        if not SportCommissionLedger.query.filter_by(payment_id=p.id).first():
            _ensure_ledger(p)
            changed = True
    if changed:
        db.session.commit()


# Close legacy admin shortcuts for club-level accounts.
admin2._is_admin = _super_ok
admin1._is_admin = _super_ok
core._sporthub_is_admin = _super_ok


LOGIN_HTML = r'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول الإدارة | SPORT HUB</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Tahoma,Arial,sans-serif;background:linear-gradient(135deg,#07130d,#17452a);display:grid;place-items:center;padding:20px}.box{width:min(460px,100%);background:#fff;border-radius:28px;padding:32px;box-shadow:0 32px 90px #0007}.logo{width:72px;height:72px;border-radius:22px;background:#0e1d15;color:#fff;display:grid;place-items:center;margin:auto;font-weight:1000;font-size:25px}.logo b{color:#67f69d}.head{text-align:center}.head h1{margin:15px 0 6px}.head p{color:#718078;font-size:13px;line-height:1.8;margin:0}.field{display:block;margin-top:15px;font-size:12px;font-weight:900;color:#4d5c54}.field input{width:100%;margin-top:7px;padding:14px;border:1px solid #d5e0da;border-radius:13px;outline:none;font-size:15px}.field input:focus{border-color:#54c582;box-shadow:0 0 0 3px #e3f7eb}.btn{width:100%;margin-top:18px;padding:14px;border:0;border-radius:13px;background:#11231a;color:#fff;font-size:16px;font-weight:1000;cursor:pointer}.err{background:#feeaea;color:#9f3434;padding:11px 13px;border-radius:11px;margin-top:15px;font-size:12px}.back{display:block;text-align:center;margin-top:17px;text-decoration:none;color:#169153;font-weight:900;font-size:12px}.hint{margin-top:18px;border-top:1px solid #e8eeea;padding-top:15px;color:#849188;font-size:11px;text-align:center;line-height:1.8}
</style></head><body><div class="box"><div class="head"><div class="logo"><b>S</b>H</div><h1>دخول إدارة SPORT HUB</h1><p>نفس الصفحة لمدير المنصة ومدراء الأندية. كل حساب يرى صلاحياته فقط.</p></div>{% if error %}<div class="err">{{error}}</div>{% endif %}<form method="post"><label class="field">اسم المستخدم<input name="username" autocomplete="username" required autofocus></label><label class="field">كلمة المرور<input type="password" name="password" autocomplete="current-password" required></label><button class="btn">تسجيل الدخول</button></form><a class="back" href="/sporthub/shop">الدخول للمتجر كزبون ←</a><div class="hint">مدير النادي لا يستطيع رؤية أو تعديل بيانات أي نادي آخر.</div></div></body></html>'''


def login_v5():
    if _any_admin():
        return redirect('/sporthub/admin')
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        super_user = access.os.environ.get('SPORTHUB_ADMIN_USER', 'admin')
        super_pass = access.os.environ.get('SPORTHUB_ADMIN_PASS', '')
        if username == super_user and super_pass and access.hmac.compare_digest(password, super_pass):
            session.clear()
            session['sporthub_admin'] = True
            session['sporthub_role'] = 'super'
            session['sporthub_admin_user'] = username
            session.permanent = True
            return redirect('/sporthub/admin')
        account = SportClubAccount.query.filter(func.lower(SportClubAccount.username) == username.lower(), SportClubAccount.active.is_(True)).first()
        if account and check_password_hash(account.password_hash, password):
            club = SportClub.query.get(account.club_id)
            if club and club.active:
                session.clear()
                session['sporthub_admin'] = True
                session['sporthub_role'] = 'club'
                session['sporthub_club_id'] = club.id
                session['sporthub_admin_user'] = account.username
                session['sporthub_club_name'] = club.name
                session.permanent = True
                return redirect('/sporthub/admin')
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'
    return render_template_string(LOGIN_HTML, error=error)


app.view_functions['sporthub_admin_login_v4'] = login_v5


def _logout_v5():
    session.clear()
    return redirect('/sporthub/admin/login')

app.view_functions['sporthub_admin_logout_v4'] = _logout_v5


BASE_CSS = r'''
:root{--bg:#f4f7f5;--card:#fff;--ink:#122019;--mut:#6c7b73;--green:#1dad61;--green2:#e8f8ee;--line:#dfe8e3;--dark:#0f2018;--red:#c94a4a;--amber:#b97914}*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial,sans-serif;background:var(--bg);color:var(--ink)}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}.shell{display:grid;grid-template-columns:265px 1fr;min-height:100vh}.side{background:var(--dark);color:#fff;padding:23px 17px;position:sticky;top:0;height:100vh}.logo{font-size:24px;font-weight:1000}.logo b{color:#6dff9d}.who{margin:9px 0 22px;color:#a4b9ae;font-size:12px;line-height:1.7}.nav{display:grid;gap:7px}.nav a{padding:13px 14px;border-radius:12px;font-weight:800;color:#d9e7df}.nav a:hover,.nav a.active{background:#21392d;color:#fff}.sidefoot{margin-top:22px;border-top:1px solid #2a4437;padding-top:15px;display:grid;gap:8px}.sidefoot a{padding:11px;border-radius:11px;text-align:center;background:#fff;color:#102019;font-weight:900;font-size:12px}.sidefoot .logout{background:#3e2426;color:#ffd9d9}.main{padding:28px;max-width:1320px;width:100%;margin:auto}.top{display:flex;justify-content:space-between;align-items:end;gap:14px;margin-bottom:22px}.top h1{margin:0;font-size:31px}.sub{color:var(--mut);font-size:13px;margin-top:6px}.role{display:inline-flex;padding:7px 11px;border-radius:999px;background:var(--green2);color:#177145;font-size:11px;font-weight:1000}.flash{padding:11px 13px;border-radius:11px;background:#e8f7ee;border:1px solid #c3e9d0;color:#17643e;margin:10px 0}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.stat{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.stat span{color:var(--mut);font-size:11px}.stat b{display:block;font-size:28px;margin-top:8px}.section{margin-top:23px}.sectionhead{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:12px}.sectionhead h2{margin:0;font-size:22px}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:13px}.field{display:block;font-size:11px;font-weight:800;color:var(--mut)}.field input,.field select,.field textarea{width:100%;margin-top:6px;padding:11px;border:1px solid #cfddd5;border-radius:10px;background:#fff}.field textarea{min-height:86px}.span2{grid-column:1/-1}.btn{border:0;border-radius:10px;padding:10px 14px;font-weight:900;cursor:pointer}.primary{background:var(--green);color:#fff}.secondary{background:#edf3ef;color:#183126}.danger{background:#feeaea;color:#a53a3a}.warn{background:#fff3df;color:#8a5a0e}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.tablewrap{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:18px}.table{width:100%;border-collapse:collapse;min-width:900px}.table th,.table td{padding:12px;text-align:right;border-bottom:1px solid #edf2ef;vertical-align:middle}.table th{background:#f8fbf9;color:var(--mut);font-size:11px}.money{font-weight:1000;white-space:nowrap}.badge{display:inline-flex;padding:5px 8px;border-radius:999px;background:var(--green2);color:#177145;font-size:10px;font-weight:1000}.badge.pending{background:#fff3df;color:#91600f}.badge.rejected{background:#feeaea;color:#a13a3a}.clubs{display:grid;grid-template-columns:repeat(2,1fr);gap:13px}.clubcard{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.clubhead{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}.clubhead h3{margin:0}.commission{font-size:20px;font-weight:1000;color:var(--green)}.qr{width:74px;height:74px;object-fit:contain;background:#fff;border:1px solid var(--line);border-radius:11px;padding:5px}.emptyqr{width:74px;height:74px;display:grid;place-items:center;text-align:center;border:1px dashed #bccac2;border-radius:11px;color:var(--mut);font-size:10px}.mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}.mini{background:#f7faf8;border-radius:12px;padding:11px}.mini small{display:block;color:var(--mut);font-size:9px}.mini b{display:block;margin-top:5px;font-size:14px}.note{background:#f8fbf9;border:1px solid var(--line);padding:12px;border-radius:12px;color:var(--mut);font-size:12px;line-height:1.8}@media(max-width:950px){.shell{grid-template-columns:1fr}.side{position:relative;height:auto}.nav{grid-template-columns:repeat(4,1fr)}.nav a{text-align:center;font-size:11px}.stats{grid-template-columns:1fr 1fr}.clubs{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}.span2{grid-column:auto}}@media(max-width:560px){.main{padding:15px}.nav{grid-template-columns:1fr 1fr}.stats{grid-template-columns:1fr 1fr}.top{display:block}.top h1{font-size:26px}}
'''


def _layout(title, body, active='dashboard', **ctx):
    role = _role()
    is_super = role == 'super'
    club_name = session.get('sporthub_club_name') or ''
    nav = [
        ('dashboard','/sporthub/admin','الرئيسية'),
        ('products','/sporthub/admin/products','المنتجات'),
        ('orders','/sporthub/admin/orders','الطلبات والمبيعات'),
    ]
    if is_super:
        nav.insert(1, ('clubs','/sporthub/admin/clubs','الأندية والعمولات'))
    else:
        nav.insert(1, ('myclub','/sporthub/admin/my-club','إعدادات النادي'))
    html = r'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} | SPORT HUB</title><style>''' + BASE_CSS + r'''</style></head><body><div class="shell"><aside class="side"><div class="logo"><b>SPORT</b> HUB</div><div class="who">{% if is_super %}مدير المنصة الرئيسي<br>تشاهد جميع الأندية والعمولات{% else %}مدير نادي<br><b>{{club_name}}</b>{% endif %}</div><nav class="nav">{% for key,url,label in nav %}<a class="{{'active' if active==key else ''}}" href="{{url}}">{{label}}</a>{% endfor %}</nav><div class="sidefoot"><a href="/sporthub/shop">فتح المتجر كزبون</a><a class="logout" href="/sporthub/admin/logout">تسجيل الخروج</a></div></aside><main class="main"><div class="top"><div><h1>{{title}}</h1><div class="sub">{{subtitle}}</div></div><span class="role">{{'SUPER ADMIN' if is_super else 'CLUB ADMIN'}}</span></div>{% with ms=get_flashed_messages() %}{% for m in ms %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}''' + body + r'''</main></div></body></html>'''
    return render_template_string(html, title=title, active=active, nav=nav, is_super=is_super, club_name=club_name, **ctx)


def _club_stats(cid):
    gross = db.session.query(func.coalesce(func.sum(SportCommissionLedger.gross_syp), 0)).filter_by(club_id=cid).scalar() or 0
    comm = db.session.query(func.coalesce(func.sum(SportCommissionLedger.commission_syp), 0)).filter_by(club_id=cid).scalar() or 0
    net = db.session.query(func.coalesce(func.sum(SportCommissionLedger.club_net_syp), 0)).filter_by(club_id=cid).scalar() or 0
    pending = db.session.query(func.coalesce(func.sum(SportPayment.amount_syp), 0)).filter_by(club_id=cid, status='pending_verification').scalar() or 0
    orders = db.session.query(func.count(func.distinct(SportPayment.order_id))).filter_by(club_id=cid).scalar() or 0
    return {'gross': int(gross), 'commission': int(comm), 'net': int(net), 'pending': int(pending), 'orders': int(orders)}


def dashboard_v5():
    g = _guard()
    if g: return g
    _backfill_ledgers()
    if _super_ok():
        clubs = SportClub.query.order_by(SportClub.id.asc()).all()
        rows=[]
        total_gross=total_comm=total_net=total_pending=0
        for c in clubs:
            s=_club_stats(c.id); a=_account_for_club(c.id); s.update(club=c, account=a, rate=_rate_for_club(c.id)); rows.append(s)
            total_gross+=s['gross']; total_comm+=s['commission']; total_net+=s['net']; total_pending+=s['pending']
        body=r'''<div class="stats"><div class="stat"><span>المبيعات المؤكدة</span><b>{{money(total_gross)}} ل.س</b></div><div class="stat"><span>عمولتك المستحقة</span><b>{{money(total_comm)}} ل.س</b></div><div class="stat"><span>صافي الأندية</span><b>{{money(total_net)}} ل.س</b></div><div class="stat"><span>دفعات معلقة</span><b>{{money(total_pending)}} ل.س</b></div></div><section class="section"><div class="sectionhead"><div><h2>إحصائية كل نادي</h2><div class="sub">النسبة تُثبت على الدفعة وقت تأكيدها.</div></div><a class="btn primary" href="/sporthub/admin/clubs">+ إضافة نادي</a></div><div class="tablewrap"><table class="table"><thead><tr><th>النادي</th><th>نسبتك الحالية</th><th>المبيعات المؤكدة</th><th>عمولتك</th><th>صافي النادي</th><th>معلق</th><th>الطلبات</th></tr></thead><tbody>{% for r in rows %}<tr><td><b>{{r.club.name}}</b><br><small>{{r.club.city or ''}}</small></td><td><b>{{r.rate}}%</b></td><td class="money">{{money(r.gross)}} ل.س</td><td class="money">{{money(r.commission)}} ل.س</td><td class="money">{{money(r.net)}} ل.س</td><td class="money">{{money(r.pending)}} ل.س</td><td>{{r.orders}}</td></tr>{% else %}<tr><td colspan="7">لا يوجد أندية.</td></tr>{% endfor %}</tbody></table></div></section>'''
        return _layout('لوحة المنصة',body,'dashboard',subtitle='ملخص المبيعات والعمولات لجميع الأندية.',rows=rows,money=_money,total_gross=total_gross,total_comm=total_comm,total_net=total_net,total_pending=total_pending)
    cid=_club_id(); c=SportClub.query.get_or_404(cid); s=_club_stats(cid); products=SportProduct.query.filter_by(club_id=cid).count(); rate=_rate_for_club(cid)
    body=r'''<div class="stats"><div class="stat"><span>مبيعات ناديك المؤكدة</span><b>{{money(s.gross)}} ل.س</b></div><div class="stat"><span>عمولة المنصة</span><b>{{money(s.commission)}} ل.س</b></div><div class="stat"><span>صافي ناديك</span><b>{{money(s.net)}} ل.س</b></div><div class="stat"><span>دفعات معلقة</span><b>{{money(s.pending)}} ل.س</b></div></div><section class="section"><div class="card"><h2 style="margin-top:0">{{club.name}}</h2><div class="grid2"><div class="note"><b>نسبة عمولة المنصة:</b> {{rate}}%<br>هذه النسبة يحددها مدير المنصة.</div><div class="note"><b>منتجاتك:</b> {{products}} منتج<br><b>طلبات مرتبطة بناديك:</b> {{s.orders}}</div></div><div class="actions"><a class="btn primary" href="/sporthub/admin/products">إدارة المنتجات والأسعار</a><a class="btn secondary" href="/sporthub/admin/orders">عرض الطلبات والمبيعات</a></div></div></section>'''
    return _layout('لوحة ناديك',body,'dashboard',subtitle='تدير منتجات وأسعار ناديك فقط.',club=c,s=s,rate=rate,products=products,money=_money)

app.view_functions['sporthub_admin'] = dashboard_v5


def clubs_v5():
    if not _super_ok():
        return redirect('/sporthub/admin') if _any_admin() else redirect('/sporthub/admin/login')
    clubs=SportClub.query.order_by(SportClub.id.asc()).all(); rows=[]
    for c in clubs:
        rows.append({'club':c,'account':_account_for_club(c.id),'stats':_club_stats(c.id),'rate':_rate_for_club(c.id)})
    body=r'''<section class="section"><div class="sectionhead"><div><h2>إضافة نادي جديد</h2><div class="sub">كل نادي يحتاج حساب مدير مستقل ونسبة عمولة خاصة بك.</div></div></div><form class="card" method="post" enctype="multipart/form-data" action="/sporthub/admin/clubs/new"><div class="grid2"><label class="field">اسم النادي<input name="name" required></label><label class="field">المدينة<input name="city"></label><label class="field">حساب شام كاش<input name="shamcash_account"></label><label class="field">QR شام كاش<input type="file" name="qr" accept="image/*"></label><label class="field">اسم مستخدم مدير النادي<input name="club_username" required placeholder="مثال: power_admin"></label><label class="field">كلمة مرور مدير النادي<input type="password" name="club_password" minlength="6" required></label><label class="field">نسبتك من المبيعات %<input type="number" step="0.01" min="0" max="100" name="commission_pct" value="10" required></label></div><div class="actions"><button class="btn primary">+ إنشاء النادي وحساب المدير</button></div></form></section><section class="section"><div class="sectionhead"><div><h2>الأندية الحالية</h2><div class="sub">يمكنك تعديل العمولة أو بيانات دخول مدير النادي في أي وقت.</div></div></div><div class="clubs">{% for r in rows %}<form class="clubcard" method="post" enctype="multipart/form-data" action="/sporthub/admin/clubs/{{r.club.id}}/save"><div class="clubhead"><div style="display:flex;gap:12px;align-items:center">{% if r.club.shamcash_qr %}<img class="qr" src="/sporthub/club/{{r.club.id}}/qr">{% else %}<div class="emptyqr">لا يوجد<br>QR</div>{% endif %}<div><h3>{{r.club.name}}</h3><span class="badge">{{'فعال' if r.club.active else 'موقوف'}}</span></div></div><div class="commission">{{r.rate}}%</div></div><div class="grid2"><label class="field">اسم النادي<input name="name" value="{{r.club.name}}" required></label><label class="field">المدينة<input name="city" value="{{r.club.city or ''}}"></label><label class="field">حساب شام كاش<input name="shamcash_account" value="{{r.club.shamcash_account or ''}}"></label><label class="field">تغيير QR<input type="file" name="qr" accept="image/*"></label><label class="field">اسم مستخدم مدير النادي<input name="club_username" value="{{r.account.username if r.account else ''}}" required></label><label class="field">كلمة مرور جديدة <small>(اتركها فارغة إن لم تتغير)</small><input type="password" name="club_password" minlength="6"></label><label class="field">نسبتك من المبيعات %<input type="number" step="0.01" min="0" max="100" name="commission_pct" value="{{r.rate}}" required></label></div><div class="mini-grid"><div class="mini"><small>المبيعات</small><b>{{money(r.stats.gross)}} ل.س</b></div><div class="mini"><small>عمولتك</small><b>{{money(r.stats.commission)}} ل.س</b></div><div class="mini"><small>صافي النادي</small><b>{{money(r.stats.net)}} ل.س</b></div></div><div class="actions"><button class="btn primary" name="action" value="save">حفظ</button><button class="btn secondary" name="action" value="toggle">{{'إيقاف النادي' if r.club.active else 'تفعيل النادي'}}</button></div></form>{% endfor %}</div></section>'''
    return _layout('الأندية والعمولات',body,'clubs',subtitle='أنشئ حساباً مستقلاً لكل نادي وحدد نسبة المنصة.',rows=rows,money=_money)

app.view_functions['sporthub_admin_clubs_v2'] = clubs_v5


def club_new_v5():
    if not _super_ok(): abort(403)
    name=(request.form.get('name') or '').strip(); username=(request.form.get('club_username') or '').strip(); password=request.form.get('club_password') or ''
    if not name or not username or len(password)<6:
        flash('اسم النادي واسم المستخدم وكلمة مرور 6 أحرف على الأقل مطلوبة'); return redirect('/sporthub/admin/clubs')
    if SportClubAccount.query.filter(func.lower(SportClubAccount.username)==username.lower()).first():
        flash('اسم مستخدم مدير النادي مستخدم مسبقاً'); return redirect('/sporthub/admin/clubs')
    c=SportClub(slug=admin2._slug(name),name=name[:180],city=(request.form.get('city') or '').strip()[:120],shamcash_account=(request.form.get('shamcash_account') or '').strip()[:250],active=True)
    raw,mime=admin2._read_image('qr')
    if raw: c.shamcash_qr=raw; c.shamcash_qr_mime=mime
    db.session.add(c); db.session.flush()
    a=SportClubAccount(club_id=c.id,username=username[:120],password_hash=generate_password_hash(password),commission_pct=_commission_value(request.form.get('commission_pct')),active=True)
    db.session.add(a); db.session.commit(); flash('تم إنشاء النادي وحساب مديره ونسبة العمولة')
    return redirect('/sporthub/admin/clubs')

app.view_functions['sporthub_admin_clubs_new_v2'] = club_new_v5


def club_save_v5(cid):
    if not _super_ok(): abort(403)
    c=SportClub.query.get_or_404(cid)
    if request.form.get('action')=='toggle':
        c.active=not bool(c.active); a=_account_for_club(cid)
        if a: a.active=bool(c.active)
        db.session.commit(); flash('تم تغيير حالة النادي'); return redirect('/sporthub/admin/clubs')
    c.name=(request.form.get('name') or c.name).strip()[:180]; c.city=(request.form.get('city') or '').strip()[:120]; c.shamcash_account=(request.form.get('shamcash_account') or '').strip()[:250]
    raw,mime=admin2._read_image('qr')
    if raw: c.shamcash_qr=raw; c.shamcash_qr_mime=mime
    username=(request.form.get('club_username') or '').strip(); password=request.form.get('club_password') or ''; rate=_commission_value(request.form.get('commission_pct'))
    a=_account_for_club(cid)
    if not a:
        if not username or len(password)<6:
            flash('لإنشاء حساب مدير لهذا النادي أدخل اسم مستخدم وكلمة مرور جديدة'); return redirect('/sporthub/admin/clubs')
        exists=SportClubAccount.query.filter(func.lower(SportClubAccount.username)==username.lower()).first()
        if exists: flash('اسم المستخدم مستخدم مسبقاً'); return redirect('/sporthub/admin/clubs')
        a=SportClubAccount(club_id=cid,username=username[:120],password_hash=generate_password_hash(password),commission_pct=rate,active=True); db.session.add(a)
    else:
        if username and username.lower()!=a.username.lower():
            exists=SportClubAccount.query.filter(func.lower(SportClubAccount.username)==username.lower(),SportClubAccount.id!=a.id).first()
            if exists: flash('اسم المستخدم مستخدم مسبقاً'); return redirect('/sporthub/admin/clubs')
            a.username=username[:120]
        if password:
            if len(password)<6: flash('كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل'); return redirect('/sporthub/admin/clubs')
            a.password_hash=generate_password_hash(password)
        a.commission_pct=rate; a.active=bool(c.active)
    db.session.commit(); flash('تم حفظ النادي وحسابه ونسبة العمولة'); return redirect('/sporthub/admin/clubs')

app.view_functions['sporthub_admin_clubs_save_v2'] = club_save_v5


@app.get('/sporthub/admin/my-club')
def my_club_v5():
    if not _club_ok():
        return redirect('/sporthub/admin') if _super_ok() else redirect('/sporthub/admin/login')
    c=SportClub.query.get_or_404(_club_id()); rate=_rate_for_club(c.id); s=_club_stats(c.id)
    body=r'''<section class="section"><form class="card" method="post" enctype="multipart/form-data"><div class="sectionhead"><div><h2>{{club.name}}</h2><div class="sub">يمكنك تحديث معلومات الدفع الخاصة بناديك. نسبة العمولة يحددها مدير المنصة فقط.</div></div></div><div class="grid2"><label class="field">اسم النادي<input value="{{club.name}}" disabled></label><label class="field">المدينة<input value="{{club.city or ''}}" disabled></label><label class="field">حساب شام كاش<input name="shamcash_account" value="{{club.shamcash_account or ''}}"></label><label class="field">تغيير QR شام كاش<input type="file" name="qr" accept="image/*"></label></div><div class="note" style="margin-top:13px">نسبة عمولة المنصة الحالية: <b>{{rate}}%</b></div><div class="actions"><button class="btn primary">حفظ معلومات شام كاش</button></div></form></section>'''
    return _layout('إعدادات ناديك',body,'myclub',subtitle='بيانات النادي والدفع فقط.',club=c,rate=rate,s=s)


@app.post('/sporthub/admin/my-club')
def my_club_save_v5():
    if not _club_ok(): abort(403)
    c=SportClub.query.get_or_404(_club_id()); c.shamcash_account=(request.form.get('shamcash_account') or '').strip()[:250]
    raw,mime=admin2._read_image('qr')
    if raw: c.shamcash_qr=raw; c.shamcash_qr_mime=mime
    db.session.commit(); flash('تم حفظ معلومات شام كاش'); return redirect('/sporthub/admin/my-club')


def products_v5():
    g=_guard()
    if g:return g
    if _super_ok():
        clubs=SportClub.query.order_by(SportClub.name.asc()).all(); products=SportProduct.query.order_by(SportProduct.id.desc()).all(); fixed=None
    else:
        fixed=_club_id(); clubs=[SportClub.query.get_or_404(fixed)]; products=SportProduct.query.filter_by(club_id=fixed).order_by(SportProduct.id.desc()).all()
    body=r'''<section class="section"><div class="sectionhead"><div><h2>إضافة منتج</h2><div class="sub">مدير النادي يضيف ويسعّر منتجات ناديه بنفسه.</div></div></div><form class="card" method="post" action="/sporthub/admin/products/new"><div class="grid2">{% if is_super %}<label class="field">النادي<select name="club_id" required>{% for c in clubs %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></label>{% else %}<input type="hidden" name="club_id" value="{{fixed}}">{% endif %}<label class="field">اسم المنتج<input name="name" required></label><label class="field">التصنيف<select name="category"><option value="protein">بروتين</option><option value="creatine">كرياتين</option><option value="supplements">مكملات</option><option value="accessories">إكسسوارات</option><option value="apparel">ملابس</option><option value="other">أخرى</option></select></label><label class="field">السعر بالليرة<input type="number" min="0" name="price_syp" required></label><label class="field">المخزون<input type="number" min="0" name="stock_qty" value="0" required></label><label class="field span2">الوصف<textarea name="description"></textarea></label></div><div class="actions"><button class="btn primary">+ إضافة المنتج</button></div></form></section><section class="section"><div class="sectionhead"><div><h2>المنتجات الحالية</h2><div class="sub">عدّل السعر والمخزون مباشرة.</div></div></div><div class="tablewrap"><table class="table"><thead><tr><th>المنتج</th>{% if is_super %}<th>النادي</th>{% endif %}<th>السعر</th><th>المخزون</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody>{% for p in products %}<tr><form method="post" action="/sporthub/admin/products/{{p.id}}/save"><td><input name="name" value="{{p.name}}" required style="padding:8px;border:1px solid #d2ded7;border-radius:8px;min-width:180px"><input type="hidden" name="category" value="{{p.category}}"><input type="hidden" name="description" value="{{p.description or ''}}"></td>{% if is_super %}<td><select name="club_id" style="padding:8px;border:1px solid #d2ded7;border-radius:8px">{% for c in clubs %}<option value="{{c.id}}" {{'selected' if c.id==p.club_id else ''}}>{{c.name}}</option>{% endfor %}</select></td>{% else %}<input type="hidden" name="club_id" value="{{fixed}}">{% endif %}<td><input type="number" min="0" name="price_syp" value="{{p.price_syp}}" style="width:130px;padding:8px;border:1px solid #d2ded7;border-radius:8px"></td><td><input type="number" min="0" name="stock_qty" value="{{p.stock_qty}}" style="width:85px;padding:8px;border:1px solid #d2ded7;border-radius:8px"></td><td><span class="badge">{{'ظاهر' if p.active else 'مخفي'}}</span></td><td><button class="btn primary" name="action" value="save">حفظ</button> <button class="btn secondary" name="action" value="toggle">{{'إخفاء' if p.active else 'إظهار'}}</button></td></form></tr>{% else %}<tr><td colspan="6">لا توجد منتجات.</td></tr>{% endfor %}</tbody></table></div></section>'''
    return _layout('المنتجات والأسعار',body,'products',subtitle='إدارة الأسعار والمخزون حسب صلاحية الحساب.',clubs=clubs,products=products,fixed=fixed,is_super=_super_ok())

app.view_functions['sporthub_admin_products_v2'] = products_v5


def product_new_v5():
    g=_guard()
    if g:return g
    try: cid=int(request.form.get('club_id')); price=max(0,int(request.form.get('price_syp') or 0)); stock=max(0,int(request.form.get('stock_qty') or 0))
    except Exception: flash('تحقق من القيم'); return redirect('/sporthub/admin/products')
    if _club_ok() and cid!=_club_id(): abort(403)
    if not SportClub.query.get(cid): abort(404)
    name=(request.form.get('name') or '').strip()
    if not name: flash('اسم المنتج مطلوب'); return redirect('/sporthub/admin/products')
    p=SportProduct(club_id=cid,name=name[:220],category=(request.form.get('category') or 'other')[:80],description=(request.form.get('description') or '').strip(),price_syp=price,stock_qty=stock,active=True)
    db.session.add(p); db.session.commit(); flash('تمت إضافة المنتج'); return redirect('/sporthub/admin/products')

app.view_functions['sporthub_admin_products_new_v2'] = product_new_v5


def product_save_v5(pid):
    g=_guard()
    if g:return g
    p=SportProduct.query.get_or_404(pid)
    if _club_ok() and p.club_id!=_club_id(): abort(403)
    if request.form.get('action')=='toggle': p.active=not bool(p.active); db.session.commit(); flash('تم تغيير ظهور المنتج'); return redirect('/sporthub/admin/products')
    try: cid=int(request.form.get('club_id')); price=max(0,int(request.form.get('price_syp') or 0)); stock=max(0,int(request.form.get('stock_qty') or 0))
    except Exception: flash('تحقق من القيم'); return redirect('/sporthub/admin/products')
    if _club_ok(): cid=_club_id()
    elif not SportClub.query.get(cid): abort(404)
    p.club_id=cid; p.name=(request.form.get('name') or p.name).strip()[:220]; p.price_syp=price; p.stock_qty=stock; p.category=(request.form.get('category') or p.category)[:80]; p.description=(request.form.get('description') or p.description or '').strip()
    db.session.commit(); flash('تم حفظ المنتج'); return redirect('/sporthub/admin/products')

app.view_functions['sporthub_admin_products_save_v2'] = product_save_v5


def orders_v5():
    g=_guard()
    if g:return g
    _backfill_ledgers()
    q=SportPayment.query.order_by(SportPayment.id.desc())
    if _club_ok(): q=q.filter_by(club_id=_club_id())
    payments=q.limit(200).all(); rows=[]
    for p in payments:
        order=SportOrder.query.get(p.order_id); club=SportClub.query.get(p.club_id); ledger=SportCommissionLedger.query.filter_by(payment_id=p.id).first()
        rows.append({'payment':p,'order':order,'club':club,'ledger':ledger})
    body=r'''<section class="section"><div class="sectionhead"><div><h2>الطلبات والدفعات</h2><div class="sub">تأكيد الدفع يثبت نسبة العمولة على العملية.</div></div></div><div class="tablewrap"><table class="table"><thead><tr><th>الطلب</th>{% if is_super %}<th>النادي</th>{% endif %}<th>العميل</th><th>حصة النادي من الطلب</th><th>رقم عملية شام كاش</th><th>الحالة</th><th>العمولة</th><th>إجراء</th></tr></thead><tbody>{% for r in rows %}<tr><td><b>{{r.order.order_no if r.order else r.payment.order_id}}</b><br><small>{{r.order.created_at.strftime('%Y-%m-%d %H:%M') if r.order and r.order.created_at else ''}}</small></td>{% if is_super %}<td>{{r.club.name if r.club else ''}}</td>{% endif %}<td>{{r.order.customer_name if r.order else ''}}<br><small>{{r.order.phone if r.order else ''}}</small></td><td class="money">{{money(r.payment.amount_syp)}} ل.س</td><td>{{r.payment.shamcash_transaction or '—'}}</td><td><span class="badge {{'pending' if r.payment.status=='pending_verification' else ('rejected' if r.payment.status=='rejected' else '')}}">{{status_label(r.payment.status)}}</span></td><td>{% if r.ledger %}<b>{{r.ledger.commission_pct}}%</b><br><small>{{money(r.ledger.commission_syp)}} ل.س</small>{% else %}—{% endif %}</td><td>{% if r.payment.status=='pending_verification' %}<form method="post" action="/sporthub/admin/payments/{{r.payment.id}}/status" style="display:flex;gap:5px"><button class="btn primary" name="status" value="verified">تأكيد</button><button class="btn danger" name="status" value="rejected">رفض</button></form>{% else %}<form method="post" action="/sporthub/admin/payments/{{r.payment.id}}/status"><button class="btn secondary" name="status" value="pending_verification">إرجاع للمراجعة</button></form>{% endif %}</td></tr>{% else %}<tr><td colspan="8">لا يوجد دفعات بعد.</td></tr>{% endfor %}</tbody></table></div></section>'''
    labels=lambda s:{'pending_verification':'بانتظار التحقق','verified':'مؤكد','paid':'مدفوع','rejected':'مرفوض'}.get(s,s)
    return _layout('الطلبات والمبيعات',body,'orders',subtitle='كل حساب يرى فقط الطلبات المسموحة له.',rows=rows,is_super=_super_ok(),money=_money,status_label=labels)

app.view_functions['sporthub_admin_orders_v2'] = orders_v5


@app.post('/sporthub/admin/payments/<int:payment_id>/status')
def payment_status_v5(payment_id):
    g=_guard()
    if g:return g
    p=SportPayment.query.get_or_404(payment_id)
    if _club_ok() and p.club_id!=_club_id(): abort(403)
    status=request.form.get('status') or ''
    if status not in ('verified','rejected','pending_verification'): abort(400)
    p.status=status
    ledger=SportCommissionLedger.query.filter_by(payment_id=p.id).first()
    if status=='verified':
        if not ledger: _ensure_ledger(p)
    else:
        if ledger: db.session.delete(ledger)
    db.session.commit(); flash('تم تحديث حالة الدفعة')
    return redirect('/sporthub/admin/orders')
