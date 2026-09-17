# -*- coding: utf-8 -*-
"""Dedicated authentication layer for SPORT HUB.

Customers always use the public storefront as guests. Admin routes require a
SPORT HUB-only login backed by Render environment variables, separate from the
Nahda accounting login/session.
"""
import hmac
import os
from functools import wraps

from flask import request, session, redirect, url_for, render_template_string, flash, abort

import web_sporthub_storefront_v3 as storefront
import web_sporthub_admin_v2 as admin_v2

app = storefront.app

ADMIN_USER = os.environ.get("SPORTHUB_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("SPORTHUB_ADMIN_PASSWORD", "")


def sporthub_admin_logged_in():
    return bool(session.get("sporthub_admin") is True)


def sporthub_admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not sporthub_admin_logged_in():
            return redirect(url_for("sporthub_admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


# Make all existing v2 admin actions use the dedicated SPORT HUB session.
admin_v2._is_admin = sporthub_admin_logged_in
admin_v2._require_admin = lambda: None if sporthub_admin_logged_in() else abort(403)

LOGIN_HTML = r'''
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SPORT HUB | دخول الإدارة</title>
<style>
:root{--dark:#0b1510;--green:#18b565;--mut:#728078;--line:#dfe7e2;--bg:#f3f6f4}*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial;background:linear-gradient(145deg,#eef5f0,#f9fbfa);min-height:100vh;display:grid;place-items:center;padding:20px;color:#101712}.shell{width:min(980px,100%);min-height:580px;background:#fff;border:1px solid var(--line);border-radius:30px;overflow:hidden;display:grid;grid-template-columns:1.02fr .98fr;box-shadow:0 30px 90px #10201818}.visual{background:radial-gradient(circle at 20% 15%,#235b3a,#0b1510 58%);color:#fff;padding:55px;display:flex;flex-direction:column;justify-content:space-between}.brand{display:flex;align-items:center;gap:12px;font-weight:1000}.mark{width:48px;height:48px;border-radius:14px;background:#fff;color:#0b1510;display:grid;place-items:center}.mark b{color:var(--green)}.visual h1{font-size:48px;line-height:1.08;margin:0 0 18px}.visual p{color:#b9c9bf;line-height:1.9;max-width:430px}.chips{display:flex;gap:8px;flex-wrap:wrap}.chip{font-size:11px;padding:8px 10px;border-radius:999px;background:#ffffff12;border:1px solid #ffffff18}.login{padding:55px;display:flex;flex-direction:column;justify-content:center}.eyebrow{color:var(--green);font-size:12px;font-weight:1000}.login h2{font-size:34px;margin:9px 0 8px}.sub{color:var(--mut);font-size:13px;line-height:1.8;margin-bottom:24px}.field{display:block;font-size:12px;font-weight:900;margin:13px 0}.field input{width:100%;margin-top:7px;padding:14px;border:1px solid var(--line);border-radius:13px;outline:none;font-size:15px}.field input:focus{border-color:#7dd8a3;box-shadow:0 0 0 4px #e9f8ef}.btn{width:100%;border:0;border-radius:13px;padding:14px;background:var(--dark);color:#fff;font-weight:1000;font-size:15px;cursor:pointer;margin-top:8px}.btn:hover{background:var(--green)}.guest{margin-top:13px;text-align:center}.guest a{color:#187d4a;text-decoration:none;font-weight:900;font-size:12px}.flash{padding:11px 12px;border-radius:11px;background:#fff0f0;color:#9d2f2f;border:1px solid #f0cccc;margin:10px 0;font-size:12px}.secure{margin-top:22px;padding:12px;border-radius:12px;background:var(--bg);color:var(--mut);font-size:11px;line-height:1.7}@media(max-width:760px){.shell{grid-template-columns:1fr;min-height:auto}.visual{display:none}.login{padding:34px 24px}.login h2{font-size:29px}}
</style></head><body><div class="shell"><section class="visual"><div class="brand"><div class="mark"><b>S</b>H</div><span>SPORT HUB ADMIN</span></div><div><h1>إدارة المتجر<br>من مكان واحد.</h1><p>الأندية، حسابات شام كاش، المنتجات، المخزون والطلبات — منفصلة بالكامل عن واجهة الزبون.</p><div class="chips"><span class="chip">الأندية</span><span class="chip">Sham Cash</span><span class="chip">المخزون</span><span class="chip">الطلبات</span></div></div><small style="color:#8fa299">لوحة خاصة بالإدارة فقط</small></section><section class="login"><span class="eyebrow">تسجيل دخول الإدارة</span><h2>أهلاً بك</h2><div class="sub">الزبائن لا يحتاجون حساباً للدخول إلى المتجر. هذه الصفحة مخصصة للمدير فقط.</div>{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}<form method="post"><label class="field">اسم المستخدم<input name="username" autocomplete="username" required autofocus></label><label class="field">كلمة المرور<input type="password" name="password" autocomplete="current-password" required></label><button class="btn">دخول لوحة الإدارة</button></form><div class="guest"><a href="/">← دخول المتجر كزبون</a></div><div class="secure">بيانات دخول SPORT HUB مستقلة عن نظام المحاسبة القديم، ولا تظهر للزبائن.</div></section></div></body></html>
'''


@app.route("/sporthub/admin/login", methods=["GET", "POST"])
def sporthub_admin_login():
    if sporthub_admin_logged_in():
        return redirect("/sporthub/admin")
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        ok_user = hmac.compare_digest(username, ADMIN_USER)
        ok_pass = bool(ADMIN_PASSWORD) and hmac.compare_digest(password, ADMIN_PASSWORD)
        if ok_user and ok_pass:
            session["sporthub_admin"] = True
            session["sporthub_admin_user"] = username
            nxt = request.args.get("next") or "/sporthub/admin"
            if not nxt.startswith("/sporthub/admin"):
                nxt = "/sporthub/admin"
            return redirect(nxt)
        flash("اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template_string(LOGIN_HTML)


@app.get("/sporthub/admin/logout")
def sporthub_admin_logout():
    session.pop("sporthub_admin", None)
    session.pop("sporthub_admin_user", None)
    return redirect(url_for("sporthub_admin_login"))


# Replace the v2 dashboard view with a guarded wrapper while keeping all routes/actions.
_original_dashboard = app.view_functions.get("sporthub_admin")
if _original_dashboard:
    @wraps(_original_dashboard)
    def _guarded_dashboard(*args, **kwargs):
        if not sporthub_admin_logged_in():
            return redirect(url_for("sporthub_admin_login"))
        return _original_dashboard(*args, **kwargs)
    app.view_functions["sporthub_admin"] = _guarded_dashboard


# Guard every known SPORT HUB admin mutation route, even if someone calls it directly.
for endpoint, view in list(app.view_functions.items()):
    if endpoint.startswith("sporthub_admin_") and endpoint not in {"sporthub_admin_login", "sporthub_admin_logout"}:
        if endpoint == "sporthub_admin":
            continue
        app.view_functions[endpoint] = sporthub_admin_required(view)


# Short friendly aliases on the public SPORT HUB hostname/proxy.
@app.get("/admin")
def sporthub_admin_short():
    return redirect("/sporthub/admin")

@app.get("/admin/login")
def sporthub_admin_login_short():
    return redirect("/sporthub/admin/login")

@app.get("/customer")
def sporthub_customer_short():
    return redirect("/sporthub")
