# -*- coding: utf-8 -*-
"""SPORT HUB - standalone Arabic sports marketplace.
No connection to the suspended Nahda database. The optional DATABASE_URL
enables a persistent PostgreSQL backend; without it this runs in DEMO mode.
"""
import os
import hmac
import secrets
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=1024 * 1024,
)
database_url = os.getenv("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif database_url.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
DEMO = not bool(database_url)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:////tmp/sporthub-new-preview.sqlite3"
db = SQLAlchemy(app)


class Club(db.Model):
    __tablename__ = "sh_clubs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False, default="")
    shamcash = db.Column(db.String(150), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True)


class Product(db.Model):
    __tablename__ = "sh_products"
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("sh_clubs.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(500), nullable=False, default="")
    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    icon = db.Column(db.String(20), nullable=False, default="🏋️")
    active = db.Column(db.Boolean, nullable=False, default=True)
    club = db.relationship("Club")


class Order(db.Model):
    __tablename__ = "sh_orders"
    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    address = db.Column(db.String(250), nullable=False, default="")
    payment_ref = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(40), nullable=False, default="pending")
    total = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OrderItem(db.Model):
    __tablename__ = "sh_order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sh_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("sh_products.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)


with app.app_context():
    db.create_all()
    if not Club.query.first():
        clubs = [Club(name="POWER GYM", city="دمشق"),
                 Club(name="TITAN CLUB", city="حلب"),
                 Club(name="ARENA FITNESS", city="إدلب")]
        db.session.add_all(clubs)
        db.session.flush()
        items = [
            (0,"بروتين واي 2 كغ","مكملات","بروتين لتعزيز التعافي بعد التمرين",450000,15,"🥛"),
            (0,"كرياتين 300 غ","مكملات","كرياتين مونوهيدرات للتمارين القوية",185000,24,"⚡"),
            (0,"شيكر احترافي","إكسسوارات","قارورة عملية للماء والمكملات",65000,30,"🥤"),
            (1,"قفازات رياضية","إكسسوارات","راحة وحماية أثناء رفع الأوزان",90000,18,"🧤"),
            (1,"حقيبة النادي","إكسسوارات","حقيبة عصرية للملابس والمعدات",220000,12,"🎒"),
            (1,"حبل قفز سريع","معدات","تمارين كارديو ولياقة يومية",75000,20,"🪢"),
            (2,"تيشيرت رياضي","ملابس","قماش رياضي خفيف ومريح",160000,20,"👕"),
            (2,"بروتين آيزوليت 1 كغ","مكملات","بروتين معزول بنكهة الفانيليا",390000,12,"💪"),
            (2,"حزام رفع أثقال","معدات","دعم إضافي في تمارين الأوزان",145000,14,"🏋️"),
        ]
        db.session.add_all(Product(club_id=clubs[c].id, name=n,category=cat,
                  description=desc,price=price,stock=stock,icon=icon)
                           for c,n,cat,desc,price,stock,icon in items)
        db.session.commit()

