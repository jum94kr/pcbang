from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import sqlite3, os, io, hashlib, json, random
import pandas as pd
from datetime import datetime, timedelta, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'pcbang_secret'
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'data', 'pcbang.db')
BRANCHES = ["지점 A", "지점 B"]  # 필요 시 확장

# ---------- DB ----------
def init_db():
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS staff(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      phone TEXT,
      shift_type TEXT,          -- day/night
      work_days TEXT            -- CSV of 0..6 (월=0)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      staff_id INTEGER,
      work_date TEXT,           -- YYYY-MM-DD
      branch TEXT,
      start_time TEXT,          -- HH:MM
      end_time TEXT,            -- HH:MM
      FOREIGN KEY(staff_id) REFERENCES staff(id)
    )""")
    conn.commit(); conn.close()
init_db()

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- auth ----------
def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrap

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("username")=="admin" and request.form.get("password")=="방영민1!":
            session["logged_in"]=True
            return redirect(url_for("dashboard"))
        error = "아이디 또는 비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- utils ----------
def hash_color(name: str):
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)
    r = 80 + (h % 150)
    g = 80 + ((h >> 8) % 150)
    b = 80 + ((h >> 16) % 150)
    return f"#{r:02x}{g:02x}{b:02x}"

def hours_between(start, end):
    try:
        sH,sM = map(int,start.split(":")); eH,eM = map(int,end.split(":"))
        s = sH*60+sM; e = eH*60+eM
        if e < s: e += 24*60
        return (e-s)/60.0
    except: return 0.0

# ---------- dashboard ----------
@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", branches=BRANCHES)

@app.route("/api/events")
@login_required
def api_events():
    # FullCalendar: start & end(ISO8601)
    start = request.args.get("start","")[:10]
    end   = request.args.get("end","")[:10]
    conn = db()
    rows = conn.execute("""
      SELECT sh.id, sh.work_date, sh.start_time, sh.end_time, sh.branch,
             st.name, st.shift_type
      FROM shifts sh JOIN staff st ON st.id=sh.staff_id
      WHERE sh.work_date BETWEEN ? AND ?
    """,(start,end)).fetchall()
    conn.close()
    events=[]
    for r in rows:
        title = f"{r['name']} {r['start_time']}-{r['end_time']} ({r['branch']})"
        color = hash_color(r['name'])
        bg = "rgba(100,150,255,0.18)" if r['shift_type']=="day" else "rgba(30,50,90,0.55)"
        events.append({
            "id": r["id"],
            "title": title,
            "start": f"{r['work_date']}T{r['start_time']}:00",
            "end":   f"{r['work_date']}T{r['end_time']}:00",
            "display": "block",
            "color": color,
            "backgroundColor": bg,
            "borderColor": color
        })
    return jsonify(events)

@app.route("/api/schedule", methods=["POST"])
@login_required
def api_schedule_create():
    data = request.get_json(force=True)
    conn = db()
    conn.execute("""INSERT INTO shifts (staff_id, work_date, branch, start_time, end_time)
                    VALUES (?,?,?,?,?)""",
                 (data["staff_id"], data["work_date"], data["branch"], data["start_time"], data["end_time"]))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/schedule/<int:sid>", methods=["DELETE"])
@login_required
def api_schedule_delete(sid):
    conn = db()
    conn.execute("DELETE FROM shifts WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ---------- staff ----------
@app.route("/staff")
@login_required
def staff_list():
    conn = db()
    rows = conn.execute("SELECT * FROM staff ORDER BY name").fetchall()
    conn.close()
    return render_template("staff.html", staff=rows, color=hash_color)

@app.route("/staff/add", methods=["GET","POST"])
@login_required
def staff_add():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        phone=request.form.get("phone","").strip()
        shift=request.form.get("shift_type","day")
        days=",".join(request.form.getlist("work_days"))  # "0,2,4"
        conn=db()
        conn.execute("INSERT INTO staff(name,phone,shift_type,work_days) VALUES (?,?,?,?)",
                     (name,phone,shift,days))
        conn.commit(); conn.close()
        return redirect(url_for("staff_list"))
    return render_template("staff_form.html", item=None)

@app.route("/staff/edit/<int:sid>", methods=["GET","POST"])
@login_required
def staff_edit(sid):
    conn=db()
    row=conn.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone()
    if not row:
        conn.close(); return "Not found",404
    if request.method=="POST":
        name=request.form.get("name", row["name"]).strip()
        phone=request.form.get("phone", row["phone"]).strip()
        shift=request.form.get("shift_type", row["shift_type"])
        days=",".join(request.form.getlist("work_days")) or row["work_days"]
        conn.execute("UPDATE staff SET name=?, phone=?, shift_type=?, work_days=? WHERE id=?",
                     (name,phone,shift,days,sid))
        conn.commit(); conn.close()
        return redirect(url_for("staff_list"))
    conn.close()
    return render_template("staff_form.html", item=row)

@app.route("/staff/delete/<int:sid>", methods=["POST"])
@login_required
def staff_delete(sid):
    conn=db()
    conn.execute("DELETE FROM staff WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return redirect(url_for("staff_list"))

# ---------- auto assign ----------
@app.route("/auto_assign", methods=["POST"])
@login_required
def auto_assign():
    data = request.get_json(force=True)
    start_str = data.get("monday")  # YYYY-MM-DD(월요일)
    start = datetime.strptime(start_str,"%Y-%m-%d").date()
    conn = db()
    staff = conn.execute("SELECT * FROM staff").fetchall()
    for i in range(7):
        d = start + timedelta(days=i)
        weekday = d.weekday()
        day_staff  = [r for r in staff if r["shift_type"]=="day"   and str(weekday) in (r["work_days"] or "").split(",")]
        night_staff= [r for r in staff if r["shift_type"]=="night" and str(weekday) in (r["work_days"] or "").split(",")]
        random.shuffle(day_staff); random.shuffle(night_staff)
        # 지점 A/B 각각 1명씩(가능할 때)
        for idx, b in enumerate(BRANCHES):
            if idx < len(day_staff):
                sid = day_staff[idx]["id"]
                exists = conn.execute("SELECT 1 FROM shifts WHERE work_date=? AND branch=? AND staff_id=? AND start_time='09:00' AND end_time='18:00'",
                                      (d.isoformat(), b, sid)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO shifts(staff_id,work_date,branch,start_time,end_time) VALUES (?,?,?,?,?)",
                                 (sid, d.isoformat(), b, "09:00","18:00"))
            if idx < len(night_staff):
                sid = night_staff[idx]["id"]
                exists = conn.execute("SELECT 1 FROM shifts WHERE work_date=? AND branch=? AND staff_id=? AND start_time='20:00' AND end_time='02:00'",
                                      (d.isoformat(), b, sid)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO shifts(staff_id,work_date,branch,start_time,end_time) VALUES (?,?,?,?,?)",
                                 (sid, d.isoformat(), b, "20:00","02:00"))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ---------- report & export ----------
@app.route("/report")
@login_required
def report():
    # 직원별 주간/전체 합계(시간)
    conn = db()
    q = """
    SELECT st.id sid, st.name, st.phone, st.shift_type, sh.start_time, sh.end_time
    FROM staff st LEFT JOIN shifts sh ON st.id=sh.staff_id
    """
    rows = conn.execute(q).fetchall(); conn.close()
    totals = {}
    for r in rows:
        t = totals.setdefault(r["sid"], {"name":r["name"],"phone":r["phone"],"shift":r["shift_type"],"hours":0.0})
        if r["start_time"] and r["end_time"]:
            t["hours"] += hours_between(r["start_time"], r["end_time"])
    return render_template("report.html", totals=list(totals.values()))

@app.route("/export_excel")
@login_required
def export_excel():
    conn = db()
    df = pd.read_sql_query("""
        SELECT st.name '직원', st.phone '전화', st.shift_type '타입',
               sh.work_date '날짜', sh.branch '지점', sh.start_time '시작', sh.end_time '종료'
        FROM shifts sh JOIN staff st ON st.id=sh.staff_id
        ORDER BY sh.work_date, st.name
    """, conn)
    conn.close()
    if df.empty:
        df = pd.DataFrame(columns=['직원','전화','타입','날짜','지점','시작','종료'])
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="근무기록")
    bio.seek(0)
    filename = f"근무기록_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(bio, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/health")
def health():
    return "ok",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
