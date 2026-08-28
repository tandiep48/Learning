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
from flask import Flask, render_template, redirect, url_for, request, send_from_directory, session
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
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
from service.i18n_service import get_current_lang, get_translations, t as i18n_t, SUPPORTED_LANGUAGES
from entity.user.service import update_user_ui_language
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
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

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

@app.context_processor
def inject_avatar_helpers():
    return {"avatar_url": gcs_service.avatar_url, "hsk_image_url": gcs_service.hsk_image_url}

# Jinja-only i18n wiring. Superseded by GET /api/i18n/translations (routes/i18n/i18n_routes.py)
# for the Next.js frontend; remove this context processor once Jinja templates are gone.
@app.context_processor
def inject_i18n_helpers():
    lang = get_current_lang()
    return {"t": i18n_t, "current_lang": lang, "translations_json": get_translations(lang)}

@app.route('/set-ui-language/<lang>')
def set_ui_language(lang):
    """Guest-facing language switch: no login required, persists to DB if already logged in."""
    if lang in SUPPORTED_LANGUAGES:
        session['ui_language'] = lang
        if current_user.is_authenticated:
            update_user_ui_language(current_user.id, lang)
            current_user.ui_language = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vocab')
@login_required
def vocab_page():
    return render_template('vocab/vocab.html')

@app.route('/vocab-training-batch')
@login_required
def vocab_training_batch_page():
    return render_template('vocab/vocab_training_batch.html')

@app.route('/vocab-review')
@login_required
def vocab_review_page():
    return render_template('vocab/vocab_review.html')

@app.route('/vocab-learning')
@login_required
def vocab_learning_dashboard():
    return render_template('vocab_learning/vocab_learning.html')

@app.route('/learning')
@login_required
def learning_page():
    return render_template('learning/learning.html')

@app.route('/translation')
@login_required
def translation_page():
    return render_template('translation/translation.html')

@app.route('/grammar')
@login_required
def grammar_page():
    return render_template('grammar/grammar.html')

@app.route('/lesson')
@login_required
def lesson_page():
    return render_template('lesson/lesson.html')

@app.route('/lesson/basic-pinyin')
@login_required
def basic_pinyin_page():
    return render_template('lesson/basic_pinyin.html')

@app.route('/lesson/advanced-pinyin')
@login_required
def advanced_pinyin_page():
    return render_template('lesson/advanced_pinyin.html')

@app.route('/reading')
@login_required
def reading_page():
    return render_template('reading/reading.html')

@app.route('/practice')
@login_required
def practice_dashboard():
    category = request.args.get('category', 'practice')
    if category not in ('practice', 'exam'):
        category = 'practice'
    return render_template('practice/practice_select.html', category=category)

@app.route('/recommend')
@login_required
def recommend_page():
    return render_template('recommend/recommend.html')

@app.route('/review')
@login_required
def review_page():
    return render_template('review/review.html')

@app.route('/learn-together')
@login_required
def learn_together_page():
    return render_template('competition/learn_together.html')

@app.route('/practice/<int:number>')
@login_required
def practice_lesson_select(number):
    category = request.args.get('category', 'practice')
    if category not in ('practice', 'exam'):
        category = 'practice'
    return render_template('practice/practice_lesson_select.html', number=number, category=category)

@app.route('/practice/<int:number>/<lesson_id>')
@login_required
def practice_page(number, lesson_id):
    category = request.args.get('category', 'practice')
    if category not in ('practice', 'exam'):
        category = 'practice'
    return render_template('practice/practice_standard.html', number=number, lesson_id=lesson_id, category=category)

@app.route('/practice/<int:number>/<lesson_id>/<path:progress>')
@login_required
def practice_progress_group(number, lesson_id, progress):
    """Deep-link: opens practice_standard.html scoped to a specific progress group."""
    category = request.args.get('category', 'practice')
    return render_template('practice/practice_standard.html', number=number, lesson_id=lesson_id,
                           progress_filter=progress, category=category)

@app.route('/practice/multi')
@login_required
def practice_multi():
    """Multi-select practice mode."""
    return render_template('practice/practice.html', multi_mode=True)

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