STYLE = r"""
:root{--bg:#080d10;--panel:#12191c;--panel2:#172126;--border:#293236;--ink:#f3f9f7;--muted:#9daaad;--lime:#ccff4d;--cyan:#6ee7e0}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 Tahoma,Arial,sans-serif}
a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}button{cursor:pointer}
.wrap{width:min(1200px,92%);margin:auto}.nav{position:sticky;top:0;z-index:20;background:#0a1012ed;backdrop-filter:blur(16px);border-bottom:1px solid var(--border)}
.navIn{display:flex;align-items:center;justify-content:space-between;min-height:76px;gap:18px}.brand{display:flex;align-items:center;gap:10px;font-size:23px;font-weight:1000;letter-spacing:.2px;direction:ltr}.brandIcon{background:var(--lime);border-radius:12px;color:#13200a;padding:5px 10px;font-size:20px}.brand span{color:var(--lime)}
.links{display:flex;align-items:center;gap:23px;color:#cfdbd6;font-size:13px}.links a:hover{color:var(--lime)}
.btn{display:inline-flex;align-items:center;justify-content:center;border:1px solid transparent;gap:8px;border-radius:12px;padding:13px 20px;font-weight:800;background:var(--lime);color:#101809;transition:.2s}
.btn:hover{filter:brightness(.9)}.btn.ghost{background:#1b2428;border-color:#344145;color:var(--ink)}.btn.small{font-size:12px;padding:9px 13px}
.flag{display:inline-flex;color:#131a10;font-weight:800;background:#eaffaa;padding:6px 12px;border-radius:30px;font-size:11px}
.notice{background:#2c2818;border-bottom:1px solid #6d5821;color:#f7e0aa;padding:9px 0;font-size:12px}
.hero{position:relative;overflow:hidden;padding:90px 0 105px;background:radial-gradient(ellipse at 24% 15%,#254337 0%,transparent 50%),radial-gradient(ellipse at 85% 85%,#1e3441 0%,transparent 40%),#0b1417}
.heroFlex{display:grid;grid-template-columns:1.2fr .8fr;align-items:center;gap:50px}.eyebrow{font-size:12px;font-weight:900;letter-spacing:1px;color:var(--lime)}
h1{font-size:clamp(40px,5vw,70px);line-height:1.2;letter-spacing:-1px;margin:15px 0 20px}h1 em{color:var(--lime);font-style:normal}.hero p{color:#a8bbba;max-width:610px;font-size:17px;line-height:2}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:30px}.heroArt{min-height:390px;border:1px solid #476448;border-radius:26px;display:grid;place-items:center;position:relative;background:linear-gradient(135deg,#243a27,#101b24);box-shadow:0 30px 100px #0009;overflow:hidden}
.heroArt:before{content:"";width:270px;height:270px;border:45px solid #ccff4d28;border-radius:100%;position:absolute;transform:rotate(-30deg)}.heroArt strong{font-size:135px;filter:drop-shadow(0 18px 20px #0008);z-index:1}.heroTag{position:absolute;bottom:25px;right:24px;left:24px;border:1px solid #ffffff29;border-radius:14px;background:#0a1010ba;padding:12px 18px;display:flex;justify-content:space-between;align-items:center}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding-top:28px}.stat{border-left:1px solid #31413b;padding-left:13px}.stat b{display:block;font-size:24px}.stat small{color:#a1b4af}
.section{padding:74px 0}.sectionTop{display:flex;align-items:end;justify-content:space-between;margin-bottom:25px;gap:20px}.sectionTop h2{font-size:32px;margin:5px 0}.sectionTop p{color:var(--muted);margin:0}
.clubs{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.club{border:1px solid var(--border);background:linear-gradient(140deg,#172122,#10181c);border-radius:18px;padding:25px;min-height:140px;position:relative}.club small{color:var(--muted)}.club b{font-size:23px;display:block;margin:10px 0}.club .mark{position:absolute;left:20px;top:25px;color:var(--lime);font-size:26px}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:23px}.input{background:#151e22;color:#f4faf7;border:1px solid #374448;border-radius:12px;padding:13px 15px;outline:none;width:100%}.input:focus{border-color:var(--lime)}.toolbar .search{flex:1;min-width:220px}.toolbar select{min-width:160px;max-width:230px}
.products{display:grid;grid-template-columns:repeat(3,1fr);gap:17px}.product{border:1px solid #2d383a;background:#11191c;border-radius:20px;overflow:hidden;transition:.2s}.product:hover{border-color:#7d9c57;transform:translateY(-2px)}
.productArt{height:200px;background:radial-gradient(circle at 50% 60%,#354a42,#162325 70%);display:flex;align-items:center;justify-content:center;position:relative;font-size:77px}.productArt .tag{position:absolute;top:15px;right:15px;background:#1a2323;border:1px solid #4d6055;border-radius:30px;padding:5px 10px;font-size:10px;color:#cbebc7}
.productBody{padding:19px}.productBody h3{font-size:19px;margin:5px 0}.productBody p{font-size:12px;line-height:1.8;color:var(--muted);min-height:43px;margin:8px 0}.productFoot{display:flex;align-items:center;justify-content:space-between;margin-top:16px;gap:8px}.price{font-weight:1000;font-size:19px;color:var(--lime)}.productFoot small{color:var(--muted)}
.footer{background:#0c1214;border-top:1px solid var(--border);padding:40px 0;color:var(--muted);font-size:13px}.footerIn{display:flex;align-items:center;justify-content:space-between;gap:20px}
.drawerBackdrop{position:fixed;inset:0;background:#000b;z-index:49;display:none}.drawerBackdrop.on{display:block}
.drawer{position:fixed;z-index:50;right:0;top:0;bottom:0;width:min(480px,100vw);background:#121b1e;border-left:1px solid #42504b;transform:translateX(105%);transition:transform .22s;overflow:auto;padding:25px}.drawer.on{transform:translateX(0)}
.drawerHeader{display:flex;justify-content:space-between;align-items:center}.drawer h2{margin:10px 0 20px}.cartLine{border-bottom:1px solid #344043;padding:14px 0;display:flex;align-items:center;gap:12px}.cartLine .art{font-size:32px;background:#243331;padding:11px;border-radius:12px}.cartLine b{display:block}.cartLine small{color:var(--muted)}.qty{display:flex;align-items:center;gap:9px;margin-right:auto}.qty button{background:#2a3639;color:#fff;border:0;border-radius:7px;width:30px;height:30px}
.field{margin:12px 0}.field label{display:block;color:#bdccc6;font-size:12px;margin-bottom:6px}.summary{border-top:1px solid #384646;display:flex;justify-content:space-between;padding:20px 0;margin-top:20px;font-weight:900}
.panel{background:#131c20;border:1px solid #344044;padding:26px;border-radius:22px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:15px}.adminWrap{max-width:1120px;margin:48px auto;padding:0 18px}.dataTable{width:100%;border-collapse:collapse;font-size:13px;text-align:right}.dataTable th,.dataTable td{border-bottom:1px solid #303c3e;padding:13px 9px;vertical-align:middle}.dataTable th{color:#afc0bb}.inlineForm{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.inlineForm input,.inlineForm select{padding:8px;background:#10181a;color:#fff;border:1px solid #405052;border-radius:8px;max-width:120px}.empty{padding:45px;text-align:center;color:var(--muted)}
@media(max-width:900px){.heroFlex{grid-template-columns:1fr}.heroArt{min-height:290px}.clubs,.products{grid-template-columns:repeat(2,1fr)}.links a{display:none}}
@media(max-width:600px){.hero{padding:50px 0 60px}h1{font-size:42px}.heroArt{min-height:250px}.stats{grid-template-columns:repeat(3,1fr)}.clubs,.products,.grid2{grid-template-columns:1fr}.section{padding:45px 0}.sectionTop h2{font-size:27px}.navIn{min-height:65px}.brand{font-size:17px}.footerIn{display:block}.dataTable{font-size:11px}}
"""

