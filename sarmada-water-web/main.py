from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from passlib.hash import pbkdf2_sha256
import sqlite3, os, secrets
from datetime import datetime

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'data','sarmada_web.db')
os.makedirs(os.path.dirname(DB),exist_ok=True)
app=FastAPI(title='المحتسب للمياه - محطة سرمدا')
app.add_middleware(SessionMiddleware, secret_key=os.environ.get('SESSION_SECRET',secrets.token_hex(32)), https_only=True, same_site='lax')
app.mount('/static',StaticFiles(directory=os.path.join(BASE,'static')),name='static')

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 c=db(); c.executescript("""
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL, display TEXT, role TEXT DEFAULT 'manager', active INTEGER DEFAULT 1, created TEXT);
 CREATE TABLE IF NOT EXISTS subscribers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, meter TEXT UNIQUE NOT NULL, sector TEXT DEFAULT '', phone TEXT DEFAULT '', address TEXT DEFAULT '', previous REAL DEFAULT 0, current REAL DEFAULT 0, rate REAL DEFAULT 0, debt REAL DEFAULT 0, active INTEGER DEFAULT 1, sort_order REAL DEFAULT 0, notes TEXT DEFAULT '', created TEXT);
 CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, sub_id INTEGER NOT NULL, month TEXT NOT NULL, previous REAL DEFAULT 0, current REAL DEFAULT 0, qty REAL DEFAULT 0, rate REAL DEFAULT 0, amount REAL DEFAULT 0, created TEXT, UNIQUE(sub_id,month), FOREIGN KEY(sub_id) REFERENCES subscribers(id));
 CREATE TABLE IF NOT EXISTS month_tariffs(sub_id INTEGER NOT NULL, month TEXT NOT NULL, rate REAL NOT NULL, updated TEXT, PRIMARY KEY(sub_id,month), FOREIGN KEY(sub_id) REFERENCES subscribers(id));
 CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, sub_id INTEGER NOT NULL, amount REAL NOT NULL, month TEXT DEFAULT '', method TEXT DEFAULT 'نقدي', note TEXT DEFAULT '', created TEXT, FOREIGN KEY(sub_id) REFERENCES subscribers(id));
 CREATE TABLE IF NOT EXISTS cash(id INTEGER PRIMARY KEY, kind TEXT, amount REAL, currency TEXT DEFAULT 'SYP', description TEXT DEFAULT '', created TEXT);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, username TEXT, action TEXT, details TEXT, created TEXT);
 """)
 if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
  c.execute('INSERT INTO users(username,password_hash,display,role,created) VALUES(?,?,?,?,?)',('admin',pbkdf2_sha256.hash(os.environ.get('INITIAL_ADMIN_PASSWORD','ChangeMe-1234')),'مدير النظام','manager',datetime.now().isoformat(timespec='seconds')))
 c.commit(); c.close()
init()

def who(request): return request.session.get('user')
def need(request):
 if not who(request): raise HTTPException(401,'يلزم تسجيل الدخول')
