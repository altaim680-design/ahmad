# -*- coding: utf-8 -*-
"""Nahda Syria V33 Cloud server.

Small-office central server for the desktop accounting client. It is intended to
run on an always-on VPS. SQLite remains on the VPS local disk (never on a shared
Drive), while clients communicate through this authenticated HTTP API.

For Internet use place this service behind HTTPS (Caddy/Nginx) or a private VPN
such as Tailscale. Administrative database replace/download/backup operations
use a separate admin key from normal client traffic.
"""
from __future__ import annotations
import os, json, sqlite3, threading, time, secrets, datetime, shutil, urllib.parse, base64, re
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("NAHDA_CONFIG", os.path.join(BASE_DIR, "server_config.json"))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "server_data")

def _env_int(name, default, lo=None, hi=None):
    try: v=int(os.environ.get(name, default))
    except Exception: v=int(default)
    if lo is not None: v=max(lo,v)
    if hi is not None: v=min(hi,v)
    return v

def load_config():
    cfg={
        "host":"0.0.0.0",
        "port":8765,
        "api_key":"",
        "admin_key":"",
        "server_name":"Nahda Cloud Server",
        "data_dir":DEFAULT_DATA_DIR,
        "backup_interval_hours":6,
        "backup_retention_days":30,
        "max_upload_mb":100,
    }
    if os.path.isfile(CONFIG_PATH):
        try:
            data=json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
            if isinstance(data,dict): cfg.update(data)
        except Exception: pass
    mapping={
        "NAHDA_HOST":"host","NAHDA_API_KEY":"api_key","NAHDA_ADMIN_KEY":"admin_key",
        "NAHDA_SERVER_NAME":"server_name","NAHDA_DATA_DIR":"data_dir",
    }
    for env,key in mapping.items():
        if os.environ.get(env): cfg[key]=os.environ[env]
    cfg["port"]=_env_int("NAHDA_PORT", os.environ.get("PORT", cfg.get("port",8765)), 1, 65535)
    cfg["backup_interval_hours"]=_env_int("NAHDA_BACKUP_INTERVAL_HOURS",cfg.get("backup_interval_hours",6),1,168)
    cfg["backup_retention_days"]=_env_int("NAHDA_BACKUP_RETENTION_DAYS",cfg.get("backup_retention_days",30),1,3650)
    cfg["max_upload_mb"]=_env_int("NAHDA_MAX_UPLOAD_MB",cfg.get("max_upload_mb",100),1,2048)
    changed=False
    if not cfg.get("api_key"):
        cfg["api_key"]=secrets.token_urlsafe(36); changed=True
    if not cfg.get("admin_key"):
        cfg["admin_key"]=secrets.token_urlsafe(42); changed=True
    if changed and not (os.environ.get("NAHDA_API_KEY") and os.environ.get("NAHDA_ADMIN_KEY")):
        try:
            serial={k:v for k,v in cfg.items() if k!="data_dir" or not os.environ.get("NAHDA_DATA_DIR")}
            Path(CONFIG_PATH).write_text(json.dumps(serial,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception: pass
    return cfg

CFG=load_config()
DATA_DIR=os.path.abspath(str(CFG.get("data_dir") or DEFAULT_DATA_DIR))
DB_PATH=os.path.join(DATA_DIR,"nahda_accounting.db")
FILES_DIR=os.path.join(DATA_DIR,"files")
BACKUP_DIR=os.path.join(DATA_DIR,"backups")
for d in (DATA_DIR,FILES_DIR,BACKUP_DIR): os.makedirs(d,exist_ok=True)
MAX_BODY=int(CFG.get("max_upload_mb",100))*1024*1024

SESSIONS={}; SESSIONS_LOCK=threading.RLock(); DB_REPLACE_LOCK=threading.RLock()

class Session:
    def __init__(self):
        self.conn=sqlite3.connect(DB_PATH,timeout=30,isolation_level=None,check_same_thread=False)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.lock=threading.RLock(); self.last=time.time()
    def close(self):
        try:self.conn.close()
        except Exception:pass

def close_all_sessions():
    with SESSIONS_LOCK:
        vals=list(SESSIONS.values()); SESSIONS.clear()
    for s in vals:s.close()

def cleanup_sessions_loop():
    while True:
        time.sleep(60); cutoff=time.time()-600; dead=[]
        with SESSIONS_LOCK:
            for sid,s in list(SESSIONS.items()):
                if s.last<cutoff: dead.append(s); SESSIONS.pop(sid,None)
        for s in dead:s.close()
threading.Thread(target=cleanup_sessions_loop,daemon=True).start()

def make_backup(prefix="auto"):
    with DB_REPLACE_LOCK:
        if not os.path.isfile(DB_PATH): return None
        os.makedirs(BACKUP_DIR,exist_ok=True)
        name=f"{prefix}_backup_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".db"
        out=os.path.join(BACKUP_DIR,name)
        src=sqlite3.connect(DB_PATH); dst=sqlite3.connect(out)
        try:
            src.backup(dst); ok=dst.execute("PRAGMA integrity_check").fetchone()[0]
            if ok!="ok": raise RuntimeError("فشل فحص النسخة الاحتياطية: "+str(ok))
            dst.commit()
        finally: src.close(); dst.close()
        return out

def prune_backups():
    cutoff=time.time()-int(CFG.get("backup_retention_days",30))*86400
    for p in Path(BACKUP_DIR).glob("*.db"):
        try:
            if p.stat().st_mtime<cutoff:p.unlink()
        except Exception:pass

def backup_loop():
    while True:
        time.sleep(int(CFG.get("backup_interval_hours",6))*3600)
        try: make_backup("auto"); prune_backups()
        except Exception as e: print("[backup]",e)
threading.Thread(target=backup_loop,daemon=True).start()

def json_restore(v):
    if isinstance(v,dict):
        if set(v.keys())=={"__nahda_bytes__"}: return base64.b64decode(v["__nahda_bytes__"])
        return {k:json_restore(x) for k,x in v.items()}
    if isinstance(v,list): return [json_restore(x) for x in v]
    return v

def safe_component(v,default="عام"):
    v=str(v or default).strip(); v=re.sub(r'[<>:"/\\|?*\x00-\x1f]+','_',v)
    return v[:120] or default

def safe_server_file(key):
    p=os.path.abspath(os.path.join(FILES_DIR,str(key or "").replace("/",os.sep)))
    root=os.path.abspath(FILES_DIR)+os.sep
    if not p.startswith(root): raise RuntimeError("مسار غير صالح")
    return p

class Handler(BaseHTTPRequestHandler):
    server_version="NahdaServer/33"
    protocol_version="HTTP/1.1"
    def log_message(self, fmt, *args):
        print("[%s] %s - %s"%(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),self.client_address[0],fmt%args))
    def _same(self,a,b): return bool(a) and secrets.compare_digest(str(a),str(b))
    def _auth(self): return self._same(self.headers.get("X-Nahda-Key",""),CFG.get("api_key",""))
    def _admin(self): return self._auth() and self._same(self.headers.get("X-Nahda-Admin-Key",""),CFG.get("admin_key",""))
    def _json(self,code,obj):
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)
    def _length(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        if n<0 or n>MAX_BODY: raise RuntimeError("حجم الطلب أكبر من الحد المسموح")
        return n
    def _read_json(self):
        n=self._length(); raw=self.rfile.read(n) if n else b"{}"
        return json_restore(json.loads(raw.decode("utf-8")))
    def _need_auth(self):
        if not self._auth(): self._json(401,{"ok":False,"error":"مفتاح الاتصال بالخادم غير صحيح"}); return False
        return True
    def _need_admin(self):
        if not self._admin(): self._json(403,{"ok":False,"error":"هذه العملية تحتاج مفتاح إدارة الخادم"}); return False
        return True
    def do_HEAD(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/api/health"}:
            self.send_response(200); self.send_header("Content-Length","0"); self.send_header("Cache-Control","no-store"); self.end_headers(); return
        self.send_response(404); self.send_header("Content-Length","0"); self.end_headers()
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=="/":
            self._json(200,{"ok":True,"service":"Nahda Syria Cloud","version":33}); return
        if parsed.path=="/api/health":
            if not self._need_auth():return
            proto=self.headers.get("X-Forwarded-Proto") or "http"
            self._json(200,{"ok":True,"version":33,"server_name":CFG.get("server_name"),"time":datetime.datetime.now().isoformat(timespec="seconds"),"active_sessions":len(SESSIONS),"transport":proto}); return
        if parsed.path=="/api/database/download":
            if not self._need_admin():return
            try:
                with DB_REPLACE_LOCK:
                    if not os.path.isfile(DB_PATH): raise RuntimeError("قاعدة بيانات الخادم غير موجودة")
                    tmp=make_backup("download"); data=Path(tmp).read_bytes()
                self.send_response(200); self.send_header("Content-Type","application/x-sqlite3"); self.send_header("Content-Disposition",'attachment; filename="nahda_accounting.db"'); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception as e:self._json(500,{"ok":False,"error":str(e)})
            return
        if not self._need_auth():return
        if parsed.path=="/api/files/download":
            try:
                key=urllib.parse.parse_qs(parsed.query).get("key",[""])[0]; p=safe_server_file(key)
                if not os.path.isfile(p):raise RuntimeError("الملف غير موجود على الخادم")
                size=os.path.getsize(p); self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Length",str(size)); self.end_headers()
                with open(p,"rb") as f:
                    while True:
                        b=f.read(1024*1024)
                        if not b:break
                        self.wfile.write(b)
            except Exception as e:self._json(404,{"ok":False,"error":str(e)})
            return
        self._json(404,{"ok":False,"error":"المسار غير موجود"})
    def do_POST(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path in {"/api/database/backup","/api/database/upload"}:
            if not self._need_admin():return
        elif not self._need_auth():return
        try:
            if parsed.path=="/api/session/open":
                self._read_json()
                sid=secrets.token_urlsafe(24); s=Session()
                with SESSIONS_LOCK:SESSIONS[sid]=s
                self._json(200,{"ok":True,"session":sid});return
            if parsed.path.startswith("/api/session/"):
                body=self._read_json(); sid=body.get("session")
                with SESSIONS_LOCK:s=SESSIONS.get(sid)
                if not s:raise RuntimeError("انتهت جلسة قاعدة البيانات. أعد المحاولة.")
                s.last=time.time(); action=parsed.path.rsplit("/",1)[-1]
                with s.lock:
                    if action=="execute":
                        cur=s.conn.execute(str(body.get("sql") or ""),tuple(body.get("params") or [])); cols=[x[0] for x in (cur.description or [])]; rows=[list(r) for r in cur.fetchall()] if cur.description else []
                        self._json(200,{"ok":True,"columns":cols,"rows":rows,"lastrowid":cur.lastrowid,"rowcount":cur.rowcount});return
                    if action=="script":s.conn.executescript(str(body.get("script") or ""));self._json(200,{"ok":True,"columns":[],"rows":[],"lastrowid":None,"rowcount":-1});return
                    if action=="commit":s.conn.commit();self._json(200,{"ok":True});return
                    if action=="rollback":s.conn.rollback();self._json(200,{"ok":True});return
                    if action=="close":
                        with SESSIONS_LOCK:SESSIONS.pop(sid,None)
                        s.close();self._json(200,{"ok":True});return
                raise RuntimeError("عملية جلسة غير معروفة")
            if parsed.path=="/api/database/backup":
                out=make_backup("manual"); prune_backups(); self._json(200,{"ok":True,"filename":os.path.basename(out) if out else None});return
            if parsed.path=="/api/database/upload":
                if self.headers.get("X-Nahda-Confirm")!="replace":raise RuntimeError("تأكيد استبدال قاعدة البيانات مفقود")
                n=self._length()
                if n<100:raise RuntimeError("ملف قاعدة البيانات المرفوع غير صالح")
                tmp=os.path.join(DATA_DIR,"incoming_"+secrets.token_hex(8)+".db")
                with open(tmp,"wb") as f:
                    remaining=n
                    while remaining:
                        b=self.rfile.read(min(1024*1024,remaining))
                        if not b:break
                        f.write(b);remaining-=len(b)
                if remaining:raise RuntimeError("لم يصل ملف قاعدة البيانات كاملاً")
                test=sqlite3.connect(tmp)
                try:
                    ok=test.execute("PRAGMA integrity_check").fetchone()[0]
                    if ok!="ok":raise RuntimeError("فشل فحص قاعدة البيانات المرفوعة: "+str(ok))
                finally:test.close()
                with DB_REPLACE_LOCK:
                    close_all_sessions()
                    if os.path.isfile(DB_PATH):make_backup("before_replace")
                    for sidecar in (DB_PATH+"-wal",DB_PATH+"-shm"):
                        try:
                            if os.path.exists(sidecar):os.remove(sidecar)
                        except Exception:pass
                    os.replace(tmp,DB_PATH)
                self._json(200,{"ok":True,"message":"تم رفع قاعدة البيانات إلى الخادم بنجاح","bytes":n});return
            if parsed.path=="/api/files/upload":
                n=self._length()
                if n<=0:raise RuntimeError("الملف فارغ")
                name=safe_component(urllib.parse.unquote(self.headers.get("X-Filename","file.bin")),"file.bin")
                category=safe_component(urllib.parse.unquote(self.headers.get("X-Category","عام")),"عام")
                day=datetime.datetime.now().strftime("%Y/%m"); rel=os.path.join(day,category,secrets.token_hex(8)+"_"+name); out=os.path.join(FILES_DIR,rel);os.makedirs(os.path.dirname(out),exist_ok=True)
                with open(out,"wb") as f:
                    remaining=n
                    while remaining:
                        b=self.rfile.read(min(1024*1024,remaining))
                        if not b:break
                        f.write(b);remaining-=len(b)
                if remaining:raise RuntimeError("لم يصل الملف كاملاً")
                key=rel.replace(os.sep,"/");self._json(200,{"ok":True,"key":key,"size":os.path.getsize(out)});return
            if parsed.path=="/api/files/delete":
                key=urllib.parse.parse_qs(parsed.query).get("key",[""])[0];p=safe_server_file(key)
                if os.path.isfile(p):os.remove(p)
                self._json(200,{"ok":True});return
            self._json(404,{"ok":False,"error":"المسار غير موجود"})
        except Exception as e:self._json(500,{"ok":False,"error":str(e)})

def main():
    host=str(CFG.get("host","0.0.0.0"));port=int(CFG.get("port",8765))
    print("="*72);print("Nahda Syria V33 Cloud Server");print("Server:",CFG.get("server_name"));print("Listening: http://%s:%s"%(host,port));print("Data:",DATA_DIR);print("Database:",DB_PATH);print("API key: [hidden]");print("Admin key: [hidden]");print("Automatic backup: every %s h / retention %s days"%(CFG.get("backup_interval_hours"),CFG.get("backup_retention_days")));print("Internet use: place behind HTTPS or private VPN/Tailscale.");print("="*72)
    srv=ThreadingHTTPServer((host,port),Handler);srv.daemon_threads=True;srv.serve_forever()

if __name__=="__main__":main()