SHOP_HTML = r"""
<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1417">
<title>SPORT HUB | منصة الأندية الرياضية</title><style>{{style|safe}}</style></head><body>
{% if demo %}<div class="notice"><div class="wrap">⚠️ نسخة معاينة: قاعدة البيانات الدائمة لم تُربط بعد؛ الطلبات المالية معطلة لحماية العملاء.</div></div>{% endif %}
<header class="nav"><div class="wrap navIn">
<a class="brand" href="/"><span class="brandIcon">S</span> SPORT <span>HUB</span></a>
<div class="links"><a href="#clubs">الأندية</a><a href="#store">المتجر</a><a href="#about">عن المنصة</a></div>
<button class="btn small" onclick="toggleCart(true)">🛒 السلة <span id="count">0</span></button></div></header>
<main><section class="hero"><div class="wrap heroFlex"><div>
<div class="eyebrow">SPORT HUB • SYRIA</div>
<h1>كل طاقتك تبدأ <em>من هون.</em></h1>
<p>منصة تجمع الأندية الرياضية ومتاجرها في مكان واحد. اكتشف منتجات اللياقة والمكملات والإكسسوارات، وتسوق من ناديك المفضل.</p>
<div class="actions"><a href="#store" class="btn">تسوق الآن ←</a><a href="#clubs" class="btn ghost">استكشف الأندية</a></div>
<div class="stats"><div class="stat"><b id="sclubs">3</b><small>أندية</small></div><div class="stat"><b id="sproducts">9</b><small>منتجات</small></div><div class="stat"><b>100%</b><small>تجربة عربية</small></div></div>
</div><div class="heroArt"><strong>🏋️</strong><div class="heroTag"><span>🔥 TRAIN HARD. SHOP SMART.</span><span style="color:var(--lime)">SPORT HUB</span></div></div></div></section>
<section id="clubs" class="section"><div class="wrap"><div class="sectionTop"><div><div class="eyebrow">OUR PARTNERS</div><h2>الأندية المشتركة</h2><p>لكل نادٍ مجموعته الخاصة من المنتجات.</p></div></div><div class="clubs" id="clubList"></div></div></section>
<section id="store" class="section" style="background:#0d1518"><div class="wrap"><div class="sectionTop"><div><div class="eyebrow">THE STORE</div><h2>المتجر الرياضي</h2><p>اختر ما يناسب تمارينك واحتياجاتك.</p></div><span class="flag" id="productTotal">تصفح المنتجات</span></div>
<div class="toolbar"><input class="input search" placeholder="ابحث عن منتج أو نادي..." id="search" oninput="renderProducts()">
<select class="input" id="clubFilter" onchange="renderProducts()"><option value="">جميع الأندية</option></select>
<select class="input" id="categoryFilter" onchange="renderProducts()"><option value="">كل الأقسام</option></select></div><div class="products" id="products"></div></div></section>
<section id="about" class="section"><div class="wrap"><div class="panel"><div class="eyebrow">ONE PLATFORM, MANY CLUBS</div><h2>منصة واحدة. فرص أكبر.</h2><p style="color:var(--muted)">SPORT HUB صُممت لتمنح كل نادٍ مساحة يعرض فيها منتجاته، مع إدارة الطلبات والمدفوعات والتحصيل من مكان واحد.</p><span class="flag">الدفع عبر شام كاش عند تفعيل الحسابات</span></div></div></section></main>
<footer class="footer"><div class="wrap footerIn"><div class="brand">SPORT <span>HUB</span></div><div>© 2026 SPORT HUB • جميع الحقوق محفوظة</div><a href="/admin/login">إدارة المنصة</a></div></footer>
<div class="drawerBackdrop" id="shade" onclick="toggleCart(false)"></div>
<aside class="drawer" id="drawer"><div class="drawerHeader"><h2>🛒 سلة التسوق</h2><button class="btn ghost small" onclick="toggleCart(false)">إغلاق ✕</button></div>
<div id="cartItems"></div><div class="summary"><span>المجموع</span><strong id="total">0 ل.س</strong></div>
<div id="checkout">
<div class="field"><label>الاسم الكامل</label><input class="input" id="customer" placeholder="اسم المشتري"></div>
<div class="field"><label>رقم الهاتف</label><input class="input" id="phone" placeholder="رقم للتواصل"></div>
<div class="field"><label>عنوان التوصيل</label><input class="input" id="address" placeholder="المدينة / الشارع"></div>
<div class="field"><label>رقم حوالة شام كاش (اختياري)</label><input class="input" id="payment" placeholder="رقم العملية"></div>
{% if demo %}<p style="color:#f0cd77">الشراء معطّل في وضع المعاينة حتى يتم ربط قاعدة البيانات الدائمة وتفعيل حسابات الدفع.</p>
<button class="btn" style="width:100%;opacity:.5" disabled>إتمام الطلب – غير متاح مؤقتًا</button>
{% else %}<button class="btn" style="width:100%" onclick="submitOrder()">تأكيد الطلب</button>{% endif %}
</div></aside>
<script>
let clubs=[],products=[],cart={};
try{cart=JSON.parse(localStorage.getItem("shCart")||"{}")}catch(e){}
const money=n=>new Intl.NumberFormat("ar-SY").format(n)+" ل.س";
const byId=id=>document.getElementById(id);
const safe=t=>String(t??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function persist(){localStorage.setItem("shCart",JSON.stringify(cart));renderCart()}
function toggleCart(on){byId("drawer").classList.toggle("on",on);byId("shade").classList.toggle("on",on)}
function add(id){let p=products.find(x=>x.id===id);if(!p)return;cart[id]=Math.min(p.stock,(cart[id]||0)+1);persist();toggleCart(true)}
function adjust(id,delta){cart[id]=(cart[id]||0)+delta;if(cart[id]<=0)delete cart[id];persist()}
function renderCart(){let lines=Object.entries(cart),total=0,count=0;
byId("cartItems").innerHTML=lines.map(([id,q])=>{let p=products.find(x=>x.id==id);if(!p)return "";
total+=p.price*q;count+=q;return '<div class="cartLine"><div class="art">'+safe(p.icon)+'</div><div><b>'+safe(p.name)+'</b><small>'+money(p.price)+' × '+q+'</small></div><div class="qty"><button onclick="adjust('+p.id+',1)">+</button>'+q+'<button onclick="adjust('+p.id+',-1)">−</button></div></div>';
}).join("")||'<div class="empty">سلتك فاضية حاليًا. أضف منتجاتك المفضلة!</div>';
byId("count").textContent=count;byId("total").textContent=money(total);
}
function renderProducts(){let term=byId("search").value.trim().toLowerCase(),club=byId("clubFilter").value,cat=byId("categoryFilter").value;
let list=products.filter(p=>(!club||p.club_id==club)&&(!cat||p.category==cat)&&(!term||(p.name+" "+p.club+" "+p.description).toLowerCase().includes(term)));
byId("productTotal").textContent=list.length+" منتجات";
byId("products").innerHTML=list.map(p=>'<article class="product"><div class="productArt"><span class="tag">'+safe(p.category)+'</span>'+safe(p.icon)+'</div><div class="productBody"><small style="color:var(--cyan)">'+safe(p.club)+'</small><h3>'+safe(p.name)+'</h3><p>'+safe(p.description)+'</p><div class="productFoot"><div><div class="price">'+money(p.price)+'</div><small>المتوفر: '+p.stock+'</small></div><button class="btn small" '+(p.stock?'onclick="add('+p.id+')"':'disabled')+'>'+(p.stock?"+ أضف":"نفدت الكمية")+'</button></div></div></article>').join("")||'<div class="empty">لا توجد منتجات مطابقة.</div>';
}
async function boot(){try{
let r=await fetch("/api/catalog");if(!r.ok)throw Error("catalog error");let data=await r.json();clubs=data.clubs;products=data.products;
byId("sclubs").textContent=clubs.length;byId("sproducts").textContent=products.length;
byId("clubList").innerHTML=clubs.map(c=>'<a class="club" href="#store" onclick="byId(\'clubFilter\').value='+c.id+';renderProducts()"><span class="mark">↗</span><small>'+safe(c.city)+'</small><b>'+safe(c.name)+'</b><small>تصفح منتجات النادي ←</small></a>').join("");
byId("clubFilter").innerHTML+='<option value="">'.slice(0,0)+clubs.map(c=>'<option value="'+c.id+'">'+safe(c.name)+'</option>').join("");
byId("categoryFilter").innerHTML+=[...new Set(products.map(p=>p.category))].map(c=>'<option>'+safe(c)+'</option>').join("");
renderProducts();renderCart();
}catch(e){byId("products").innerHTML='<p>تعذّر تحميل المتجر. حاول تحديث الصفحة.</p>'}}
async function submitOrder(){let items=Object.entries(cart).map(([id,q])=>({id:Number(id),qty:q}));
if(!items.length)return alert("السلة فارغة");let customer=byId("customer").value.trim(),phone=byId("phone").value.trim();if(!customer||!phone)return alert("يرجى إدخال الاسم ورقم الهاتف");
let r=await fetch("/api/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items,customer,phone,address:byId("address").value,payment_ref:byId("payment").value})});
let d=await r.json();if(!r.ok)return alert(d.error||"تعذر تسجيل الطلب");
cart={};persist();toggleCart(false);alert("تم استلام الطلب رقم "+d.id+"، وسيتم التواصل معك للتأكيد.");}
boot();
</script></body></html>
"""

