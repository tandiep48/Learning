import os
import sys
import time
import random
import json
import re
import subprocess
import tempfile
import wave
import pandas as pd
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

# Add web_app directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import (
    get_db_connection, 
    insert_learning_progress, 
    get_unlearned_words_from_db, 
    get_unsure_words_from_db, 
    get_hard_semantic_learned_words, 
    get_hard_stroke_learned_words,
    get_course_vocab,
    has_vocab_history,
    get_vocab_lessons,
    get_passage_vocab
)


vocab_bp = Blueprint('vocab', __name__, url_prefix='/api/vocab')

SPEAKING_SCORE_THRESHOLD = int(os.getenv("SPEAKING_SCORE_THRESHOLD", "80"))
SPEAKING_MAX_AUDIO_BYTES = int(os.getenv("SPEAKING_MAX_AUDIO_BYTES", str(5 * 1024 * 1024)))
SPEAKING_SAMPLE_RATE = int(os.getenv("SPEAKING_SAMPLE_RATE", "16000"))
DEFAULT_VOSK_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "vosk-model-small-cn-0.22"
)
_SPEAKING_ASR_MODEL = None


def get_speaking_asr_model():
    global _SPEAKING_ASR_MODEL
    if _SPEAKING_ASR_MODEL is not None:
        return _SPEAKING_ASR_MODEL

    from vosk import Model

    model_path = os.getenv("VOSK_MODEL_PATH", DEFAULT_VOSK_MODEL_PATH)
    if not os.path.isdir(model_path):
        raise FileNotFoundError(
            f"Vosk model folder not found at {model_path}. "
            "Download a Chinese Vosk model and set VOSK_MODEL_PATH."
        )

    _SPEAKING_ASR_MODEL = Model(model_path)
    return _SPEAKING_ASR_MODEL


def convert_audio_to_vosk_wav(input_path):
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-ac",
        "1",
        "-ar",
        str(SPEAKING_SAMPLE_RATE),
        "-f",
        "wav",
        output_path,
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except FileNotFoundError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError("ffmpeg is required to decode browser audio for Vosk.") from e
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError("ffmpeg could not convert this recording.") from e


def transcribe_with_vosk(model, wav_path):
    from vosk import KaldiRecognizer

    parts = []
    with wave.open(wav_path, "rb") as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("Vosk requires mono 16-bit PCM WAV audio.")

        recognizer = KaldiRecognizer(model, wav_file.getframerate())
        recognizer.SetWords(False)

        while True:
            data = wav_file.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                partial = json.loads(recognizer.Result()).get("text", "")
                if partial:
                    parts.append(partial)

        final = json.loads(recognizer.FinalResult()).get("text", "")
        if final:
            parts.append(final)

    return "".join(parts)


def normalize_spoken_text(value):
    value = str(value or "").strip()
    return re.sub(r"[^\u3400-\u9fffA-Za-z0-9]+", "", value)


def text_to_tone_pinyin(value):
    from pypinyin import Style, lazy_pinyin

    cleaned = normalize_spoken_text(value)
    return " ".join(lazy_pinyin(cleaned, style=Style.TONE3, errors="ignore")).lower().strip()


def score_spoken_word(expected_word, audio_path):
    from rapidfuzz import fuzz

    model = get_speaking_asr_model()
    wav_path = None
    try:
        wav_path = convert_audio_to_vosk_wav(audio_path)
        recognized_text = normalize_spoken_text(transcribe_with_vosk(model, wav_path))
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

    expected_pinyin = text_to_tone_pinyin(expected_word)
    recognized_pinyin = text_to_tone_pinyin(recognized_text)

    score = 0
    if expected_pinyin and recognized_pinyin:
        score = round(float(fuzz.ratio(expected_pinyin, recognized_pinyin)), 1)

    return {
        "recognized_text": recognized_text,
        "expected_pinyin": expected_pinyin,
        "recognized_pinyin": recognized_pinyin,
        "score": score,
        "threshold": SPEAKING_SCORE_THRESHOLD,
        "is_correct": score >= SPEAKING_SCORE_THRESHOLD
    }

