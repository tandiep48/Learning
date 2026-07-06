from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from service.i18n_service import t

auth_bp = Blueprint('auth', __name__)
DEFAULT_HANZI_FONT = 'Noto Sans'
DEFAULT_HANZI_SCRIPT = 'simplified'
DEFAULT_UI_LANGUAGE = 'en'

class User(UserMixin):
    def __init__(self, id, username, email, level, avatar_path=None, hanzi_font=None, hanzi_script=None, ui_language=None):
        self.id = id
        self.username = username
        self.email = email
        self.level = level
        self.avatar_path = avatar_path
        self.hanzi_font = hanzi_font or DEFAULT_HANZI_FONT
        self.hanzi_script = hanzi_script or DEFAULT_HANZI_SCRIPT
        self.ui_language = ui_language or DEFAULT_UI_LANGUAGE

def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT id, username, email, password, level, avatar_path, hanzi_font, hanzi_script, ui_language FROM users WHERE username = %s", (username,))
            except Exception:
                conn.rollback()
                cur.execute("SELECT id, username, email, password, level, NULL AS avatar_path, %s AS hanzi_font, 'simplified' AS hanzi_script, 'en' AS ui_language FROM users WHERE username = %s", (DEFAULT_HANZI_FONT, username))
            row = cur.fetchone()
            if row:
                return {'id': row[0], 'username': row[1], 'email': row[2], 'password': row[3], 'level': row[4], 'avatar_path': row[5], 'hanzi_font': row[6] or DEFAULT_HANZI_FONT, 'hanzi_script': row[7] or DEFAULT_HANZI_SCRIPT, 'ui_language': row[8] or DEFAULT_UI_LANGUAGE}
    finally:
        conn.close()
    return None

def get_user_by_id(user_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT id, username, email, password, level, avatar_path, hanzi_font, hanzi_script, ui_language FROM users WHERE id = %s", (user_id,))
            except Exception:
                conn.rollback()
                cur.execute("SELECT id, username, email, password, level, NULL AS avatar_path, %s AS hanzi_font, 'simplified' AS hanzi_script, 'en' AS ui_language FROM users WHERE id = %s", (DEFAULT_HANZI_FONT, user_id))
            row = cur.fetchone()
            if row:
                return User(row[0], row[1], row[2], row[4], row[5], row[6] or DEFAULT_HANZI_FONT, row[7] or DEFAULT_HANZI_SCRIPT, row[8] or DEFAULT_UI_LANGUAGE)
    finally:
        conn.close()
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = get_user_by_username(username)
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['username'], user_data['email'], user_data['level'], user_data.get('avatar_path'), user_data.get('hanzi_font'), user_data.get('hanzi_script'), user_data.get('ui_language'))
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash(t('flash.invalid_login'), 'error')
            
    return render_template('shared/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash(t('flash.fill_all_fields'), 'error')
            return redirect(url_for('auth.register'))

        conn = get_db_connection()
        if not conn:
            flash(t('flash.database_error'), 'error')
            return redirect(url_for('auth.register'))

        try:
            with conn.cursor() as cur:
                # Check if username or email exists
                cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                if cur.fetchone():
                    flash(t('flash.user_exists'), 'error')
                    return redirect(url_for('auth.register'))

                pwd_hash = generate_password_hash(password)
                cur.execute("INSERT INTO users (username, email, password, level) VALUES (%s, %s, %s, %s)",
                            (username, email, pwd_hash, 1))
                conn.commit()
                flash(t('flash.registration_success'), 'success')
                return redirect(url_for('auth.login'))
        finally:
            conn.close()
            
    return render_template('shared/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
