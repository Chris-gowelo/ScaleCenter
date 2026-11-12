import sqlite3, secrets, hashlib
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB = "scalecenter.db"
app = FastAPI(title="ScaleCenter")

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def hp(p, s): return hashlib.pbkdf2_hmac("sha256", p.encode(), s.encode(), 100000).hex()

def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, pw TEXT, salt TEXT,
      role TEXT, field TEXT DEFAULT '', skills TEXT DEFAULT '', bio TEXT DEFAULT '', banned INTEGER DEFAULT 0,
      is_admin INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, uid INTEGER);
    CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, uid INTEGER, kind TEXT, title TEXT, body TEXT,
      field TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, frm INTEGER, to_ INTEGER, body TEXT,
      created TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    if not c.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
        s = secrets.token_hex(8)
        c.execute("INSERT INTO users(name,email,pw,salt,role,is_admin) VALUES(?,?,?,?,?,1)",
                  ("Admin", "admin@scalecenter.com", hp("admin123", s), s, "admin"))
    c.commit()
init()

def me(authorization: str = Header("")):
    r = db().execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.uid WHERE token=?", (authorization,)).fetchone()
    if not r or r["banned"]: raise HTTPException(401, "Please log in")
    return dict(r)

def admin(u=Depends(me)):
    if not u["is_admin"]: raise HTTPException(403, "Admins only")
    return u

def pub(r):
    d = dict(r); d.pop("pw", None); d.pop("salt", None); return d

class Reg(BaseModel):
    name: str; email: str; password: str; role: str = "talent"
class Login(BaseModel):
    email: str; password: str
class Prof(BaseModel):
    name: str; field: str = ""; skills: str = ""; bio: str = ""
class Post(BaseModel):
    kind: str; title: str; body: str; field: str
class Msg(BaseModel):
    to: int; body: str

@app.post("/api/register")
def register(d: Reg):
    if d.role not in ("talent", "employer", "investor"): raise HTTPException(400, "Invalid role")
    if len(d.password) < 6: raise HTTPException(400, "Password needs 6+ characters")
    c = db(); s = secrets.token_hex(8)
    try:
        c.execute("INSERT INTO users(name,email,pw,salt,role) VALUES(?,?,?,?,?)",
                  (d.name.strip(), d.email.lower().strip(), hp(d.password, s), s, d.role)); c.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Email already registered")
    return login(Login(email=d.email, password=d.password))

@app.post("/api/login")
def login(d: Login):
    c = db(); r = c.execute("SELECT * FROM users WHERE email=?", (d.email.lower().strip(),)).fetchone()
    if not r or hp(d.password, r["salt"]) != r["pw"]: raise HTTPException(401, "Wrong email or password")
    if r["banned"]: raise HTTPException(403, "This account is suspended")
    t = secrets.token_hex(24); c.execute("INSERT INTO sessions VALUES(?,?)", (t, r["id"])); c.commit()
    return {"token": t, "user": pub(r)}

@app.get("/api/me")
def get_me(u=Depends(me)): return pub(u)

@app.put("/api/me")
def put_me(d: Prof, u=Depends(me)):
    c = db(); c.execute("UPDATE users SET name=?,field=?,skills=?,bio=? WHERE id=?", (d.name, d.field, d.skills, d.bio, u["id"])); c.commit()
    return {"ok": True}

@app.get("/api/posts")
def posts(kind: str = "", field: str = "", q: str = "", u=Depends(me)):
    sql = "SELECT p.*, u.name author, u.role FROM posts p JOIN users u ON u.id=p.uid WHERE u.banned=0"
    a = []
    if kind: sql += " AND p.kind=?"; a.append(kind)
    if field: sql += " AND p.field=?"; a.append(field)
    if q: sql += " AND (p.title LIKE ? OR p.body LIKE ?)"; a += [f"%{q}%"] * 2
    return [dict(r) for r in db().execute(sql + " ORDER BY p.id DESC LIMIT 100", a)]

