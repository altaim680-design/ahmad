# -*- coding: utf-8 -*-
"""Expanded SPORT HUB administration.

Adds club creation with Sham Cash account/QR and full product management while
reusing the public storefront, database models, checkout, and existing login.
"""
import re
from datetime import datetime

from flask import request, session, redirect, url_for, render_template_string, abort, flash

import web_sporthub_patch as base

app = base.app
db = base.db
SportClub = base.SportClub
SportProduct = base.SportProduct
SportOrder = base.SportOrder
SportPayment = base.SportPayment


def _is_admin():
    role = (session.get("role") or "").lower()
    return bool(session.get("uid") or session.get("user_id")) and role in ("admin", "manager", "owner")


def _require_admin():
    if not _is_admin():
        abort(403)


def _read_qr(field="qr"):
    f = request.files.get(field)
    if not f or not f.filename:
        return None, None
    raw = f.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        return None, None
    mime = (f.mimetype or "image/png")[:100]
    if not mime.startswith("image/"):
        return None, None
    return raw, mime


def _unique_slug(name):
    raw = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:55]
    if not raw:
        raw = "club"
    slug = raw
    n = 2
    while SportClub.query.filter_by(slug=slug).first():
        slug = f"{raw}-{n}"
        n += 1
    return slug


ADMIN_HTML = r'''
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPORT HUB | لوحة الإدارة</title>
<style>
:root{--bg:#07110e;--panel:#10211b;--panel2:#142b23;--txt:#f5f8f6;--mut:#9eb2aa;--acc:#7dfc7b;--danger:#ff7979;--line:rgba(255,255,255,.10)}
*{box-sizing:border-box}body{font-family:Tahoma,Arial;background:radial-gradient(circle at 15% 0%,rgba(125,252,123,.08),transparent 24%),var(--bg);color:var(--txt);margin:0}
a{color:inherit;text-decoration:none}button,input,select,textarea{font:inherit}.top{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:12px;padding:16px 5vw;background:rgba(7,17,14,.94);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}.brand{font-size:20px;font-weight:1000;margin-left:auto}.brand b{color:var(--acc)}.top a{padding:9px 12px;border-radius:10px;background:#fff;color:#07110e;font-weight:800;font-size:12px}.wrap{max-width:1240px;margin:auto;padding:35px 20px 70px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:25px}.hero h1{font-size:38px;margin:4px 0}.eyebrow{color:var(--acc);font-size:12px;font-weight:900}.mut{color:var(--mut)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0 30px}.stat{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px}.stat small{color:var(--mut)}.stat b{display:block;font-size:27px;margin-top:7px}.section{margin:30px 0}.section-title{display:flex;justify-content:space-between;align-items:end;gap:15px;margin-bottom:14px}.section-title h2{margin:0;font-size:25px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:15px}.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px}.card h3{margin:0 0 12px}.formgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.field{display:block;color:var(--mut);font-size:12px}.field input,.field select,.field textarea{width:100%;margin-top:6px;padding:11px;border-radius:10px;border:1px solid #31483f;background:#08130f;color:#fff}.field textarea{min-height:88px;resize:vertical}.span2{grid-column:1/-1}.btn{border:0;border-radius:10px;padding:10px 14px;font-weight:900;cursor:pointer}.green{background:var(--acc);color:#06100c}.ghost{background:#20352e;color:#fff}.danger{background:#522526;color:#ffd7d7}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.club-head{display:flex;align-items:center;gap:12px}.qr-thumb{width:68px;height:68px;object-fit:contain;border-radius:10px;background:#fff;padding:5px}.qr-empty{width:68px;height:68px;border-radius:10px;border:1px dashed #496057;display:grid;place-items:center;color:var(--mut);font-size:10px;text-align:center}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:16px}.table{width:100%;border-collapse:collapse;min-width:850px;background:var(--panel)}.table th,.table td{padding:12px;text-align:right;border-bottom:1px solid var(--line);vertical-align:top}.table th{color:var(--mut);font-size:12px;background:#0b1914}.table tr:last-child td{border-bottom:0}.price{white-space:nowrap;font-weight:900}.badge{display:inline-block;padding:5px 8px;border-radius:999px;background:rgba(125,252,123,.1);color:var(--acc);font-size:11px}.badge.off{background:rgba(255,121,121,.1);color:#ff9b9b}.flash{padding:12px 14px;border-radius:12px;background:rgba(125,252,123,.1);border:1px solid rgba(125,252,123,.25);margin:12px 0}.note{padding:12px;border-radius:12px;background:rgba(255,255,255,.035);color:var(--mut);font-size:12px;line-height:1.8}
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}.grid2{grid-template-columns:1fr}.formgrid{grid-template-columns:1fr}.span2{grid-column:auto}.hero{display:block}}
@media(max-width:520px){.stats{grid-template-columns:1fr}.wrap{padding-left:14px;padding-right:14px}.hero h1{font-size:30px}}
</style></head><body>
<header class="top"><div class="brand"><b>SPORT</b> HUB ADMIN</div><a href="/">فتح المتجر</a></header>
<main class="wrap">
<div class="hero"><div><span class="eyebrow">لوحة المدير</span><h1>إدارة الأندية والمنتجات</h1><div class="mut">كل نادي يملك حساب شام كاش وQR مستقل، وكل منتج مرتبط بنادي محدد.</div></div></div>
{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="stats"><div class="stat"><small>الأندية</small><b>{{clubs|length}}</b></div><div class="stat"><small>المنتجات</small><b>{{products|length}}</b></div><div class="stat"><small>الطلبات</small><b>{{order_count}}</b></div><div class="stat"><small>دفعات بانتظار التحقق</small><b>{{pending_payments}}</b></div></div>

<section class="section"><div class="section-title"><div><span class="eyebrow">إضافة</span><h2>نادي جديد</h2></div></div>
<form class="card" method="post" enctype="multipart/form-data" action="{{url_for('sporthub_admin_club_new')}}"><div class="formgrid">
<label class="field">اسم النادي<input name="name" required placeholder="مثال: نادي القوة الرياضي"></label>
<label class="field">المدينة<input name="city" placeholder="دمشق"></label>
<label class="field">حساب شام كاش<input name="shamcash_account" placeholder="رقم/معرّف حساب شام كاش"></label>
<label class="field">QR شام كاش<input type="file" name="qr" accept="image/*"></label>
</div><div class="actions"><button class="btn green">إضافة النادي</button></div></form></section>

<section class="section"><div class="section-title"><div><span class="eyebrow">الدفع</span><h2>الأندية وحسابات شام كاش</h2></div></div><div class="grid2">
{% for c in clubs %}<form class="card" method="post" enctype="multipart/form-data" action="{{url_for('sporthub_admin_club', cid=c.id)}}">
<div class="club-head">{% if c.shamcash_qr %}<img class="qr-thumb" src="{{url_for('sporthub_club_qr',cid=c.id)}}" alt="QR">{% else %}<div class="qr-empty">لا يوجد<br>QR</div>{% endif %}<div><h3>{{c.name}}</h3><span class="badge {{'' if c.active else 'off'}}">{{'فعال' if c.active else 'موقوف'}}</span></div></div>
<div class="formgrid" style="margin-top:14px"><label class="field">اسم النادي<input name="name" value="{{c.name}}" required></label><label class="field">المدينة<input name="city" value="{{c.city or ''}}"></label><label class="field">حساب شام كاش<input name="shamcash_account" value="{{c.shamcash_account or ''}}" placeholder="حساب شام كاش"></label><label class="field">تغيير QR<input type="file" name="qr" accept="image/*"></label></div>
<div class="actions"><button class="btn green">حفظ النادي وشام كاش</button><button class="btn ghost" formaction="{{url_for('sporthub_admin_club_toggle',cid=c.id)}}" formmethod="post">{{'إيقاف النادي' if c.active else 'تفعيل النادي'}}</button></div></form>{% endfor %}
</div></section>

<section class="section"><div class="section-title"><div><span class="eyebrow">المتجر</span><h2>إضافة منتج</h2></div></div>
<form class="card" method="post" action="{{url_for('sporthub_admin_product_new')}}"><div class="formgrid">
<label class="field">النادي<select name="club_id" required>{% for c in clubs %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></label>
<label class="field">اسم المنتج<input name="name" required placeholder="Whey Protein 2KG"></label>
<label class="field">التصنيف<select name="category"><option value="protein">بروتين</option><option value="creatine">كرياتين</option><option value="supplements">مكملات</option><option value="accessories">إكسسوارات</option><option value="apparel">ملابس</option><option value="other">أخرى</option></select></label>
<label class="field">السعر بالليرة السورية<input type="number" min="0" name="price_syp" required></label>
<label class="field">الكمية بالمخزون<input type="number" min="0" name="stock_qty" value="0" required></label>
<label class="field span2">الوصف<textarea name="description" placeholder="وصف مختصر للمنتج"></textarea></label>
</div><div class="actions"><button class="btn green">إضافة المنتج</button></div></form></section>

<section class="section"><div class="section-title"><div><span class="eyebrow">المخزون</span><h2>المنتجات الحالية</h2></div><span class="mut">يمكن تعديل السعر والكمية والنادي من نفس الجدول.</span></div>
<div class="tablewrap"><table class="table"><thead><tr><th>ID</th><th>المنتج</th><th>النادي</th><th>التصنيف</th><th>السعر</th><th>المخزون</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>
{% for p in products %}<tr><form method="post" action="{{url_for('sporthub_admin_product_update',pid=p.id)}}"><td>{{p.id}}</td><td><input name="name" value="{{p.name}}" required style="min-width:180px;padding:8px;border-radius:8px;border:1px solid #31483f;background:#08130f;color:#fff"><textarea name="description" style="display:block;margin-top:6px;min-width:180px;padding:8px;border-radius:8px;border:1px solid #31483f;background:#08130f;color:#fff">{{p.description or ''}}</textarea></td><td><select name="club_id" style="padding:8px;border-radius:8px;background:#08130f;color:#fff;border:1px solid #31483f">{% for c in clubs %}<option value="{{c.id}}" {{'selected' if c.id==p.club_id else ''}}>{{c.name}}</option>{% endfor %}</select></td><td><input name="category" value="{{p.category}}" style="width:110px;padding:8px;border-radius:8px;border:1px solid #31483f;background:#08130f;color:#fff"></td><td><input type="number" min="0" name="price_syp" value="{{p.price_syp}}" style="width:130px;padding:8px;border-radius:8px;border:1px solid #31483f;background:#08130f;color:#fff"></td><td><input type="number" min="0" name="stock_qty" value="{{p.stock_qty}}" style="width:80px;padding:8px;border-radius:8px;border:1px solid #31483f;background:#08130f;color:#fff"></td><td><span class="badge {{'' if p.active else 'off'}}">{{'فعال' if p.active else 'مخفي'}}</span></td><td><div class="actions" style="margin:0"><button class="btn green">حفظ</button><button class="btn {{'danger' if p.active else 'ghost'}}" formaction="{{url_for('sporthub_admin_product_toggle',pid=p.id)}}" formmethod="post">{{'إخفاء' if p.active else 'إظهار'}}</button></div></td></form></tr>{% else %}<tr><td colspan="8">لا توجد منتجات.</td></tr>{% endfor %}
</tbody></table></div></section>

<section class="section"><div class="section-title"><div><span class="eyebrow">المبيعات</span><h2>آخر الطلبات</h2></div></div><div class="tablewrap"><table class="table"><thead><tr><th>الطلب</th><th>العميل</th><th>الهاتف</th><th>الإجمالي</th><th>الحالة</th><th>التاريخ</th></tr></thead><tbody>{% for o in orders %}<tr><td><b>{{o.order_no}}</b></td><td>{{o.customer_name}}</td><td>{{o.phone}}</td><td class="price">{{'{:,}'.format(o.total_syp or 0)}} ل.س</td><td>{{o.status}}</td><td>{{o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else ''}}</td></tr>{% else %}<tr><td colspan="6">لا يوجد طلبات بعد.</td></tr>{% endfor %}</tbody></table></div></section>
<div class="note">ملاحظة: إخفاء المنتج أو إيقاف النادي لا يحذف الطلبات القديمة، بل يمنع ظهوره للزبائن مع بقاء السجلات المحاسبية محفوظة.</div>
</main></body></html>
'''


