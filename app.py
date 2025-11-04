
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3, os, io, pandas as pd
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'pcbang_secret'
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'pcbang.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    phone TEXT,
                    shift_type TEXT,
                    work_days TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id INTEGER,
                    date TEXT,
                    branch TEXT,
                    FOREIGN KEY(staff_id) REFERENCES staff(id)
                )''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uid = request.form.get('username')
        pw = request.form.get('password')
        if uid == 'admin' and pw == '방영민1!':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="아이디 또는 비밀번호가 올바르지 않습니다.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/staff')
@login_required
def staff():
    conn = sqlite3.connect(DB_PATH)
    staff = conn.execute("SELECT * FROM staff").fetchall()
    conn.close()
    return render_template('staff.html', staff=staff)

@app.route('/staff/add', methods=['GET','POST'])
@login_required
def staff_add():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        shift_type = request.form['shift_type']
        work_days = ','.join(request.form.getlist('work_days'))
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO staff (name, phone, shift_type, work_days) VALUES (?,?,?,?)",
                     (name, phone, shift_type, work_days))
        conn.commit(); conn.close()
        return redirect(url_for('staff'))
    return render_template('staff_form.html')

@app.route('/report')
@login_required
def report():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT s.name, sc.date, sc.branch FROM schedule sc JOIN staff s ON sc.staff_id=s.id", conn)
    conn.close()
    report = df.groupby('name').size().to_dict() if not df.empty else {}
    return render_template('report.html', report=report)

@app.route('/export_excel')
@login_required
def export_excel():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT s.name, s.phone, s.shift_type, sc.date, sc.branch FROM schedule sc JOIN staff s ON sc.staff_id=s.id", conn)
    conn.close()
    output = io.BytesIO()
    if df.empty:
        df = pd.DataFrame(columns=['직원명','전화번호','근무타입','날짜','지점'])
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='근무기록')
    output.seek(0)
    filename = f"근무기록_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=8000)
