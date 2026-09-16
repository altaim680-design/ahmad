# -*- coding: utf-8 -*-
from datetime import datetime
import base64

from flask import request, session, redirect, url_for, render_template_string, jsonify, abort
import web_invoice_barcode_patch as base
import web_multitenant_patch as mt

app = base.app
db = mt.db

class SportClub(db.Model):
    __tablename__ = "sporthub_club"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(120), default="")
    shamcash_account = db.Column(db.String(250), default="")
    shamcash_qr = db.Column(db.LargeBinary, nullable=True)
    shamcash_qr_mime = db.Column(db.String(100), default="image/png")
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SportProduct(db.Model):
    __tablename__ = "sporthub_product"
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("sporthub_club.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(80), default="supplements")
    description = db.Column(db.Text, default="")
    price_syp = db.Column(db.BigInteger, default=0, nullable=False)
    stock_qty = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    club = db.relationship("SportClub", backref=db.backref("products", lazy=True))

class SportOrder(db.Model):
    __tablename__ = "sporthub_order"
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(60), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(300), default="")
    total_syp = db.Column(db.BigInteger, default=0, nullable=False)
    status = db.Column(db.String(40), default="pending_payment", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SportOrderItem(db.Model):
    __tablename__ = "sporthub_order_item"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sporthub_order.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey("sporthub_club.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("sporthub_product.id"), nullable=False, index=True)
    product_name = db.Column(db.String(220), nullable=False)
    qty = db.Column(db.Integer, default=1, nullable=False)
    unit_price_syp = db.Column(db.BigInteger, default=0, nullable=False)
    line_total_syp = db.Column(db.BigInteger, default=0, nullable=False)

class SportPayment(db.Model):
    __tablename__ = "sporthub_payment"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sporthub_order.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey("sporthub_club.id"), nullable=False, index=True)
    amount_syp = db.Column(db.BigInteger, default=0, nullable=False)
    shamcash_transaction = db.Column(db.String(180), default="")
    receipt_image = db.Column(db.LargeBinary, nullable=True)
    receipt_mime = db.Column(db.String(100), default="")
    status = db.Column(db.String(40), default="pending_verification", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def _seed():
    with app.app_context():
        db.create_all()
        if SportClub.query.count() == 0:
            clubs = [
                SportClub(slug="power-gym", name="POWER GYM", city="دمشق"),
                SportClub(slug="titan-club", name="TITAN CLUB", city="حلب"),
                SportClub(slug="arena-fitness", name="ARENA FITNESS", city="إدلب"),
            ]
            db.session.add_all(clubs)
            db.session.commit()
        if SportProduct.query.count() == 0:
            clubs = {c.slug: c for c in SportClub.query.all()}
            db.session.add_all([
                SportProduct(club_id=clubs["power-gym"].id, name="Whey Protein 2KG", category="protein", description="بروتين مصل الحليب", price_syp=450000, stock_qty=15),
                SportProduct(club_id=clubs["power-gym"].id, name="Creatine 300G", category="creatine", description="كرياتين مونوهيدرات", price_syp=185000, stock_qty=24),
                SportProduct(club_id=clubs["titan-club"].id, name="Shaker Pro", category="accessories", description="شيكر رياضي محكم", price_syp=65000, stock_qty=30),
                SportProduct(club_id=clubs["titan-club"].id, name="Gym Gloves", category="accessories", description="قفازات تمارين", price_syp=90000, stock_qty=18),
                SportProduct(club_id=clubs["arena-fitness"].id, name="Oversized T-Shirt", category="apparel", description="تيشيرت رياضي", price_syp=160000, stock_qty=20),
                SportProduct(club_id=clubs["arena-fitness"].id, name="Whey Isolate 1KG", category="protein", description="بروتين آيزوليت", price_syp=390000, stock_qty=12),
            ])
            db.session.commit()

_seed()

HOME_HTML = r'''
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPORT HUB | متجر الأندية الرياضية</title>
<style>
:root{--bg:#07110e;--panel:#10211b;--panel2:#142b23;--txt:#f5f8f6;--mut:#9eb2aa;--acc:#7dfc7b;--line:rgba(255,255,255,.09)}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0%,rgba(125,252,123,.09),transparent 25%),var(--bg);color:var(--txt);font-family:Tahoma,Arial,sans-serif}
a{color:inherit;text-decoration:none}button,input,select{font:inherit}.top{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:22px;padding:16px 6vw;background:rgba(7,17,14,.93);border-bottom:1px solid var(--line)}
.brand{font-weight:1000;font-size:20px;margin-left:auto}.brand b{color:var(--acc)}.top a{font-size:13px;color:#dce6e1}.cart{border:0;border-radius:12px;padding:10px 14px;font-weight:900}
.hero{padding:80px 8vw 55px;display:grid;grid-template-columns:1.2fr .8fr;gap:35px;align-items:center}.hero h1{font-size:clamp(42px,6vw,78px);line-height:1.05;margin:10px 0 18px}.hero p{color:var(--mut);line-height:1.9;font-size:17px}.eyebrow{color:var(--acc);font-size:12px;font-weight:900}.cta{display:inline-block;margin-top:20px;background:var(--acc);color:#06100c;padding:14px 20px;border-radius:12px;font-weight:900}
.paybox{background:linear-gradient(145deg,#163127,#0b1914);border:1px solid var(--line);border-radius:28px;padding:25px}.qr{width:170px;aspect-ratio:1;margin:18px auto;background:repeating-linear-gradient(45deg,#fff 0 6px,#111 6px 12px);border:10px solid #fff;border-radius:10px;display:grid;place-items:center;color:#111;font-weight:900;text-align:center}.section{padding:60px 8vw}.head{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:22px}.head h2{font-size:36px;margin:6px 0}.muted{color:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.club{padding:22px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(145deg,var(--panel2),var(--panel))}
.club h3{margin:5px 0}.club small{color:var(--mut)}.products{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.product{overflow:hidden;border:1px solid var(--line);border-radius:18px;background:var(--panel)}.art{height:180px;display:grid;place-items:center;background:#14231e}.art span{width:95px;height:125px;background:linear-gradient(#fff,#aebbb5);color:#08110d;border-radius:12px;display:grid;place-items:center;font-weight:1000;transform:rotate(-4deg)}.body{padding:16px}.pill{color:var(--acc);font-size:10px}.body h3{font-size:16px}.body p{color:var(--mut);font-size:12px;min-height:34px}.bottom{display:flex;align-items:center;justify-content:space-between;gap:8px}.add{border:0;border-radius:10px;padding:8px 10px;font-weight:900;cursor:pointer}
.drawer{position:fixed;inset:0 0 0 auto;width:min(460px,100vw);background:#0b1814;z-index:20;padding:22px;transform:translateX(100%);transition:.25s;overflow:auto}.drawer.open{transform:none}.close{float:left;background:none;border:0;color:#fff;font-size:28px}.line{padding:12px 0;border-bottom:1px solid var(--line)}.line small{display:block;color:var(--mut);margin-top:4px}.total{display:flex;justify-content:space-between;font-size:19px;margin:20px 0}.field{display:block;margin:10px 0}.field span{display:block;color:var(--mut);font-size:12px;margin-bottom:5px}.field input{width:100%;padding:11px;border-radius:10px;border:1px solid var(--line);background:#08130f;color:#fff}.paygroup{border:1px solid var(--line);border-radius:16px;padding:14px;margin:12px 0}.paygroup img{width:150px;max-width:100%;background:white;padding:8px;border-radius:10px}.submit{width:100%;border:0;border-radius:12px;padding:13px;background:var(--acc);font-weight:900;cursor:pointer}.msg{padding:12px;border-radius:10px;background:rgba(125,252,123,.08);display:none;margin:10px 0}
@media(max-width:900px){.hero{grid-template-columns:1fr}.paybox{display:none}.grid{grid-template-columns:1fr 1fr}.products{grid-template-columns:1fr 1fr}.top a{display:none}}
@media(max-width:560px){.hero,.section{padding-left:18px;padding-right:18px}.grid,.products{grid-template-columns:1fr}.hero h1{font-size:43px}.head{display:block}}
</style></head><body>
<header class="top"><div class="brand"><b>SPORT</b> HUB</div><a href="#clubs">الأندية</a><a href="#products">المنتجات</a><a href="#pay">شام كاش</a><button class="cart" onclick="openCart()">السلة <span id="count">0</span></button></header>
<section class="hero"><div><span class="eyebrow">منصة رياضية سورية متعددة الأندية</span><h1>متجر ناديك، والدفع مباشرة عبر شام كاش.</h1><p>منتجات رياضية ومكملات وإكسسوارات. لكل نادي متجر وحساب شام كاش وQR مستقل.</p><a class="cta" href="#products">تصفح المنتجات</a></div><div class="paybox"><b>دفع شام كاش</b><div class="qr">QR النادي</div><p class="muted">عند الدفع يظهر QR الحساب المخصص للنادي والمبلغ المطلوب.</p></div></section>
<section id="clubs" class="section"><div class="head"><div><span class="eyebrow">الأندية</span><h2>اختر ناديك</h2></div><span class="muted">كل نادي يملك حساب دفع مستقل</span></div><div class="grid" id="clubsGrid"></div></section>
<section id="products" class="section"><div class="head"><div><span class="eyebrow">المتجر</span><h2>المنتجات</h2></div><select id="clubFilter" onchange="renderProducts()"><option value="">كل الأندية</option></select></div><div class="products" id="productsGrid"></div></section>
<section id="pay" class="section"><div class="head"><div><span class="eyebrow">الدفع</span><h2>شام كاش</h2></div></div><p class="muted">إذا كانت السلة من أكثر من نادي، يقسم النظام المبلغ ويعرض QR كل نادي بشكل مستقل.</p></section>
<div class="drawer" id="drawer"><button class="close" onclick="closeCart()">×</button><h2>السلة والدفع</h2><div id="cartLines"></div><div class="total"><span>الإجمالي</span><b id="total">0 ل.س</b></div>
<div id="checkout" style="display:none"><label class="field"><span>اسم العميل</span><input id="name"></label><label class="field"><span>رقم الهاتف</span><input id="phone"></label><label class="field"><span>العنوان</span><input id="address"></label><div id="payments"></div><div class="msg" id="msg"></div><button class="submit" onclick="placeOrder()">تسجيل الطلب</button></div>
<button id="goPay" class="submit" onclick="showCheckout()">متابعة للدفع</button></div>
<script>
let clubs=[],products=[],cart={};
const money=n=>new Intl.NumberFormat('ar-SY').format(n)+' ل.س';
async function boot(){clubs=await (await fetch('/sporthub/api/clubs')).json();products=await (await fetch('/sporthub/api/products')).json();renderClubs();renderProducts();renderCart()}
function renderClubs(){let g=document.getElementById('clubsGrid');g.innerHTML='';let f=document.getElementById('clubFilter');clubs.forEach(c=>{g.innerHTML+=`<article class="club"><span class="eyebrow">${c.city||''}</span><h3>${c.name}</h3><small>متجر مستقل • دفع شام كاش</small></article>`;f.innerHTML+=`<option value="${c.id}">${c.name}</option>`})}
function renderProducts(){let g=document.getElementById('productsGrid'),cf=document.getElementById('clubFilter').value;g.innerHTML='';products.filter(p=>!cf||String(p.club_id)===cf).forEach(p=>{g.innerHTML+=`<article class="product"><div class="art"><span>${p.category.toUpperCase().slice(0,7)}</span></div><div class="body"><span class="pill">${p.club_name}</span><h3>${p.name}</h3><p>${p.description||''}</p><div class="bottom"><b>${money(p.price_syp)}</b><button class="add" onclick="add(${p.id})">أضف</button></div></div></article>`})}
function add(id){cart[id]=(cart[id]||0)+1;renderCart();openCart()}
function renderCart(){let box=document.getElementById('cartLines'),tot=0,cnt=0;box.innerHTML='';Object.entries(cart).forEach(([id,q])=>{let p=products.find(x=>x.id==id);if(!p)return;tot+=p.price_syp*q;cnt+=q;box.innerHTML+=`<div class="line"><b>${p.name}</b><small>${p.club_name} • ${q} × ${money(p.price_syp)}</small></div>`});document.getElementById('count').textContent=cnt;document.getElementById('total').textContent=money(tot)}
function openCart(){document.getElementById('drawer').classList.add('open')}function closeCart(){document.getElementById('drawer').classList.remove('open')}
function showCheckout(){if(!Object.keys(cart).length)return;document.getElementById('checkout').style.display='block';document.getElementById('goPay').style.display='none';let groups={};Object.entries(cart).forEach(([id,q])=>{let p=products.find(x=>x.id==id);groups[p.club_id]=(groups[p.club_id]||0)+p.price_syp*q});let b=document.getElementById('payments');b.innerHTML='';Object.entries(groups).forEach(([cid,amt])=>{let c=clubs.find(x=>x.id==cid);b.innerHTML+=`<div class="paygroup"><b>${c.name}</b><p>${money(amt)}</p>${c.qr_url?`<img src="${c.qr_url}">`:`<div class="muted">لم يضف النادي QR بعد.</div>`}<div class="muted">حساب شام كاش: ${c.shamcash_account||'غير محدد'}</div><label class="field"><span>رقم عملية شام كاش</span><input data-tx="${cid}" placeholder="أدخل رقم العملية بعد الدفع"></label><label class="field"><span>صورة الإيصال (اختياري)</span><input type="file" accept="image/*" data-receipt="${cid}"></label></div>`})}
function file64(inp){return new Promise(res=>{if(!inp||!inp.files||!inp.files[0])return res(null);let r=new FileReader();r.onload=()=>res(r.result);r.readAsDataURL(inp.files[0])})}
async function placeOrder(){let name=document.getElementById('name').value.trim(),phone=document.getElementById('phone').value.trim();if(!name||!phone){alert('أدخل الاسم ورقم الهاتف');return}let items=Object.entries(cart).map(([id,q])=>({product_id:+id,qty:q}));let pay=[];for(let inp of document.querySelectorAll('[data-tx]')){let cid=+inp.dataset.tx,receipt=await file64(document.querySelector(`[data-receipt="${cid}"]`));pay.push({club_id:cid,transaction:inp.value.trim(),receipt})}let r=await fetch('/sporthub/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_name:name,phone,address:document.getElementById('address').value.trim(),items,payments:pay})});let j=await r.json();let m=document.getElementById('msg');m.style.display='block';if(!r.ok){m.textContent=j.error||'تعذر تسجيل الطلب';return}m.innerHTML=`تم تسجيل الطلب <b>${j.order_no}</b>. حالة الدفع: بانتظار التحقق.`;cart={};renderCart()}
boot();
</script></body></html>
'''

ADMIN_HTML = r'''
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SPORT HUB Admin</title>
<style>body{font-family:Tahoma,Arial;background:#07110e;color:#fff;margin:0;padding:30px}.wrap{max-width:1000px;margin:auto}.card{background:#10211b;border:1px solid #294238;border-radius:16px;padding:18px;margin:14px 0}label{display:block;margin:10px 0;color:#a9bbb4}input{width:100%;padding:10px;background:#08130f;color:#fff;border:1px solid #31483f;border-radius:9px;box-sizing:border-box}button{padding:10px 14px;border:0;border-radius:9px;font-weight:bold}.green{background:#7dfc7b;color:#06100c}.mut{color:#9eb2aa}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:650px){.row{grid-template-columns:1fr}}</style></head><body><div class="wrap">
<h1>SPORT HUB — إدارة الأندية</h1><p class="mut">إضافة حساب شام كاش وQR مستقل لكل نادي.</p>
{% for c in clubs %}<form class="card" method="post" enctype="multipart/form-data" action="{{url_for('sporthub_admin_club', cid=c.id)}}">
<h3>{{c.name}}</h3><div class="row"><label>اسم النادي<input name="name" value="{{c.name}}"></label><label>المدينة<input name="city" value="{{c.city or ''}}"></label><label>حساب شام كاش<input name="shamcash_account" value="{{c.shamcash_account or ''}}"></label><label>QR شام كاش<input type="file" name="qr" accept="image/*"></label></div><button class="green">حفظ بيانات النادي</button></form>{% endfor %}
<h2>الطلبات الأخيرة</h2>{% for o in orders %}<div class="card"><b>{{o.order_no}}</b> — {{o.customer_name}} — {{o.total_syp}} ل.س — {{o.status}}</div>{% else %}<p class="mut">لا يوجد طلبات بعد.</p>{% endfor %}
</div></body></html>
'''

@app.get("/sporthub")
def sporthub_home():
    return render_template_string(HOME_HTML)

@app.get("/sporthub/health")
def sporthub_health():
    return jsonify(ok=True, database=str(db.engine.url).split("@")[-1], clubs=SportClub.query.count(), products=SportProduct.query.count())

@app.get("/sporthub/api/clubs")
def sporthub_api_clubs():
    rows = SportClub.query.filter_by(active=True).order_by(SportClub.id.asc()).all()
    return jsonify([{"id":c.id,"slug":c.slug,"name":c.name,"city":c.city,"shamcash_account":c.shamcash_account or "","qr_url":url_for("sporthub_club_qr",cid=c.id) if c.shamcash_qr else ""} for c in rows])

@app.get("/sporthub/api/products")
def sporthub_api_products():
    q = SportProduct.query.filter_by(active=True).order_by(SportProduct.id.desc())
    club_id = request.args.get("club_id", type=int)
    if club_id:
        q = q.filter_by(club_id=club_id)
    rows = q.all()
    return jsonify([{"id":p.id,"club_id":p.club_id,"club_name":p.club.name,"name":p.name,"category":p.category,"description":p.description or "","price_syp":int(p.price_syp or 0),"stock_qty":int(p.stock_qty or 0)} for p in rows])

@app.get("/sporthub/club/<int:cid>/qr")
def sporthub_club_qr(cid):
    c = SportClub.query.get_or_404(cid)
    if not c.shamcash_qr:
        abort(404)
    return app.response_class(c.shamcash_qr, mimetype=c.shamcash_qr_mime or "image/png")

@app.post("/sporthub/api/orders")
def sporthub_create_order():
    data = request.get_json(silent=True) or {}
    customer_name = str(data.get("customer_name") or "").strip()[:180]
    phone = str(data.get("phone") or "").strip()[:80]
    if not customer_name or not phone:
        return jsonify(error="الاسم ورقم الهاتف مطلوبان"), 400
    raw_items = data.get("items") or []
    if not raw_items:
        return jsonify(error="السلة فارغة"), 400
    resolved=[]; totals_by_club={}; total=0
    for item in raw_items:
        try:
            pid=int(item.get("product_id")); qty=max(1,min(50,int(item.get("qty") or 1)))
        except Exception:
            return jsonify(error="بيانات منتج غير صالحة"),400
        p=SportProduct.query.filter_by(id=pid,active=True).first()
        if not p:
            return jsonify(error="أحد المنتجات غير متاح"),400
        if p.stock_qty < qty:
            return jsonify(error=f"الكمية غير متوفرة للمنتج: {p.name}"),409
        line_total=int(p.price_syp or 0)*qty; total+=line_total; totals_by_club[p.club_id]=totals_by_club.get(p.club_id,0)+line_total; resolved.append((p,qty,line_total))
    order=SportOrder(order_no="SH-"+datetime.utcnow().strftime("%y%m%d%H%M%S%f")[-16:],customer_name=customer_name,phone=phone,address=str(data.get("address") or "").strip()[:300],total_syp=total,status="pending_payment")
    db.session.add(order); db.session.flush()
    for p,qty,line_total in resolved:
        db.session.add(SportOrderItem(order_id=order.id,club_id=p.club_id,product_id=p.id,product_name=p.name,qty=qty,unit_price_syp=int(p.price_syp or 0),line_total_syp=line_total)); p.stock_qty-=qty
    pay_map={}
    for x in (data.get("payments") or []):
        try: pay_map[int(x.get("club_id"))]=x
        except Exception: pass
    for cid,amount in totals_by_club.items():
        x=pay_map.get(cid,{})
        receipt_bytes=None; receipt_mime=""; raw=x.get("receipt")
        if isinstance(raw,str) and raw.startswith("data:") and ";base64," in raw:
            try:
                head,body=raw.split(";base64,",1); receipt_mime=head[5:][:100]; decoded=base64.b64decode(body)
                if len(decoded)<=4*1024*1024: receipt_bytes=decoded
            except Exception: receipt_bytes=None
        db.session.add(SportPayment(order_id=order.id,club_id=cid,amount_syp=amount,shamcash_transaction=str(x.get("transaction") or "").strip()[:180],receipt_image=receipt_bytes,receipt_mime=receipt_mime,status="pending_verification"))
    db.session.commit()
    return jsonify(ok=True,order_no=order.order_no,total_syp=order.total_syp,status=order.status)

def _sporthub_is_admin():
    role=(session.get("role") or "").lower()
    return bool(session.get("uid") or session.get("user_id")) and role in ("admin","manager","owner")

@app.get("/sporthub/admin")
def sporthub_admin():
    if not _sporthub_is_admin():
        return redirect("/login?next=/sporthub/admin")
    clubs=SportClub.query.order_by(SportClub.id.asc()).all()
    orders=SportOrder.query.order_by(SportOrder.id.desc()).limit(30).all()
    return render_template_string(ADMIN_HTML,clubs=clubs,orders=orders)

@app.post("/sporthub/admin/club/<int:cid>")
def sporthub_admin_club(cid):
    if not _sporthub_is_admin():
        abort(403)
    c=SportClub.query.get_or_404(cid)
    c.name=(request.form.get("name") or c.name).strip()[:180]
    c.city=(request.form.get("city") or "").strip()[:120]
    c.shamcash_account=(request.form.get("shamcash_account") or "").strip()[:250]
    f=request.files.get("qr")
    if f and f.filename:
        raw=f.read(4*1024*1024+1)
        if len(raw)<=4*1024*1024:
            c.shamcash_qr=raw; c.shamcash_qr_mime=(f.mimetype or "image/png")[:100]
    db.session.commit()
    return redirect(url_for("sporthub_admin"))