def normalize_hsk_level(hsk_level):
    if not hsk_level:
        return ""
    hsk_level = str(hsk_level).upper()
    if hsk_level.startswith("H") and not hsk_level.startswith("HSK") and len(hsk_level) == 2:
        return "HSK" + hsk_level[1]
    return hsk_level

def hsk_to_passage_prefix(hsk_level):
    hsk_level = normalize_hsk_level(hsk_level)
    if hsk_level.startswith("HSK"):
        return "H" + hsk_level[3:]
    return hsk_level

def clean_vocab_value(value):
    if pd.isna(value):
        return ""
    return value

def normalize_vocab_row(row):
    word = clean_vocab_value(row.get("word", row.get("cn", "")))
    return {
        "word": word,
        "cn": word,
        "pinyin": clean_vocab_value(row.get("pinyin", "")),
        "meaning_vn": clean_vocab_value(row.get("meaning_vn", "")),
        "meaning_en": clean_vocab_value(row.get("meaning_en", "")),
        "audio_key": clean_vocab_value(row.get("audio_key", "")),
        "level": clean_vocab_value(row.get("level", row.get("hsk_level", "")))
    }

def get_full_lesson_records():
    conn = get_db_connection()
    df = get_course_vocab(conn)
    conn.close()
    if not df.empty:
        return df[['word','pinyin','meaning_en','meaning_vn', 'audio_key', 'level']].dropna(subset=['word']).drop_duplicates(subset=['word']).reset_index(drop=True)
    return pd.DataFrame()

def build_vocab_tasks(subset_df):
    subset_df = subset_df.fillna("")
    task_types = ["listen", "typing", "meaning"]
    tasks = []

    for _, row in subset_df.iterrows():
        for t_type in task_types:
            task = {
                "word": row["word"],
                "pinyin": row["pinyin"],
                "meaning_en": row["meaning_en"],
                "meaning_vn": row["meaning_vn"],
                "type": t_type,
                "audio_key": row.get("audio_key", "")
            }

            if t_type in ["listen", "meaning"]:
                lesson_pool = subset_df[subset_df["word"] != row["word"]]["meaning_vn"].dropna().unique().tolist()
                sample_size = min(3, len(lesson_pool))
                other_words = random.sample(lesson_pool, sample_size)
                options = [row["meaning_vn"]] + other_words
                random.shuffle(options)
                task["options"] = options

            tasks.append(task)

    random.shuffle(tasks)
    return tasks

def get_records_for_words(words):
    if not words:
        return pd.DataFrame()

    full_lesson_records = get_full_lesson_records()
    if full_lesson_records.empty:
        return pd.DataFrame()

    cleaned_words = []
    seen = set()
    for word in words:
        word = str(word).strip()
        if word and word not in seen:
            cleaned_words.append(word)
            seen.add(word)

    subset_df = full_lesson_records[full_lesson_records["word"].isin(cleaned_words)].copy()
    if subset_df.empty:
        return subset_df

    order_map = {word: index for index, word in enumerate(cleaned_words)}
    subset_df["__selected_order"] = subset_df["word"].map(order_map)
    return subset_df.sort_values("__selected_order").drop(columns=["__selected_order"]).reset_index(drop=True)

def paginate_rows(rows, page, page_size):
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total, total_pages, page

