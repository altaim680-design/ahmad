# -*- coding: utf-8 -*-
"""Passkey / biometric login for Nahda web platform.

Uses WebAuthn so biometric verification stays on the user's device. The server
stores only the credential id/public key/counter, never biometric images/data.
"""
import base64
import json
from datetime import datetime

import web_trip_tenant_hotfix as base
import web_login_premium_patch as loginbase
import web_multitenant_patch as mt
from flask import request, session, redirect, url_for, render_template_string, jsonify, flash

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

app = base.app
db = mt.db
User = mt.User
Tenant = mt.Tenant
core = mt.core


class PasskeyCredential(db.Model):
    __tablename__ = 'user_passkey'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    credential_id = db.Column(db.String(600), nullable=False, unique=True, index=True)
    public_key = db.Column(db.LargeBinary, nullable=False)
    sign_count = db.Column(db.BigInteger, nullable=False, default=0)
    device_type = db.Column(db.String(60), default='')
    backed_up = db.Column(db.Boolean, nullable=False, default=False)
    transports = db.Column(db.Text, default='[]')
    label = db.Column(db.String(120), default='جهاز موثوق')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)


with app.app_context():
    db.create_all()


def _b64(data):
    return base64.urlsafe_b64encode(bytes(data)).rstrip(b'=').decode('ascii')


def _unb64(value):
    value = (value or '').strip()
    value += '=' * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value.encode('ascii'))


def _current_user():
    uid = session.get('uid') or session.get('user_id')
    if not uid:
        return None
    return User.query.execution_options(tenant_bypass=True).filter_by(id=int(uid), active=True).first()


def _origin():
    proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'https').split(',')[0].strip()
    host = (request.headers.get('X-Forwarded-Host') or request.host).split(',')[0].strip()
    return f'{proto}://{host}'


def _rp_id():
    host = (request.headers.get('X-Forwarded-Host') or request.host).split(',')[0].strip()
    return host.split(':')[0]


def _eligible_email_users(email):
    email = loginbase.emailbase._norm_email(email)
    if not loginbase.emailbase.EMAIL_RE.match(email):
        return []
    users = User.query.execution_options(tenant_bypass=True).filter(
        db.func.lower(User.email) == email,
        User.active.is_(True),
    ).order_by(User.id.asc()).all()
    result = []
    for u in users:
        t = Tenant.query.get(u.tenant_id)
        if t and t.active:
            result.append(u)
    return result


@app.post('/passkey/register/options')
def passkey_register_options():
    u = _current_user()
    if not u:
        return jsonify(ok=False, error='سجّل الدخول أولاً'), 401

    existing = PasskeyCredential.query.filter_by(user_id=u.id).all()
    opts = generate_registration_options(
        rp_id=_rp_id(),
        rp_name='نهضة سوريا',
        user_id=str(u.id).encode('utf-8'),
        user_name=u.email or u.login_name or u.username,
        user_display_name=u.login_name or u.email or u.username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=_unb64(x.credential_id)) for x in existing
        ],
        timeout=60000,
    )
    session['passkey_reg_challenge'] = _b64(opts.challenge)
    return app.response_class(options_to_json(opts), mimetype='application/json')


@app.post('/passkey/register/verify')
def passkey_register_verify():
    u = _current_user()
    if not u:
        return jsonify(ok=False, error='انتهت جلسة الدخول'), 401
    challenge = session.pop('passkey_reg_challenge', None)
    if not challenge:
        return jsonify(ok=False, error='انتهت محاولة التفعيل، أعد المحاولة'), 400

    credential = request.get_json(silent=True) or {}
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=_unb64(challenge),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=True,
        )
        cid = _b64(verification.credential_id)
        if PasskeyCredential.query.filter_by(credential_id=cid).first():
            return jsonify(ok=False, error='هذه البصمة مفعّلة مسبقاً'), 409
        row = PasskeyCredential(
            user_id=u.id,
            tenant_id=u.tenant_id,
            credential_id=cid,
            public_key=bytes(verification.credential_public_key),
            sign_count=int(verification.sign_count or 0),
            device_type=str(verification.credential_device_type or ''),
            backed_up=bool(verification.credential_backed_up),
            transports=json.dumps(((credential.get('response') or {}).get('transports') or []), ensure_ascii=False),
            label=(request.args.get('label') or 'بصمة / Passkey').strip()[:120],
        )
        db.session.add(row)
        db.session.commit()
        return jsonify(ok=True, message='تم تفعيل الدخول بالبصمة بنجاح')
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error='تعذر تفعيل البصمة على هذا الجهاز'), 400


