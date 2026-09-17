# -*- coding: utf-8 -*-
"""SPORT HUB V10 - persistent product images.

Adds product image upload/editing without using the web service filesystem.
The migration works with both SQLite and PostgreSQL deployments.
"""
import re
from flask import request, redirect, flash, abort, jsonify, render_template_string
from sqlalchemy import text

import web_sporthub_hotfix_v9 as v9
import web_sporthub_marketplace_v5 as v5
import web_sporthub_patch as core
import web_sporthub_storefront_v3 as store

app = v9.app
db = core.db
SportClub = core.SportClub
SportProduct = core.SportProduct

_ALLOWED_IMAGE_TYPES = {
    'image/jpeg': 'image/jpeg',
    'image/png': 'image/png',
    'image/webp': 'image/webp',
    'image/gif': 'image/gif',
}
_MAX_IMAGE_BYTES = 4 * 1024 * 1024


def _migrate_product_images():
    dialect = (db.engine.dialect.name or '').lower()
    with db.engine.begin() as conn:
        if dialect == 'sqlite':
            columns = {str(r[1]) for r in conn.execute(text('PRAGMA table_info(sporthub_product)')).all()}
            if 'image_data' not in columns:
                conn.execute(text('ALTER TABLE sporthub_product ADD COLUMN image_data BLOB'))
            if 'image_mime' not in columns:
                conn.execute(text("ALTER TABLE sporthub_product ADD COLUMN image_mime VARCHAR(100) DEFAULT ''"))
        else:
            conn.execute(text('ALTER TABLE sporthub_product ADD COLUMN IF NOT EXISTS image_data BYTEA'))
            conn.execute(text("ALTER TABLE sporthub_product ADD COLUMN IF NOT EXISTS image_mime VARCHAR(100) DEFAULT ''"))


def _valid_magic(raw, mime):
    if mime == 'image/jpeg':
        return raw.startswith(b'\xff\xd8\xff')
    if mime == 'image/png':
        return raw.startswith(b'\x89PNG\r\n\x1a\n')
    if mime == 'image/webp':
        return len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP'
    if mime == 'image/gif':
        return raw.startswith((b'GIF87a', b'GIF89a'))
    return False


def _read_product_image(field='image'):
    f = request.files.get(field)
    if not f or not f.filename:
        return None, None, None
    mime = (f.mimetype or '').lower().strip()
    if mime not in _ALLOWED_IMAGE_TYPES:
        return None, None, 'نوع الصورة غير مدعوم. استخدم JPG أو PNG أو WebP أو GIF.'
    raw = f.read(_MAX_IMAGE_BYTES + 1)
    if not raw:
        return None, None, 'ملف الصورة فارغ.'
    if len(raw) > _MAX_IMAGE_BYTES:
        return None, None, 'حجم صورة المنتج يجب ألا يتجاوز 4 ميغابايت.'
    if not _valid_magic(raw, mime):
        return None, None, 'ملف الصورة غير صالح أو امتداده لا يطابق محتواه.'
    return raw, _ALLOWED_IMAGE_TYPES[mime], None


def _set_product_image(pid, raw, mime):
    db.session.execute(
        text('UPDATE sporthub_product SET image_data=:raw, image_mime=:mime WHERE id=:pid'),
        {'raw': raw, 'mime': mime, 'pid': int(pid)},
    )


def _remove_product_image(pid):
    db.session.execute(
        text("UPDATE sporthub_product SET image_data=NULL, image_mime='' WHERE id=:pid"),
        {'pid': int(pid)},
    )


def _image_product_ids(ids=None):
    present = {int(r[0]) for r in db.session.execute(text('SELECT id FROM sporthub_product WHERE image_data IS NOT NULL')).all()}
    if ids is None:
        return present
    wanted = {int(x) for x in ids}
    return present.intersection(wanted)


with app.app_context():
    _migrate_product_images()


def _product_image_response(pid):
    row = db.session.execute(
        text("SELECT image_data, COALESCE(image_mime,'') FROM sporthub_product WHERE id=:pid"),
        {'pid': pid},
    ).first()
    if not row or not row[0]:
        abort(404)
    resp = app.response_class(row[0], mimetype=row[1] or 'image/jpeg')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


def _product_image_dispatch_v10():
    if request.method != 'GET':
        return None
    m = re.fullmatch(r'/sporthub/product/(\d+)/image/?', request.path)
    if not m:
        return None
    return _product_image_response(int(m.group(1)))

# V8/V9 perform startup test requests during import, so registering a normal
# Flask route here would be rejected. Insert directly into before_request chain.
app.before_request_funcs.setdefault(None, []).insert(0, _product_image_dispatch_v10)


def api_products_v10():
    q = SportProduct.query.filter_by(active=True).order_by(SportProduct.id.desc())
    club_id = request.args.get('club_id', type=int)
    if club_id:
        q = q.filter_by(club_id=club_id)
    rows = q.all()
    with_images = _image_product_ids([p.id for p in rows])
    return jsonify([
        {
            'id': p.id,
            'club_id': p.club_id,
            'club_name': p.club.name,
            'name': p.name,
            'category': p.category,
            'description': p.description or '',
            'price_syp': int(p.price_syp or 0),
            'stock_qty': int(p.stock_qty or 0),
            'image_url': f'/sporthub/product/{p.id}/image' if p.id in with_images else '',
        }
        for p in rows
    ])

