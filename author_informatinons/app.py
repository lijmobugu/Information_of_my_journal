import sqlite3
import json
import datetime
import functools
from flask import Flask, render_template, request, redirect, url_for, g, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 数据库配置 ---
DATABASE = 'journal_guide.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-key-that-you-should-change'

# --- 数据库辅助函数 ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        print("Initializing database... Creating tables if not exists.")
        cursor.execute("CREATE TABLE IF NOT EXISTS journals (id INTEGER PRIMARY KEY AUTOINCREMENT, journal_name TEXT NOT NULL, issn TEXT, publisher TEXT, impact_factor REAL, formatting_requirements TEXT, font_specifications TEXT, word_count_limit INTEGER, reference_style TEXT, reference_count_limit INTEGER, submission_url TEXT, official_guidelines_url TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL, last_updated TEXT NOT NULL, update_history TEXT, flags_count INTEGER DEFAULT 0, comments TEXT);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_name ON journals (journal_name);")
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user');")
        users_to_add = [('admin', generate_password_hash('admin123'), 'admin'), ('user1', generate_password_hash('user123'), 'user'), ('user2', generate_password_hash('user123'), 'user')]
        for username, pwd_hash, role in users_to_add:
            if db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone() is None:
                db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, pwd_hash, role))
                print(f"User '{username}' created.")
        db.commit()
        print("Database initialized.")

# --- 用户会话和登录保护 ---

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone() if user_id else None

def login_required(view):
    """登录保护装饰器，将未登录用户重定向到登录页面"""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# --- 路由定义 ---

@app.route('/')
def index():
    if g.user:
        return redirect(url_for('journals_list'))
    return redirect(url_for('login'))

# --- 用户路由 (公开访问) ---

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user: return redirect(url_for('index'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db, error = get_db(), None
        if not username: error = 'Username is required.'
        elif not password: error = 'Password is required.'
        elif db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone(): error = f"User {username} is already registered."
        if error is None:
            db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, generate_password_hash(password)))
            db.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        flash(error)
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user: return redirect(url_for('index'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db, error = get_db(), None
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if not user: error = 'Incorrect username.'
        elif not check_password_hash(user['password_hash'], password): error = 'Incorrect password.'
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash(error)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 内容路由 (使用 @login_required 保护) ---

@app.route('/journals')
@login_required
def journals_list():
    all_journals = get_db().execute("SELECT id, journal_name, impact_factor FROM journals ORDER BY last_updated DESC").fetchall()
    return render_template('journals.html', journals=all_journals)

@app.route('/journal/<int:journal_id>')
@login_required
def journal_detail(journal_id):
    journal_raw = get_db().execute("SELECT * FROM journals WHERE id = ?", (journal_id,)).fetchone()
    if not journal_raw: return "Journal not found", 404
    journal = dict(journal_raw)
    journal['update_history'] = json.loads(journal['update_history'] or '[]')
    journal['comments'] = json.loads(journal['comments'] or '[]')
    for record in journal['update_history']: record['timestamp'] = datetime.datetime.fromisoformat(record['timestamp'])
    for comment in journal['comments']: comment['timestamp'] = datetime.datetime.fromisoformat(comment['timestamp'])
    return render_template('journal_detail.html', journal=journal)

@app.route('/search')
@login_required
def search():
    query_name, query_if = request.args.get('journal_name'), request.args.get('impact_factor')
    query, params = "SELECT id, journal_name, impact_factor FROM journals WHERE 1=1", []
    if query_name: query, params = query + " AND journal_name LIKE ?", params + [f"%{query_name}%"]
    if query_if: 
        try: 
            if float(query_if) >= 0: query, params = query + " AND impact_factor >= ?", params + [float(query_if)]
        except (ValueError, TypeError): pass
    results = get_db().execute(query + " ORDER BY last_updated DESC", params).fetchall()
    return render_template('journals.html', journals=results)

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == 'POST':
        form_data, now, db = request.form, datetime.datetime.utcnow(), get_db()
        initial_history = json.dumps([{'timestamp': now.isoformat(), 'author': g.user['username'], 'changes': 'Initial creation.'}])
        db.execute("INSERT INTO journals (journal_name, issn, publisher, impact_factor, formatting_requirements, font_specifications, word_count_limit, reference_style, reference_count_limit, submission_url, official_guidelines_url, notes, created_at, last_updated, update_history, comments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (form_data.get('journal_name'), form_data.get('issn'), form_data.get('publisher'), form_data.get('impact_factor') or None, form_data.get('formatting_requirements'), form_data.get('font_specifications'), form_data.get('word_count_limit') or None, form_data.get('reference_style'), form_data.get('reference_count_limit') or None, form_data.get('submission_url'), form_data.get('official_guidelines_url'), form_data.get('notes'), now.isoformat(), now.isoformat(), initial_history, json.dumps([])))
        db.commit()
        flash("New journal successfully submitted!")
        return redirect(url_for('journals_list'))
    return render_template('submit.html')

@app.route('/journal/<int:journal_id>/delete', methods=('POST',))
@login_required
def delete_journal(journal_id):
    if g.user['role'] != 'admin':
        flash('You do not have permission to delete.')
        return redirect(url_for('journal_detail', journal_id=journal_id))
    db = get_db()
    db.execute('DELETE FROM journals WHERE id = ?', (journal_id,))
    db.commit()
    flash('Journal entry successfully deleted.')
    return redirect(url_for('journals_list'))

@app.route('/journal/<int:journal_id>/flag', methods=['POST'])
@login_required
def flag_journal(journal_id):
    db = get_db()
    db.execute("UPDATE journals SET flags_count = flags_count + 1 WHERE id = ?", (journal_id,))
    db.commit()
    return redirect(url_for('journal_detail', journal_id=journal_id))

@app.route('/journal/<int:journal_id>/comment', methods=['POST'])
@login_required
def add_comment(journal_id):
    comment_text = request.form.get('comment_text')
    if comment_text:
        db, now = get_db(), datetime.datetime.utcnow()
        journal = db.execute("SELECT comments FROM journals WHERE id = ?", (journal_id,)).fetchone()
        if journal:
            comments = json.loads(journal['comments'] or '[]')
            comments.append({'author': g.user['username'], 'text': comment_text, 'timestamp': now.isoformat()})
            db.execute("UPDATE journals SET comments = ?, last_updated = ? WHERE id = ?", (json.dumps(comments), now.isoformat(), journal_id))
            db.commit()
    return redirect(url_for('journal_detail', journal_id=journal_id))

# --- 应用启动 ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)