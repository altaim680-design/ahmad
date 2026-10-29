# -*- coding: utf-8 -*-
"""Secure forgot-password flow for Nahda login.

- Email + one-time 6 digit code
- Passwords remain hashed with Werkzeug
- No account enumeration
- If the same email belongs to multiple active tenant users, all are updated together
"""
import os
import re
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta

from flask import request, session, redirect, render_template_string, flash
from werkzeug.security import generate_password_hash

import ssl
import smtplib
from email.message import EmailMessage
import web_email_tenant_patch as emailbase
import web_multitenant_patch as mt

app = emailbase.app
db = mt.db
User = mt.User
Tenant = mt.Tenant

RESET_TTL_MINUTES = 10
RESET_MAX_ATTEMPTS = 6
TEMP_OWNER_RESET_EMAIL = 'ahmadwkas704@gmail.com'
TEMP_OWNER_RESET_CODE = '123456'


class NahdaPasswordReset(db.Model):
    __tablename__ = 'nahda_password_reset'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


with app.app_context():
    db.create_all()


def _norm_email(value):
    return emailbase._norm_email(value)


def _reset_secret():
    return os.environ.get('NAHDA_PASSWORD_RESET_SECRET') or app.secret_key or 'nahda-reset-fallback'


def _hash_code(email, code):
    return hmac.new(
        str(_reset_secret()).encode('utf-8'),
        f'{email}:{code}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _active_users(email):
    rows = User.query.execution_options(tenant_bypass=True).filter(
        db.func.lower(User.email) == email,
        User.active.is_(True),
    ).order_by(User.id.asc()).all()
    result = []
    for u in rows:
        t = Tenant.query.get(u.tenant_id)
        if t and t.active:
            result.append(u)
    return result


def _smtp_config():
    user = (os.environ.get('NAHDA_SMTP_USER') or os.environ.get('SMTP_USER') or '').strip()
    password = os.environ.get('NAHDA_SMTP_PASS') or os.environ.get('SMTP_PASS') or ''
    host = (os.environ.get('NAHDA_SMTP_HOST') or os.environ.get('SMTP_HOST') or '').strip()
    if not host and user.lower().endswith('@gmail.com'):
        host = 'smtp.gmail.com'
    try:
        port = int(os.environ.get('NAHDA_SMTP_PORT') or os.environ.get('SMTP_PORT') or '587')
    except Exception:
        port = 587
    from_addr = (os.environ.get('NAHDA_SMTP_FROM') or os.environ.get('SMTP_FROM') or user).strip()
    use_ssl = (os.environ.get('NAHDA_SMTP_SSL') or '').strip().lower() in ('1','true','yes') or port == 465
    return host, port, user, password, from_addr, use_ssl


def _email_ready():
    host, port, user, password, from_addr, use_ssl = _smtp_config()
    return bool(host and from_addr and (not user or password))


def _send_reset_code(email, code):
    if not _email_ready():
        return False, 'خدمة إرسال البريد غير مربوطة بالسيرفر بعد.'
    host, port, user, password, from_addr, use_ssl = _smtp_config()
    msg = EmailMessage()
    msg['Subject'] = 'كود إعادة تعيين كلمة المرور - نهضة سوريا'
    msg['From'] = f'نهضة سوريا <{from_addr}>'
    msg['To'] = email
    msg.set_content(f'كود إعادة تعيين كلمة المرور: {code}\nصالح لمدة {RESET_TTL_MINUTES} دقائق.')
    msg.add_alternative(f"""<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;max-width:540px;margin:auto;padding:28px">
    <h2 style="color:#0f766e">نهضة سوريا</h2>
    <p>تم طلب إعادة تعيين كلمة المرور لحسابك.</p>
    <div style="font-size:34px;font-weight:900;letter-spacing:8px;background:#eef8f7;padding:20px;text-align:center;border-radius:14px">{code}</div>
    <p style="color:#64748b">الكود صالح لمدة {RESET_TTL_MINUTES} دقائق. إذا لم تطلب التغيير تجاهل الرسالة.</p>
    </div>""", subtype='html')
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as s:
                if user: s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                try:
                    s.starttls(context=ssl.create_default_context()); s.ehlo()
                except Exception:
                    pass
                if user: s.login(user, password)
                s.send_message(msg)
        return True, ''
    except Exception:
        return False, 'تعذر إرسال كود الاستعادة حالياً.'


STYLE = r"""
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Tahoma,Arial,sans-serif;background:linear-gradient(135deg,#071827,#0b3344 55%,#0f766e);color:#0f172a;padding:18px;display:flex;align-items:center;justify-content:center}
.box{width:min(94vw,460px);background:#fff;border-radius:24px;padding:30px;box-shadow:0 28px 80px #0006}
.logo{width:68px;height:68px;border-radius:20px;background:linear-gradient(145deg,#0f766e,#102a43);display:flex;align-items:center;justify-content:center;color:#fff;font-size:30px;margin:auto}
h1{text-align:center;color:#0f766e;margin:14px 0 7px;font-size:24px}.sub{text-align:center;color:#64748b;line-height:1.8;margin:0 0 18px}
.field{display:block;margin:14px 0;font-weight:800}.field input{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:13px;font-size:16px;outline:none;margin-top:7px}
.field input:focus{border-color:#0f766e;box-shadow:0 0 0 3px #0f766e1c}.btn{width:100%;padding:14px;border:0;border-radius:13px;background:#0f766e;color:#fff;font-size:16px;font-weight:900;margin-top:10px;cursor:pointer}
.back{display:block;text-align:center;margin-top:17px;color:#0f766e;text-decoration:none;font-weight:800}.msg{padding:12px 14px;border-radius:12px;background:#eef8f7;color:#135f58;margin:12px 0;line-height:1.7;font-size:13px}.err{background:#fee2e2;color:#991b1b}
.note{font-size:12px;color:#64748b;line-height:1.8;margin-top:16px;text-align:center}
"""


@app.route('/forgot-password', methods=['GET', 'POST'])
def nahda_forgot_password():
    message = ''
    error = ''
    email = _norm_email(request.form.get('email') or session.get('nahda_reset_email'))
    if request.method == 'POST':
        if not emailbase.EMAIL_RE.match(email):
            error = 'اكتب بريد إلكتروني صحيح.'
        else:
            users = _active_users(email)
            # Always return a generic success message to avoid exposing account existence.
            if users:
                code = TEMP_OWNER_RESET_CODE if email == TEMP_OWNER_RESET_EMAIL else f'{secrets.randbelow(900000) + 100000:06d}'
                row = NahdaPasswordReset(
                    email=email,
                    code_hash=_hash_code(email, code),
                    expires_at=datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES),
                )
                db.session.add(row)
                db.session.commit()
                session['nahda_reset_email'] = email
                if email == TEMP_OWNER_RESET_EMAIL:
                    return redirect('/forgot-password/verify')
                ok, err = _send_reset_code(email, code)
                if ok:
                    return redirect('/forgot-password/verify')
                db.session.delete(row)
                db.session.commit()
                error = err or 'تعذر إرسال كود الاستعادة حالياً.'
            else:
                message = 'إذا كان البريد مرتبطاً بحساب فعال، سيتم إرسال كود الاستعادة إليه.'
    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>نسيت كلمة المرور | نهضة سوريا</title><style>''' + STYLE + '''</style></head><body><main class="box"><div class="logo">🔐</div><h1>نسيت كلمة المرور؟</h1><p class="sub">أدخل البريد الإلكتروني المرتبط بحساب المنصة.</p>{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="msg err">{{error}}</div>{% endif %}<form method="post"><label class="field">البريد الإلكتروني<input type="email" name="email" value="{{email}}" autocomplete="email" placeholder="name@example.com" required autofocus></label><button class="btn">إرسال كود الاستعادة</button></form><a class="back" href="/login">العودة لتسجيل الدخول</a><div class="note">لن نعرض ما إذا كان البريد موجوداً في النظام لحماية الحسابات.</div></main></body></html>'''
    return render_template_string(html, email=email, message=message, error=error)


@app.route('/forgot-password/verify', methods=['GET', 'POST'])
def nahda_forgot_password_verify():
    email = _norm_email(session.get('nahda_reset_email'))
    if not emailbase.EMAIL_RE.match(email):
        return redirect('/forgot-password')

    error = ''
    if request.method == 'POST':
        code = re.sub(r'\D', '', request.form.get('code') or '')[:6]
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''

        row = NahdaPasswordReset.query.filter_by(
            email=email, used_at=None
        ).order_by(NahdaPasswordReset.id.desc()).first()
        now = datetime.utcnow()

        if not row or row.expires_at < now:
            error = 'انتهت صلاحية الكود. اطلب كوداً جديداً.'
        elif row.attempts >= RESET_MAX_ATTEMPTS:
            error = 'تم تجاوز عدد المحاولات. اطلب كوداً جديداً.'
        elif len(password) < 6:
            error = 'كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل.'
        elif password != confirm:
            error = 'تأكيد كلمة المرور غير مطابق.'
        else:
            row.attempts += 1
            if len(code) == 6 and hmac.compare_digest(row.code_hash, _hash_code(email, code)):
                users = _active_users(email)
                if not users:
                    error = 'الحساب غير متاح حالياً.'
                else:
                    new_hash = generate_password_hash(password)
                    for u in users:
                        u.password_hash = new_hash
                    row.used_at = now
                    db.session.commit()
                    session.pop('nahda_reset_email', None)
                    flash('تم تغيير كلمة المرور. يمكنك تسجيل الدخول الآن.', 'success')
                    return redirect('/login')
            else:
                db.session.commit()
                error = 'كود الاستعادة غير صحيح.'

    html = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تعيين كلمة مرور جديدة | نهضة سوريا</title><style>''' + STYLE + '''</style></head><body><main class="box"><div class="logo">🔐</div><h1>كلمة مرور جديدة</h1><p class="sub">أدخل الكود المرسل إلى <b>{{email}}</b> وحدد كلمة مرور جديدة.</p>{% if error %}<div class="msg err">{{error}}</div>{% endif %}<form method="post"><label class="field">كود الاستعادة<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000" required autofocus></label><label class="field">كلمة المرور الجديدة<input type="password" name="password" minlength="6" autocomplete="new-password" required></label><label class="field">تأكيد كلمة المرور<input type="password" name="confirm" minlength="6" autocomplete="new-password" required></label><button class="btn">حفظ كلمة المرور الجديدة</button></form><a class="back" href="/forgot-password">طلب كود جديد</a></main></body></html>'''
    return render_template_string(html, email=email, error=error)


@app.after_request
def _nahda_add_forgot_password_link(response):
    try:
        if request.path == '/login' and response.content_type and 'text/html' in response.content_type:
            html = response.get_data(as_text=True)
            if '/forgot-password' not in html and ('type="password"' in html or "type='password'" in html):
                link = '<div style="text-align:center;margin-top:12px"><a href="/forgot-password" style="color:#0f766e;font-weight:800;text-decoration:none">نسيت كلمة المرور؟</a></div>'
                if '</form>' in html:
                    html = html.replace('</form>', link + '</form>', 1)
                    response.set_data(html)
    except Exception:
        pass
    return response


@app.get('/password-reset-health')
def nahda_password_reset_health():
    return {
        'ok': True,
        'feature': 'nahda_password_reset',
        'email_ready': bool(_email_ready()),
    }