@vocab_bp.route('/table', methods=['GET'])
@login_required
def get_vocab_table():
    table_mode = request.args.get("mode", "free")
    hsk_level = normalize_hsk_level(request.args.get("hsk_level", ""))
    lesson = request.args.get("lesson")
    part = request.args.get("part")
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(5, int(request.args.get("page_size", 20))))

    rows = []
    passage_id = None

    if table_mode == "standard":
        if not hsk_level or not lesson or not part:
            return jsonify({
                "rows": [],
                "page": 1,
                "page_size": page_size,
                "total": 0,
                "total_pages": 1,
                "passage_id": None
            })

        passage_id = f"{hsk_to_passage_prefix(hsk_level)}_{lesson}_{part}"
        db_conn = get_db_connection()
        if not db_conn:
            return jsonify({"error": "Database connection failed."}), 500
        try:
            rows = [normalize_vocab_row(row) for row in get_passage_vocab(db_conn, passage_id)]
        finally:
            db_conn.close()

    elif table_mode == "free":
        if not hsk_level:
            return jsonify({
                "rows": [],
                "page": 1,
                "page_size": page_size,
                "total": 0,
                "total_pages": 1
            })

        full_lesson_records = get_full_lesson_records()
        if not full_lesson_records.empty:
            level_df = full_lesson_records[full_lesson_records["level"] == hsk_level].reset_index(drop=True)
            rows = [normalize_vocab_row(row) for row in level_df.to_dict("records")]

    elif table_mode in ("unlearn", "unsure"):
        db_conn = get_db_connection()
        if not db_conn:
            return jsonify({"error": "Database connection failed."}), 500
        try:
            if table_mode == "unlearn":
                words = get_unlearned_words_from_db(db_conn, current_user.id)
            else:
                words = get_unsure_words_from_db(db_conn, current_user.id)
        finally:
            db_conn.close()

        subset_df = get_records_for_words(words)
        if not subset_df.empty:
            rows = [normalize_vocab_row(row) for row in subset_df.to_dict("records")]
    else:
        return jsonify({"error": "Invalid table mode."}), 400

    page_rows, total, total_pages, page = paginate_rows(rows, page, page_size)
    return jsonify({
        "rows": page_rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "passage_id": passage_id
    })

@vocab_bp.route('/flashcards', methods=['POST'])
@login_required
def get_flashcard_words():
    data = request.json or {}
    words = data.get("words", [])
    subset_df = get_records_for_words(words)
    if subset_df.empty:
        return jsonify({"words": []})
    return jsonify({"words": [normalize_vocab_row(row) for row in subset_df.to_dict("records")]})

@vocab_bp.route('/has_history', methods=['GET'])
@login_required
def check_has_history():
    """Returns whether the current user has any vocab learning history."""
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({"has_history": False})
    result = has_vocab_history(db_conn, current_user.id)
    db_conn.close()
    return jsonify({"has_history": result})

@vocab_bp.route('/lessons/<hsk_level>', methods=['GET'])
@login_required
def get_lessons_for_level(hsk_level):
    """Returns lesson groups (chunks of 10 words) for a given HSK level."""
    # Normalize: H1 -> HSK1
    hsk_level = normalize_hsk_level(hsk_level)

    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({"error": "Database connection failed."}), 500

    lessons = get_vocab_lessons(db_conn, hsk_level)
    db_conn.close()

    if not lessons:
        return jsonify({"error": f"No vocabulary found for {hsk_level}."}), 404

    return jsonify({"hsk_level": hsk_level, "lessons": lessons})

@vocab_bp.route('/preview', methods=['POST'])
@login_required
def preview_mode():
    data = request.json
    mode = str(data.get("mode"))
    
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({"error": "Database connection failed."}), 500
    
    words = []
    if mode == "2":
        words = get_unlearned_words_from_db(db_conn, current_user.id)
    elif mode == "3":
        words = get_unsure_words_from_db(db_conn, current_user.id)
    elif mode == "4":
        words = get_hard_semantic_learned_words(db_conn, current_user.id)
    elif mode == "5":
        words = get_hard_stroke_learned_words(db_conn, current_user.id)
    elif mode == "6":
        passage_id = data.get("passage_id")
        passage_vocab = get_passage_vocab(db_conn, passage_id)
        words = [w["cn"] for w in passage_vocab]
    else:
        db_conn.close()
        return jsonify({"error": "Invalid preview mode."}), 400
        
    db_conn.close()
    
    if not words:
        return jsonify({"words": []})
        
    full_lesson_records = get_full_lesson_records()
    if full_lesson_records.empty:
        return jsonify({"words": []})
        
    subset_df = full_lesson_records[full_lesson_records["word"].isin(words)].drop_duplicates("word").reset_index(drop=True)
    word_list = subset_df.to_dict('records')
    return jsonify({"words": word_list})

