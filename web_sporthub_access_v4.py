# -*- coding: utf-8 -*-
import os
import hmac
import time
from datetime import timedelta

from flask import request, session, redirect, render_template_string
from markupsafe import escape

import web_sporthub_storefront_v3 as store
import web_sporthub_admin_v2 as admin2
import web_sporthub_admin_patch as admin1
import web_sporthub_patch as core

app = store.app
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)


def _admin_ok():
    return bool(session.get('sporthub_admin') is True)


def _admin_guard():
    if not _admin_ok():
        return redirect('/sporthub/admin/login')

# Make all SPORT HUB admin pages/actions use the dedicated SPORT HUB session,
# without granting access to the separate accounting-system admin area.
admin2._is_admin = _admin_ok
admin2._guard = _admin_guard
if hasattr(admin1, '_is_admin'):
    admin1._is_admin = _admin_ok
if hasattr(core, '_sporthub_is_admin'):
    core._sporthub_is_admin = _admin_ok

# Add a clean logout action to the existing strong admin layout.
_original_layout = admin2._layout

def _layout_v4(title, body, active='dashboard', **ctx):
    html = _original_layout(title, body, active, **ctx)
    user = str(escape(session.get('sporthub_admin_user') or 'admin'))
    html = html.replace('حساب المدير', f'المدير: {user}')
    html = html.replace(
        '<div class="store"><a href="/">فتح المتجر</a></div>',
        '<div class="store"><a href="/shop">فتح المتجر كزبون</a><a href="/admin/logout" style="margin-top:9px;background:#402226;color:#ffd9d9">تسجيل الخروج</a></div>'
    )
    return html

admin2._layout = _layout_v4

