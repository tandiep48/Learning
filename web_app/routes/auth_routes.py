from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection

auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, id, username, email, level):
        self.id = id
        self.username = username
        self.email = email
        self.level = level

def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email, password, level FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row:
                return {'id': row[0], 'username': row[1], 'email': row[2], 'password': row[3], 'level': row[4]}
    finally:
        conn.close()
    return None

def get_user_by_id(user_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email, password, level FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return User(row[0], row[1], row[2], row[4])
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
            user = User(user_data['id'], user_data['username'], user_data['email'], user_data['level'])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            
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
            flash('Please fill out all fields', 'error')
            return redirect(url_for('auth.register'))
            
        conn = get_db_connection()
        if not conn:
            flash('Database error', 'error')
            return redirect(url_for('auth.register'))
            
        try:
            with conn.cursor() as cur:
                # Check if username or email exists
                cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                if cur.fetchone():
                    flash('Username or Email already exists', 'error')
                    return redirect(url_for('auth.register'))
                
                pwd_hash = generate_password_hash(password)
                cur.execute("INSERT INTO users (username, email, password, level) VALUES (%s, %s, %s, %s)",
                            (username, email, pwd_hash, 1))
                conn.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
        finally:
            conn.close()
            
    return render_template('shared/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