def sporthub_admin_dashboard():
    if not _is_admin():
        return redirect("/login?next=/sporthub/admin")
    clubs = SportClub.query.order_by(SportClub.id.asc()).all()
    products = SportProduct.query.order_by(SportProduct.id.desc()).all()
    orders = SportOrder.query.order_by(SportOrder.id.desc()).limit(40).all()
    return render_template_string(
        ADMIN_HTML,
        clubs=clubs,
        products=products,
        orders=orders,
        order_count=SportOrder.query.count(),
        pending_payments=SportPayment.query.filter_by(status="pending_verification").count(),
    )

# Replace the original minimal admin dashboard, preserving the public URL.
app.view_functions["sporthub_admin"] = sporthub_admin_dashboard


@app.post("/sporthub/admin/clubs/new")
def sporthub_admin_club_new():
    _require_admin()
    name = (request.form.get("name") or "").strip()[:180]
    if not name:
        flash("اسم النادي مطلوب")
        return redirect(url_for("sporthub_admin"))
    c = SportClub(
        slug=_unique_slug(name),
        name=name,
        city=(request.form.get("city") or "").strip()[:120],
        shamcash_account=(request.form.get("shamcash_account") or "").strip()[:250],
        active=True,
    )
    qr, mime = _read_qr()
    if qr:
        c.shamcash_qr = qr
        c.shamcash_qr_mime = mime
    db.session.add(c)
    db.session.commit()
    flash("تمت إضافة النادي بنجاح")
    return redirect(url_for("sporthub_admin"))


