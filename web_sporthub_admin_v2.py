# -*- coding: utf-8 -*-
import re
from flask import request, session, redirect, url_for, render_template_string, abort, flash

import web_sporthub_admin_patch as old

app = old.app
db = old.db
SportClub = old.SportClub
SportProduct = old.SportProduct
SportOrder = old.SportOrder
SportPayment = old.SportPayment


def _is_admin():
    role = (session.get('role') or '').lower()
    return bool(session.get('uid') or session.get('user_id')) and role in ('admin','manager','owner')


def _guard():
    if not _is_admin():
        return redirect('/login?next=/sporthub/admin')


def _read_image(field, max_mb=4):
    f = request.files.get(field)
    if not f or not f.filename:
        return None, None
    raw = f.read(max_mb * 1024 * 1024 + 1)
    if len(raw) > max_mb * 1024 * 1024:
        return None, None
    mime = (f.mimetype or 'image/png')[:100]
    if not mime.startswith('image/'):
        return None, None
    return raw, mime


def _slug(name):
    base = re.sub(r'[^a-z0-9]+','-',(name or '').lower()).strip('-')[:50] or 'club'
    out = base; n = 2
    while SportClub.query.filter_by(slug=out).first():
        out = f'{base}-{n}'; n += 1
    return out


def _layout(title, body, active='dashboard', **ctx):
    html = r'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} | SPORT HUB</title>
