import os
import sys
import time
import random
import json
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
    get_vocab_lessons
)


vocab_bp = Blueprint('vocab', __name__, url_prefix='/api/vocab')

def get_full_lesson_records():
    conn = get_db_connection()
    df = get_course_vocab(conn)
    conn.close()
    if not df.empty:
        return df[['word','pinyin','meaning_en','meaning_vn', 'audio_key', 'level']].dropna(subset=['word']).drop_duplicates(subset=['word']).reset_index(drop=True)
    return pd.DataFrame()

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
    if hsk_level.startswith("H") and len(hsk_level) == 2:
        hsk_level = "HSK" + hsk_level[1]

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
        if hsk_level.startswith("H") and len(hsk_level) == 2:
            hsk_level = "HSK" + hsk_level[1]
            
        start_idx = int(data.get("start_idx", 0))
        end_idx = int(data.get("end_idx", 10))
        
        full_lesson_records = get_full_lesson_records()
        if not full_lesson_records.empty:
            lesson = full_lesson_records[full_lesson_records['level'] == hsk_level].reset_index(drop=True)
            subset = lesson.iloc[start_idx:end_idx+1].reset_index(drop=True)
            subset_words = subset["word"].tolist()
        
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
                # Use only other words from the same lesson as distractors
                lesson_pool = subset_df[subset_df["word"] != row["word"]]["meaning_vn"].dropna().unique().tolist()
                sample_size = min(3, len(lesson_pool))
                other_words = random.sample(lesson_pool, sample_size)
                options = [row["meaning_vn"]] + other_words
                random.shuffle(options)
                task["options"] = options
            
            tasks.append(task)
            
    random.shuffle(tasks)
    
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
