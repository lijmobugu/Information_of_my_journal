
import os
import json
import datetime
import functools
from flask import Flask, render_template, request, redirect, url_for, g, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- App & Database Initialization ---
app = Flask(__name__)

# Configure the database connection using the DATABASE_URL from Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key-for-local-dev')

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    journal_name = db.Column(db.String(200), nullable=False, index=True)
    issn = db.Column(db.String(50))
    publisher = db.Column(db.String(150))
    impact_factor = db.Column(db.Float, index=True)
    formatting_requirements = db.Column(db.Text)
    font_specifications = db.Column(db.Text)
    word_count_limit = db.Column(db.Integer)
    reference_style = db.Column(db.String(100))
    reference_count_limit = db.Column(db.Integer)
    submission_url = db.Column(db.String(500))
    official_guidelines_url = db.Column(db.String(500), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    update_history = db.Column(db.Text) # JSON-encoded text
    flags_count = db.Column(db.Integer, default=0)
    comments = db.Column(db.Text) # JSON-encoded text

# --- User Session & Auth ---

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# --- Routes ---

@app.route('/')
def index():
    return redirect(url_for('login')) if g.user is None else redirect(url_for('journals_list'))

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user: return redirect(url_for('journals_list'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = User.query.filter_by(username=username).first()
        error = None
        if not user: error = 'Incorrect username.'
        elif not check_password_hash(user.password_hash, password): error = 'Incorrect password.'
        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('journals_list'))
        flash(error)
    return render_template('login.html')

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user: return redirect(url_for('journals_list'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        error = None
        if not username: error = 'Username is required.'
        elif not password: error = 'Password is required.'
        elif User.query.filter_by(username=username).first() is not None: error = f"User {username} is already registered."
        if error is None:
            new_user = User(username=username, password_hash=generate_password_hash(password), role='user')
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        flash(error)
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/journals')
@login_required
def journals_list():
    all_journals = Journal.query.order_by(Journal.last_updated.desc()).all()
    return render_template('journals.html', journals=all_journals)

@app.route('/journal/<int:journal_id>')
@login_required
def journal_detail(journal_id):
    journal = Journal.query.get_or_404(journal_id)
    # Decode JSON fields for template
    journal.update_history_list = json.loads(journal.update_history or '[]')
    journal.comments_list = json.loads(journal.comments or '[]')
    return render_template('journal_detail.html', journal=journal)

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == 'POST':
        form_data = request.form
        now = datetime.datetime.utcnow()
        initial_history = json.dumps([{'timestamp': now.isoformat(), 'author': g.user.username, 'changes': 'Initial creation.'}])
        
        new_journal = Journal(
            journal_name=form_data.get('journal_name'),
            issn=form_data.get('issn'),
            publisher=form_data.get('publisher'),
            impact_factor=float(form_data.get('impact_factor')) if form_data.get('impact_factor') else None,
            formatting_requirements=form_data.get('formatting_requirements'),
            font_specifications=form_data.get('font_specifications'),
            word_count_limit=int(form_data.get('word_count_limit')) if form_data.get('word_count_limit') else None,
            reference_style=form_data.get('reference_style'),
            reference_count_limit=int(form_data.get('reference_count_limit')) if form_data.get('reference_count_limit') else None,
            submission_url=form_data.get('submission_url'),
            official_guidelines_url=form_data.get('official_guidelines_url'),
            notes=form_data.get('notes'),
            update_history=initial_history,
            comments=json.dumps([])
        )
        db.session.add(new_journal)
        db.session.commit()
        flash("New journal successfully submitted!")
        return redirect(url_for('journals_list'))
    return render_template('submit.html')

@app.route('/journal/<int:journal_id>/delete', methods=('POST',))
@login_required
def delete_journal(journal_id):
    if g.user.role != 'admin':
        flash('You do not have permission to delete.')
        return redirect(url_for('journal_detail', journal_id=journal_id))
    journal_to_delete = Journal.query.get_or_404(journal_id)
    db.session.delete(journal_to_delete)
    db.session.commit()
    flash('Journal entry successfully deleted.')
    return redirect(url_for('journals_list'))

# ... [Other routes like search, flag, comment need similar updates] ...

if __name__ == '__main__':
    # This block is for local development only.
    # On Render, the gunicorn command is used and this is not executed.
    with app.app_context():
        db.create_all() # Create tables from models
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password_hash=generate_password_hash('admin123'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created.")
    app.run(debug=True, port=5001)