LOGIN_HTML = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول الإدارة | SPORT HUB</title><style>{{style|safe}}</style></head>
<body><header class="nav"><div class="wrap navIn"><a href="/" class="brand">SPORT <span>HUB</span></a><a class="btn ghost small" href="/">العودة للمتجر ←</a></div></header>
<div style="width:min(440px,92%);margin:90px auto" class="panel">
<div class="eyebrow">ADMIN ACCESS</div><h1 style="font-size:32px">دخول إدارة SPORT HUB</h1>
{% if error %}<p style="color:#ffaaa2">{{error}}</p>{% endif %}
<form method="post"><input type="hidden" name="csrf" value="{{csrf}}">
<div class="field"><label>اسم المستخدم</label><input class="input" name="username" required autocomplete="username"></div>
<div class="field"><label>كلمة المرور</label><input class="input" name="password" type="password" required autocomplete="current-password"></div>
<button class="btn" style="width:100%;margin-top:16px">تسجيل الدخول</button></form></div></body></html>"""

ADMIN_HTML = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة الإدارة | SPORT HUB</title><style>{{style|safe}}</style></head><body>
<header class="nav"><div class="wrap navIn"><a class="brand" href="/">SPORT <span>HUB</span></a><div><a class="btn ghost small" href="/">المتجر</a> <a class="btn ghost small" href="/admin/logout">خروج</a></div></div></header>
<div class="adminWrap"><div class="eyebrow">CONTROL CENTER</div><h1 style="font-size:36px">لوحة إدارة المنصة</h1>
{% if demo %}<div class="notice" style="border-radius:9px;padding:13px;margin-bottom:20px">نسخة معاينة مؤقتة: التغييرات في البيانات قد تضيع عند إعادة تشغيل الخادم. ربط قاعدة PostgreSQL ضروري للعمل التجاري.</div>{% endif %}
<div class="grid2"><div class="panel"><small>عدد الأندية</small><h2>{{clubs|length}}</h2></div><div class="panel"><small>المنتجات</small><h2>{{products|length}}</h2></div><div class="panel"><small>عدد الطلبات</small><h2>{{orders|length}}</h2></div><div class="panel"><small>قيمة الطلبات</small><h2>{{total_orders}} ل.س</h2></div></div>
<h2 style="margin-top:38px">إضافة منتج</h2><div class="panel"><form method="post" action="/admin/product/add">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid2"><div class="field"><label>اسم المنتج</label><input class="input" name="name" required maxlength="150"></div>
<div class="field"><label>النادي</label><select class="input" name="club_id">{% for c in clubs %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select></div>
<div class="field"><label>السعر بالليرة السورية</label><input class="input" name="price" type="number" min="1" required></div>
<div class="field"><label>الكمية المتاحة</label><input class="input" name="stock" type="number" min="0" required></div>
<div class="field"><label>الفئة</label><input class="input" name="category" value="معدات" maxlength="60" required></div>
<div class="field"><label>الرمز</label><input class="input" name="icon" value="🏋️" maxlength="20"></div>
</div><div class="field"><label>الوصف</label><input class="input" name="description" maxlength="500"></div><button class="btn">إضافة المنتج</button></form></div>
<h2 style="margin-top:35px">المخزون والأسعار</h2><div class="panel" style="overflow:auto"><table class="dataTable"><thead><tr><th>المنتج</th><th>النادي</th><th>السعر</th><th>المخزون</th><th>تعديل</th></tr></thead><tbody>
{% for p in products %}<tr><td>{{p.icon}} {{p.name}}</td><td>{{p.club.name}}</td><td>{{p.price}}</td><td>{{p.stock}}</td>
<td><form class="inlineForm" method="post" action="/admin/product/{{p.id}}/update"><input type="hidden" name="csrf" value="{{csrf}}">
<input type="number" name="price" value="{{p.price}}" min="1" required title="السعر"><input type="number" name="stock" value="{{p.stock}}" min="0" required title="الكمية">
<button class="btn small">حفظ</button></form></td></tr>{% endfor %}</tbody></table></div>
<h2 style="margin-top:35px">الطلبات</h2><div class="panel" style="overflow:auto"><table class="dataTable"><thead><tr><th>رقم</th><th>العميل</th><th>الهاتف</th><th>الإجمالي</th><th>الدفع</th><th>الحالة</th></tr></thead><tbody>
{% for o in orders %}<tr><td>#{{o.id}}</td><td>{{o.customer}}</td><td dir="ltr">{{o.phone}}</td><td>{{o.total}}</td><td>{{o.payment_ref or "—"}}</td>
<td><form class="inlineForm" method="post" action="/admin/order/{{o.id}}/status"><input type="hidden" name="csrf" value="{{csrf}}">
<select name="status"><option value="pending" {% if o.status=="pending" %}selected{% endif %}>بانتظار التأكيد</option>
<option value="paid" {% if o.status=="paid" %}selected{% endif %}>مدفوع</option><option value="delivered" {% if o.status=="delivered" %}selected{% endif %}>تم التسليم</option>
<option value="cancelled" {% if o.status=="cancelled" %}selected{% endif %}>ملغي</option></select><button class="btn small">تحديث</button></form></td></tr>
{% else %}<tr><td colspan="6" class="empty">لا توجد طلبات حتى الآن.</td></tr>{% endfor %}</tbody></table></div>
</div></body></html>"""


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def require_admin():
    return session.get("sporthub_admin") is True


