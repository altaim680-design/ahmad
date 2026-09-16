# -*- coding: utf-8 -*-
"""Premium responsive login UI for Nahda multi-company platform."""
import web_email_login_hotfix as hotfix
import web_email_tenant_patch as emailbase
from flask import request, session, redirect, url_for, flash, render_template_string
from werkzeug.security import check_password_hash

app = hotfix.app
db = emailbase.db
User = emailbase.User
Tenant = emailbase.Tenant


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
    return redirect(url_for('debts') if u.role == 'collector' else url_for('home'))


LOGIN_HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#071827">
<title>تسجيل الدخول | نهضة سوريا</title>
<style>
:root{--navy:#071827;--navy2:#0b2739;--teal:#0e7c70;--teal2:#14a394;--gold:#d6ad55;--text:#10202c;--muted:#6b7c89;--line:#dce6eb;--danger:#b42318}
*{box-sizing:border-box}html,body{min-height:100%;margin:0}body{font-family:Tahoma,Arial,sans-serif;background:#071827;color:var(--text);overflow-x:hidden}
.shell{min-height:100vh;display:grid;grid-template-columns:minmax(360px,46%) 1fr;position:relative;background:radial-gradient(circle at 75% 10%,#0c5e5b55 0 18%,transparent 42%),linear-gradient(135deg,#06131f 0%,#092536 50%,#0d4c4c 100%)}
.shell:before,.shell:after{content:"";position:absolute;border-radius:50%;filter:blur(1px);pointer-events:none}.shell:before{width:320px;height:320px;border:1px solid #ffffff12;left:-130px;bottom:-100px}.shell:after{width:430px;height:430px;border:1px solid #d6ad5520;right:-170px;top:-190px}
.panel{background:#f8fbfc;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:42px 7vw;position:relative;z-index:2;box-shadow:35px 0 90px #0003}.card{width:min(100%,500px)}
.brand-mobile{display:none}.eyebrow{display:inline-flex;align-items:center;gap:8px;border:1px solid #cfe5e2;background:#edf8f6;color:#0c6b62;border-radius:999px;padding:8px 12px;font-size:12px;font-weight:800;margin-bottom:18px}.dot{width:8px;height:8px;border-radius:50%;background:#15a58f;box-shadow:0 0 0 5px #15a58f18}
h1{font-size:34px;line-height:1.3;margin:0 0 8px;color:#0b2232}.sub{color:var(--muted);font-size:15px;line-height:1.9;margin:0 0 28px}
.flash{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;background:#fff0ef;border:1px solid #f8c9c5;color:#9f241a;border-radius:13px;margin:0 0 14px;font-size:14px;font-weight:700}.flash i{font-style:normal;font-size:17px}
.field{margin:15px 0}.field label{display:block;font-weight:800;color:#233746;margin-bottom:8px;font-size:14px}.control{position:relative}.control input{width:100%;height:54px;border:1px solid var(--line);background:#fff;border-radius:14px;padding:0 48px 0 14px;font-size:16px;outline:none;transition:.2s;color:#112b3a}.control input:focus{border-color:#23a394;box-shadow:0 0 0 4px #23a39416}.icon{position:absolute;right:16px;top:50%;transform:translateY(-50%);opacity:.68;font-size:18px}.peek{position:absolute;left:9px;top:50%;transform:translateY(-50%);width:38px;height:38px;border:0;border-radius:10px;background:#f0f5f6;cursor:pointer;font-size:17px;color:#3b5361}.peek:hover{background:#e6eeee}
.meta{display:flex;justify-content:space-between;gap:12px;align-items:center;margin:8px 2px 18px;color:#73828d;font-size:12px}.secure{display:flex;align-items:center;gap:6px}.secure b{color:#177d71}.hint{color:#72818c}
.submit{width:100%;height:55px;border:0;border-radius:14px;background:linear-gradient(135deg,#0e7c70,#0b615c);color:#fff;font-size:16px;font-weight:900;cursor:pointer;box-shadow:0 12px 28px #0e7c7030;transition:.2s;display:flex;align-items:center;justify-content:center;gap:10px}.submit:hover{transform:translateY(-1px);box-shadow:0 16px 34px #0e7c7040}.submit:active{transform:translateY(0)}
.foot{margin-top:20px;padding-top:18px;border-top:1px solid #e3eaee;text-align:center;color:#84919a;font-size:12px;line-height:1.8}.foot strong{color:#4d626f}
.hero{position:relative;z-index:1;color:#fff;display:flex;align-items:center;justify-content:center;padding:8vw}.hero-inner{max-width:630px}.logo-wrap{display:flex;align-items:center;gap:19px;margin-bottom:40px}.logo-box{width:108px;height:108px;border-radius:26px;background:#0a1f31;border:1px solid #d6ad5555;box-shadow:0 20px 55px #0005;display:flex;align-items:center;justify-content:center;overflow:hidden}.logo-box img{width:100%;height:100%;object-fit:cover}.logo-fallback{font-size:42px;color:var(--gold)}.brand-name{font-size:27px;font-weight:900;line-height:1.5}.brand-name small{display:block;color:#bfd0d7;font-size:13px;font-weight:500;letter-spacing:.4px}.hero h2{font-size:46px;line-height:1.35;margin:0 0 16px;letter-spacing:-.5px}.hero h2 span{color:#e2bc69}.hero p{font-size:17px;line-height:2;color:#d2dde2;max-width:590px;margin:0 0 28px}.features{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.feature{border:1px solid #ffffff18;background:#ffffff0d;backdrop-filter:blur(10px);border-radius:15px;padding:14px 15px;color:#e7eff2;font-size:13px;display:flex;gap:9px;align-items:center}.feature b{font-size:17px;color:#e2bc69}.version{margin-top:24px;color:#8fa7b1;font-size:11px;letter-spacing:.3px}
@media(max-width:900px){.shell{display:block;background:linear-gradient(165deg,#071827 0,#0b3d43 32%,#f8fbfc 32%)}.hero{display:none}.panel{min-height:100vh;padding:26px 18px 34px;background:transparent;box-shadow:none;align-items:flex-start}.card{margin:2vh auto 0;background:#fff;border-radius:24px;padding:24px 19px;box-shadow:0 24px 70px #00151e45}.brand-mobile{display:flex;align-items:center;gap:13px;margin:-2px 0 22px}.brand-mobile .logo-box{width:68px;height:68px;border-radius:18px;flex:0 0 68px}.brand-mobile .brand-name{font-size:18px;color:#102d3b}.brand-mobile .brand-name small{color:#71828d;font-size:11px}.eyebrow{margin-bottom:13px}h1{font-size:27px}.sub{font-size:14px;margin-bottom:20px}.control input{height:56px;font-size:16px}.meta{align-items:flex-start;flex-direction:column}.foot{font-size:11px}}
@media(max-width:390px){.panel{padding:18px 12px 26px}.card{padding:21px 15px}.brand-mobile .brand-name{font-size:16px}h1{font-size:24px}}
</style>
</head>
<body>
<div class="shell">
  <section class="panel">
    <div class="card">
      <div class="brand-mobile">
        <div class="logo-box"><img src="{{url_for('company_logo')}}" alt="الشعار" onerror="this.style.display='none';this.parentNode.innerHTML='<div class=&quot;logo-fallback&quot;>N</div>'"></div>
        <div class="brand-name">نهضة سوريا<small>التخليص الجمركي والنقل بالترانزيت</small></div>
      </div>
      <div class="eyebrow"><span class="dot"></span> منصة الشركات المتعددة</div>
      <h1>مرحباً بعودتك</h1>
      <p class="sub">سجّل الدخول بحسابك، وسيحدد النظام شركتك وصلاحياتك تلقائياً.</p>
      {% with ms=get_flashed_messages(with_categories=true) %}{% for c,m in ms %}<div class="flash"><i>⚠</i><span>{{m}}</span></div>{% endfor %}{% endwith %}
      <form method="post" autocomplete="on" id="loginForm">
        <div class="field"><label>البريد الإلكتروني</label><div class="control"><span class="icon">✉</span><input type="email" name="email" value="{{request.form.get('email','')}}" autocomplete="email" inputmode="email" placeholder="name@example.com" required autofocus></div></div>
        <div class="field"><label>كلمة المرور</label><div class="control"><span class="icon">🔒</span><input id="pwd" type="password" name="password" autocomplete="current-password" placeholder="أدخل كلمة المرور" required><button class="peek" type="button" onclick="togglePwd()" aria-label="إظهار أو إخفاء كلمة المرور" id="peekBtn">◉</button></div></div>
        <div class="meta"><span class="secure"><span>🛡</span><span>اتصال <b>آمن ومشفّر</b></span></span><span class="hint">الدخول بحسب صلاحيات كل مستخدم</span></div>
        <button class="submit" type="submit" id="submitBtn"><span>دخول إلى النظام</span><span>←</span></button>
      </form>
      <div class="foot"><strong>نهضة سوريا</strong> · نظام إدارة التخليص الجمركي والمحاسبة<br>بيانات كل شركة معزولة عن الشركات الأخرى.</div>
    </div>
  </section>
  <section class="hero">
    <div class="hero-inner">
      <div class="logo-wrap"><div class="logo-box"><img src="{{url_for('company_logo')}}" alt="نهضة سوريا" onerror="this.style.display='none';this.parentNode.innerHTML='<div class=&quot;logo-fallback&quot;>N</div>'"></div><div class="brand-name">نهضة سوريا<small>Customs Clearance & Transit Management</small></div></div>
      <h2>إدارة أعمالك من مكان واحد، <span>بوضوح وأمان.</span></h2>
      <p>منصة موحدة للبيانات والرحلات والفواتير والديون والمحاسبة، مع صلاحيات منفصلة لكل مستخدم وعزل كامل بين الشركات.</p>
      <div class="features"><div class="feature"><b>✓</b> شركات متعددة ببيانات مستقلة</div><div class="feature"><b>✓</b> صلاحيات دقيقة للمستخدمين</div><div class="feature"><b>✓</b> فواتير وديون ومحاسبة</div><div class="feature"><b>✓</b> يعمل على الجوال والكمبيوتر</div></div>
      <div class="version">NAHDA BUSINESS PLATFORM · SECURE ACCESS</div>
    </div>
  </section>
</div>
<script>
function togglePwd(){const p=document.getElementById('pwd'),b=document.getElementById('peekBtn');if(p.type==='password'){p.type='text';b.textContent='⊘'}else{p.type='password';b.textContent='◉'}}
document.getElementById('loginForm').addEventListener('submit',function(){const b=document.getElementById('submitBtn');b.disabled=true;b.style.opacity='.82';b.innerHTML='<span>جارٍ تسجيل الدخول...</span>'});
</script>
</body></html>'''


def premium_login():
    if request.method == 'POST':
        email = emailbase._norm_email(request.form.get('email'))
        password = request.form.get('password') or ''
        session.clear()
        if not emailbase.EMAIL_RE.match(email):
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
        return redirect(url_for('home'))
    return render_template_string(LOGIN_HTML)


app.view_functions['login'] = premium_login


@app.route('/premium-login-health')
def premium_login_health():
    return {'ok': True, 'premium_login': True, 'responsive': True, 'email_auth': True}
