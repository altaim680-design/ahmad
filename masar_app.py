"""Masar International Transport - functional marketplace preview.
For production: configure persistent PostgreSQL, mail verification, licensed payment provider,
fraud controls, legal terms, monitoring and independent security review.
"""
import os, re, hmac, secrets, hashlib, html, json, base64, threading, urllib.request, urllib.error
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import quote
from contextlib import contextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary, ForeignKey, UniqueConstraint, select, func
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import IntegrityError
from jinja2 import Environment, DictLoader, select_autoescape

SITE = "مسار للنقل الدولي"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////tmp/masar_marketplace_preview.db")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
if DATABASE_URL.startswith("postgresql://"): DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
SUPABASE_URL = os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY","")
SUPABASE_SYNC_SECRET = os.environ.get("SUPABASE_SYNC_SECRET","")
REMOTE_STATE_ENABLED = bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SYNC_SECRET)
DB_IS_PREVIEW = DATABASE_URL.startswith("sqlite:") and not REMOTE_STATE_ENABLED
TRADER_BPS = int(os.environ.get("TRADER_FEE_BPS", "200"))
CARRIER_BPS = int(os.environ.get("CARRIER_FEE_BPS", "300"))
if not 0 <= TRADER_BPS <= 3000 or not 0 <= CARRIER_BPS <= 3000: raise RuntimeError("Invalid fee percentage")
PAYMENT_RECEIVER = os.environ.get("SHAMCASH_RECEIVER", "").strip()
PAYMENTS_ENABLED = os.environ.get("PAYMENTS_ENABLED", "0") == "1" and bool(PAYMENT_RECEIVER)
SETUP_TOKEN = os.environ.get("ADMIN_SETUP_TOKEN", "")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_urlsafe(48))
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread":False} if DB_IS_PREVIEW else {})
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
def utc(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True)
    name=Column(String(90),nullable=False)
    email=Column(String(180),unique=True,nullable=False)
    hash=Column(String(400),nullable=False)
    role=Column(String(20),nullable=False)
    company=Column(String(120),default="")
    created=Column(String(40),default=utc)
class Listing(Base):
    __tablename__="listings"
    id=Column(Integer,primary_key=True)
    trader_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    title=Column(String(160),nullable=False)
    origin_country=Column(String(70),nullable=False)
    origin_city=Column(String(90),nullable=False)
    dest_country=Column(String(70),nullable=False)
    dest_city=Column(String(90),nullable=False)
    weight_kg=Column(Integer,nullable=False)
    description=Column(Text,default="")
    currency=Column(String(3),nullable=False,default="USD")
    status=Column(String(25),nullable=False,default="open")
    created=Column(String(40),default=utc)
class Offer(Base):
    __tablename__="offers"
    __table_args__=(UniqueConstraint("listing_id","carrier_id",name="unique_carrier_offer"),)
    id=Column(Integer,primary_key=True)
    listing_id=Column(Integer,ForeignKey("listings.id"),nullable=False)
    carrier_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    price_cents=Column(Integer,nullable=False)
    note=Column(String(500),default="")
    status=Column(String(20),nullable=False,default="pending")
    created=Column(String(40),default=utc)
class Booking(Base):
    __tablename__="bookings"
    id=Column(Integer,primary_key=True)
    listing_id=Column(Integer,ForeignKey("listings.id"),unique=True,nullable=False)
    offer_id=Column(Integer,ForeignKey("offers.id"),unique=True,nullable=False)
    trader_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    carrier_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    freight_cents=Column(Integer,nullable=False)
    trader_fee_cents=Column(Integer,nullable=False)
    carrier_fee_cents=Column(Integer,nullable=False)
    total_due_cents=Column(Integer,nullable=False)
    carrier_due_cents=Column(Integer,nullable=False)
    status=Column(String(30),nullable=False,default="awaiting_payment")
    payment_status=Column(String(30),nullable=False,default="not_submitted")
    created=Column(String(40),default=utc)
class PaymentClaim(Base):
    __tablename__="payment_claims"
    id=Column(Integer,primary_key=True)
    booking_id=Column(Integer,ForeignKey("bookings.id"),nullable=False)
    submitted_by=Column(Integer,ForeignKey("users.id"),nullable=False)
    transfer_ref=Column(String(120),nullable=False)
    amount_cents=Column(Integer,nullable=False)
    status=Column(String(25),nullable=False,default="pending")
    reviewed_by=Column(Integer,ForeignKey("users.id"),nullable=True)
    created=Column(String(40),default=utc)
    reviewed=Column(String(40),nullable=True)
class Audit(Base):
    __tablename__="audit"
    id=Column(Integer,primary_key=True)
    actor_id=Column(Integer,ForeignKey("users.id"),nullable=True)
    entity=Column(String(30),nullable=False)
    entity_id=Column(Integer,nullable=False)
    action=Column(String(60),nullable=False)
    created=Column(String(40),default=utc)
class Photo(Base):
    __tablename__="listing_photos"
    id=Column(Integer,primary_key=True)
    listing_id=Column(Integer,ForeignKey("listings.id"),nullable=False,index=True)
    owner_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    mime=Column(String(30),nullable=False)
    data=Column(LargeBinary,nullable=False)
    created=Column(String(40),default=utc)
Base.metadata.create_all(engine)

SYNC_MODELS=(User,Listing,Offer,Booking,PaymentClaim,Audit,Photo)
DELETE_MODELS=(PaymentClaim,Booking,Offer,Photo,Audit,Listing,User)
_SYNC_LOCK=threading.RLock()

def _remote_headers(extra=None):
    h={
        "apikey":SUPABASE_ANON_KEY,
        "Authorization":"Bearer "+SUPABASE_ANON_KEY,
        "x-masar-secret":SUPABASE_SYNC_SECRET,
        "Content-Type":"application/json",
        "Accept":"application/json",
    }
    if extra:h.update(extra)
    return h

def _remote_request(method,path,payload=None,prefer=None):
    if not REMOTE_STATE_ENABLED:return None
    body=None if payload is None else json.dumps(payload,separators=(",",":")).encode("utf-8")
    headers=_remote_headers({"Prefer":prefer} if prefer else None)
    req=urllib.request.Request(SUPABASE_URL+path,data=body,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=20) as resp:
        raw=resp.read()
        if not raw:return None
        return json.loads(raw.decode("utf-8"))

def _encode_value(v):
    if isinstance(v,(bytes,bytearray,memoryview)):
        return {"__bytes__":base64.b64encode(bytes(v)).decode("ascii")}
    return v