def csrf_valid():
    return hmac.compare_digest(str(request.form.get("csrf", "")), str(session.get("csrf", "")))


@app.get("/healthz")
def health():
    return jsonify(ok=True, service="sporthub-new", mode="demo" if DEMO else "database")


@app.get("/")
@app.get("/shop")
@app.get("/sporthub")
@app.get("/sporthub/shop")
def shop():
    return render_template_string(SHOP_HTML, style=STYLE, demo=DEMO)


@app.get("/api/catalog")
def catalog():
    clubs = Club.query.filter_by(active=True).order_by(Club.id).all()
    products = Product.query.filter_by(active=True).order_by(Product.id.desc()).all()
    return jsonify(
        clubs=[dict(id=c.id, name=c.name, city=c.city) for c in clubs],
        products=[dict(id=p.id,club_id=p.club_id,club=p.club.name,name=p.name,
                       category=p.category,description=p.description,price=p.price,
                       stock=p.stock,icon=p.icon) for p in products],
        demo=DEMO,
    )


@app.post("/api/orders")
def create_order():
    if DEMO:
        return jsonify(error="الطلبات المالية معطلة حتى ربط قاعدة بيانات دائمة."), 503
    data = request.get_json(silent=True) or {}
    name = str(data.get("customer", "")).strip()[:150]
    phone = str(data.get("phone", "")).strip()[:60]
    if not name or not phone or not isinstance(data.get("items"), list):
        return jsonify(error="يرجى إدخال الاسم والهاتف واختيار المنتجات."), 400
    if len(data["items"]) > 30:
        return jsonify(error="عدد المنتجات يتجاوز الحد المسموح."), 400
    validated, total = [], 0
    try:
        for entry in data["items"]:
            pid, qty = int(entry["id"]), int(entry["qty"])
            if qty < 1 or qty > 99:
                raise ValueError()
            p = db.session.get(Product, pid)
            if not p or not p.active or qty > p.stock:
                return jsonify(error="منتج غير متوفر بالكمية المطلوبة."), 409
            validated.append((p, qty))
            total += p.price * qty
    except (TypeError, ValueError, KeyError):
        return jsonify(error="تفاصيل السلة غير صالحة."), 400
    if not validated:
        return jsonify(error="السلة فارغة."), 400
    o = Order(customer=name, phone=phone, address=str(data.get("address", ""))[:250],
              payment_ref=str(data.get("payment_ref", ""))[:120], total=total)
    db.session.add(o)
    db.session.flush()
    for p, qty in validated:
        db.session.add(OrderItem(order_id=o.id,product_id=p.id,name=p.name,
                                 qty=qty,unit_price=p.price))
        p.stock -= qty
    db.session.commit()
    return jsonify(id=o.id,total=total,status=o.status), 201