core.app.view_functions['sporthub_api_products'] = api_products_v10


PRODUCTS_BODY = r'''
<section class="section">
  <div class="sectionhead"><div><h2>إضافة منتج</h2><div class="sub">أضف صورة المنتج مع السعر والمخزون. الصورة تظهر مباشرة للزبون.</div></div></div>
  <form class="card" method="post" enctype="multipart/form-data" action="/sporthub/admin/products/new">
    <div class="grid2">
      {% if is_super %}<label class="field">النادي<select name="club_id" required>{% for c in clubs %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></label>{% else %}<input type="hidden" name="club_id" value="{{fixed}}">{% endif %}
      <label class="field">اسم المنتج<input name="name" required></label>
      <label class="field">صورة المنتج<input type="file" name="image" accept="image/jpeg,image/png,image/webp,image/gif"><small style="display:block;margin-top:6px;color:#7b8981">JPG / PNG / WebP / GIF — حتى 4MB</small></label>
      <label class="field">التصنيف<select name="category"><option value="protein">بروتين</option><option value="creatine">كرياتين</option><option value="supplements">مكملات</option><option value="accessories">إكسسوارات</option><option value="apparel">ملابس</option><option value="other">أخرى</option></select></label>
      <label class="field">السعر بالليرة<input type="number" min="0" name="price_syp" required></label>
      <label class="field">المخزون<input type="number" min="0" name="stock_qty" value="0" required></label>
      <label class="field span2">الوصف<textarea name="description"></textarea></label>
    </div>
    <div class="actions"><button class="btn primary">+ إضافة المنتج</button></div>
  </form>
</section>
<section class="section">
  <div class="sectionhead"><div><h2>المنتجات الحالية</h2><div class="sub">يمكنك تغيير الصورة والسعر والمخزون أو إخفاء المنتج.</div></div></div>
  <div class="tablewrap"><table class="table"><thead><tr><th>الصورة</th><th>المنتج</th>{% if is_super %}<th>النادي</th>{% endif %}<th>السعر</th><th>المخزون</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody>
  {% for p in products %}<tr><form method="post" enctype="multipart/form-data" action="/sporthub/admin/products/{{p.id}}/save">
    <td style="min-width:120px">{% if p.id in with_images %}<img src="/sporthub/product/{{p.id}}/image?v={{p.id}}" style="width:72px;height:72px;object-fit:cover;border-radius:12px;border:1px solid #dfe8e3;display:block;margin-bottom:7px">{% else %}<div style="width:72px;height:72px;border-radius:12px;background:#eef3f0;display:grid;place-items:center;color:#7f8e86;font-size:10px;margin-bottom:7px">لا صورة</div>{% endif %}<input type="file" name="image" accept="image/jpeg,image/png,image/webp,image/gif" style="width:105px;font-size:10px">{% if p.id in with_images %}<button class="btn danger" style="padding:5px 7px;margin-top:5px;font-size:10px" name="action" value="remove_image">حذف الصورة</button>{% endif %}</td>
    <td><input name="name" value="{{p.name}}" required style="padding:8px;border:1px solid #d2ded7;border-radius:8px;min-width:180px"><input type="hidden" name="category" value="{{p.category}}"><input type="hidden" name="description" value="{{p.description or ''}}"></td>
    {% if is_super %}<td><select name="club_id" style="padding:8px;border:1px solid #d2ded7;border-radius:8px">{% for c in clubs %}<option value="{{c.id}}" {{'selected' if c.id==p.club_id else ''}}>{{c.name}}</option>{% endfor %}</select></td>{% else %}<input type="hidden" name="club_id" value="{{fixed}}">{% endif %}
    <td><input type="number" min="0" name="price_syp" value="{{p.price_syp}}" style="width:130px;padding:8px;border:1px solid #d2ded7;border-radius:8px"></td>
    <td><input type="number" min="0" name="stock_qty" value="{{p.stock_qty}}" style="width:85px;padding:8px;border:1px solid #d2ded7;border-radius:8px"></td>
    <td><span class="badge">{{'ظاهر' if p.active else 'مخفي'}}</span></td>
    <td><button class="btn primary" name="action" value="save">حفظ</button> <button class="btn secondary" name="action" value="toggle">{{'إخفاء' if p.active else 'إظهار'}}</button></td>
  </form></tr>{% else %}<tr><td colspan="7">لا توجد منتجات.</td></tr>{% endfor %}
  </tbody></table></div>
</section>
'''