@app.post('/passkey/auth/options')
def passkey_auth_options():
    body = request.get_json(silent=True) or {}
    email = loginbase.emailbase._norm_email(body.get('email'))
    users = _eligible_email_users(email)
    if not users:
        return jsonify(ok=False, error='لا يوجد حساب فعال بهذا البريد'), 404

    user_ids = [u.id for u in users]
    creds = PasskeyCredential.query.filter(PasskeyCredential.user_id.in_(user_ids)).order_by(PasskeyCredential.id.asc()).all()
    if not creds:
        return jsonify(ok=False, error='لم يتم تفعيل البصمة لهذا الحساب بعد'), 404

    opts = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[PublicKeyCredentialDescriptor(id=_unb64(x.credential_id)) for x in creds],
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60000,
    )
    session['passkey_auth_challenge'] = _b64(opts.challenge)
    session['passkey_auth_credential_ids'] = [x.credential_id for x in creds]
    return app.response_class(options_to_json(opts), mimetype='application/json')


@app.post('/passkey/auth/verify')
def passkey_auth_verify():
    challenge = session.get('passkey_auth_challenge')
    allowed = session.get('passkey_auth_credential_ids') or []
    credential = request.get_json(silent=True) or {}
    cid = (credential.get('id') or '').strip()
    if not challenge or not cid or cid not in allowed:
        return jsonify(ok=False, error='محاولة دخول غير صالحة أو منتهية'), 400

    row = PasskeyCredential.query.filter_by(credential_id=cid).first()
    if not row:
        return jsonify(ok=False, error='مفتاح الدخول غير معروف'), 404
    u = User.query.execution_options(tenant_bypass=True).filter_by(id=row.user_id, active=True).first()
    if not u:
        return jsonify(ok=False, error='الحساب موقوف أو غير موجود'), 403
    t = Tenant.query.get(u.tenant_id)
    if not t or not t.active:
        return jsonify(ok=False, error='الشركة موقوفة'), 403

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=_unb64(challenge),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=bytes(row.public_key),
            credential_current_sign_count=int(row.sign_count or 0),
            require_user_verification=True,
        )
        row.sign_count = int(verification.new_sign_count or 0)
        row.device_type = str(verification.credential_device_type or row.device_type or '')
        row.backed_up = bool(verification.credential_backed_up)
        row.last_used_at = datetime.utcnow()
        db.session.commit()
        session.pop('passkey_auth_challenge', None)
        session.pop('passkey_auth_credential_ids', None)
        resp = loginbase._activate_user(u)
        return jsonify(ok=True, redirect=getattr(resp, 'location', None) or url_for('home'))
    except Exception:
        db.session.rollback()
        return jsonify(ok=False, error='تعذر التحقق من البصمة، جرّب مرة ثانية'), 400


