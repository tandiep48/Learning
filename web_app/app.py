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
def lesson_page():
    return render_template('lesson.html')

@app.route('/reading')
def reading_page():
    return render_template('reading.html')

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

@app.route('/lesson_audio/<path:filename>')
def serve_lesson_audio(filename):
    return send_from_directory(LESSON_AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
