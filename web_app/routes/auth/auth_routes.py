from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
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
from service.gcs_service import avatar_url

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

def _build_user(data: dict) -> User:
    return User(
        data['id'], data['username'], data['email'], data['level'],
        data.get('avatar_path'), data.get('hanzi_font'), data.get('hanzi_script'), data.get('ui_language'),
    )

def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "level": user.level,
        "avatar_path": user.avatar_path,
        "avatar_url": avatar_url(user.avatar_path),
        "hanzi_font": user.hanzi_font,
        "hanzi_script": user.hanzi_script,
        "ui_language": user.ui_language,
    }

def _ok(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code

def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code

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


# ---------------------------------------------------------------------------
# JSON API — used by the Next.js frontend (yi-chinese-manage).
# Session-cookie based, same as the Jinja routes above: login_user() /
# current_user still drive Flask-Login, these endpoints just speak JSON
# instead of rendering/redirecting. Requires CORS(app, supports_credentials=True)
# in app.py and the frontend to fetch with credentials: 'include'.
# ---------------------------------------------------------------------------

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    if current_user.is_authenticated:
        return _ok(_serialize_user(current_user))

    data = request.get_json(silent=True) or {}
    username = str(data.get('username') or '').strip()
    password = str(data.get('password') or '')
    if not username or not password:
        return _error("Username and password are required.", 400)

    user_data = get_user_by_username(username)
    if not user_data or not check_password_hash(user_data['password'], password):
        return _error(t('flash.invalid_login'), 401)

    user = _build_user(user_data)
    login_user(user)
    return _ok(_serialize_user(user))


@auth_bp.route('/api/auth/register', methods=['POST'])
def api_register():
    if current_user.is_authenticated:
        return _ok(_serialize_user(current_user))

    data = request.get_json(silent=True) or {}
    username = str(data.get('username') or '').strip()
    email = str(data.get('email') or '').strip()
    password = str(data.get('password') or '')
    if not username or not email or not password:
        return _error(t('flash.fill_all_fields'), 400)

    if username_or_email_exists(username, email):
        return _error(t('flash.user_exists'), 409)

    try:
        create_user({"username": username, "email": email, "password": password, "level": 1})
    except UserServiceError as exc:
        return _error(exc.message, exc.status_code)

    user = _build_user(get_user_by_username(username))
    login_user(user)
    return _ok(_serialize_user(user), 201)


@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return _ok({"message": "Logged out."})


@auth_bp.route('/api/auth/me', methods=['GET'])
def api_me():
    if not current_user.is_authenticated:
        return _error("Not authenticated.", 401)
    return _ok(_serialize_user(current_user))