PASSKEY_SETUP_HTML = r'''
<div class="hero"><h1>🔐 الدخول بالبصمة / Face ID</h1><p>فعّل هذا الجهاز للدخول لاحقاً بدون كتابة كلمة المرور. التحقق البيومتري يتم داخل جهازك ولا تُرسل بصمتك أو صورة وجهك إلى النظام.</p></div>
<div class="card">
  <div class="section-title">تفعيل جهاز جديد</div>
  <p style="color:#64748b;line-height:1.9">يدعم Face ID وTouch ID وWindows Hello وبصمة الإصبع وأي Passkey يدعمها جهازك.</p>
  <button class="btn green" type="button" onclick="registerPasskey()" id="regBtn">🔐 تفعيل البصمة على هذا الجهاز</button>
  <div id="pkMsg" style="margin-top:14px;font-weight:700"></div>
</div>
<div class="card">
  <div class="section-title">الأجهزة المفعّلة</div>
  <div class="tablewrap"><table><thead><tr><th>الجهاز</th><th>تاريخ التفعيل</th><th>آخر استخدام</th><th></th></tr></thead><tbody>
  {% for x in rows %}<tr><td>{{x.label or 'Passkey'}}</td><td>{{x.created_at.strftime('%Y-%m-%d %H:%M') if x.created_at else '—'}}</td><td>{{x.last_used_at.strftime('%Y-%m-%d %H:%M') if x.last_used_at else '—'}}</td><td><form method="post" action="{{url_for('passkey_delete', pid=x.id)}}" onsubmit="return confirm('حذف بصمة هذا الجهاز؟')"><button class="btn" style="background:#b42318">حذف</button></form></td></tr>{% else %}<tr><td colspan="4">لا يوجد جهاز مفعّل بعد.</td></tr>{% endfor %}
  </tbody></table></div>
</div>
<script>
function b64ToBuf(v){v=v.replace(/-/g,'+').replace(/_/g,'/');while(v.length%4)v+='=';const s=atob(v),a=new Uint8Array(s.length);for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a.buffer}
function bufToB64(buf){const a=new Uint8Array(buf);let s='';for(const b of a)s+=String.fromCharCode(b);return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
function regJSON(c){return {id:c.id,rawId:bufToB64(c.rawId),type:c.type,authenticatorAttachment:c.authenticatorAttachment||null,response:{clientDataJSON:bufToB64(c.response.clientDataJSON),attestationObject:bufToB64(c.response.attestationObject),transports:c.response.getTransports?c.response.getTransports():[]},clientExtensionResults:c.getClientExtensionResults?c.getClientExtensionResults():{}}}
async function registerPasskey(){const msg=document.getElementById('pkMsg'),btn=document.getElementById('regBtn');if(!window.PublicKeyCredential){msg.textContent='هذا المتصفح لا يدعم تسجيل الدخول بالبصمة.';return}btn.disabled=true;msg.textContent='جارٍ طلب التحقق من الجهاز...';try{let r=await fetch('{{url_for("passkey_register_options")}}',{method:'POST',credentials:'same-origin'}),o=await r.json();if(!r.ok)throw new Error(o.error||'تعذر بدء التفعيل');o.challenge=b64ToBuf(o.challenge);o.user.id=b64ToBuf(o.user.id);o.excludeCredentials=(o.excludeCredentials||[]).map(x=>({...x,id:b64ToBuf(x.id)}));const c=await navigator.credentials.create({publicKey:o});r=await fetch('{{url_for("passkey_register_verify")}}',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(regJSON(c))});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'فشل التفعيل');msg.textContent='✅ '+j.message;setTimeout(()=>location.reload(),800)}catch(e){msg.textContent='⚠ '+(e.message||'تم إلغاء العملية')}finally{btn.disabled=false}}
</script>
'''


@app.route('/passkey/setup')
def passkey_setup():
    u = _current_user()
    if not u:
        return redirect(url_for('login'))
    rows = PasskeyCredential.query.filter_by(user_id=u.id).order_by(PasskeyCredential.id.desc()).all()
    return core.layout('الدخول بالبصمة', PASSKEY_SETUP_HTML, rows=rows)


