import os, sqlite3
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET")
DB = os.getenv("DB_PATH", "zaem_host.db")

CSS = """
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#eef2ff;font-family:Arial,sans-serif}
nav{display:flex;justify-content:space-between;align-items:center;padding:18px 7%;background:#11182d}
nav a{color:#cbd5e1;text-decoration:none;margin-right:16px}main{max-width:1100px;margin:auto;padding:24px}
.hero{text-align:center;padding:80px 20px}.hero h1{font-size:42px}.card{background:#141d35;border:1px solid #263252;border-radius:18px;padding:22px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
input{width:100%;padding:13px;margin:7px 0;border-radius:10px;border:1px solid #334155;background:#0f172a;color:white}
.btn{display:inline-block;border:0;border-radius:10px;padding:12px 18px;background:#4f46e5;color:white;text-decoration:none;cursor:pointer}
.flash{background:#7f1d1d;padding:12px;border-radius:10px;margin:15px 0}.row{display:flex;gap:10px}.row input{flex:1}
@media(max-width:600px){.hero h1{font-size:32px}.row{flex-direction:column}}
</style>
"""

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,is_admin INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,name TEXT NOT NULL,status TEXT DEFAULT 'stopped');
    """)
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        c.execute("INSERT INTO users(username,password,is_admin) VALUES(?,?,1)",("admin",generate_password_hash("admin123")))
    c.commit(); c.close()

def user():
    if "uid" not in session: return None
    return db().execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone()

def page(body,title="ZAEM HOST"):
    u=user()
    nav = '<b>ZAEM HOST</b><span>'
    if u:
        nav += '<a href="/dashboard">لوحتي</a>'
        if u["is_admin"]: nav += '<a href="/admin">Admin</a>'
        nav += '<a href="/logout">خروج</a>'
    else:
        nav += '<a href="/login">دخول</a><a href="/register">حساب جديد</a>'
    nav += '</span>'
    msgs=''.join(f'<div class="flash">{m}</div>' for m in get_messages())
    return f'<!doctype html><html lang="ar" dir="rtl"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}<nav>{nav}</nav><main>{msgs}{body}</main></html>'

def get_messages():
    return session.pop("_flash", [])

def msg(x):
    session.setdefault("_flash",[]).append(x)

@app.before_request
def setup(): init_db()

@app.route("/")
def home():
    return page('<section class="hero"><h1>ZAEM HOST</h1><p>منصة لإدارة مشاريع وبوتاتك.</p><a class="btn" href="/register">ابدأ الآن</a></section>')

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","")
        if not u or len(p)<6: msg("كلمة المرور يجب أن تكون 6 أحرف على الأقل."); return redirect(url_for("register"))
        c=db()
        try:
            cur=c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,generate_password_hash(p))); c.commit()
            session["uid"]=cur.lastrowid; return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError: msg("اسم المستخدم موجود بالفعل.")
        finally: c.close()
    return page('<div class="card"><h2>إنشاء حساب</h2><form method="post"><input name="username" placeholder="اسم المستخدم" required><input name="password" type="password" placeholder="كلمة المرور" required><button class="btn">إنشاء</button></form></div>')

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        r=db().execute("SELECT * FROM users WHERE username=?",(request.form.get("username","").strip(),)).fetchone()
        if r and check_password_hash(r["password"],request.form.get("password","")):
            session["uid"]=r["id"]; return redirect(url_for("admin" if r["is_admin"] else "dashboard"))
        msg("بيانات الدخول غير صحيحة.")
    return page('<div class="card"><h2>تسجيل الدخول</h2><form method="post"><input name="username" placeholder="اسم المستخدم" required><input name="password" type="password" placeholder="كلمة المرور" required><button class="btn">دخول</button></form></div>')

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

@app.route("/dashboard")
def dashboard():
    u=user()
    if not u: return redirect("/login")
    ps=db().execute("SELECT * FROM projects WHERE user_id=?",(u["id"],)).fetchall()
    cards=''.join(f'<div class="card"><h3>{p["name"]}</h3><p>الحالة: <b>{p["status"]}</b></p><form method="post" action="/project/{p["id"]}/toggle"><button class="btn">{"إيقاف" if p["status"]=="running" else "تشغيل"}</button></form></div>' for p in ps)
    return page(f'<h1>لوحة التحكم</h1><div class="card"><h3>مشروع جديد</h3><form method="post" action="/project/new" class="row"><input name="name" placeholder="اسم المشروع" required><button class="btn">إنشاء</button></form></div><div class="grid">{cards or "<p>لا توجد مشاريع.</p>"}</div>')

@app.route("/project/new",methods=["POST"])
def new_project():
    u=user()
    if not u: return redirect("/login")
    n=request.form.get("name","").strip()
    if n:
        c=db(); c.execute("INSERT INTO projects(user_id,name) VALUES(?,?)",(u["id"],n)); c.commit(); c.close()
    return redirect("/dashboard")

@app.route("/project/<int:pid>/toggle",methods=["POST"])
def toggle(pid):
    u=user()
    if not u: return redirect("/login")
    c=db(); r=c.execute("SELECT * FROM projects WHERE id=? AND user_id=?",(pid,u["id"])).fetchone()
    if r:
        c.execute("UPDATE projects SET status=? WHERE id=?",("stopped" if r["status"]=="running" else "running",pid)); c.commit()
    c.close(); return redirect("/dashboard")

@app.route("/admin")
def admin():
    u=user()
    if not u or not u["is_admin"]: return redirect("/login")
    c=db(); users=c.execute("SELECT * FROM users ORDER BY id DESC").fetchall(); ps=c.execute("SELECT p.*,u.username FROM projects p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC").fetchall(); c.close()
    us=''.join(f'<p>#{x["id"]} — {x["username"]} {"👑" if x["is_admin"] else ""}</p>' for x in users)
    pp=''.join(f'<p>{p["name"]} — {p["username"]} — {p["status"]}</p>' for p in ps)
    return page(f'<h1>لوحة Admin</h1><div class="grid"><div class="card"><h3>المستخدمون</h3><b>{len(users)}</b></div><div class="card"><h3>المشاريع</h3><b>{len(ps)}</b></div></div><div class="card"><h2>المستخدمون</h2>{us}</div><div class="card"><h2>المشاريع</h2>{pp}</div>')

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