<style>
:root{--bg:#f4f7f5;--card:#fff;--ink:#122019;--mut:#6c7c74;--green:#1faa62;--green2:#e7f7ee;--line:#dfe8e3;--dark:#102019;--red:#c74343}
*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial,sans-serif;background:var(--bg);color:var(--ink)}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}
.shell{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.side{background:var(--dark);color:#fff;padding:24px 16px;position:sticky;top:0;height:100vh}.logo{font-weight:1000;font-size:23px;margin-bottom:8px}.logo b{color:#6dff9c}.side p{color:#9db3a8;font-size:12px;line-height:1.7;margin:0 0 24px}.nav{display:grid;gap:8px}.nav a{padding:13px 14px;border-radius:12px;color:#d8e5de;font-weight:800}.nav a.active,.nav a:hover{background:#20372c;color:#fff}.store{margin-top:20px;border-top:1px solid #294238;padding-top:16px}.store a{display:block;background:#fff;color:#102019;padding:12px;border-radius:12px;text-align:center;font-weight:900}
.main{padding:28px;max-width:1250px;width:100%;margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:24px}.top h1{margin:0;font-size:32px}.sub{color:var(--mut);margin-top:6px}.badge{display:inline-flex;padding:6px 10px;border-radius:999px;background:var(--green2);color:#187447;font-size:12px;font-weight:900}.badge.off{background:#fdeaea;color:#a63737}.flash{background:#e8f7ee;border:1px solid #bde7cd;color:#175f3c;padding:12px 14px;border-radius:12px;margin:12px 0}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 8px 28px #1434220a}.stat span{color:var(--mut);font-size:12px}.stat b{display:block;font-size:30px;margin-top:8px}.quick{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}.quick a{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px;display:block}.quick h3{margin:0 0 8px}.quick p{margin:0;color:var(--mut);font-size:13px;line-height:1.7}.quick strong{display:inline-block;margin-top:16px;color:var(--green)}
.section{margin-top:22px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:15px;margin-bottom:12px}.section-head h2{margin:0}.btn{border:0;border-radius:11px;padding:11px 15px;font-weight:900;cursor:pointer}.primary{background:var(--green);color:#fff}.secondary{background:#eef3f0;color:#183127}.danger{background:#feeaea;color:#a33434}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.field{display:block;font-size:12px;color:var(--mut);font-weight:700}.field input,.field select,.field textarea{width:100%;margin-top:6px;padding:12px;border:1px solid #cfdcd5;border-radius:11px;background:#fff;color:#142019}.field textarea{min-height:90px;resize:vertical}.span2{grid-column:1/-1}.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}
.club-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.club-card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.club-top{display:flex;align-items:center;gap:14px;margin-bottom:14px}.qr{width:82px;height:82px;object-fit:contain;background:#fff;border:1px solid var(--line);border-radius:12px;padding:5px}.qr-empty{width:82px;height:82px;border:1px dashed #b8c8bf;border-radius:12px;display:grid;place-items:center;color:var(--mut);font-size:11px;text-align:center}.club-top h3{margin:0 0 5px}.hint{background:#f8fbf9;border:1px solid var(--line);border-radius:12px;padding:12px;color:var(--mut);font-size:12px;line-height:1.8}
.tablewrap{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:18px}.table{width:100%;border-collapse:collapse;min-width:850px}.table th,.table td{padding:13px;text-align:right;border-bottom:1px solid #edf2ef;vertical-align:middle}.table th{font-size:12px;color:var(--mut);background:#f8fbf9}.table tr:last-child td{border-bottom:0}.money{font-weight:900;white-space:nowrap}.inline{padding:8px 9px;border:1px solid #d3dfd8;border-radius:9px;min-width:90px}.empty{padding:45px;text-align:center;color:var(--mut)}
@media(max-width:900px){.shell{grid-template-columns:1fr}.side{position:relative;height:auto}.nav{grid-template-columns:repeat(4,1fr)}.nav a{text-align:center;font-size:12px}.cards{grid-template-columns:1fr 1fr}.quick{grid-template-columns:1fr}.club-grid{grid-template-columns:1fr}.formgrid{grid-template-columns:1fr}.span2{grid-column:auto}}
@media(max-width:560px){.main{padding:16px}.cards{grid-template-columns:1fr 1fr}.nav{grid-template-columns:1fr 1fr}.top{display:block}.top h1{font-size:26px}}
</style></head><body><div class="shell"><aside class="side"><div class="logo"><b>SPORT</b> HUB</div><p>لوحة إدارة واضحة ومقسمة حسب المهمة.</p><nav class="nav"><a class="{{'active' if active=='dashboard' else ''}}" href="/admin">الرئيسية</a><a class="{{'active' if active=='clubs' else ''}}" href="/admin/clubs">الأندية وشام كاش</a><a class="{{'active' if active=='products' else ''}}" href="/admin/products">المنتجات</a><a class="{{'active' if active=='orders' else ''}}" href="/admin/orders">الطلبات</a></nav><div class="store"><a href="/">فتح المتجر</a></div></aside><main class="main"><div class="top"><div><h1>{{title}}</h1><div class="sub">{{subtitle}}</div></div><span class="badge">حساب المدير</span></div>{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}''' + body + r'''</main></div></body></html>'''
    return render_template_string(html, title=title, active=active, **ctx)


def dashboard():
    g = _guard()
    if g: return g
    clubs = SportClub.query.count(); products = SportProduct.query.count(); orders = SportOrder.query.count(); pending = SportPayment.query.filter_by(status='pending_verification').count()
    body = r'''<div class="cards"><div class="card stat"><span>الأندية</span><b>{{clubs}}</b></div><div class="card stat"><span>المنتجات</span><b>{{products}}</b></div><div class="card stat"><span>الطلبات</span><b>{{orders}}</b></div><div class="card stat"><span>دفعات تنتظر التحقق</span><b>{{pending}}</b></div></div><div class="quick"><a href="/admin/clubs"><h3>1. الأندية وشام كاش</h3><p>أضف نادي جديد، ثم ضع حساب شام كاش وارفع QR الخاص به.</p><strong>فتح إدارة الأندية ←</strong></a><a href="/admin/products"><h3>2. المنتجات</h3><p>أضف بروتين، كرياتين، ملابس أو أي منتج واختر النادي التابع له.</p><strong>فتح إدارة المنتجات ←</strong></a><a href="/admin/orders"><h3>3. الطلبات</h3><p>شاهد الطلبات والمدفوعات وحالة كل طلب.</p><strong>فتح الطلبات ←</strong></a></div><section class="section"><div class="hint"><b>طريقة العمل:</b> أولاً أضف النادي وحساب شام كاش وQR. بعدها انتقل إلى المنتجات وأضف منتجات النادي. عند شراء العميل منتجاً، سيظهر له حساب شام كاش وQR الخاص بالنادي تلقائياً.</div></section>'''
    return _layout('الرئيسية', body, 'dashboard', subtitle='من هنا تبدأ إدارة الموقع خطوة بخطوة.', clubs=clubs, products=products, orders=orders, pending=pending)

app.view_functions['sporthub_admin'] = dashboard


@app.get('/sporthub/admin/clubs')
def sporthub_admin_clubs_v2():
    g = _guard()
    if g: return g
    clubs = SportClub.query.order_by(SportClub.id.asc()).all()
    body = r'''<section class="section"><div class="section-head"><div><h2>إضافة نادي جديد</h2><div class="sub">أضف النادي ومعه شام كاش مباشرة، أو أضفه ثم عدّل بياناته لاحقاً.</div></div></div><form class="card" method="post" enctype="multipart/form-data" action="/sporthub/admin/clubs/new"><div class="formgrid"><label class="field">اسم النادي<input name="name" required placeholder="مثال: نادي القوة الرياضي"></label><label class="field">المدينة<input name="city" placeholder="دمشق"></label><label class="field">حساب شام كاش<input name="shamcash_account" placeholder="رقم أو معرف حساب شام كاش"></label><label class="field">QR شام كاش<input type="file" name="qr" accept="image/*"></label></div><div class="actions"><button class="btn primary">+ إضافة النادي</button></div></form></section><section class="section"><div class="section-head"><div><h2>الأندية الحالية</h2><div class="sub">لكل نادي حساب شام كاش وQR مستقل.</div></div></div><div class="club-grid">{% for c in clubs %}<form class="club-card" method="post" enctype="multipart/form-data" action="/sporthub/admin/clubs/{{c.id}}/save"><div class="club-top">{% if c.shamcash_qr %}<img class="qr" src="/sporthub/club/{{c.id}}/qr">{% else %}<div class="qr-empty">لا يوجد<br>QR</div>{% endif %}<div><h3>{{c.name}}</h3><span class="badge {{'' if c.active else 'off'}}">{{'فعال' if c.active else 'موقوف'}}</span></div></div><div class="formgrid"><label class="field">اسم النادي<input name="name" value="{{c.name}}" required></label><label class="field">المدينة<input name="city" value="{{c.city or ''}}"></label><label class="field">حساب شام كاش<input name="shamcash_account" value="{{c.shamcash_account or ''}}"></label><label class="field">تغيير QR<input type="file" name="qr" accept="image/*"></label></div><div class="actions"><button class="btn primary" name="action" value="save">حفظ التعديلات</button><button class="btn secondary" name="action" value="toggle">{{'إيقاف النادي' if c.active else 'تفعيل النادي'}}</button></div></form>{% else %}<div class="empty">لا يوجد أندية بعد.</div>{% endfor %}</div></section>'''
    return _layout('الأندية وشام كاش', body, 'clubs', subtitle='هذه أهم صفحة: كل نادي يأخذ حساب الدفع وQR الخاص به.', clubs=clubs)


@app.post('/sporthub/admin/clubs/new')
def sporthub_admin_clubs_new_v2():
    g = _guard()
    if g: return g
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('اسم النادي مطلوب'); return redirect('/sporthub/admin/clubs')
    c = SportClub(slug=_slug(name), name=name[:180], city=(request.form.get('city') or '').strip()[:120], shamcash_account=(request.form.get('shamcash_account') or '').strip()[:250], active=True)
    raw,mime = _read_image('qr')
    if raw: c.shamcash_qr=raw; c.shamcash_qr_mime=mime
    db.session.add(c); db.session.commit(); flash('تمت إضافة النادي بنجاح')
    return redirect('/sporthub/admin/clubs')


@app.post('/sporthub/admin/clubs/<int:cid>/save')
def sporthub_admin_clubs_save_v2(cid):
    g = _guard()
    if g: return g
    c = SportClub.query.get_or_404(cid)
    if request.form.get('action') == 'toggle':
        c.active = not bool(c.active); db.session.commit(); flash('تم تغيير حالة النادي'); return redirect('/sporthub/admin/clubs')
    c.name=(request.form.get('name') or c.name).strip()[:180]; c.city=(request.form.get('city') or '').strip()[:120]; c.shamcash_account=(request.form.get('shamcash_account') or '').strip()[:250]
    raw,mime=_read_image('qr')
    if raw: c.shamcash_qr=raw; c.shamcash_qr_mime=mime
    db.session.commit(); flash('تم حفظ النادي وحساب شام كاش')
    return redirect('/sporthub/admin/clubs')


@app.get('/sporthub/admin/products')
def sporthub_admin_products_v2():
    g = _guard()
    if g: return g
    clubs = SportClub.query.order_by(SportClub.name.asc()).all(); products=SportProduct.query.order_by(SportProduct.id.desc()).all()
    body = r'''<section class="section"><div class="section-head"><div><h2>إضافة منتج</h2><div class="sub">اختر النادي أولاً، لأن الدفع سيذهب إلى شام كاش الخاص بهذا النادي.</div></div></div><form class="card" method="post" action="/sporthub/admin/products/new"><div class="formgrid"><label class="field">النادي<select name="club_id" required>{% for c in clubs %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></label><label class="field">اسم المنتج<input name="name" required placeholder="Whey Protein 2KG"></label><label class="field">التصنيف<select name="category"><option value="protein">بروتين</option><option value="creatine">كرياتين</option><option value="supplements">مكملات</option><option value="accessories">إكسسوارات</option><option value="apparel">ملابس</option><option value="other">أخرى</option></select></label><label class="field">السعر بالليرة<input type="number" name="price_syp" min="0" required></label><label class="field">الكمية بالمخزون<input type="number" name="stock_qty" min="0" value="0" required></label><label class="field span2">الوصف<textarea name="description" placeholder="وصف مختصر"></textarea></label></div><div class="actions"><button class="btn primary">+ إضافة المنتج</button></div></form></section><section class="section"><div class="section-head"><div><h2>المنتجات الحالية</h2><div class="sub">عدّل السعر أو المخزون أو النادي ثم اضغط حفظ.</div></div></div><div class="tablewrap"><table class="table"><thead><tr><th>المنتج</th><th>النادي</th><th>السعر</th><th>المخزون</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody>{% for p in products %}<tr><form method="post" action="/sporthub/admin/products/{{p.id}}/save"><td><input class="inline" name="name" value="{{p.name}}" required style="min-width:190px"></td><td><select class="inline" name="club_id">{% for c in clubs %}<option value="{{c.id}}" {{'selected' if c.id==p.club_id else ''}}>{{c.name}}</option>{% endfor %}</select></td><td><input class="inline" type="number" min="0" name="price_syp" value="{{p.price_syp}}"></td><td><input class="inline" type="number" min="0" name="stock_qty" value="{{p.stock_qty}}" style="width:85px"></td><td><span class="badge {{'' if p.active else 'off'}}">{{'ظاهر' if p.active else 'مخفي'}}</span></td><td><button class="btn primary" name="action" value="save">حفظ</button> <button class="btn secondary" name="action" value="toggle">{{'إخفاء' if p.active else 'إظهار'}}</button><input type="hidden" name="category" value="{{p.category}}"><input type="hidden" name="description" value="{{p.description or ''}}"></td></form></tr>{% else %}<tr><td colspan="6" class="empty">لا توجد منتجات بعد.</td></tr>{% endfor %}</tbody></table></div></section>'''
    return _layout('المنتجات', body, 'products', subtitle='أضف المنتجات واربط كل منتج بالنادي الصحيح.', clubs=clubs, products=products)


@app.post('/sporthub/admin/products/new')
def sporthub_admin_products_new_v2():
    g = _guard()
    if g: return g
    try:
        club_id=int(request.form.get('club_id')); price=max(0,int(request.form.get('price_syp') or 0)); stock=max(0,int(request.form.get('stock_qty') or 0))
    except Exception:
        flash('تحقق من النادي والسعر والكمية'); return redirect('/sporthub/admin/products')
    name=(request.form.get('name') or '').strip()
    if not name or not SportClub.query.get(club_id): flash('بيانات المنتج غير مكتملة'); return redirect('/sporthub/admin/products')
    p=SportProduct(club_id=club_id,name=name[:220],category=(request.form.get('category') or 'other')[:80],description=(request.form.get('description') or '').strip(),price_syp=price,stock_qty=stock,active=True)
    db.session.add(p); db.session.commit(); flash('تمت إضافة المنتج بنجاح'); return redirect('/sporthub/admin/products')


@app.post('/sporthub/admin/products/<int:pid>/save')
def sporthub_admin_products_save_v2(pid):
    g = _guard()
    if g: return g
    p=SportProduct.query.get_or_404(pid)
    if request.form.get('action')=='toggle': p.active=not bool(p.active); db.session.commit(); flash('تم تغيير ظهور المنتج'); return redirect('/sporthub/admin/products')
    try:
        cid=int(request.form.get('club_id')); price=max(0,int(request.form.get('price_syp') or 0)); stock=max(0,int(request.form.get('stock_qty') or 0))
    except Exception:
        flash('تحقق من القيم'); return redirect('/sporthub/admin/products')
    if SportClub.query.get(cid): p.club_id=cid
    p.name=(request.form.get('name') or p.name).strip()[:220]; p.price_syp=price; p.stock_qty=stock; p.category=(request.form.get('category') or p.category)[:80]; p.description=(request.form.get('description') or p.description or '').strip()
    db.session.commit(); flash('تم حفظ المنتج'); return redirect('/sporthub/admin/products')


@app.get('/sporthub/admin/orders')
def sporthub_admin_orders_v2():
    g = _guard()
    if g: return g
    orders=SportOrder.query.order_by(SportOrder.id.desc()).limit(100).all()
    body=r'''<section class="section"><div class="section-head"><div><h2>آخر الطلبات</h2><div class="sub">عرض سريع وواضح للطلبات المسجلة.</div></div></div><div class="tablewrap"><table class="table"><thead><tr><th>رقم الطلب</th><th>العميل</th><th>الهاتف</th><th>الإجمالي</th><th>الحالة</th><th>التاريخ</th></tr></thead><tbody>{% for o in orders %}<tr><td><b>{{o.order_no}}</b></td><td>{{o.customer_name}}</td><td>{{o.phone}}</td><td class="money">{{'{:,}'.format(o.total_syp or 0)}} ل.س</td><td><span class="badge">{{o.status}}</span></td><td>{{o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else ''}}</td></tr>{% else %}<tr><td colspan="6" class="empty">لا يوجد طلبات بعد.</td></tr>{% endfor %}</tbody></table></div></section>'''
    return _layout('الطلبات', body, 'orders', subtitle='كل طلب مسجل يظهر هنا.', orders=orders)