@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/sporthub/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        user = os.getenv("SPORTHUB_ADMIN_USER", "admin")
        password = os.getenv("SPORTHUB_ADMIN_PASSWORD", "")
        if not csrf_valid():
            error = "جلسة منتهية، حدّث الصفحة وأعد المحاولة."
        elif (password and hmac.compare_digest(request.form.get("username", ""), user)
              and hmac.compare_digest(request.form.get("password", ""), password)):
            session.clear()
            session["sporthub_admin"] = True
            csrf_token()
            return redirect("/admin")
        else:
            error = "اسم المستخدم أو كلمة المرور غير صحيحة."
    return render_template_string(LOGIN_HTML, style=STYLE, error=error, csrf=csrf_token())


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/")


@app.get("/admin")
@app.get("/sporthub/admin")
def admin():
    if not require_admin():
        return redirect("/admin/login")
    clubs = Club.query.order_by(Club.id).all()
    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.id.desc()).limit(100).all()
    return render_template_string(ADMIN_HTML, style=STYLE, clubs=clubs,
        products=products, orders=orders, csrf=csrf_token(), demo=DEMO,
        total_orders=f"{sum(o.total for o in orders):,}")


@app.post("/admin/product/add")
def product_add():
    if not require_admin():
        return redirect("/admin/login")
    if not csrf_valid():
        return "Invalid session", 403
    try:
        price, stock, cid = int(request.form["price"]), int(request.form["stock"]), int(request.form["club_id"])
        club = db.session.get(Club, cid)
        name = request.form["name"].strip()[:150]
        if not club or not name or price <= 0 or stock < 0:
            raise ValueError()
    except (ValueError, KeyError):
        return "بيانات المنتج غير صالحة", 400
    db.session.add(Product(name=name,club_id=cid,price=price,stock=stock,
               category=request.form.get("category","معدات")[:60],
               description=request.form.get("description","")[:500],
               icon=request.form.get("icon","🏋️")[:20]))
    db.session.commit()
    return redirect("/admin")


@app.post("/admin/product/<int:pid>/update")
def product_update(pid):
    if not require_admin():
        return redirect("/admin/login")
    if not csrf_valid():
        return "Invalid session", 403
    p = db.session.get(Product, pid)
    if p is None:
        return "غير موجود", 404
    try:
        price, stock = int(request.form["price"]), int(request.form["stock"])
        if price <= 0 or stock < 0:
            raise ValueError()
    except (ValueError, KeyError):
        return "السعر والكمية غير صالحين", 400
    p.price, p.stock = price, stock
    db.session.commit()
    return redirect("/admin")


@app.post("/admin/order/<int:oid>/status")
def order_status(oid):
    if not require_admin():
        return redirect("/admin/login")
    if not csrf_valid():
        return "Invalid session", 403
    o = db.session.get(Order, oid)
    status = request.form.get("status")
    if o is None or status not in ("pending","paid","delivered","cancelled"):
        return "طلب أو حالة غير صالحة", 400
    o.status = status
    db.session.commit()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
