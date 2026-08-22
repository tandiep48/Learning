from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash

from entity.user.service import (
    UserServiceError,
    get_user_auth_by_username,
    get_user_auth_by_id,
    username_or_email_exists,
    create_user,
)
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
    return get_user_auth_by_username(username)

def get_user_by_id(user_id):
    data = get_user_auth_by_id(user_id)
    if not data:
        return None
    return User(
        data['id'], data['username'], data['email'], data['level'],
        data['avatar_path'], data['hanzi_font'], data['hanzi_script'], data['ui_language'],
    )

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

        if username_or_email_exists(username, email):
            flash(t('flash.user_exists'), 'error')
            return redirect(url_for('auth.register'))

        try:
            create_user({"username": username, "email": email, "password": password, "level": 1})
            flash(t('flash.registration_success'), 'success')
            return redirect(url_for('auth.login'))
        except UserServiceError:
            flash(t('flash.database_error'), 'error')
            return redirect(url_for('auth.register'))

    return render_template('shared/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