def _decode_value(v):
    if isinstance(v,dict) and "__bytes__" in v:
        return base64.b64decode(v["__bytes__"])
    return v

def _snapshot_payload():
    db=Session()
    try:
        out={}
        for cls in SYNC_MODELS:
            rows=[]
            for obj in db.scalars(select(cls).order_by(cls.id.asc())).all():
                row={}
                for col in cls.__table__.columns:
                    value=getattr(obj,col.name)
                    if cls is Photo and col.name=="data":
                        value=b""
                    row[col.name]=_encode_value(value)
                rows.append(row)
            out[cls.__tablename__]=rows
        return out
    finally:
        db.close()

def _restore_payload(payload):
    if not isinstance(payload,dict) or not any(isinstance(v,list) and v for v in payload.values()):
        return False
    db=Session()
    try:
        for cls in DELETE_MODELS:
            db.query(cls).delete(synchronize_session=False)
        for cls in SYNC_MODELS:
            for row in payload.get(cls.__tablename__,[]) or []:
                vals={k:_decode_value(v) for k,v in row.items()}
                if cls is Photo: vals["data"]=b""
                db.add(cls(**vals))
        db.commit()
        return True
    except:
        db.rollback()
        raise
    finally:
        db.close()

def restore_from_supabase():
    if not REMOTE_STATE_ENABLED:return False
    with _SYNC_LOCK:
        rows=_remote_request("GET","/rest/v1/masar_state?id=eq.main&select=payload")
        if rows and isinstance(rows,list):
            return _restore_payload(rows[0].get("payload"))
        return False

def sync_to_supabase():
    if not REMOTE_STATE_ENABLED:return False
    with _SYNC_LOCK:
        payload=_snapshot_payload()
        _remote_request(
            "PATCH",
            "/rest/v1/masar_state?id=eq.main",
            {"payload":payload,"updated_at":utc()},
            "return=minimal"
        )
        return True

def persist_photo_remote(photo_id,listing_id,owner_id,mime,data):
    if not REMOTE_STATE_ENABLED:return False
    item={
        "id":int(photo_id),
        "listing_id":int(listing_id),
        "owner_id":int(owner_id),
        "mime":mime,
        "data_base64":base64.b64encode(bytes(data)).decode("ascii"),
        "updated_at":utc(),
    }
    _remote_request(
        "POST",
        "/rest/v1/masar_photos",
        item,
        "resolution=merge-duplicates,return=minimal"
    )
    return True

def fetch_photo_remote(photo_id):
    if not REMOTE_STATE_ENABLED:return None
    rows=_remote_request("GET",f"/rest/v1/masar_photos?id=eq.{int(photo_id)}&select=mime,data_base64")
    if not rows:return None
    item=rows[0]
    return item.get("mime"),base64.b64decode(item.get("data_base64",""))

try:
    if REMOTE_STATE_ENABLED:
        restored=restore_from_supabase()
        if restored:
            print("Masar: restored persistent state from Supabase")
        else:
            sync_to_supabase()
            print("Masar: initialized persistent Supabase state")
except Exception as exc:
    print("Masar persistence startup warning:",repr(exc))

app=FastAPI(title=SITE)
app.add_middleware(SessionMiddleware,secret_key=SECRET_KEY,same_site="lax",https_only=os.environ.get("SECURE_COOKIES","0")=="1",max_age=86400)

@app.middleware("http")
async def persist_mutations(request,call_next):
    response=await call_next(request)
    if REMOTE_STATE_ENABLED and request.method in ("POST","PUT","PATCH","DELETE") and response.status_code<400:
        try:
            sync_to_supabase()
        except Exception as exc:
            print("Masar persistence sync warning:",repr(exc))
    return response
@contextmanager
def session():
    db=Session()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally: db.close()
def password_hash(v):
    salt=secrets.token_bytes(16)
    return salt.hex()+":"+hashlib.pbkdf2_hmac("sha256",v.encode(),salt,390000).hex()
def password_ok(v,digest):
    try:
        salt,reference=digest.split(":")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",v.encode(),bytes.fromhex(salt),390000),bytes.fromhex(reference))
    except (TypeError,ValueError):return False