def products_v10():
    g = v5._guard()
    if g:
        return g
    if v5._super_ok():
        clubs = SportClub.query.order_by(SportClub.name.asc()).all()
        products = SportProduct.query.order_by(SportProduct.id.desc()).all()
        fixed = None
    else:
        fixed = v5._club_id()
        clubs = [SportClub.query.get_or_404(fixed)]
        products = SportProduct.query.filter_by(club_id=fixed).order_by(SportProduct.id.desc()).all()
    with_images = _image_product_ids([p.id for p in products])
    return v5._layout(
        'المنتجات والأسعار', PRODUCTS_BODY, 'products',
        subtitle='إدارة صور المنتجات والأسعار والمخزون حسب صلاحية الحساب.',
        clubs=clubs, products=products, fixed=fixed,
        is_super=v5._super_ok(), with_images=with_images,
    )


def product_new_v10():
    g = v5._guard()
    if g:
        return g
    try:
        cid = int(request.form.get('club_id'))
        price = max(0, int(request.form.get('price_syp') or 0))
        stock = max(0, int(request.form.get('stock_qty') or 0))
    except Exception:
        flash('تحقق من القيم')
        return redirect('/sporthub/admin/products')
    if v5._club_ok() and cid != v5._club_id():
        abort(403)
    if not SportClub.query.get(cid):
        abort(404)
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('اسم المنتج مطلوب')
        return redirect('/sporthub/admin/products')
    raw, mime, error = _read_product_image('image')
    if error:
        flash(error)
        return redirect('/sporthub/admin/products')
    p = SportProduct(
        club_id=cid,
        name=name[:220],
        category=(request.form.get('category') or 'other')[:80],
        description=(request.form.get('description') or '').strip(),
        price_syp=price,
        stock_qty=stock,
        active=True,
    )
    db.session.add(p)
    db.session.flush()
    if raw:
        _set_product_image(p.id, raw, mime)
    db.session.commit()
    flash('تمت إضافة المنتج' + (' مع الصورة' if raw else ''))
    return redirect('/sporthub/admin/products')


def product_save_v10(pid):
    g = v5._guard()
    if g:
        return g
    p = SportProduct.query.get_or_404(pid)
    if v5._club_ok() and p.club_id != v5._club_id():
        abort(403)
    action = request.form.get('action') or 'save'
    if action == 'toggle':
        p.active = not bool(p.active)
        db.session.commit()
        flash('تم تغيير ظهور المنتج')
        return redirect('/sporthub/admin/products')
    if action == 'remove_image':
        _remove_product_image(p.id)
        db.session.commit()
        flash('تم حذف صورة المنتج')
        return redirect('/sporthub/admin/products')
    try:
        cid = int(request.form.get('club_id'))
        price = max(0, int(request.form.get('price_syp') or 0))
        stock = max(0, int(request.form.get('stock_qty') or 0))
    except Exception:
        flash('تحقق من القيم')
        return redirect('/sporthub/admin/products')
    if v5._club_ok():
        cid = v5._club_id()
    elif not SportClub.query.get(cid):
        abort(404)
    raw, mime, error = _read_product_image('image')
    if error:
        flash(error)
        return redirect('/sporthub/admin/products')
    p.club_id = cid
    p.name = (request.form.get('name') or p.name).strip()[:220]
    p.price_syp = price
    p.stock_qty = stock
    p.category = (request.form.get('category') or p.category)[:80]
    p.description = (request.form.get('description') or p.description or '').strip()
    if raw:
        _set_product_image(p.id, raw, mime)
    db.session.commit()
    flash('تم حفظ المنتج' + (' وتحديث صورته' if raw else ''))
    return redirect('/sporthub/admin/products')


v5.products_v5 = products_v10
v5.product_new_v5 = product_new_v10
v5.product_save_v5 = product_save_v10
if 'sporthub_admin_products_v2' in app.view_functions:
    app.view_functions['sporthub_admin_products_v2'] = products_v10
if 'sporthub_admin_products_new_v2' in app.view_functions:
    app.view_functions['sporthub_admin_products_new_v2'] = product_new_v10
if 'sporthub_admin_products_save_v2' in app.view_functions:
    app.view_functions['sporthub_admin_products_save_v2'] = product_save_v10


_img_css = '.productimg{width:100%;height:100%;object-fit:cover;display:block}.pvisual.hasimg{background:#fff}'
if _img_css not in store.STORE_HTML:
    store.STORE_HTML = store.STORE_HTML.replace('</style>', _img_css + '</style>', 1)

_old_visual = '<div class="pvisual"><span class="tag">${p.stock_qty>0?\'متوفر\':\'غير متوفر\'}</span><div class="pack"><div><b>${shortCat(p.category)}</b><small>${p.club_name}</small></div></div></div>'
_new_visual = '<div class="pvisual ${p.image_url?\'hasimg\':\'\'}"><span class="tag">${p.stock_qty>0?\'متوفر\':\'غير متوفر\'}</span>${p.image_url?`<img class="productimg" src="${p.image_url}" alt="${p.name}">`:`<div class="pack"><div><b>${shortCat(p.category)}</b><small>${p.club_name}</small></div></div>`}</div>'
store.STORE_HTML = store.STORE_HTML.replace(_old_visual, _new_visual)


def premium_storefront_v10():
    return render_template_string(store.STORE_HTML)

store.premium_storefront = premium_storefront_v10

print('SPORTHUB_V10_PRODUCT_IMAGES_READY', flush=True)
