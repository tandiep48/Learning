import os
import secrets
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request
from flask_cors import CORS
from flask_login import LoginManager, login_required
from routes.vocab_routes import vocab_bp
from routes.lesson_routes import lesson_bp
from routes.practice_routes import practice_bp
from routes.auth_routes import auth_bp, get_user_by_id

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
CORS(app)

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
app.register_blueprint(auth_bp)

GCS_BUCKET_URL = os.getenv('GCS_BUCKET_URL', '')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vocab')
@login_required
def vocab_page():
    return render_template('vocab/vocab.html')

@app.route('/vocab-learning')
@login_required
def vocab_learning_dashboard():
    return render_template('shared/level_select.html', app_mode='vocab-learning')

@app.route('/vocab-learning/<hsk_level>')
@login_required
def vocab_learning_page(hsk_level):
    return render_template('vocab_learning/vocab_learning.html', hsk_level=hsk_level)

@app.route('/lesson')
@login_required
def lesson_dashboard():
    return render_template('shared/level_select.html', app_mode='lesson')

@app.route('/lesson/<hsk_level>')
@login_required
def lesson_page(hsk_level):
    return render_template('lesson/lesson.html', hsk_level=hsk_level)

@app.route('/reading')
@login_required
def reading_dashboard():
    return render_template('shared/level_select.html', app_mode='reading')

@app.route('/reading/<hsk_level>')
@login_required
def reading_page(hsk_level):
    return render_template('reading/reading.html', hsk_level=hsk_level)

@app.route('/practice')
@login_required
def practice_dashboard():
    return render_template('practice/practice_select.html')

@app.route('/recommend')
@login_required
def recommend_page():
    return render_template('recommend/recommend.html')

@app.route('/practice/<int:number>')
@login_required
def practice_lesson_select(number):
    return render_template('practice/practice_lesson_select.html', number=number)

@app.route('/practice/<int:number>/<lesson_id>')
@login_required
def practice_page(number, lesson_id):
    return render_template('practice/practice.html', number=number, lesson_id=lesson_id)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