@app.post("/api/posts")
def new_post(d: Post, u=Depends(me)):
    if d.kind == "job" and u["role"] == "talent": raise HTTPException(403, "Only employers and investors can post jobs")
    if d.kind == "skill" and u["role"] != "talent": raise HTTPException(403, "Only talents can post skills")
    c = db(); c.execute("INSERT INTO posts(uid,kind,title,body,field) VALUES(?,?,?,?,?)", (u["id"], d.kind, d.title, d.body, d.field)); c.commit()
    return {"ok": True}

@app.delete("/api/posts/{pid}")
def del_post(pid: int, u=Depends(me)):
    c = db(); r = c.execute("SELECT uid FROM posts WHERE id=?", (pid,)).fetchone()
    if not r or (r["uid"] != u["id"] and not u["is_admin"]): raise HTTPException(403, "Not allowed")
    c.execute("DELETE FROM posts WHERE id=?", (pid,)); c.commit(); return {"ok": True}

@app.get("/api/people")
def people(q: str = "", u=Depends(me)):
    return [pub(r) for r in db().execute(
        "SELECT * FROM users WHERE banned=0 AND is_admin=0 AND (name LIKE ? OR skills LIKE ? OR field LIKE ?) ORDER BY id DESC LIMIT 100", [f"%{q}%"] * 3)]

@app.get("/api/threads")
def threads(u=Depends(me)):
    return [dict(r) for r in db().execute("""SELECT x.id, x.name, x.role, (SELECT body FROM messages m WHERE (m.frm=x.id AND m.to_=?1) OR (m.frm=?1 AND m.to_=x.id) ORDER BY m.id DESC LIMIT 1) last
      FROM users x WHERE x.id IN (SELECT to_ FROM messages WHERE frm=?1 UNION SELECT frm FROM messages WHERE to_=?1)""", (u["id"],))]

@app.get("/api/messages/{oid}")
def chat(oid: int, u=Depends(me)):
    o = db().execute("SELECT id,name,role FROM users WHERE id=?", (oid,)).fetchone()
    m = db().execute("SELECT * FROM messages WHERE (frm=?1 AND to_=?2) OR (frm=?2 AND to_=?1) ORDER BY id", (u["id"], oid))
    return {"with": dict(o) if o else None, "messages": [dict(r) for r in m]}

@app.post("/api/messages")
def send(d: Msg, u=Depends(me)):
    if not d.body.strip(): raise HTTPException(400, "Message is empty")
    c = db(); c.execute("INSERT INTO messages(frm,to_,body) VALUES(?,?,?)", (u["id"], d.to, d.body.strip())); c.commit(); return {"ok": True}

@app.get("/api/admin/stats")
def stats(a=Depends(admin)):
    c = db(); n = lambda q: c.execute(q).fetchone()[0]
    return {"users": n("SELECT COUNT(*) FROM users WHERE is_admin=0"), "talents": n("SELECT COUNT(*) FROM users WHERE role='talent'"),
            "employers": n("SELECT COUNT(*) FROM users WHERE role='employer'"), "investors": n("SELECT COUNT(*) FROM users WHERE role='investor'"),
            "jobs": n("SELECT COUNT(*) FROM posts WHERE kind='job'"), "skills": n("SELECT COUNT(*) FROM posts WHERE kind='skill'"),
            "messages": n("SELECT COUNT(*) FROM messages")}

@app.get("/api/admin/users")
def a_users(a=Depends(admin)): return [pub(r) for r in db().execute("SELECT * FROM users WHERE is_admin=0 ORDER BY id DESC")]

@app.post("/api/admin/users/{uid}/ban")
def ban(uid: int, a=Depends(admin)):
    c = db(); c.execute("UPDATE users SET banned=1-banned WHERE id=? AND is_admin=0", (uid,)); c.execute("DELETE FROM sessions WHERE uid=?", (uid,)); c.commit(); return {"ok": True}

@app.delete("/api/admin/users/{uid}")
def rm(uid: int, a=Depends(admin)):
    c = db()
    for q in ("DELETE FROM posts WHERE uid=?", "DELETE FROM sessions WHERE uid=?", "DELETE FROM messages WHERE frm=? OR to_=?", "DELETE FROM users WHERE id=? AND is_admin=0"):
        c.execute(q, (uid,) * q.count("?"))
    c.commit(); return {"ok": True}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