def audit(user,action,details=''):
 c=db(); c.execute('INSERT INTO audit(username,action,details,created) VALUES(?,?,?,?)',(user,action,details,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close()

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
 from fastapi.templating import Jinja2Templates
 return Jinja2Templates(directory=os.path.join(BASE,'templates')).TemplateResponse('index.html',{'request':request,'user':who(request)})
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/login')
def login(request:Request, username:str=Form(...), password:str=Form(...)):
 c=db(); u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone(); c.close()
 if not u or not pbkdf2_sha256.verify(password,u['password_hash']): return RedirectResponse('/?error=1',303)
 request.session['user']={'username':u['username'],'display':u['display'],'role':u['role']}; audit(username,'تسجيل دخول'); return RedirectResponse('/',303)
@app.post('/logout')
def logout(request:Request): request.session.clear(); return RedirectResponse('/',303)
@app.get('/api/summary')
def summary(request:Request):
 need(request); c=db(); out={'subscribers':c.execute('SELECT count(*) n FROM subscribers WHERE active=1').fetchone()['n'],'sectors':c.execute("SELECT count(DISTINCT sector) n FROM subscribers WHERE active=1 AND sector<>''").fetchone()['n'],'due':c.execute('SELECT COALESCE(sum(debt),0) n FROM subscribers WHERE active=1').fetchone()['n'],'payments':c.execute("SELECT COALESCE(sum(amount),0) n FROM payments WHERE substr(created,1,7)=?",(datetime.now().strftime('%Y-%m'),)).fetchone()['n']}; c.close(); return out
@app.get('/api/subscribers')
def subscribers(request:Request,q:str=''):
 need(request); c=db(); rows=c.execute('SELECT * FROM subscribers WHERE active=1 AND (name LIKE ? OR meter LIKE ? OR sector LIKE ?) ORDER BY sort_order,id LIMIT 1000',(f'%{q}%',f'%{q}%',f'%{q}%')).fetchall(); c.close(); return [dict(x) for x in rows]
@app.post('/api/subscribers')
def add_subscriber(request:Request,payload:dict):
 need(request); name=payload.get('name','').strip(); meter=str(payload.get('meter','')).strip()
 if not name or not meter: raise HTTPException(400,'الاسم ورقم العداد مطلوبان')
 c=db()
 try:
  c.execute('INSERT INTO subscribers(name,meter,sector,phone,address,previous,current,rate,debt,sort_order,notes,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(name,meter,payload.get('sector',''),payload.get('phone',''),payload.get('address',''),float(payload.get('previous') or 0),float(payload.get('current') or 0),float(payload.get('rate') or 0),float(payload.get('debt') or 0),float(payload.get('sort_order') or 0),payload.get('notes',''),datetime.now().isoformat(timespec='seconds'))); c.commit(); audit(who(request)['username'],'إضافة مشترك',meter)
 except sqlite3.IntegrityError: c.close(); raise HTTPException(409,'رقم العداد مستخدم مسبقاً')
 c.close(); return {'ok':True}
@app.post('/api/readings')
def save_reading(request:Request,payload:dict):
 need(request); sid=int(payload['sub_id']); month=payload['month']; current=float(payload['current']); c=db(); sub=c.execute('SELECT * FROM subscribers WHERE id=?',(sid,)).fetchone()
 if not sub: c.close(); raise HTTPException(404,'المشترك غير موجود')
 prev=float(payload.get('previous',sub['current'])); rate_row=c.execute('SELECT rate FROM month_tariffs WHERE sub_id=? AND month=?',(sid,month)).fetchone(); rate=float(rate_row['rate']) if rate_row else float(payload.get('rate') or sub['rate'])
 qty=max(0,current-prev); amount=qty*rate
 c.execute('INSERT INTO readings(sub_id,month,previous,current,qty,rate,amount,created) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(sub_id,month) DO UPDATE SET previous=excluded.previous,current=excluded.current,qty=excluded.qty,rate=excluded.rate,amount=excluded.amount,created=excluded.created',(sid,month,prev,current,qty,rate,amount,datetime.now().isoformat(timespec='seconds')))
 c.execute('UPDATE subscribers SET current=?,previous=? WHERE id=?',(current,prev,sid)); c.commit(); c.close(); audit(who(request)['username'],'تسجيل قراءة',f'{sid}/{month}/{amount}'); return {'ok':True,'quantity':qty,'amount':amount,'rate':rate}
@app.post('/api/tariff')
def tariff(request:Request,payload:dict):
 need(request)
 if who(request)['role']!='manager': raise HTTPException(403,'صلاحية المدير مطلوبة')
 c=db(); c.execute('INSERT INTO month_tariffs(sub_id,month,rate,updated) VALUES(?,?,?,?) ON CONFLICT(sub_id,month) DO UPDATE SET rate=excluded.rate,updated=excluded.updated',(int(payload['sub_id']),payload['month'],float(payload['rate']),datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); audit(who(request)['username'],'تعديل تعرفة شهرية',str(payload)); return {'ok':True}
@app.get('/api/readings')
def get_readings(request:Request,month:str):
 need(request); c=db(); rows=c.execute('SELECT r.*,s.name,s.meter,s.sector FROM readings r JOIN subscribers s ON s.id=r.sub_id WHERE r.month=? ORDER BY s.sort_order,s.id',(month,)).fetchall(); c.close(); return [dict(x) for x in rows]
