import os
import secrets
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_required
from flask_socketio import SocketIO
from routes.vocab_routes import vocab_bp
from routes.lesson_routes import lesson_bp
from routes.practice_routes import practice_bp
from routes.competition_routes import competition_bp
from routes.auth_routes import auth_bp, get_user_by_id
from routes.user_routes import user_bp
from routes.vocab_crud_routes import vocab_crud_bp
from routes.passage_crud_routes import passage_crud_bp
from competition_socket import init_competition_socket

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
CORS(app)
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
init_competition_socket(socketio)

GCS_BUCKET_URL = os.getenv('GCS_BUCKET_URL', '')

@app.context_processor
def inject_avatar_helpers():
    def avatar_url(avatar_path):
        if not avatar_path or not GCS_BUCKET_URL:
            return None
        return f"{GCS_BUCKET_URL.rstrip('/')}/{str(avatar_path).lstrip('/')}"

    def hsk_image_url(level):
        if not GCS_BUCKET_URL:
            return ''
        level_num = str(level).replace('HSK', '').replace('hsk', '').replace('H', '').replace('h', '')
        if level_num not in {'1', '2', '3', '4', '5', '6'}:
            return ''
        return f"{GCS_BUCKET_URL.rstrip('/')}/hsk_images/hsk{level_num}.png"

    return {"avatar_url": avatar_url, "hsk_image_url": hsk_image_url}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vocab')
@login_required
def vocab_page():
    return render_template('vocab/vocab.html')

@app.route('/vocab-training')
@login_required
def vocab_training_page():
    return render_template('vocab/vocab_training.html')

@app.route('/vocab-learning')
@login_required
def vocab_learning_dashboard():
    return render_template('vocab_learning/vocab_learning.html')

@app.route('/learning')
@login_required
def learning_page():
    return render_template('learning/learning.html')

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
    return render_template('practice/practice.html', number=number, lesson_id=lesson_id, category=category)

@app.route('/practice/<int:number>/<lesson_id>/<path:progress>')
@login_required
def practice_progress_group(number, lesson_id, progress):
    """Deep-link: opens practice.html scoped to a specific progress group."""
    category = request.args.get('category', 'practice')
    return render_template('practice/practice.html', number=number, lesson_id=lesson_id,
                           progress_filter=progress, category=category)

@app.route('/practice/multi')
@login_required
def practice_multi():
    """Multi-select practice mode."""
    return render_template('practice/practice.html', multi_mode=True)

@app.route('/practice_image/<int:level>/<path:filename>')
def serve_practice_image(level, filename):
    category = request.args.get('category', 'practice')
    return redirect(f"{GCS_BUCKET_URL}/images/{category}/{level}/{filename}")

@app.route('/practice_audio/<int:number>/<path:filename>')
def serve_practice_audio(number, filename):
    category = request.args.get('category', 'practice')
    return redirect(f"{GCS_BUCKET_URL}/question_bank/{category}/{category}-{number}/{filename}")

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return redirect(f"{GCS_BUCKET_URL}/vocab_audio/{filename}")

@app.route('/lesson_audio/<path:filename>')
def serve_lesson_audio(filename):
    return redirect(f"{GCS_BUCKET_URL}/lesson_audio/{filename}")

@app.route('/lesson-image/<hsk>/<filename>')
def serve_lesson_image(hsk, filename):
    # Convert formats like 'h1-lesson-2.png' to 'H1-lesson 2.png'
    formatted_filename = filename.lower().replace('-lesson-', '-lesson ')
    if formatted_filename.startswith(hsk.lower()):
        formatted_filename = hsk.upper() + formatted_filename[len(hsk):]
    return redirect(f"{GCS_BUCKET_URL}/lesson_images/{hsk.upper()}/{formatted_filename}")

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=debug_mode, port=port, use_reloader=False, allow_unsafe_werkzeug=True)
