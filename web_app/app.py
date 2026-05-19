import os
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from routes.vocab_routes import vocab_bp
from routes.lesson_routes import lesson_bp

app = Flask(__name__)
CORS(app)

# Register Blueprints
app.register_blueprint(vocab_bp)
app.register_blueprint(lesson_bp)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FOLDER = os.path.join(BASE_DIR, "data", "vocab_audio")
LESSON_AUDIO_FOLDER = os.path.join(BASE_DIR, "data", "lesson_audio")

@app.route('/')
def index():
    # This will be the main dashboard
    return render_template('index.html')

@app.route('/vocab')
def vocab_page():
    return render_template('vocab.html')

@app.route('/lesson')
def lesson_dashboard():
    return render_template('level_select.html', app_mode='lesson')

@app.route('/lesson/<hsk_level>')
def lesson_page(hsk_level):
    return render_template('lesson.html', hsk_level=hsk_level)

@app.route('/reading')
def reading_dashboard():
    return render_template('level_select.html', app_mode='reading')

@app.route('/reading/<hsk_level>')
def reading_page(hsk_level):
    return render_template('reading.html', hsk_level=hsk_level)

GCS_BUCKET_URL = "https://storage.googleapis.com/chinese-learning-audio-assets"

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    from flask import redirect
    return redirect(f"{GCS_BUCKET_URL}/vocab_audio/{filename}")

@app.route('/lesson_audio/<path:filename>')
def serve_lesson_audio(filename):
    from flask import redirect
    return redirect(f"{GCS_BUCKET_URL}/lesson_audio/{filename}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