def money(v):
    try:
        d=Decimal(str(v))
        if not d.is_finite() or d<=0 or d>100000000: return None
        return int((d*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    except (TypeError,InvalidOperation,ValueError): return None
def cents(v): return f"{v/100:,.2f}"
def fee(value,bps):return (value*bps+5000)//10000
def csrf(req):
    if "csrf" not in req.session:req.session["csrf"]=secrets.token_urlsafe(28)
    return req.session["csrf"]
def valid(req,form):
    return bool(req.session.get("csrf")) and hmac.compare_digest(req.session["csrf"],str(form.get("csrf","")))
def current(req,db):
    uid=req.session.get("uid")
    return db.get(User,uid) if isinstance(uid,int) else None
def login_redirect():return RedirectResponse("/login",status_code=303)
def go(url):return RedirectResponse(url,status_code=303)
def error(req,msg,status=400):return page(req,"رسالة",f'<section class="panel"><h2>تنبيه</h2><p>{html.escape(msg)}</p><a class="btn" href="/">العودة للرئيسية</a></section>',status)
def require_form(req,form):
    if not valid(req,form):return error(req,"انتهت الجلسة، أعد تحميل الصفحة.",403)
def log(db,who,what,ident,action):db.add(Audit(actor_id=who,entity=what,entity_id=ident,action=action))
def template(source,**data):return env.from_string(source).render(**data)
def page(req,title,body,status=200):
    with session() as db:
        u=current(req,db)
        user={"id":u.id,"name":u.name,"role":u.role} if u else None
    markup=template(LAYOUT,site=SITE,title=title,body=body,user=user,csrf=csrf(req),preview=DB_IS_PREVIEW,receiver=PAYMENT_RECEIVER,enabled=PAYMENTS_ENABLED)
    return HTMLResponse(markup,status_code=status,headers={"Cache-Control":"no-store"})
STYLE="""
:root{--ink:#142c3a;--teal:#087d71;--pale:#e9f8f4;--muted:#637783;--edge:#dce9eb}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f8f8;color:var(--ink);font-family:Tahoma,Arial,sans-serif;line-height:1.8}
a{color:inherit;text-decoration:none}button,input,select,textarea{font:inherit}button{cursor:pointer}h1,h2,h3{line-height:1.45}
.wrap{max-width:1160px;margin:auto;padding:0 20px}.notice{background:#fff1d7;color:#6a4810;text-align:center;font-size:12px;padding:7px 15px}
nav{background:#fff;box-shadow:0 2px 15px #153b4912;position:sticky;top:0;z-index:5}nav .wrap{min-height:71px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{font-weight:900;font-size:23px}.logo span{color:var(--teal)}.navlinks{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:13px}
.btn{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:11px;background:var(--teal);color:white;padding:10px 17px;font-weight:bold;cursor:pointer}.btn.soft{background:var(--pale);color:var(--teal)}.btn.white{background:white;color:var(--ink)}.btn.danger{background:#b93c42}
.hero{background:linear-gradient(120deg,#0b2735,#155b5c);color:white;padding:56px 0}.hero h1{font-size:clamp(30px,4vw,49px);margin:10px 0}.hero p{color:#d2e7e5;max-width:660px}
main{min-height:68vh;padding:35px 0 65px}.panel,.card{background:white;border:1px solid var(--edge);border-radius:17px;padding:23px;margin-bottom:16px;box-shadow:0 4px 17px #132b3708}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.cards .card{margin:0}.tag{display:inline-block;background:var(--pale);color:var(--teal);font-size:12px;font-weight:bold;border-radius:99px;padding:3px 11px}
.muted{color:var(--muted);font-size:13px}.actions{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}.price{font-weight:900;font-size:20px;color:var(--teal)}
.form{max-width:650px}.form label{display:block;font-weight:bold;font-size:13px;margin:12px 0 5px}.input{display:block;width:100%;padding:11px;border:1px solid #d2e2e4;border-radius:10px;background:white;color:var(--ink)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.line{border-bottom:1px solid var(--edge);padding:9px 0}.line:last-child{border:0}
.flex{display:flex;align-items:center;justify-content:space-between;gap:13px;flex-wrap:wrap}
.tablewrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:630px}th,td{text-align:right;border-bottom:1px solid var(--edge);padding:12px 9px;font-size:13px}th{background:#eff6f6}
footer{background:#112b39;color:#c0d5d6;padding:25px 0;font-size:12px}
.listing-photo,.photo-placeholder{display:grid;place-items:center;width:100%;height:160px;border-radius:13px;object-fit:cover;margin-bottom:14px;background:linear-gradient(125deg,#074e56,#16867c);color:white}.photo-placeholder span{font-size:66px;filter:drop-shadow(0 6px 12px #062d3c66)}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:16px 0}.gallery img{width:100%;height:165px;object-fit:cover;border-radius:12px;border:1px solid var(--edge)}.card{transition:transform .18s,box-shadow .18s}.card:hover{transform:translateY(-3px);box-shadow:0 12px 30px #133e4818}.hero{background:radial-gradient(circle at 15% 5%,#23766c 0,transparent 36%),linear-gradient(120deg,#092330,#15464e)}.hero h1{letter-spacing:-1px}.price{letter-spacing:-.3px}input:focus,select:focus,textarea:focus{outline:2px solid #11877880;outline-offset:2px}
@media(max-width:780px){.cards{grid-template-columns:1fr}.row{grid-template-columns:1fr}.navlinks{font-size:12px}.panel,.card{padding:16px}main{padding-top:18px}}
"""
LAYOUT="""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} | {{site}}</title><style>"""+STYLE+"""</style></head><body>
{% if preview %}<div class="notice">⚠️ بيئة تجريبية: قاعدة البيانات مؤقتة وقد تُمحى عند إعادة تشغيل الخادم. لا تدفع أموالاً أو تضع بيانات شحن حساسة.</div>{% endif %}
<nav><div class="wrap"><a class="logo" href="/">مسار <span>للنقل الدولي</span></a><div class="navlinks"><a href="/">الحمولات</a>{% if user %}<a href="/dashboard">حسابي</a>{% if user.role=="trader" %}<a href="/new">انشر حمولة</a>{% endif %}{% if user.role=="admin" %}<a href="/admin">الإدارة</a>{% endif %}<form method="post" action="/logout" style="display:inline"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn soft">خروج</button></form>{% else %}<a href="/login">دخول</a><a class="btn" href="/register">إنشاء حساب</a>{% endif %}</div></div></nav>
<main><div class="wrap">{{body | safe}}</div></main><footer><div class="wrap">© مسار للنقل الدولي — نموذج تشغيل مبدئي. لا يتم تحصيل أي أموال عبر هذه الصفحة دون تفعيل وسيلة دفع معتمدة.</div></footer></body></html>"""
env=Environment(autoescape=select_autoescape(default_for_string=True,default=True))
def amt(n):return cents(n)
env.filters["amt"]=amt
def action(url,token,label,extra="",kind=""):
    return f'<form method="post" action="{html.escape(url,quote=True)}"><input type="hidden" name="csrf" value="{html.escape(token,quote=True)}">{extra}<button class="btn {kind}">{html.escape(label)}</button></form>'
@app.get("/",response_class=HTMLResponse)
def index(req:Request,q:str=""):
    with session() as db:
        rows=db.scalars(select(Listing).where(Listing.status=="open").order_by(Listing.id.desc()).limit(100)).all()
        rows=[{"id":x.id,"title":x.title,"origin":x.origin_city+"، "+x.origin_country,"dest":x.dest_city+"، "+x.dest_country,"kg":x.weight_kg,"description":x.description,"photo_id":db.scalar(select(Photo.id).where(Photo.listing_id==x.id).order_by(Photo.id.desc()).limit(1))} for x in rows if q.casefold() in (x.title+" "+x.origin_city+" "+x.dest_city).casefold()]
    body=template("""<header class="hero" style="border-radius:20px;padding:35px;margin-bottom:23px"><span class="tag">منصة الشحن والتجارة الدولية</span><h1>من الحمولة إلى التسليم<br>في مكان واحد 🚛</h1><p>سوق حمولات فعلي لتجربة حسابات التجار والناقلين والحجوزات وعرض رسوم المنصة بوضوح على الطرفين.</p><div class="actions"><a class="btn white" href="/new">انشر حمولة</a><a class="btn soft" href="/register">انضم إلى المنصة</a></div></header><section class="panel"><h2>ابحث عن حمولة</h2><form method="get" class="flex"><input class="input" name="q" value="{{q}}" placeholder="بلد، مدينة، أو نوع البضاعة" style="flex:1;min-width:180px"><button class="btn">بحث</button></form></section><h2>الحمولات المنشورة</h2><div class="cards">{% for l in listings %}<article class="card">{% if l.photo_id %}<a href="/listing/{{l.id}}"><img class="listing-photo" loading="lazy" alt="صورة للحمولة" src="/photo/{{l.photo_id}}"></a>{% else %}<a href="/listing/{{l.id}}" class="photo-placeholder" aria-label="تفاصيل الحمولة"><span>🚛</span></a>{% endif %}<span class="tag">حمولة #{{l.id}}</span><h3>{{l.title}}</h3><p>📍 {{l.origin}} ← {{l.dest}}</p><p class="muted">الوزن: {{l.kg}} كغ</p><p class="muted">{{l.description[:100]}}</p><a class="btn soft" href="/listing/{{l.id}}">التفاصيل والعروض</a></article>{% else %}<article class="card"><h3>لا توجد حمولات منشورة بعد</h3><p class="muted">يمكن للتجار إضافة الحمولة الأولى.</p></article>{% endfor %}</div>""",q=q[:80],listings=rows)
    return page(req,"الرئيسية",body)
@app.get("/register",response_class=HTMLResponse)
def reg_page(req:Request):
    body=template("""<section class="panel form"><h2>إنشاء حساب</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>الاسم</label><input class="input" name="name" required maxlength="90"><label>البريد الإلكتروني</label><input class="input" name="email" type="email" required maxlength="180"><label>اسم الشركة (اختياري)</label><input class="input" name="company" maxlength="120"><label>نوع الحساب</label><select name="role" class="input"><option value="trader">تاجر / صاحب حمولة</option><option value="carrier">سائق / شركة نقل</option></select><label>كلمة المرور (12 حرفاً على الأقل)</label><input class="input" name="password" type="password" required minlength="12" maxlength="200"><p class="muted">التسجيل لا يعني التحقق من الهوية. استخدم بيانات تجريبية فقط.</p><button class="btn">إنشاء الحساب</button></form></section>""",csrf=csrf(req))
    return page(req,"تسجيل",body)
@app.post("/register")
async def register(req:Request):
    form=await req.form()
    if bad:=require_form(req,form):return bad
    name=str(form.get("name","")).strip()[:90];email=str(form.get("email","")).strip().lower()[:180]
    role=str(form.get("role",""));pwd=str(form.get("password",""));company=str(form.get("company","")).strip()[:120]
    if len(name)<2 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or role not in ("trader","carrier") or not 12<=len(pwd)<=200:return error(req,"بيانات التسجيل غير صالحة.")
    try:
        with session() as db:
            u=User(name=name,email=email,hash=password_hash(pwd),role=role,company=company)
            db.add(u);db.flush();uid=u.id
    except IntegrityError:return error(req,"البريد مسجل مسبقاً.")
    req.session.clear();req.session["uid"]=uid;return go("/dashboard")
@app.get("/login",response_class=HTMLResponse)
def login_page(req:Request):
    return page(req,"دخول",template("""<section class="panel form"><h2>تسجيل الدخول</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>البريد الإلكتروني</label><input class="input" name="email" type="email" required><label>كلمة المرور</label><input class="input" name="password" type="password" required><div class="actions"><button class="btn">دخول</button><a class="btn soft" href="/register">حساب جديد</a></div></form></section>""",csrf=csrf(req)))
@app.post("/login")
async def login(req:Request):
    form=await req.form()
    if bad:=require_form(req,form):return bad
    with session() as db:
        u=db.scalar(select(User).where(User.email==str(form.get("email","")).strip().lower()))
        if not u or not password_ok(str(form.get("password","")),u.hash):return error(req,"البريد أو كلمة المرور غير صحيحين.",401)
        uid=u.id
    req.session.clear();req.session["uid"]=uid;return go("/dashboard")
@app.post("/logout")
async def logout(req:Request):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    req.session.clear();return go("/")
@app.get("/new",response_class=HTMLResponse)
def new_page(req:Request):
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        if u.role!="trader":return error(req,"النشر مخصص للتجار.",403)
    body=template("""<section class="panel form"><h2>إضافة حمولة</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>عنوان الحمولة</label><input class="input" name="title" maxlength="160" required placeholder="مثال: منسوجات معبأة"><div class="row"><div><label>بلد الانطلاق</label><input class="input" name="origin_country" required maxlength="70"></div><div><label>مدينة الانطلاق</label><input class="input" name="origin_city" required maxlength="90"></div></div><div class="row"><div><label>بلد الوصول</label><input class="input" name="dest_country" required maxlength="70"></div><div><label>مدينة الوصول</label><input class="input" name="dest_city" required maxlength="90"></div></div><label>الوزن بالكيلوغرام</label><input class="input" name="weight_kg" type="number" min="1" max="1000000" required><label>وصف الحمولة</label><textarea class="input" name="description" rows="4" maxlength="1500"></textarea><p class="muted">يُعرض السعر والرسوم عند اختيار عرض الناقل، وعملة الحجز في هذه النسخة USD.</p><button class="btn">نشر الحمولة</button></form></section>""",csrf=csrf(req))
    return page(req,"نشر حمولة",body)
@app.post("/new")
async def create_listing(req:Request):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        if u.role!="trader":return error(req,"غير مصرح.",403)
        fields={k:str(f.get(k,"")).strip() for k in ("title","origin_country","origin_city","dest_country","dest_city","description")}
        if any(len(fields[k])<2 or len(fields[k])>n for k,n in (("title",160),("origin_country",70),("origin_city",90),("dest_country",70),("dest_city",90))) or len(fields["description"])>1500:return error(req,"تحقق من تفاصيل الحمولة.")
        try:weight=int(str(f.get("weight_kg","")))
        except ValueError:return error(req,"الوزن غير صالح.")
        if not 1<=weight<=1000000:return error(req,"الوزن غير صالح.")
        obj=Listing(trader_id=u.id,weight_kg=weight,**fields)
        db.add(obj);db.flush();ident=obj.id;log(db,u.id,"listing",ident,"created")
    return go(f"/listing/{ident}")
@app.get("/listing/{ident}",response_class=HTMLResponse)
def listing_page(req:Request,ident:int):
    with session() as db:
        l=db.get(Listing,ident)
        if not l:return error(req,"الحمولة غير موجودة.",404)
        u=current(req,db)
        items=db.scalars(select(Offer).where(Offer.listing_id==ident).order_by(Offer.id.desc())).all()
        uname={o.carrier_id:db.get(User,o.carrier_id).name for o in items}
        data={"id":l.id,"title":l.title,"from_":f"{l.origin_city}، {l.origin_country}","to":f"{l.dest_city}، {l.dest_country}","weight":l.weight_kg,"description":l.description,"status":l.status,"trader_id":l.trader_id}
        offers=[{"id":o.id,"carrier":uname[o.carrier_id],"price":cents(o.price_cents),"note":o.note,"status":o.status,"carrier_id":o.carrier_id} for o in items]
        own=bool(u and u.id==l.trader_id);carrier=bool(u and u.role=="carrier" and u.id!=l.trader_id)
        booked=db.scalar(select(Booking).where(Booking.listing_id==ident))
        booking_id=booked.id if booked else None
        photos=[p.id for p in db.scalars(select(Photo).where(Photo.listing_id==ident).order_by(Photo.id.desc())).all()]
        offered=bool(u and any(o.carrier_id==u.id for o in items))
    body=template("""<section class="panel"><span class="tag">حمولة #{{l.id}} | {{l.status}}</span><h1>{{l.title}}</h1>{% if photos %}<div class="gallery">{% for pid in photos %}<a href="/photo/{{pid}}" target="_blank" rel="noopener"><img src="/photo/{{pid}}" loading="lazy" alt="صورة للحمولة"></a>{% endfor %}</div>{% endif %}<p>📍 {{l.from_}} ← {{l.to}}</p><p>⚖️ {{l.weight}} كغ</p><p>{{l.description}}</p></section>
{% if own and photos|length < 5 %}<section class="panel form"><h2>📸 إضافة صور الحمولة</h2><p class="muted">ارفع صورة حقيقية توضح الحمولة دون وجوه أشخاص أو وثائق شخصية. يُسمح حتى 5 صور، بصيغة JPG أو PNG أو WebP وبحجم لا يتجاوز 1 ميغابايت للصورة.</p><form method="post" enctype="multipart/form-data" action="/listing/{{l.id}}/photo"><input type="hidden" name="csrf" value="{{csrf}}"><input class="input" name="photo" type="file" accept="image/jpeg,image/png,image/webp" required><div class="actions"><button class="btn">إضافة الصورة</button></div></form></section>{% endif %}
{% if booked %}<section class="panel"><p>تم اختيار الناقل لهذه الحمولة.</p><a class="btn" href="/booking/{{booked}}">تفاصيل الحجز</a></section>{% endif %}
{% if carrier and l.status=="open" and not offered %}<section class="panel form"><h2>تقديم عرض نقل</h2><form method="post" action="/listing/{{l.id}}/offer"><input type="hidden" name="csrf" value="{{csrf}}"><label>أجرة النقل بالدولار USD</label><input class="input" type="number" name="price" step="0.01" min="1" max="100000000" required><label>تفاصيل العرض</label><textarea class="input" name="note" maxlength="500"></textarea><p class="muted">عمولة الناقل {{carrier_pct}}% تُخصم من الأجرة عند إتمام الحجز. التاجر يدفع أجرة النقل إضافة إلى عمولة {{trader_pct}}%. قد توجد رسوم خارج المنصة.</p><button class="btn">إرسال عرض السعر</button></form></section>{% endif %}
{% if offered %}<p class="tag">قدمت عرضاً بالفعل على هذه الحمولة.</p>{% endif %}
{% if own %}<section class="panel"><h2>عروض الناقلين</h2>{% for o in offers %}<div class="line flex"><div><b>{{o.carrier}}</b> — <span class="price">{{o.price}} USD</span><p class="muted">{{o.note}} | الحالة: {{o.status}}</p></div>{% if l.status=="open" and o.status=="pending" %}<form method="post" action="/offer/{{o.id}}/accept"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn">قبول العرض والحجز</button></form>{% endif %}</div>{% else %}<p class="muted">لم تصل عروض بعد.</p>{% endfor %}</section>{% endif %}""",l=data,offers=offers,booked=booking_id,photos=photos,own=own,carrier=carrier,offered=offered,csrf=csrf(req),carrier_pct=CARRIER_BPS/100,trader_pct=TRADER_BPS/100)
    return page(req,"تفاصيل الحمولة",body)
@app.post("/listing/{ident}/offer")
async def offer_submit(req:Request,ident:int):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    price=money(f.get("price"))
    if price is None or price<100:return error(req,"السعر غير صالح.")
    with session() as db:
        u=current(req,db);l=db.get(Listing,ident)
        if not u:return login_redirect()
        if u.role!="carrier" or not l or l.status!="open" or l.trader_id==u.id:return error(req,"لا يمكن تقديم العرض.",403)
        if db.scalar(select(Offer).where(Offer.listing_id==ident,Offer.carrier_id==u.id)):return error(req,"قدمت عرضاً مسبقاً.")
        o=Offer(listing_id=ident,carrier_id=u.id,price_cents=price,note=str(f.get("note","")).strip()[:500])
        db.add(o);db.flush();log(db,u.id,"offer",o.id,"submitted")
    return go(f"/listing/{ident}")
@app.post("/offer/{ident}/accept")
async def accept(req:Request,ident:int):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    with session() as db:
        u=current(req,db);o=db.get(Offer,ident)
        if not u:return login_redirect()
        if not o:return error(req,"العرض غير موجود.",404)
        l=db.get(Listing,o.listing_id)
        if l.trader_id!=u.id or l.status!="open" or o.status!="pending":return error(req,"العرض غير متاح.",403)
        tf=fee(o.price_cents,TRADER_BPS);cf=fee(o.price_cents,CARRIER_BPS)
        if o.price_cents-cf<=0:return error(req,"خطأ بحساب العمولة.")
        b=Booking(listing_id=l.id,offer_id=o.id,trader_id=u.id,carrier_id=o.carrier_id,freight_cents=o.price_cents,trader_fee_cents=tf,carrier_fee_cents=cf,total_due_cents=o.price_cents+tf,carrier_due_cents=o.price_cents-cf)
        db.add(b);db.flush();l.status="assigned";o.status="accepted"
        for other in db.scalars(select(Offer).where(Offer.listing_id==l.id,Offer.id!=o.id)):other.status="declined"
        ident=b.id;log(db,u.id,"booking",ident,"created")
    return go(f"/booking/{ident}")
@app.get("/dashboard",response_class=HTMLResponse)
def dashboard(req:Request):
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        if u.role=="admin":return go("/admin")
        listings=db.scalars(select(Listing).where(Listing.trader_id==u.id).order_by(Listing.id.desc()).limit(50)).all() if u.role=="trader" else []
        offers=db.scalars(select(Offer).where(Offer.carrier_id==u.id).order_by(Offer.id.desc()).limit(50)).all() if u.role=="carrier" else []
        bookings=db.scalars(select(Booking).where((Booking.trader_id==u.id)|(Booking.carrier_id==u.id)).order_by(Booking.id.desc()).limit(70)).all()
        bs=[{"id":b.id,"status":b.status,"freight":cents(b.freight_cents),"payment":b.payment_status} for b in bookings]
        ls=[{"id":l.id,"title":l.title,"status":l.status} for l in listings]
        ofs=[{"id":o.id,"listing_id":o.listing_id,"price":cents(o.price_cents),"status":o.status} for o in offers]
        name=u.name;role=u.role
    body=template("""<section class="panel"><h1>مرحباً، {{name}}</h1><span class="tag">{{"تاجر" if role=="trader" else "ناقل"}}</span><p class="muted">هنا تتبع حجوزاتك وعروضك. لا تضع معلومات حساسة في النسخة التجريبية.</p>{% if role=="trader" %}<a class="btn" href="/new">نشر حمولة جديدة</a>{% else %}<a class="btn" href="/">ابحث عن حمولات</a>{% endif %}</section>
<section class="panel"><h2>الحجوزات</h2>{% for b in bookings %}<div class="line flex"><span>حجز #{{b.id}} — {{b.status}} — الدفع: {{b.payment}}</span><a class="btn soft" href="/booking/{{b.id}}">عرض التفاصيل</a></div>{% else %}<p class="muted">لا توجد حجوزات بعد.</p>{% endfor %}</section>
{% if role=="trader" %}<section class="panel"><h2>حمولاتي</h2>{% for l in listings %}<div class="line flex"><span>{{l.title}} — {{l.status}}</span><a href="/listing/{{l.id}}">عرض</a></div>{% else %}<p class="muted">لم تنشر حمولة بعد.</p>{% endfor %}</section>{% else %}<section class="panel"><h2>عروضي</h2>{% for o in offers %}<div class="line flex"><span>{{o.price}} USD — {{o.status}}</span><a href="/listing/{{o.listing_id}}">عرض الحمولة</a></div>{% else %}<p class="muted">لم تقدم عروضاً بعد.</p>{% endfor %}</section>{% endif %}""",name=name,role=role,bookings=bs,listings=ls,offers=ofs)
    return page(req,"حسابي",body)
@app.get("/booking/{ident}",response_class=HTMLResponse)
def booking_page(req:Request,ident:int):
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        b=db.get(Booking,ident)
        if not b:return error(req,"الحجز غير موجود.",404)
        if u.id not in (b.trader_id,b.carrier_id) and u.role!="admin":return error(req,"هذا الحجز خاص بطرفيه.",403)
        l=db.get(Listing,b.listing_id)
        claims=db.scalars(select(PaymentClaim).where(PaymentClaim.booking_id==b.id).order_by(PaymentClaim.id.desc())).all()
        data={"id":b.id,"title":l.title,"status":b.status,"pay":b.payment_status,"freight":cents(b.freight_cents),"trader_fee":cents(b.trader_fee_cents),"carrier_fee":cents(b.carrier_fee_cents),"total":cents(b.total_due_cents),"carrier_due":cents(b.carrier_due_cents),"trader":b.trader_id,"carrier":b.carrier_id}
        receipts=[{"id":c.id,"ref":c.transfer_ref,"amount":cents(c.amount_cents),"status":c.status} for c in claims]
        uid=u.id;role=u.role
    body=template("""<section class="panel"><span class="tag">الحجز #{{b.id}}</span><h1>{{b.title}}</h1><p>حالة الرحلة: <b>{{b.status}}</b> | حالة الدفع: <b>{{b.pay}}</b></p></section>
<section class="panel"><h2>تفاصيل السعر وعمولة المنصة</h2><div class="line flex"><span>أجرة الشحن المتفق عليها</span><b>{{b.freight}} USD</b></div><div class="line flex"><span>رسوم التاجر ({{trader_pct}}%)</span><b>{{b.trader_fee}} USD</b></div><div class="line flex"><span>الإجمالي المطلوب من التاجر</span><b class="price">{{b.total}} USD</b></div><div class="line flex"><span>رسوم الناقل ({{carrier_pct}}%)</span><b>{{b.carrier_fee}} USD</b></div><div class="line flex"><span>صافي مستحقات الناقل بعد عمولة المنصة</span><b>{{b.carrier_due}} USD</b></div><p class="muted">هذه القيم مستحقات محاسبية وليست تأكيداً بتحصيل أموال أو تحويلها. رسوم تحويل العملة ومعالجة الدفع والضرائب إن وجدت تُحدّد منفصلة قبل الدفع الفعلي.</p></section>
{% if uid==b.trader and b.status=="awaiting_payment" %}<section class="panel"><h2>الدفع عبر شام كاش</h2>{% if enabled %}<p>حساب المستفيد: <b>{{receiver}}</b></p><p>أرسل {{b.total}} USD وفق السعر وطريقة التسوية المعتمدين مع إدارة المنصة، ثم أضف رقم التحويل للتحقق اليدوي. لا يُعتمد الحجز بمجرد إرسال الرقم.</p><form method="post" action="/booking/{{b.id}}/claim"><input type="hidden" name="csrf" value="{{csrf}}"><label>مرجع تحويل شام كاش</label><input class="input" name="reference" maxlength="120" minlength="6" required><label>المبلغ المحوّل بالعملة المتفق عليها، USD</label><input class="input" name="amount" type="number" step="0.01" min="0.01" required><div class="actions"><button class="btn">إرسال طلب مراجعة الدفع</button></div></form>{% else %}<p class="muted">الدفع غير مفعّل في النسخة التجريبية. لا تحوّل أي مبلغ بناءً على هذه الصفحة. بعد تفعيل حساب الاستلام والتحقق المالي، سيظهر هنا نموذج طلب مراجعة الدفع.</p>{% endif %}</section>{% endif %}
{% if receipts %}<section class="panel"><h2>طلبات مراجعة الدفع</h2>{% for c in receipts %}<div class="line">#{{c.id}} — {{c.amount}} USD — {{c.status}} — المرجع: {{c.ref}}</div>{% endfor %}</section>{% endif %}
{% if uid==b.carrier and b.status=="confirmed" %}<section class="panel"><p>عند استلام الحمولة ابدأ الرحلة.</p><form method="post" action="/booking/{{b.id}}/advance"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn">تأكيد الانطلاق</button></form></section>{% elif uid==b.carrier and b.status=="in_transit" %}<section class="panel"><p>عند الوصول اطلب تأكيد التسليم من التاجر.</p><form method="post" action="/booking/{{b.id}}/advance"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn">تأكيد الوصول</button></form></section>{% elif uid==b.trader and b.status=="delivered" %}<section class="panel"><p>تأكد من استلام البضاعة قبل تأكيد إتمام الرحلة.</p><form method="post" action="/booking/{{b.id}}/advance"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn">تأكيد استلام الحمولة وإتمام الرحلة</button></form></section>{% endif %}""",b=data,receipts=receipts,uid=uid,role=role,trader_pct=TRADER_BPS/100,carrier_pct=CARRIER_BPS/100,enabled=PAYMENTS_ENABLED,receiver=PAYMENT_RECEIVER,csrf=csrf(req))
    return page(req,"الحجز",body)
@app.post("/booking/{ident}/claim")
async def claim(req:Request,ident:int):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    if not PAYMENTS_ENABLED:return error(req,"لا يوجد حساب استلام مفعّل. لا ترسل أي تحويل.",403)
    amount=money(f.get("amount"));ref=str(f.get("reference","")).strip()
    with session() as db:
        u=current(req,db);b=db.get(Booking,ident)
        if not u:return login_redirect()
        if not b or b.trader_id!=u.id or b.status!="awaiting_payment" or b.payment_status not in ("not_submitted","rejected"):return error(req,"لا يمكن تقديم طلب المراجعة.",403)
        if not 6<=len(ref)<=120 or amount!=b.total_due_cents:return error(req,"تأكد من رقم المرجع والمبلغ المتفق عليه.")
        c=PaymentClaim(booking_id=b.id,submitted_by=u.id,transfer_ref=ref,amount_cents=amount)
        db.add(c);db.flush();b.payment_status="pending_review";log(db,u.id,"payment_claim",c.id,"submitted_unverified")
    return go(f"/booking/{ident}")
@app.post("/booking/{ident}/advance")
async def advance(req:Request,ident:int):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    with session() as db:
        u=current(req,db);b=db.get(Booking,ident)
        if not u:return login_redirect()
        if not b or b.payment_status!="verified":return error(req,"لا يمكن التقدم قبل التحقق من الدفع.",403)
        steps={"confirmed":("in_transit",b.carrier_id),"in_transit":("delivered",b.carrier_id),"delivered":("completed",b.trader_id)}
        step=steps.get(b.status)
        if not step or step[1]!=u.id:return error(req,"ليس لديك صلاحية لهذه المرحلة.",403)
        b.status=step[0];log(db,u.id,"booking",b.id,step[0])
        if b.status=="completed":db.get(Listing,b.listing_id).status="completed"
    return go(f"/booking/{ident}")
@app.get("/admin/setup",response_class=HTMLResponse)
def setup_page(req:Request):
    with session() as db:
        existing=db.scalar(select(func.count()).select_from(User).where(User.role=="admin"))
    if existing or not SETUP_TOKEN:return error(req,"إعداد المدير غير متاح.",403)
    body=template("""<section class="panel form"><h2>تهيئة مدير المنصة لمرة واحدة</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>رمز التهيئة الخاص</label><input class="input" type="password" name="setup_token" required><label>اسم المدير</label><input class="input" name="name" maxlength="90" required><label>البريد</label><input class="input" name="email" type="email" required><label>كلمة المرور (12 حرفاً على الأقل)</label><input class="input" name="password" type="password" minlength="12" maxlength="200" required><button class="btn" style="margin-top:14px">تهيئة الحساب</button></form></section>""",csrf=csrf(req))
    return page(req,"تهيئة الإدارة",body)
@app.post("/admin/setup")
async def setup(req:Request):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    if not SETUP_TOKEN or not hmac.compare_digest(str(f.get("setup_token","")),SETUP_TOKEN):return error(req,"رمز التهيئة غير صحيح.",403)
    email=str(f.get("email","")).strip().lower()[:180];pwd=str(f.get("password",""));name=str(f.get("name","")).strip()[:90]
    if len(name)<2 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or not 12<=len(pwd)<=200:return error(req,"بيانات المدير غير صالحة.")
    with session() as db:
        if db.scalar(select(func.count()).select_from(User).where(User.role=="admin")):return error(req,"يوجد مدير بالفعل.",403)
        if db.scalar(select(User).where(User.email==email)):return error(req,"استخدم بريداً لم يسجل سابقاً.")
        u=User(name=name,email=email,hash=password_hash(pwd),role="admin");db.add(u);db.flush();uid=u.id;log(db,uid,"user",uid,"first_admin")
    req.session.clear();req.session["uid"]=uid;return go("/admin")
@app.get("/admin",response_class=HTMLResponse)
def admin_page(req:Request):
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        if u.role!="admin":return error(req,"غير مصرح.",403)
        bs=db.scalars(select(Booking).order_by(Booking.id.desc()).limit(80)).all()
        cs=db.scalars(select(PaymentClaim).where(PaymentClaim.status=="pending").order_by(PaymentClaim.id.desc()).limit(50)).all()
        stats={"bookings":db.scalar(select(func.count()).select_from(Booking)) or 0,"completed":db.scalar(select(func.count()).select_from(Booking).where(Booking.status=="completed")) or 0,"trader_fees":sum(b.trader_fee_cents for b in bs if b.status=="completed"),"carrier_fees":sum(b.carrier_fee_cents for b in bs if b.status=="completed")}
        bookings=[{"id":b.id,"status":b.status,"pay":b.payment_status,"freight":cents(b.freight_cents),"fee":cents(b.trader_fee_cents+b.carrier_fee_cents)} for b in bs]
        claims=[{"id":c.id,"bid":c.booking_id,"ref":c.transfer_ref,"amount":cents(c.amount_cents)} for c in cs]
    body=template("""<section class="panel"><h1>لوحة إدارة مسار للنقل الدولي</h1><p class="muted">إدارة رسوم الطرفين والحجوزات وطلبات مراجعة الدفع. لا تتعامل مع المرجع المدخل باعتباره إيصالاً معتمداً.</p><div class="cards"><div class="card"><h3>عدد الحجوزات</h3><span class="price">{{stats.bookings}}</span></div><div class="card"><h3>الحجوزات المكتملة</h3><span class="price">{{stats.completed}}</span></div><div class="card"><h3>عمولات مرتبطة بحجوزات مكتملة</h3><span class="price">{{(stats.trader_fees+stats.carrier_fees)|amt}} USD</span><p class="muted">قيمة محاسبية وليست رصيداً بنكياً مثبتاً.</p></div></div></section>
<section class="panel"><h2>طلبات التحقق من التحويل</h2>{% if not enabled %}<p class="muted">التحصيل معطل حتى تعيين حساب الاستلام وتفعيل خيار الدفع في إعدادات الخادم.</p>{% endif %}{% for c in claims %}<div class="line"><b>الطلب #{{c.id}} للحجز #{{c.bid}}</b> — {{c.amount}} USD<br>المرجع المرسل: {{c.ref}}<p class="muted">تحقق من التحويل في حسابك الرسمي بشكل مستقل قبل الموافقة.</p><div class="actions"><form method="post" action="/admin/payment/{{c.id}}/verify"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn">تأكيد بعد التحقق المستقل</button></form><form method="post" action="/admin/payment/{{c.id}}/reject"><input type="hidden" name="csrf" value="{{csrf}}"><button class="btn danger">رفض</button></form></div></div>{% else %}<p class="muted">لا توجد طلبات معلقة.</p>{% endfor %}</section>
<section class="panel"><h2>الحجوزات الأخيرة</h2><div class="tablewrap"><table><tr><th>رقم</th><th>حالة الرحلة</th><th>حالة الدفع</th><th>أجرة النقل</th><th>عمولة الطرفين</th><th>التفاصيل</th></tr>{% for b in bookings %}<tr><td>#{{b.id}}</td><td>{{b.status}}</td><td>{{b.pay}}</td><td>{{b.freight}} USD</td><td>{{b.fee}} USD</td><td><a href="/booking/{{b.id}}">عرض</a></td></tr>{% endfor %}</table></div></section>""",stats=stats,bookings=bookings,claims=claims,csrf=csrf(req),enabled=PAYMENTS_ENABLED)
    return page(req,"لوحة الإدارة",body)
@app.post("/admin/payment/{ident}/{decision}")
async def review(req:Request,ident:int,decision:str):
    f=await req.form()
    if bad:=require_form(req,f):return bad
    if decision not in ("verify","reject"):return error(req,"قرار غير صالح.",404)
    with session() as db:
        u=current(req,db)
        if not u:return login_redirect()
        if u.role!="admin":return error(req,"غير مصرح.",403)
        claim=db.get(PaymentClaim,ident)
        if not claim or claim.status!="pending":return error(req,"طلب مراجعة غير متاح.",404)
        b=db.get(Booking,claim.booking_id)
        if not b or b.payment_status!="pending_review" or b.status!="awaiting_payment":return error(req,"حالة الحجز غير متوافقة.")
        if decision=="verify" and not PAYMENTS_ENABLED:return error(req,"لا يمكن تأكيد الدفع في الوضع التجريبي.",403)
        claim.status="verified" if decision=="verify" else "rejected"
        claim.reviewed_by=u.id;claim.reviewed=utc()
        b.payment_status=claim.status
        if decision=="verify":b.status="confirmed"
        log(db,u.id,"payment_claim",claim.id,"manually_"+claim.status)
    return go("/admin")
@app.get("/photo/{ident}")
def serve_photo(ident:int):
    with session() as db:
        photo=db.get(Photo,ident)
        if not photo:return Response(status_code=404)
        local_data=bytes(photo.data or b"")
        mime=photo.mime
    if local_data:
        return Response(local_data,media_type=mime,headers={"Cache-Control":"public, max-age=3600","X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; sandbox"})
    try:
        remote=fetch_photo_remote(ident)
    except Exception as exc:
        print("Masar remote photo warning:",repr(exc));remote=None
    if not remote:return Response(status_code=404)
    mime,data=remote
    try:
        with session() as db:
            p=db.get(Photo,ident)
            if p:p.data=data
    except Exception:
        pass
    return Response(data,media_type=mime,headers={"Cache-Control":"public, max-age=3600","X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; sandbox"})

@app.post("/listing/{ident}/photo")
async def upload_photo(req:Request,ident:int):
    try:f=await req.form(max_part_size=1400000)
    except Exception:return error(req,"الملف أكبر من الحجم المسموح أو غير صالح.",413)
    if bad:=require_form(req,f):return bad
    uploaded=f.get("photo")
    if not hasattr(uploaded,"read"):return error(req,"اختر صورة صالحة.")
    try:data=await uploaded.read(1000002)
    finally:await uploaded.close()
    if not data or len(data)>1000000:return error(req,"الحجم الأقصى للصورة هو 1 ميغابايت.",413)
    if data.startswith(bytes.fromhex("ffd8ff")) and data.endswith(bytes.fromhex("ffd9")):mime="image/jpeg"
    elif data.startswith(bytes.fromhex("89504e470d0a1a0a")) and b"IEND" in data[-24:]:mime="image/png"
    elif data.startswith(b"RIFF") and data[8:12]==b"WEBP":mime="image/webp"
    else:return error(req,"يُسمح فقط بصور JPG وPNG وWebP الصالحة.")
    with session() as db:
        u=current(req,db);l=db.get(Listing,ident)
        if not u:return login_redirect()
        if not l or l.trader_id!=u.id or u.role!="trader":return error(req,"إضافة الصور متاحة لصاحب الحمولة فقط.",403)
        if (db.scalar(select(func.count()).select_from(Photo).where(Photo.listing_id==ident)) or 0)>=5:return error(req,"الحد الأقصى 5 صور لكل حمولة.")
        p=Photo(listing_id=l.id,owner_id=u.id,mime=mime,data=data)
        db.add(p);db.flush();log(db,u.id,"photo",p.id,"uploaded")
        photo_id=p.id;owner_id=u.id;listing_id=l.id
    if REMOTE_STATE_ENABLED:
        try:
            persist_photo_remote(photo_id,listing_id,owner_id,mime,data)
        except Exception as exc:
            print("Masar photo persistence warning:",repr(exc))
            with session() as db:
                doomed=db.get(Photo,photo_id)
                if doomed:db.delete(doomed)
            return error(req,"تعذر حفظ الصورة في التخزين الدائم. حاول مرة أخرى.",503)
    return go(f"/listing/{ident}")

@app.get("/health")
def health():
    with session() as db:db.scalar(select(func.count()).select_from(User))
    return {"status":"ok","database":"supabase_persistent" if REMOTE_STATE_ENABLED else ("preview_ephemeral" if DB_IS_PREVIEW else "external")}