@app.post("/sporthub/admin/club/<int:cid>/toggle")
def sporthub_admin_club_toggle(cid):
    _require_admin()
    c = SportClub.query.get_or_404(cid)
    c.active = not bool(c.active)
    db.session.commit()
    flash("تم تحديث حالة النادي")
    return redirect(url_for("sporthub_admin"))


@app.post("/sporthub/admin/products/new")
def sporthub_admin_product_new():
    _require_admin()
    club_id = request.form.get("club_id", type=int)
    club = SportClub.query.get(club_id) if club_id else None
    name = (request.form.get("name") or "").strip()[:220]
    if not club or not name:
        flash("اختر النادي واكتب اسم المنتج")
        return redirect(url_for("sporthub_admin"))
    try:
        price = max(0, int(request.form.get("price_syp") or 0))
        stock = max(0, int(request.form.get("stock_qty") or 0))
    except Exception:
        flash("السعر أو المخزون غير صحيح")
        return redirect(url_for("sporthub_admin"))
    p = SportProduct(
        club_id=club.id,
        name=name,
        category=(request.form.get("category") or "other").strip()[:80],
        description=(request.form.get("description") or "").strip(),
        price_syp=price,
        stock_qty=stock,
        active=True,
    )
    db.session.add(p)
    db.session.commit()
    flash("تمت إضافة المنتج إلى متجر النادي")
    return redirect(url_for("sporthub_admin"))