@app.post('/passkey/delete/<int:pid>')
def passkey_delete(pid):
    u = _current_user()
    if not u:
        return redirect(url_for('login'))
    row = PasskeyCredential.query.filter_by(id=pid, user_id=u.id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash('تم حذف بصمة الجهاز', 'success')
    return redirect(url_for('passkey_setup'))


PASSKEY_CSS = r'''
.bio-sep{display:flex;align-items:center;gap:12px;color:#8a98a2;font-size:12px;margin:17px 0}.bio-sep:before,.bio-sep:after{content:"";height:1px;background:#dfe8ec;flex:1}.bio-btn{width:100%;height:55px;border:1px solid #b9d8d4;border-radius:14px;background:#eef9f7;color:#0c625a;font-size:15px;font-weight:900;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:9px;transition:.2s}.bio-btn:hover{background:#e2f5f1;transform:translateY(-1px)}.bio-btn:disabled{opacity:.65;cursor:wait}.bio-msg{min-height:20px;margin-top:9px;text-align:center;color:#5c6f7a;font-size:12px;font-weight:700;line-height:1.6}
'''
PASSKEY_FORM = r'''
<div class="bio-sep"><span>أو</span></div>
<button class="bio-btn" type="button" id="passkeyBtn" onclick="passkeyLogin()"><span>🔐</span><span>الدخول بالبصمة / Face ID</span></button>
<div class="bio-msg" id="passkeyMsg">أدخل بريدك ثم اضغط الدخول بالبصمة.</div>
'''
PASSKEY_JS = r'''
function pkB64ToBuf(v){v=v.replace(/-/g,'+').replace(/_/g,'/');while(v.length%4)v+='=';const s=atob(v),a=new Uint8Array(s.length);for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a.buffer}
function pkBufToB64(buf){const a=new Uint8Array(buf);let s='';for(const b of a)s+=String.fromCharCode(b);return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
function authJSON(c){return {id:c.id,rawId:pkBufToB64(c.rawId),type:c.type,authenticatorAttachment:c.authenticatorAttachment||null,response:{clientDataJSON:pkBufToB64(c.response.clientDataJSON),authenticatorData:pkBufToB64(c.response.authenticatorData),signature:pkBufToB64(c.response.signature),userHandle:c.response.userHandle?pkBufToB64(c.response.userHandle):null},clientExtensionResults:c.getClientExtensionResults?c.getClientExtensionResults():{}}}
async function passkeyLogin(){const msg=document.getElementById('passkeyMsg'),btn=document.getElementById('passkeyBtn'),email=(document.querySelector('input[name="email"]')||{}).value||'';if(!email){msg.textContent='⚠ اكتب البريد الإلكتروني أولاً.';return}if(!window.PublicKeyCredential){msg.textContent='⚠ هذا الجهاز أو المتصفح لا يدعم Passkey.';return}btn.disabled=true;msg.textContent='جارٍ التحقق من البصمة...';try{let r=await fetch('/passkey/auth/options',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({email})}),o=await r.json();if(!r.ok)throw new Error(o.error||'تعذر بدء التحقق');o.challenge=pkB64ToBuf(o.challenge);o.allowCredentials=(o.allowCredentials||[]).map(x=>({...x,id:pkB64ToBuf(x.id)}));const c=await navigator.credentials.get({publicKey:o});r=await fetch('/passkey/auth/verify',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(authJSON(c))});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'فشل التحقق');msg.textContent='✅ تم التحقق، جارٍ فتح النظام...';location.href=j.redirect||'/'}catch(e){msg.textContent='⚠ '+(e.message||'تم إلغاء العملية')}finally{btn.disabled=false}}
'''

# Extend the existing premium login without changing password-login behavior.
if 'id="passkeyBtn"' not in loginbase.LOGIN_HTML:
    loginbase.LOGIN_HTML = loginbase.LOGIN_HTML.replace('</style>', PASSKEY_CSS + '</style>', 1)
    loginbase.LOGIN_HTML = loginbase.LOGIN_HTML.replace('</form>', PASSKEY_FORM + '</form>', 1)
    loginbase.LOGIN_HTML = loginbase.LOGIN_HTML.replace('</script>', PASSKEY_JS + '</script>', 1)

# Make the biometric setup page easy to discover after login.
_previous_layout = core.layout

def _passkey_layout(page_title, body, **ctx):
    html = _previous_layout(page_title, body, **ctx)
    if session.get('uid') and 'data-passkey-link="1"' not in html and '</body>' in html:
        href = url_for('passkey_setup')
        floating = f'<a data-passkey-link="1" href="{href}" title="الدخول بالبصمة" style="position:fixed;left:16px;bottom:16px;z-index:9998;background:#0f766e;color:#fff;text-decoration:none;padding:10px 13px;border-radius:999px;font:700 13px Tahoma,Arial;box-shadow:0 8px 24px #0003">🔐 بصمة الدخول</a>'
        html = html.replace('</body>', floating + '</body>', 1)
    return html

core.layout = _passkey_layout


@app.route('/passkey-health')
def passkey_health():
    return {'ok': True, 'passkey': True, 'webauthn': True, 'biometric_data_stored': False}
