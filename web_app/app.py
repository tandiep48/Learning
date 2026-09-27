import os

# --- Eventlet cooperation for psycopg2 -------------------------------------
# In production the app runs under `gunicorn -k eventlet`: the whole worker is a
# single OS thread of cooperative greenlets. psycopg2 is a C extension that does
# NOT yield to the eventlet hub on its own, so a single DB call would block every
# other request in the worker until it returns (this caused the gateway timeouts).
# psycogreen registers a wait-callback that makes psycopg2 cooperate. It must run
# before any database connection is opened, so it lives at the very top — and only
# when eventlet has actually monkey-patched the process (never in plain threading
# dev, where it is unnecessary).
try:
    import eventlet.patcher
    if eventlet.patcher.is_monkey_patched("socket"):
        from psycogreen.eventlet import patch_psycopg
        patch_psycopg()
except Exception:
    pass

import secrets
from dotenv import load_dotenv
from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
from flask_login import LoginManager
from flask_socketio import SocketIO
from routes.vocab import vocab_bp, vocab_crud_bp
from routes.lesson import lesson_bp
from routes.practice import practice_bp
from routes.competition import competition_bp
from routes.auth import auth_bp, get_user_by_id
from routes.user import user_bp, user_crud_bp
from routes.passage import passage_crud_bp
from routes.passage_vocab import passage_vocab_crud_bp
from routes.passage_line import passage_line_crud_bp
from routes.question import question_crud_bp
from routes.translation import translation_bp
from routes.i18n import i18n_bp
from routes.book import book_crud_bp
from routes.chinese_stroke_info import chinese_stroke_info_bp
from routes.grammar_rule import grammar_rule_crud_bp
from routes.grammar_context import grammar_context_crud_bp
from service.competition_socket import init_competition_socket
from service import gcs_service

load_dotenv()

app = Flask(__name__)
app.json.sort_keys = False
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
# supports_credentials + an explicit origin (not "*") are required so the
# Next.js frontend can send/receive the Flask-Login session cookie via
# fetch(credentials: "include"). localhost:3000 and localhost:5000 are
# same-site (same scheme+host, different port only), so the cookie's default
# SameSite=Lax still flows across them without needing SameSite=None.
CORS(app, supports_credentials=True, origins=[os.getenv('FRONTEND_ORIGIN', 'http://localhost:3000')])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=os.getenv("SOCKETIO_ASYNC_MODE", "threading"))

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

@login_manager.unauthorized_handler
def unauthorized():
    """API-only: there is no login page to redirect to. A signed-out
    @login_required request gets a JSON 401, which the Next.js frontend detects
    (legacyApiFetch treats 401 as an UnauthenticatedError)."""
    return jsonify({"success": False, "error": "Authentication required."}), 401

# Register Blueprints
app.register_blueprint(vocab_bp)
app.register_blueprint(lesson_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(competition_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(vocab_crud_bp)
app.register_blueprint(passage_crud_bp)
app.register_blueprint(passage_vocab_crud_bp)
app.register_blueprint(passage_line_crud_bp)
app.register_blueprint(user_crud_bp)
app.register_blueprint(question_crud_bp)
app.register_blueprint(translation_bp)
app.register_blueprint(i18n_bp)
app.register_blueprint(book_crud_bp)
app.register_blueprint(chinese_stroke_info_bp)
app.register_blueprint(grammar_rule_crud_bp)
app.register_blueprint(grammar_context_crud_bp)
init_competition_socket(socketio)


@app.route('/')
def index():
    """API-only health check. The learner and admin UIs are served by the
    Next.js frontend (yi-chinese-manage); this app is now JSON-only."""
    return jsonify({"success": True, "data": {"service": "yi-chinese-api", "status": "ok"}})


# ---------------------------------------------------------------------------
# Media redirects to Google Cloud Storage (used by the Next.js frontend).
# ---------------------------------------------------------------------------
@app.route('/practice_image/<int:level>/<path:filename>')
def serve_practice_image(level, filename):
    category = request.args.get('category', 'practice')
    return redirect(gcs_service.practice_image_url(category, level, filename))

@app.route('/practice_audio/<int:number>/<path:filename>')
def serve_practice_audio(number, filename):
    category = request.args.get('category', 'practice')
    return redirect(gcs_service.practice_audio_url(category, number, filename))

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return redirect(gcs_service.vocab_audio_url(filename))

@app.route('/lesson_audio/<path:filename>')
def serve_lesson_audio(filename):
    return redirect(gcs_service.lesson_audio_url(filename))

@app.route('/lesson-image/<hsk>/<filename>')
def serve_lesson_image(hsk, filename):
    return redirect(gcs_service.lesson_image_url(hsk, filename))

@app.route('/lesson-cover/<code>')
def serve_lesson_cover(code):
    # Cover image for a topic "book" lesson, e.g. /lesson-cover/AML -> lesson_cover/AML.png
    return redirect(gcs_service.lesson_cover_url(code))

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=debug_mode, port=port, use_reloader=False, allow_unsafe_werkzeug=True)