@app.post("/sporthub/admin/product/<int:pid>/update")
def sporthub_admin_product_update(pid):
    _require_admin()
    p = SportProduct.query.get_or_404(pid)
    club_id = request.form.get("club_id", type=int)
    club = SportClub.query.get(club_id) if club_id else None
    name = (request.form.get("name") or "").strip()[:220]
    if not club or not name:
        flash("بيانات المنتج غير مكتملة")
        return redirect(url_for("sporthub_admin"))
    try:
        price = max(0, int(request.form.get("price_syp") or 0))
        stock = max(0, int(request.form.get("stock_qty") or 0))
    except Exception:
        flash("السعر أو المخزون غير صحيح")
        return redirect(url_for("sporthub_admin"))
    p.club_id = club.id
    p.name = name
    p.category = (request.form.get("category") or "other").strip()[:80]
    p.description = (request.form.get("description") or "").strip()
    p.price_syp = price
    p.stock_qty = stock
    db.session.commit()
    flash("تم حفظ تعديلات المنتج")
    return redirect(url_for("sporthub_admin"))


@app.post("/sporthub/admin/product/<int:pid>/toggle")
def sporthub_admin_product_toggle(pid):
    _require_admin()
    p = SportProduct.query.get_or_404(pid)
    p.active = not bool(p.active)
    db.session.commit()
    flash("تم تحديث ظهور المنتج في المتجر")
    return redirect(url_for("sporthub_admin"))