LANDING_HTML = r'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPORT HUB | اختر طريقة الدخول</title>
<style>
:root{--green:#1fb76a;--dark:#0c1711;--mut:#708078;--line:#e3ebe6;--bg:#f5f8f6}
*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial,sans-serif;background:radial-gradient(circle at 50% -10%,#dff6e8 0,transparent 35%),var(--bg);color:#132019;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.shell{width:min(1050px,100%)}.brand{text-align:center;margin-bottom:28px}.mark{width:72px;height:72px;border-radius:22px;background:var(--dark);color:#fff;display:grid;place-items:center;margin:auto;font-size:26px;font-weight:1000;box-shadow:0 18px 45px #0b1a1230}.mark b{color:#67f69d}.brand h1{margin:14px 0 5px;font-size:34px}.brand p{margin:0;color:var(--mut)}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:32px;box-shadow:0 20px 60px #10251a10;position:relative;overflow:hidden}.card:before{content:"";position:absolute;width:180px;height:180px;border-radius:50%;left:-60px;top:-70px;background:#eff8f2}.icon{width:62px;height:62px;border-radius:18px;background:#eef8f2;display:grid;place-items:center;font-size:28px;position:relative}.card.admin .icon{background:#eef1f3}.card h2{font-size:28px;margin:22px 0 10px}.card p{color:var(--mut);line-height:1.9;margin:0 0 24px;min-height:74px}.btn{display:flex;align-items:center;justify-content:center;width:100%;padding:15px;border-radius:14px;text-decoration:none;font-weight:1000}.customer{background:var(--green);color:#fff}.adminbtn{background:var(--dark);color:#fff}.points{display:grid;gap:8px;margin-bottom:24px;color:#526159;font-size:13px}.points span:before{content:"✓";color:var(--green);font-weight:1000;margin-left:7px}.foot{text-align:center;color:#87938d;font-size:11px;margin-top:22px}
@media(max-width:720px){.cards{grid-template-columns:1fr}.brand h1{font-size:28px}.card{padding:24px}.card p{min-height:0}}
</style></head><body><main class="shell"><div class="brand"><div class="mark"><b>S</b>H</div><h1>SPORT HUB</h1><p>منصة الأندية والمنتجات الرياضية</p></div><div class="cards">
<section class="card"><div class="icon">🛍️</div><h2>الدخول كزبون</h2><p>تصفّح منتجات الأندية، أضف للسلة، وأكمل الدفع عبر شام كاش الخاص بالنادي.</p><div class="points"><span>لا يحتاج حساب أو كلمة مرور</span><span>متجر واضح وسريع على الموبايل</span><span>سلة وطلب ودفع شام كاش</span></div><a class="btn customer" href="/sporthub/shop">فتح المتجر كزبون</a></section>
<section class="card admin"><div class="icon">⚙️</div><h2>دخول الأدمن</h2><p>إدارة الأندية، حسابات شام كاش، المنتجات، المخزون والطلبات من لوحة مستقلة ومحميّة.</p><div class="points"><span>تسجيل دخول خاص بالمدير</span><span>إضافة نادي وحساب شام كاش وQR</span><span>إدارة المنتجات والمخزون والطلبات</span></div><a class="btn adminbtn" href="/sporthub/admin/login">تسجيل دخول الأدمن</a></section>
</div><div class="foot">SPORT HUB • منصة رياضية متعددة الأندية</div></main></body></html>'''

LOGIN_HTML = r'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول الأدمن | SPORT HUB</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Tahoma,Arial,sans-serif;background:linear-gradient(135deg,#07130d,#173c26);display:grid;place-items:center;padding:20px}.box{width:min(440px,100%);background:#fff;border-radius:26px;padding:30px;box-shadow:0 30px 90px #0006}.brand{text-align:center}.logo{width:68px;height:68px;margin:auto;border-radius:20px;background:#0d1b13;color:#fff;display:grid;place-items:center;font-size:24px;font-weight:1000}.logo b{color:#67f69d}.brand h1{margin:14px 0 5px;font-size:25px}.brand p{margin:0;color:#718078;font-size:13px}.field{display:block;margin:16px 0 0;font-weight:800;font-size:12px;color:#4e5e55}.field input{width:100%;margin-top:7px;padding:14px;border:1px solid #d5e0d9;border-radius:13px;outline:none;font-size:15px}.field input:focus{border-color:#5bc886;box-shadow:0 0 0 3px #e5f7ec}.btn{width:100%;margin-top:18px;padding:14px;border:0;border-radius:13px;background:#13231a;color:#fff;font-size:16px;font-weight:1000;cursor:pointer}.error{margin-top:15px;padding:11px 13px;border-radius:11px;background:#feecec;color:#a33434;font-size:12px}.back{display:block;text-align:center;margin-top:16px;text-decoration:none;color:#1c9b59;font-weight:800;font-size:12px}.hint{margin-top:18px;padding-top:15px;border-top:1px solid #e8eeea;color:#819087;font-size:11px;text-align:center;line-height:1.8}.passwrap{position:relative}.show{position:absolute;left:10px;top:17px;border:0;background:none;cursor:pointer;color:#6a7a71;font-size:12px}
</style></head><body><div class="box"><div class="brand"><div class="logo"><b>S</b>H</div><h1>دخول إدارة SPORT HUB</h1><p>هذه الصفحة للمدير فقط</p></div>{% if error %}<div class="error">{{error}}</div>{% endif %}<form method="post"><label class="field">اسم المستخدم<input name="username" autocomplete="username" required autofocus></label><label class="field">كلمة المرور<div class="passwrap"><input id="pw" type="password" name="password" autocomplete="current-password" required><button type="button" class="show" onclick="let p=document.getElementById('pw');p.type=p.type==='password'?'text':'password'">إظهار</button></div></label><button class="btn">دخول لوحة الأدمن</button></form><a class="back" href="/sporthub/shop">← الدخول كزبون بدلاً من ذلك</a><div class="hint">بعد الدخول ستظهر لك صفحات منفصلة للأندية وشام كاش، المنتجات، المخزون والطلبات.</div></div></body></html>'''


def entry_page():
    return render_template_string(LANDING_HTML)

# Replace the public SPORT HUB root with the two-mode entry page.
app.view_functions['sporthub_home'] = entry_page


@app.get('/sporthub/shop')
def sporthub_customer_shop():
    return store.premium_storefront()


@app.route('/sporthub/admin/login', methods=['GET', 'POST'])
def sporthub_admin_login_v4():
    if _admin_ok():
        return redirect('/sporthub/admin')
    error = None
    if request.method == 'POST':
        now = int(time.time())
        locked_until = int(session.get('sporthub_login_lock_until') or 0)
        if locked_until > now:
            error = 'محاولات كثيرة. انتظر دقيقة ثم حاول مجدداً.'
        else:
            username = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''
            expected_user = os.environ.get('SPORTHUB_ADMIN_USER', 'admin')
            expected_pass = os.environ.get('SPORTHUB_ADMIN_PASS', '')
            ok_user = hmac.compare_digest(username, expected_user)
            ok_pass = bool(expected_pass) and hmac.compare_digest(password, expected_pass)
            if ok_user and ok_pass:
                session.pop('sporthub_login_attempts', None)
                session.pop('sporthub_login_lock_until', None)
                session['sporthub_admin'] = True
                session['sporthub_admin_user'] = username
                session.permanent = True
                return redirect('/sporthub/admin')
            attempts = int(session.get('sporthub_login_attempts') or 0) + 1
            session['sporthub_login_attempts'] = attempts
            if attempts >= 5:
                session['sporthub_login_attempts'] = 0
                session['sporthub_login_lock_until'] = now + 60
                error = 'تم إيقاف المحاولات لمدة دقيقة للحماية.'
            else:
                error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'
    return render_template_string(LOGIN_HTML, error=error)


@app.get('/sporthub/admin/logout')
def sporthub_admin_logout_v4():
    session.pop('sporthub_admin', None)
    session.pop('sporthub_admin_user', None)
    session.pop('sporthub_login_attempts', None)
    session.pop('sporthub_login_lock_until', None)
    return redirect('/sporthub/admin/login')
