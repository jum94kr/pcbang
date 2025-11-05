from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import os, io, random, hashlib, unicodedata, hmac, pandas as pd
from datetime import datetime
from functools import wraps
import sqlite3
import psycopg2
import psycopg2.extras

# ────────────── 기본 설정 ──────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "pcbang_secret")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "방영민1!")  # 또는 qkddudals1!

DB_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "data", "pcbang.db")

BRANCHES = ["지점 A", "지점 B"]

# ────────────── DB 연결 ──────────────
def get_conn():
    if DB_URL:
        conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS staff(
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      phone TEXT,
      shift_type TEXT,
      work_days TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shifts(
      id SERIAL PRIMARY KEY,
      staff_id INTEGER REFERENCES staff(id),
      work_date TEXT,
      branch TEXT,
      start_time TEXT,
      end_time TEXT
    );
    """)
    conn.commit(); conn.close()
init_db()

# ────────────── 유틸 ──────────────
def norm(s): return unicodedata.normalize("NFC", (s or "")).strip()
def secure_eq(a,b): return hmac.compare_digest(a.encode(), b.encode())

def hash_color(name:str):
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    r = 70 + (h % 150)
    g = 100 + ((h>>8)%120)
    b = 120 + ((h>>16)%100)
    return f"rgb({r},{g},{b})"

def hours_between(start, end):
    try:
        sH,sM=map(int,start.split(":")); eH,eM=map(int,end.split(":"))
        s=sH*60+sM; e=eH*60+eM
        if e<s: e+=24*60
        return (e-s)/60.0
    except: return 0.0

# ────────────── 인증 ──────────────
def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrap

@app.route("/login", methods=["GET","POST"])
def login():
    error=None
    if request.method=="POST":
        u,p = norm(request.form["username"]), norm(request.form["password"])
        if secure_eq(u, ADMIN_USER) and secure_eq(p, ADMIN_PASS):
            session["logged_in"]=True
            return redirect(url_for("dashboard"))
        error="아이디 또는 비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ────────────── 메인 대시보드 ──────────────
@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", branches=BRANCHES)

@app.route("/api/staff")
@login_required
def api_staff():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id,name,shift_type FROM staff ORDER BY name;")
    data = cur.fetchall(); conn.close()
    return jsonify(data)

@app.route("/api/events")
@login_required
def api_events():
    start=request.args.get("start","")[:10]; end=request.args.get("end","")[:10]
    branch=request.args.get("branch")
    conn=get_conn(); cur=conn.cursor()
    q = """
    SELECT sh.id, sh.work_date, sh.start_time, sh.end_time, sh.branch, st.name, st.shift_type
    FROM shifts sh JOIN staff st ON st.id=sh.staff_id
    WHERE sh.work_date BETWEEN %s AND %s
    """
    params=[start,end]
    if branch and branch!="all":
        q+=" AND sh.branch=%s"; params.append(branch)
    q+=" ORDER BY sh.work_date, st.name"
    cur.execute(q,params); rows=cur.fetchall(); conn.close()

    events=[]
    for r in rows:
        color=hash_color(r["name"])
        bg = "rgba(60,130,255,0.4)" if r["shift_type"]=="day" else "rgba(30,30,60,0.8)"
        events.append({
            "id":r["id"],
            "title":f"{r['name']} ({r['branch']})",
            "start":f"{r['work_date']}T{r['start_time']}:00",
            "end":f"{r['work_date']}T{r['end_time']}:00",
            "color":color,
            "backgroundColor":bg,
            "textColor":"#fff" if r["shift_type"]=="night" else "#000"
        })
    return jsonify(events)

@app.route("/api/schedule", methods=["POST"])
@login_required
def api_schedule_create():
    d=request.get_json(force=True)
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""INSERT INTO shifts (staff_id,work_date,branch,start_time,end_time)
                   VALUES (%s,%s,%s,%s,%s)""",
                (d["staff_id"], d["work_date"], d["branch"], d["start_time"], d["end_time"]))
    conn.commit(); conn.close()
    return jsonify(ok=True)

@app.route("/api/schedule/<int:sid>", methods=["DELETE"])
@login_required
def api_schedule_delete(sid):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("DELETE FROM shifts WHERE id=%s",(sid,))
    conn.commit(); conn.close()
    return jsonify(ok=True)

# ────────────── 직원 관리 ──────────────
@app.route("/staff")
@login_required
def staff_list():
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT * FROM staff ORDER BY name;")
    rows=cur.fetchall(); conn.close()
    return render_template("staff.html", staff=rows, color=hash_color)

@app.route("/staff/add", methods=["GET","POST"])
@login_required
def staff_add():
    if request.method=="POST":
        name=norm(request.form["name"]); phone=request.form["phone"]
        shift=request.form["shift_type"]; days=",".join(request.form.getlist("work_days"))
        conn=get_conn(); cur=conn.cursor()
        cur.execute("INSERT INTO staff (name,phone,shift_type,work_days) VALUES (%s,%s,%s,%s)",
                    (name,phone,shift,days))
        conn.commit(); conn.close()
        return redirect(url_for("staff_list"))
    return render_template("staff_form.html")

# ────────────── 리포트 ──────────────
@app.route("/report")
@login_required
def report():
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""
      SELECT st.id, st.name, st.shift_type, sh.start_time, sh.end_time
      FROM staff st LEFT JOIN shifts sh ON st.id=sh.staff_id
    """)
    rows=cur.fetchall(); conn.close()
    totals={}
    for r in rows:
        t=totals.setdefault(r["id"],{"name":r["name"],"shift":r["shift_type"],"hours":0})
        if r["start_time"] and r["end_time"]:
            t["hours"]+=hours_between(r["start_time"],r["end_time"])
    return render_template("report.html", totals=list(totals.values()))

@app.route("/export_excel")
@login_required
def export_excel():
    conn=get_conn()
    df=pd.read_sql("""
      SELECT st.name '직원', st.phone '전화', st.shift_type '타입',
             sh.work_date '날짜', sh.branch '지점', sh.start_time '시작', sh.end_time '종료'
      FROM shifts sh JOIN staff st ON st.id=sh.staff_id ORDER BY sh.work_date, st.name
    """, conn)
    conn.close()
    if df.empty: df=pd.DataFrame(columns=['직원','전화','타입','날짜','지점','시작','종료'])
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as w: df.to_excel(w,index=False)
    bio.seek(0)
    return send_file(bio,as_attachment=True,
                     download_name=f"근무기록_{datetime.now():%Y%m%d}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/health")
def health(): return "ok",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8000)))
