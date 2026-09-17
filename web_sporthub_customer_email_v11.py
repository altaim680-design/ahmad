# -*- coding: utf-8 -*-
"""SPORT HUB V11 - customer email OTP accounts and order recovery.

Customers can browse anonymously, but checkout requires a verified email account.
OTP codes are short-lived and stored hashed. Orders are linked to the customer so
payment can be resumed after leaving the site. Email delivery uses SMTP settings
from environment variables and never stores mail credentials in the database.
"""
import os
import re
import hmac
import ssl
import smtplib
import secrets
import hashlib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import request, session, redirect, jsonify, render_template_string, abort, flash
from sqlalchemy import func

import web_sporthub_product_images_v10 as v10
import web_sporthub_marketplace_v5 as v5
import web_sporthub_access_v4 as access
import web_sporthub_patch as core
import web_sporthub_storefront_v3 as store

app = v10.app
db = core.db
SportOrder = core.SportOrder
SportOrderItem = core.SportOrderItem
SportPayment = core.SportPayment
SportClub = core.SportClub

EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
OTP_TTL_MINUTES = 10
OTP_RESEND_SECONDS = 60
OTP_MAX_PER_HOUR = 5
OTP_MAX_ATTEMPTS = 6


class SportCustomer(db.Model):
    __tablename__ = 'sporthub_customer'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(180), default='')
    phone = db.Column(db.String(80), default='')
    active = db.Column(db.Boolean, nullable=False, default=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SportCustomerOtp(db.Model):
    __tablename__ = 'sporthub_customer_otp'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class SportCustomerOrder(db.Model):
    __tablename__ = 'sporthub_customer_order'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('sporthub_customer.id', ondelete='CASCADE'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('sporthub_order.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


with app.app_context():
    db.create_all()


def _norm_email(value):
    return (value or '').strip().lower()[:255]


def _safe_next(value):
    value = (value or '').strip()
    if not value.startswith('/sporthub/') or value.startswith('//'):
        return '/sporthub/shop'
    return value[:500]


def _otp_secret():
    return os.environ.get('SPORTHUB_OTP_SECRET') or app.secret_key or 'sporthub-otp-fallback'


def _hash_otp(email, code):
    raw = f'{email}:{code}'.encode('utf-8')
    key = str(_otp_secret()).encode('utf-8')
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


def _smtp_config():
    user = (os.environ.get('SPORTHUB_SMTP_USER') or os.environ.get('SMTP_USER') or '').strip()
    password = os.environ.get('SPORTHUB_SMTP_PASS') or os.environ.get('SMTP_PASS') or ''
    host = (os.environ.get('SPORTHUB_SMTP_HOST') or os.environ.get('SMTP_HOST') or '').strip()
    if not host and user.lower().endswith('@gmail.com'):
        host = 'smtp.gmail.com'
    port_raw = os.environ.get('SPORTHUB_SMTP_PORT') or os.environ.get('SMTP_PORT') or '587'
    try:
        port = int(port_raw)
    except Exception:
        port = 587
    from_addr = (os.environ.get('SPORTHUB_SMTP_FROM') or user).strip()
    from_name = (os.environ.get('SPORTHUB_EMAIL_FROM_NAME') or 'SPORT HUB').strip()
    use_ssl = (os.environ.get('SPORTHUB_SMTP_SSL') or '').strip().lower() in ('1', 'true', 'yes') or port == 465
    return {'host': host, 'port': port, 'user': user, 'password': password, 'from': from_addr, 'name': from_name, 'ssl': use_ssl}


def _email_ready():
    c = _smtp_config()
    return bool(c['host'] and c['from'] and (not c['user'] or c['password']))


def _send_email(to_email, subject, text_body, html_body=None):
    c = _smtp_config()
    if not _email_ready():
        return False, 'خدمة إرسال البريد غير مربوطة بالسيرفر بعد.'
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"{c['name']} <{c['from']}>"
    msg['To'] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype='html')
    try:
        if c['ssl']:
            with smtplib.SMTP_SSL(c['host'], c['port'], timeout=15, context=ssl.create_default_context()) as s:
                if c['user']:
                    s.login(c['user'], c['password'])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c['host'], c['port'], timeout=15) as s:
                s.ehlo()
                try:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                except Exception:
                    pass
                if c['user']:
                    s.login(c['user'], c['password'])
                s.send_message(msg)
        return True, ''
    except Exception as exc:
        print('SPORTHUB_EMAIL_SEND_ERROR', type(exc).__name__, flush=True)
        return False, 'تعذر إرسال رسالة التحقق حالياً. حاول بعد قليل.'


def _issue_otp(email):
    now = datetime.utcnow()
    latest = SportCustomerOtp.query.filter_by(email=email).order_by(SportCustomerOtp.id.desc()).first()
    if latest and latest.created_at and (now - latest.created_at).total_seconds() < OTP_RESEND_SECONDS:
        remain = OTP_RESEND_SECONDS - int((now - latest.created_at).total_seconds())
        return False, f'انتظر {max(1, remain)} ثانية قبل طلب كود جديد.'
    hour_ago = now - timedelta(hours=1)
    count = SportCustomerOtp.query.filter(SportCustomerOtp.email == email, SportCustomerOtp.created_at >= hour_ago).count()
    if count >= OTP_MAX_PER_HOUR:
        return False, 'تم طلب عدد كبير من الأكواد. حاول بعد ساعة.'
    code = f'{secrets.randbelow(900000) + 100000:06d}'
    row = SportCustomerOtp(
        email=email,
        code_hash=_hash_otp(email, code),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.session.add(row)
    db.session.commit()
    html = f'''<div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;max-width:520px;margin:auto;padding:24px">
    <div style="font-size:22px;font-weight:800">SPORT HUB</div>
    <h2>كود تسجيل الدخول</h2>
    <p>استخدم الكود التالي لتسجيل الدخول إلى حسابك:</p>
    <div style="font-size:34px;font-weight:900;letter-spacing:7px;background:#eef8f2;padding:18px;text-align:center;border-radius:14px">{code}</div>
    <p style="color:#68776f">الكود صالح لمدة {OTP_TTL_MINUTES} دقائق. لا تشاركه مع أي شخص.</p></div>'''
    ok, err = _send_email(email, 'كود دخول SPORT HUB', f'كود دخول SPORT HUB: {code}\nصالح لمدة {OTP_TTL_MINUTES} دقائق.', html)
    if not ok:
        try:
            db.session.delete(row)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return False, err
    return True, ''


def _customer():
    try:
        cid = int(session.get('sporthub_customer_id') or 0)
    except Exception:
        cid = 0
    if not cid:
        return None
    c = SportCustomer.query.filter_by(id=cid, active=True).first()
    if not c:
        session.pop('sporthub_customer_id', None)
        session.pop('sporthub_customer_email', None)
        return None
    return c


def _customer_order(order_no):
    c = _customer()
    if not c:
        return None, None
    order = SportOrder.query.filter_by(order_no=order_no).first()
    if not order:
        return c, None
    link = SportCustomerOrder.query.filter_by(customer_id=c.id, order_id=order.id).first()
    return c, order if link else None


AUTH_STYLE = '''
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Tahoma,Arial,sans-serif;background:linear-gradient(135deg,#07150e,#17482a);color:#132019;padding:20px}.box{width:min(480px,100%);margin:6vh auto;background:#fff;border-radius:26px;padding:30px;box-shadow:0 28px 80px #0005}.brand{text-align:center}.mark{width:68px;height:68px;border-radius:20px;background:#102119;color:#fff;display:grid;place-items:center;margin:auto;font-size:23px;font-weight:1000}.mark b{color:#69f59b}.brand h1{margin:14px 0 6px}.brand p{margin:0;color:#718078;font-size:13px;line-height:1.8}.field{display:block;margin-top:16px;font-size:12px;font-weight:900;color:#536159}.field input{width:100%;margin-top:7px;padding:14px;border:1px solid #d5e0da;border-radius:13px;outline:none;font-size:16px}.field input:focus{border-color:#52c47f;box-shadow:0 0 0 3px #e5f7ec}.btn{width:100%;border:0;border-radius:13px;padding:14px;margin-top:18px;background:#14251b;color:#fff;font-weight:1000;font-size:16px;cursor:pointer}.msg{padding:11px 13px;border-radius:11px;margin-top:14px;background:#feecec;color:#9d3636;font-size:12px;line-height:1.7}.ok{background:#e8f7ee;color:#17683f}.back{display:block;text-align:center;margin-top:16px;text-decoration:none;color:#179555;font-size:12px;font-weight:900}.code{text-align:center;letter-spacing:6px;font-size:24px;font-weight:900}.hint{font-size:11px;color:#819087;text-align:center;margin-top:16px;line-height:1.8}
'''


def customer_login_page():
    c = _customer()
    nxt = _safe_next(request.values.get('next') or session.get('sporthub_customer_next'))
    if c:
        return redirect(nxt if nxt != '/sporthub/shop' else '/sporthub/customer/account')
    error = ''
    email = _norm_email(request.form.get('email') or session.get('sporthub_pending_email'))
    if request.method == 'POST':
        if not EMAIL_RE.match(email):
            error = 'اكتب بريد إلكتروني صحيح.'
        else:
            ok, error = _issue_otp(email)
            if ok:
                session['sporthub_pending_email'] = email
                session['sporthub_customer_next'] = nxt
                return redirect('/sporthub/customer/verify')
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول الزبون | SPORT HUB</title><style>''' + AUTH_STYLE + '''</style></head><body><main class="box"><div class="brand"><div class="mark"><b>S</b>H</div><h1>دخول الزبون</h1><p>أدخل إيميلك وسنرسل لك كود تحقق من 6 أرقام. لا تحتاج كلمة مرور.</p></div>{% if error %}<div class="msg">{{error}}</div>{% endif %}<form method="post"><input type="hidden" name="next" value="{{nxt}}"><label class="field">البريد الإلكتروني<input type="email" name="email" value="{{email}}" autocomplete="email" placeholder="name@example.com" required autofocus></label><button class="btn">إرسال كود التحقق</button></form><div class="hint">بعد التحقق، طلباتك تبقى مرتبطة بحسابك وتقدر ترجع تكمل الدفع لاحقاً.</div><a class="back" href="/sporthub/shop">← الرجوع للمتجر</a></main></body></html>'''
    return render_template_string(html, error=error, email=email, nxt=nxt)


def customer_verify_page():
    email = _norm_email(session.get('sporthub_pending_email'))
    if not EMAIL_RE.match(email):
        return redirect('/sporthub/customer/login')
    error = ''
    if request.method == 'POST':
        action = request.form.get('action') or 'verify'
        if action == 'resend':
            ok, error = _issue_otp(email)
            if ok:
                error = 'تم إرسال كود جديد.'
        else:
            code = re.sub(r'\D', '', request.form.get('code') or '')[:6]
            row = SportCustomerOtp.query.filter_by(email=email, used_at=None).order_by(SportCustomerOtp.id.desc()).first()
            now = datetime.utcnow()
            if not row or row.expires_at < now:
                error = 'انتهت صلاحية الكود. اطلب كوداً جديداً.'
            elif row.attempts >= OTP_MAX_ATTEMPTS:
                error = 'تم تجاوز عدد المحاولات. اطلب كوداً جديداً.'
            else:
                row.attempts += 1
                if len(code) == 6 and hmac.compare_digest(row.code_hash, _hash_otp(email, code)):
                    row.used_at = now
                    customer = SportCustomer.query.filter(func.lower(SportCustomer.email) == email).first()
                    if not customer:
                        customer = SportCustomer(email=email, verified_at=now, last_login_at=now, active=True)
                        db.session.add(customer)
                        db.session.flush()
                    else:
                        customer.verified_at = customer.verified_at or now
                        customer.last_login_at = now
                        customer.active = True
                    db.session.commit()
                    session.pop('sporthub_pending_email', None)
                    session['sporthub_customer_id'] = customer.id
                    session['sporthub_customer_email'] = customer.email
                    session.permanent = True
                    nxt = _safe_next(session.pop('sporthub_customer_next', None))
                    return redirect(nxt)
                db.session.commit()
                error = 'كود التحقق غير صحيح.'
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تحقق الإيميل | SPORT HUB</title><style>''' + AUTH_STYLE + '''</style></head><body><main class="box"><div class="brand"><div class="mark"><b>S</b>H</div><h1>تحقق من الإيميل</h1><p>أرسلنا كوداً إلى <b>{{email}}</b></p></div>{% if error %}<div class="msg {{'ok' if error.startswith('تم إرسال') else ''}}">{{error}}</div>{% endif %}<form method="post"><label class="field">كود التحقق<input class="code" inputmode="numeric" autocomplete="one-time-code" name="code" maxlength="6" placeholder="000000" required autofocus></label><button class="btn" name="action" value="verify">تأكيد ودخول</button></form><form method="post"><button class="btn" style="background:#eef3ef;color:#193126" name="action" value="resend">إرسال كود جديد</button></form><a class="back" href="/sporthub/customer/login">تغيير الإيميل</a></main></body></html>'''
    return render_template_string(html, error=error, email=email)


def customer_status_api():
    c = _customer()
    if not c:
        return jsonify(logged_in=False, email_ready=_email_ready())
    return jsonify(logged_in=True, email=c.email, name=c.name or '', phone=c.phone or '', email_ready=_email_ready())


def customer_logout():
    for key in ('sporthub_customer_id', 'sporthub_customer_email', 'sporthub_pending_email', 'sporthub_customer_next'):
        session.pop(key, None)
    return redirect('/sporthub/shop')


def _order_status_label(status):
    return {
        'pending_payment': 'بانتظار الدفع',
        'pending_verification': 'بانتظار التحقق',
        'verified': 'مؤكد',
        'paid': 'مدفوع',
        'rejected': 'مرفوض',
        'cancelled': 'ملغي',
    }.get(status or '', status or '—')


def customer_account_page():
    c = _customer()
    if not c:
        return redirect('/sporthub/customer/login?next=/sporthub/customer/account')
    message = ''
    if request.method == 'POST':
        c.name = (request.form.get('name') or '').strip()[:180]
        c.phone = (request.form.get('phone') or '').strip()[:80]
        db.session.commit()
        message = 'تم حفظ بياناتك.'
    links = SportCustomerOrder.query.filter_by(customer_id=c.id).order_by(SportCustomerOrder.id.desc()).limit(100).all()
    ids = [x.order_id for x in links]
    orders = []
    if ids:
        order_map = {o.id: o for o in SportOrder.query.filter(SportOrder.id.in_(ids)).all()}
        orders = [order_map[x.order_id] for x in links if x.order_id in order_map]
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>حسابي | SPORT HUB</title><style>
    *{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial;background:#f4f7f5;color:#122019}.top{background:#102019;color:#fff;padding:16px 5vw;display:flex;align-items:center;gap:12px}.top b{font-size:20px;margin-left:auto}.top a{color:#fff;text-decoration:none;font-size:12px;font-weight:900;padding:9px 12px;border-radius:10px;background:#20372b}.wrap{width:min(1050px,calc(100% - 28px));margin:28px auto}.grid{display:grid;grid-template-columns:330px 1fr;gap:16px}.card{background:#fff;border:1px solid #dfe8e3;border-radius:18px;padding:18px}.field{display:block;font-size:11px;font-weight:900;color:#69766f;margin-top:12px}.field input{width:100%;margin-top:6px;padding:11px;border:1px solid #d3ded8;border-radius:10px}.btn{border:0;border-radius:10px;background:#19aa60;color:#fff;padding:11px 14px;font-weight:900;margin-top:13px;cursor:pointer}.order{display:grid;grid-template-columns:1fr auto;gap:10px;padding:15px 0;border-bottom:1px solid #edf2ef}.order:last-child{border-bottom:0}.order a{text-decoration:none;color:#12854c;font-weight:900}.mut{color:#748179;font-size:11px;line-height:1.8}.price{font-weight:1000}.msg{background:#e8f7ee;color:#17633e;padding:10px;border-radius:10px;margin-bottom:10px}@media(max-width:760px){.grid{grid-template-columns:1fr}.order{grid-template-columns:1fr}}
    </style></head><body><header class="top"><b>SPORT HUB • حسابي</b><a href="/sporthub/shop">المتجر</a><a href="/sporthub/customer/logout">خروج</a></header><main class="wrap"><div class="grid"><section class="card"><h2 style="margin-top:0">بيانات الحساب</h2><div class="mut">{{c.email}}</div>{% if message %}<div class="msg">{{message}}</div>{% endif %}<form method="post"><label class="field">الاسم<input name="name" value="{{c.name or ''}}"></label><label class="field">رقم الهاتف<input name="phone" value="{{c.phone or ''}}"></label><button class="btn">حفظ البيانات</button></form></section><section class="card"><h2 style="margin-top:0">طلباتي</h2>{% for o in orders %}<div class="order"><div><a href="/sporthub/customer/order/{{o.order_no}}">{{o.order_no}}</a><div class="mut">{{o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else ''}} • {{status_label(o.status)}}</div></div><div class="price">{{money(o.total_syp)}} ل.س</div></div>{% else %}<div class="mut">ما عندك طلبات بعد.</div>{% endfor %}</section></div></main></body></html>'''
    return render_template_string(html, c=c, orders=orders, message=message, money=v5._money, status_label=_order_status_label)


def customer_order_page(order_no):
    c, order = _customer_order(order_no)
    if not c:
        return redirect('/sporthub/customer/login?next=' + _safe_next('/sporthub/customer/order/' + order_no))
    if not order:
        abort(404)
    message = ''
    if request.method == 'POST':
        try:
            pid = int(request.form.get('payment_id') or 0)
        except Exception:
            pid = 0
        payment = SportPayment.query.filter_by(id=pid, order_id=order.id).first()
        if not payment:
            abort(404)
        if payment.status in ('verified', 'paid'):
            message = 'هذه الدفعة مؤكدة ولا يمكن تعديلها.'
        else:
            tx = (request.form.get('transaction') or '').strip()[:180]
            payment.shamcash_transaction = tx
            f = request.files.get('receipt')
            if f and f.filename:
                raw = f.read(4 * 1024 * 1024 + 1)
                mime = (f.mimetype or '').lower()[:100]
                if len(raw) <= 4 * 1024 * 1024 and mime.startswith('image/'):
                    payment.receipt_image = raw
                    payment.receipt_mime = mime
                else:
                    message = 'صورة الإيصال غير صالحة أو أكبر من 4MB.'
            if not message:
                payment.status = 'pending_verification' if tx or payment.receipt_image else 'pending_payment'
                db.session.commit()
                pays = SportPayment.query.filter_by(order_id=order.id).all()
                order.status = 'pending_verification' if pays and all((p.shamcash_transaction or p.receipt_image) for p in pays) else 'pending_payment'
                db.session.commit()
                message = 'تم حفظ بيانات الدفع. ستتم مراجعتها من النادي.'
    items = SportOrderItem.query.filter_by(order_id=order.id).order_by(SportOrderItem.id.asc()).all()
    payments = SportPayment.query.filter_by(order_id=order.id).order_by(SportPayment.id.asc()).all()
    rows = []
    for p in payments:
        rows.append({'payment': p, 'club': SportClub.query.get(p.club_id)})
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{order.order_no}} | SPORT HUB</title><style>
    *{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial;background:#f4f7f5;color:#122019}.top{background:#102019;color:#fff;padding:16px 5vw}.top a{color:#fff;text-decoration:none}.wrap{width:min(920px,calc(100% - 28px));margin:26px auto}.card{background:#fff;border:1px solid #dfe8e3;border-radius:18px;padding:18px;margin-bottom:14px}.head{display:flex;justify-content:space-between;gap:12px}.mut{color:#748179;font-size:12px;line-height:1.8}.item,.paytop{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid #edf2ef}.pay{border:1px solid #dfe8e3;border-radius:15px;padding:15px;margin-top:12px}.qr{width:150px;max-width:100%;display:block;margin:12px auto;background:#fff;padding:7px;border:1px solid #e0e8e3;border-radius:12px}.field{display:block;margin-top:10px;font-size:11px;font-weight:900;color:#69766f}.field input{width:100%;margin-top:6px;padding:11px;border:1px solid #d3ded8;border-radius:10px}.btn{border:0;border-radius:10px;padding:11px 14px;background:#19aa60;color:#fff;font-weight:900;margin-top:11px}.msg{padding:11px;border-radius:10px;background:#e8f7ee;color:#17633e;margin-bottom:12px}.badge{display:inline-block;padding:5px 8px;border-radius:999px;background:#fff3df;color:#8b5b10;font-size:10px;font-weight:900}@media(max-width:620px){.head,.item,.paytop{display:block}.item b,.paytop b{display:block;margin-top:5px}}
    </style></head><body><header class="top"><a href="/sporthub/customer/account">← حسابي وطلباتي</a></header><main class="wrap">{% if message %}<div class="msg">{{message}}</div>{% endif %}<section class="card"><div class="head"><div><h2 style="margin:0">الطلب {{order.order_no}}</h2><div class="mut">{{order.customer_name}} • {{order.phone}}<br>{{order.address or ''}}</div></div><div><b>{{money(order.total_syp)}} ل.س</b><br><span class="badge">{{status_label(order.status)}}</span></div></div></section><section class="card"><h3>المنتجات</h3>{% for i in items %}<div class="item"><span>{{i.product_name}} × {{i.qty}}</span><b>{{money(i.line_total_syp)}} ل.س</b></div>{% endfor %}</section><section class="card"><h3>الدفع عبر شام كاش</h3><div class="mut">إذا خرجت من الموقع قبل إتمام الدفع، تقدر ترجع لهذه الصفحة بأي وقت من حسابك.</div>{% for r in rows %}<div class="pay"><div class="paytop"><div><b>{{r.club.name if r.club else 'النادي'}}</b><div class="mut">حساب شام كاش: {{r.club.shamcash_account if r.club and r.club.shamcash_account else 'غير محدد'}}</div></div><b>{{money(r.payment.amount_syp)}} ل.س</b></div>{% if r.club and r.club.shamcash_qr %}<img class="qr" src="/sporthub/club/{{r.club.id}}/qr">{% endif %}<div class="mut">الحالة: {{payment_label(r.payment)}}</div>{% if r.payment.status not in ('verified','paid') %}<form method="post" enctype="multipart/form-data"><input type="hidden" name="payment_id" value="{{r.payment.id}}"><label class="field">رقم عملية شام كاش<input name="transaction" value="{{r.payment.shamcash_transaction or ''}}" placeholder="أدخل رقم العملية"></label><label class="field">صورة الإيصال<input type="file" name="receipt" accept="image/*"></label><button class="btn">حفظ وإرسال للمراجعة</button></form>{% endif %}</div>{% endfor %}</section></main></body></html>'''
    def payment_label(p):
        if not p.shamcash_transaction and not p.receipt_image:
            return 'بانتظار الدفع'
        return _order_status_label(p.status)
    return render_template_string(html, order=order, items=items, rows=rows, message=message, money=v5._money, status_label=_order_status_label, payment_label=payment_label)


def _customer_dispatch_v11():
    path = request.path.rstrip('/') or '/'
    if path == '/sporthub/customer/status':
        return customer_status_api()
    if path == '/sporthub/customer/login':
        return customer_login_page()
    if path == '/sporthub/customer/verify':
        return customer_verify_page()
    if path == '/sporthub/customer/logout':
        return customer_logout()
    if path == '/sporthub/customer/account':
        return customer_account_page()
    m = re.fullmatch(r'/sporthub/customer/order/([A-Za-z0-9_-]{3,80})', path)
    if m:
        return customer_order_page(m.group(1))
    return None


# V8/V9 already execute Flask test requests during import, so custom customer
# URLs are dispatched through before_request instead of registering new rules.
app.before_request_funcs.setdefault(None, []).insert(0, _customer_dispatch_v11)


_original_create_order = core.sporthub_create_order


def sporthub_create_order_v11():
    customer = _customer()
    if not customer:
        return jsonify(error='سجل دخولك بالإيميل أولاً لإتمام الطلب.', login_url='/sporthub/customer/login?next=/sporthub/shop'), 401
    rv = _original_create_order()
    response = app.make_response(rv)
    if response.status_code < 300 and response.is_json:
        payload = response.get_json(silent=True) or {}
        order_no = payload.get('order_no')
        order = SportOrder.query.filter_by(order_no=order_no).first() if order_no else None
        if order:
            if not SportCustomerOrder.query.filter_by(order_id=order.id).first():
                db.session.add(SportCustomerOrder(customer_id=customer.id, order_id=order.id))
            data = request.get_json(silent=True) or {}
            if not customer.name:
                customer.name = (data.get('customer_name') or '').strip()[:180]
            if not customer.phone:
                customer.phone = (data.get('phone') or '').strip()[:80]
            db.session.commit()
            public = (os.environ.get('SPORTHUB_PUBLIC_URL') or 'https://sporthub-syria.onrender.com').rstrip('/')
            link = public + '/customer/order/' + order.order_no
            subject = f'طلبك {order.order_no} في SPORT HUB'
            text_body = f'تم حفظ طلبك رقم {order.order_no}. الإجمالي {int(order.total_syp or 0):,} ل.س. يمكنك متابعة الدفع من: {link}'
            html_body = f'''<div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;padding:24px"><h2>تم حفظ طلبك</h2><p>رقم الطلب: <b>{order.order_no}</b></p><p>الإجمالي: <b>{int(order.total_syp or 0):,} ل.س</b></p><p><a href="{link}" style="display:inline-block;background:#17a95f;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px">متابعة الطلب والدفع</a></p></div>'''
            _send_email(customer.email, subject, text_body, html_body)
    return response


# Replace the already-registered order endpoint without changing its public URL.
core.sporthub_create_order = sporthub_create_order_v11
if 'sporthub_create_order' in app.view_functions:
    app.view_functions['sporthub_create_order'] = sporthub_create_order_v11


# Stronger admin orders page: show customer email with each order.
def orders_v11():
    g = v5._guard()
    if g:
        return g
    v5._backfill_ledgers()
    q = core.SportPayment.query.order_by(core.SportPayment.id.desc())
    if v5._club_ok():
        q = q.filter_by(club_id=v5._club_id())
    payments = q.limit(200).all()
    rows = []
    for p in payments:
        order = SportOrder.query.get(p.order_id)
        club = SportClub.query.get(p.club_id)
        ledger = v5.SportCommissionLedger.query.filter_by(payment_id=p.id).first()
        email = ''
        if order:
            link = SportCustomerOrder.query.filter_by(order_id=order.id).first()
            if link:
                cust = SportCustomer.query.get(link.customer_id)
                email = cust.email if cust else ''
        rows.append({'payment': p, 'order': order, 'club': club, 'ledger': ledger, 'email': email})
    body = r'''<section class="section"><div class="sectionhead"><div><h2>الطلبات والدفعات</h2><div class="sub">يظهر الإيميل ورقم الهاتف حتى تقدر تتواصل مع الزبون إذا لم يكمل الدفع.</div></div></div><div class="tablewrap"><table class="table"><thead><tr><th>الطلب</th>{% if is_super %}<th>النادي</th>{% endif %}<th>العميل والتواصل</th><th>المبلغ</th><th>عملية شام كاش</th><th>الحالة</th><th>العمولة</th><th>إجراء</th></tr></thead><tbody>{% for r in rows %}<tr><td><b>{{r.order.order_no if r.order else r.payment.order_id}}</b><br><small>{{r.order.created_at.strftime('%Y-%m-%d %H:%M') if r.order and r.order.created_at else ''}}</small></td>{% if is_super %}<td>{{r.club.name if r.club else ''}}</td>{% endif %}<td>{{r.order.customer_name if r.order else ''}}<br><small>{{r.order.phone if r.order else ''}}</small>{% if r.email %}<br><a href="mailto:{{r.email}}" style="color:#168d51;font-size:11px">{{r.email}}</a>{% endif %}</td><td class="money">{{money(r.payment.amount_syp)}} ل.س</td><td>{{r.payment.shamcash_transaction or '—'}}</td><td><span class="badge {{'pending' if r.payment.status in ('pending_verification','pending_payment') else ('rejected' if r.payment.status=='rejected' else '')}}">{{status_label(r.payment)}}</span></td><td>{% if r.ledger %}<b>{{r.ledger.commission_pct}}%</b><br><small>{{money(r.ledger.commission_syp)}} ل.س</small>{% else %}—{% endif %}</td><td>{% if r.payment.status in ('pending_verification','pending_payment') %}<form method="post" action="/sporthub/admin/payments/{{r.payment.id}}/status" style="display:flex;gap:5px"><button class="btn primary" name="status" value="verified">تأكيد</button><button class="btn danger" name="status" value="rejected">رفض</button></form>{% else %}<form method="post" action="/sporthub/admin/payments/{{r.payment.id}}/status"><button class="btn secondary" name="status" value="pending_verification">إرجاع للمراجعة</button></form>{% endif %}</td></tr>{% else %}<tr><td colspan="8">لا يوجد دفعات بعد.</td></tr>{% endfor %}</tbody></table></div></section>'''
    def status_label(payment):
        if not payment.shamcash_transaction and not payment.receipt_image:
            return 'بانتظار الدفع'
        return _order_status_label(payment.status)
    return v5._layout('الطلبات والمبيعات', body, 'orders', subtitle='الطلبات مرتبطة بحسابات الزبائن الموثقة بالإيميل.', rows=rows, is_super=v5._super_ok(), money=v5._money, status_label=status_label)

v5.orders_v5 = orders_v11
if 'sporthub_admin_orders_v2' in app.view_functions:
    app.view_functions['sporthub_admin_orders_v2'] = orders_v11


# Update customer-facing entry page wording.
access.LANDING_HTML = access.LANDING_HTML.replace('لا يحتاج حساب أو كلمة مرور', 'دخول سريع بالإيميل وكود تحقق')
access.LANDING_HTML = access.LANDING_HTML.replace('سلة وطلب ودفع شام كاش', 'الطلبات محفوظة بحسابك ويمكن استكمال الدفع لاحقاً')


# Upgrade the premium storefront with customer account controls and cart persistence.
if '.accountbtn{' not in store.STORE_HTML:
    store.STORE_HTML = store.STORE_HTML.replace('</style>', '.accountbtn{border:1px solid var(--line);background:#fff;color:var(--dark);border-radius:12px;padding:10px 12px;font-weight:900;font-size:12px;white-space:nowrap}@media(max-width:720px){.accountbtn{padding:9px 10px;font-size:11px}} </style>', 1)

store.STORE_HTML = store.STORE_HTML.replace(
    '<button class="cartbtn" onclick="openCart()">السلة <span class="count" id="count">0</span></button>',
    '<a class="accountbtn" id="accountBtn" href="/sporthub/customer/login">دخول الزبون</a><button class="cartbtn" onclick="openCart()">السلة <span class="count" id="count">0</span></button>'
)
store.STORE_HTML = store.STORE_HTML.replace(
    "let clubs=[],products=[],cart={},activeCat='';",
    "let clubs=[],products=[],cart=JSON.parse(localStorage.getItem('sporthub_cart')||'{}'),activeCat='',customer={logged_in:false};"
)
store.STORE_HTML = store.STORE_HTML.replace(
    "async function boot(){try{clubs=await (await fetch('/sporthub/api/clubs')).json();products=await (await fetch('/sporthub/api/products')).json();renderClubs();renderProducts();renderCart()}catch(e){",
    "async function boot(){try{customer=await (await fetch('/sporthub/customer/status')).json();updateAccount();clubs=await (await fetch('/sporthub/api/clubs')).json();products=await (await fetch('/sporthub/api/products')).json();renderClubs();renderProducts();renderCart()}catch(e){"
)
store.STORE_HTML = store.STORE_HTML.replace(
    "function renderCart(){let box=document.getElementById('cartLines'),tot=0,cnt=0;",
    "function renderCart(){localStorage.setItem('sporthub_cart',JSON.stringify(cart));let box=document.getElementById('cartLines'),tot=0,cnt=0;"
)
store.STORE_HTML = store.STORE_HTML.replace(
    "function showCheckout(){if(!Object.keys(cart).length)return;document.getElementById('checkout').style.display='block';",
    "function showCheckout(){if(!Object.keys(cart).length)return;if(!customer.logged_in){location.href='/sporthub/customer/login?next='+encodeURIComponent('/sporthub/shop');return;}document.getElementById('checkout').style.display='block';if(customer.name&&!document.getElementById('name').value)document.getElementById('name').value=customer.name;if(customer.phone&&!document.getElementById('phone').value)document.getElementById('phone').value=customer.phone;"
)
store.STORE_HTML = store.STORE_HTML.replace(
    "async function placeOrder(){let name=document.getElementById('name').value.trim(),phone=document.getElementById('phone').value.trim(),notice=document.getElementById('notice');",
    "async function placeOrder(){if(!customer.logged_in){location.href='/sporthub/customer/login?next='+encodeURIComponent('/sporthub/shop');return;}let name=document.getElementById('name').value.trim(),phone=document.getElementById('phone').value.trim(),notice=document.getElementById('notice');"
)
store.STORE_HTML = store.STORE_HTML.replace(
    "notice.innerHTML=`تم تسجيل الطلب بنجاح. رقم الطلب: <b>${j.order_no}</b><br>حالة الدفع: بانتظار التحقق.`;cart={};renderCart()",
    "notice.innerHTML=`تم حفظ الطلب بنجاح. رقم الطلب: <b>${j.order_no}</b><br><a href=\"/sporthub/customer/order/${j.order_no}\" style=\"color:#137c49;font-weight:900\">فتح الطلب واستكمال الدفع لاحقاً</a>`;cart={};renderCart()"
)
store.STORE_HTML = store.STORE_HTML.replace(
    '<button class="primary full" onclick="placeOrder()">تسجيل الطلب</button>',
    '<button class="primary full" onclick="placeOrder()">حفظ الطلب وإرسال بيانات الدفع</button><div style="font-size:10px;color:#7a8780;line-height:1.7;margin-top:7px">طلبك سيبقى محفوظاً في حسابك، ويمكنك العودة لإكمال الدفع لاحقاً.</div>'
)
store.STORE_HTML = store.STORE_HTML.replace(
    'boot();\n</script>',
    "function updateAccount(){let b=document.getElementById('accountBtn');if(!b)return;if(customer.logged_in){b.href='/sporthub/customer/account';b.textContent=customer.name||'حسابي وطلباتي'}else{b.href='/sporthub/customer/login';b.textContent='دخول الزبون'}}\nboot();\n</script>"
)


def premium_storefront_v11():
    return render_template_string(store.STORE_HTML)

store.premium_storefront = premium_storefront_v11
if 'sporthub_customer_shop' in app.view_functions:
    app.view_functions['sporthub_customer_shop'] = premium_storefront_v11

print('SPORTHUB_V11_CUSTOMER_EMAIL_READY smtp=' + ('1' if _email_ready() else '0'), flush=True)

try:
    with app.test_client() as _tc:
        _s1 = _tc.get('/sporthub/customer/status').status_code
        _s2 = _tc.get('/sporthub/customer/login').status_code
        _s3 = _tc.get('/sporthub/shop').status_code
    print(f'SPORTHUB_V11_SELFTEST status={_s1} login={_s2} shop={_s3}', flush=True)
except Exception as _exc:
    print('SPORTHUB_V11_SELFTEST_ERROR', type(_exc).__name__, flush=True)