@vocab_bp.route('/start', methods=['POST'])
@login_required
def start_session():
    data = request.json
    mode = str(data.get("mode"))
    
    subset_words = []
    
    if mode == "1":
        hsk_level = data.get("hsk_level", "H1")
        # Normalize "H1" to "HSK1" to match database formatting
        hsk_level = normalize_hsk_level(hsk_level)
            
        start_idx = int(data.get("start_idx", 0))
        end_idx = int(data.get("end_idx", 10))
        
        full_lesson_records = get_full_lesson_records()
        if not full_lesson_records.empty:
            lesson = full_lesson_records[full_lesson_records['level'] == hsk_level].reset_index(drop=True)
            subset = lesson.iloc[start_idx:end_idx+1].reset_index(drop=True)
            subset_words = subset["word"].tolist()
        
    elif mode == "7":
        subset_df = get_records_for_words(data.get("words", []))
        if subset_df.empty:
            return jsonify({"error": "No valid words found for this selection."}), 404

        tasks = build_vocab_tasks(subset_df)
        return jsonify({
            "session_id": int(time.time() * 1000),
            "tasks": tasks
        })

    else:
        db_conn = get_db_connection()
        if not db_conn:
            return jsonify({"error": "Database connection failed."}), 500
        
        if mode == "2":
            words = get_unlearned_words_from_db(db_conn, current_user.id)
        elif mode == "3":
            words = get_unsure_words_from_db(db_conn, current_user.id)
        elif mode == "4":
            words = get_hard_semantic_learned_words(db_conn, current_user.id)
        elif mode == "5":
            words = get_hard_stroke_learned_words(db_conn, current_user.id)
        elif mode == "6":
            passage_id = data.get("passage_id")
            passage_vocab = get_passage_vocab(db_conn, passage_id)
            words = [w["cn"] for w in passage_vocab]
        else:
            db_conn.close()
            return jsonify({"error": "Invalid mode."}), 400
            
        db_conn.close()
        
        limit = data.get("limit")
        if limit is not None and str(limit).isdigit() and int(limit) > 0:
            words = random.sample(words, min(int(limit), len(words)))
            
        subset_words = words

    if not subset_words:
        return jsonify({"error": "No words found for this selection."}), 404
        
    full_lesson_records = get_full_lesson_records()
    if full_lesson_records.empty:
        return jsonify({"error": "No lesson records available."}), 404

    subset_df = full_lesson_records[full_lesson_records["word"].isin(subset_words)].reset_index(drop=True)
    tasks = build_vocab_tasks(subset_df)
    
    return jsonify({
        "session_id": int(time.time() * 1000),
        "tasks": tasks
    })

@vocab_bp.route('/submit', methods=['POST'])
@login_required
def submit_progress():
    data = request.json
    session_id = data.get("session_id")
    mode = data.get("type")
    word = data.get("word")
    round_num = data.get("round_num", 1)
    user_answer = data.get("user_answer")
    is_correct = data.get("is_correct")
    response_time_ms = data.get("response_time_ms", 0)
    game_info = data.get("game_info", "{}")
    
    db_conn = get_db_connection()
    if db_conn:
        insert_learning_progress(
            conn=db_conn,
            user_id=current_user.id,
            session_id=session_id,
            mode=mode,
            word=word,
            round_num=round_num,
            game_info=json.dumps(game_info, ensure_ascii=False),
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=datetime.now()
        )
        db_conn.close()
        
    return jsonify({"status": "success"})


@vocab_bp.route('/speaking/score', methods=['POST'])
@login_required
def score_speaking_attempt():
    word = (request.form.get("word") or "").strip()
    audio = request.files.get("audio")

    if not word:
        return jsonify({"error": "Missing target word."}), 400
    if not audio or not audio.filename:
        return jsonify({"error": "Missing audio recording."}), 400

    content_length = request.content_length or 0
    if content_length > SPEAKING_MAX_AUDIO_BYTES:
        return jsonify({"error": "Audio recording is too large. Please try a shorter attempt."}), 413

    suffix = os.path.splitext(audio.filename)[1] or ".webm"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            audio.save(temp_file)

        result = score_spoken_word(word, temp_path)
        if not result["recognized_text"]:
            result["message"] = "I could not detect clear speech. Please try again."
        elif result["is_correct"]:
            result["message"] = "Nice pronunciation."
        else:
            result["message"] = "Try again and listen closely to the pinyin."

        return jsonify(result)
    except ImportError as e:
        return jsonify({
            "error": f"Speaking dependencies are not installed: {e.name or str(e)}."
        }), 503
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        print(f"[WARN] speaking score failed: {e}")
        return jsonify({
            "error": "Could not score this recording. Please try again."
        }), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
