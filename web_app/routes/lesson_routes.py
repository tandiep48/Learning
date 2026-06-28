import os
import sys
import uuid
import random
import json
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import (
    get_db_connection,
    get_lesson_picker_progress,
    get_passages_summary,
    get_passage_content,
    get_all_vn_meanings,
    get_passage_vocab,
    get_grammar_for_passage,
    insert_lesson_progress,
    mark_lesson_part_completed,
)

lesson_bp = Blueprint('lesson', __name__, url_prefix='/api/lesson')

@lesson_bp.route('/passages', methods=['GET'])
def get_passages():
    hsk_level = request.args.get('hsk_level')
    conn = get_db_connection()
    passages = get_passages_summary(conn, hsk_level)
    conn.close()
    return jsonify({"passages": passages})


@lesson_bp.route('/picker-progress', methods=['GET'])
@login_required
def get_picker_progress():
    hsk_level = request.args.get('hsk_level')
    if not hsk_level:
        return jsonify({"error": "hsk_level is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        return jsonify(get_lesson_picker_progress(conn, current_user.id, hsk_level))
    finally:
        conn.close()


@lesson_bp.route('/part-complete', methods=['POST'])
@login_required
def complete_lesson_part():
    data = request.get_json(silent=True) or {}
    passage_id = data.get('passage_id')
    if not passage_id:
        return jsonify({"error": "passage_id is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        if not mark_lesson_part_completed(conn, current_user.id, passage_id):
            return jsonify({"error": "Could not save lesson progress"}), 500
        return jsonify({"status": "success", "passage_id": passage_id})
    finally:
        conn.close()

@lesson_bp.route('/passage/<passage_id>', methods=['GET'])
def get_passage_detail(passage_id):
    conn = get_db_connection()
    passage = get_passage_content(conn, passage_id)
    conn.close()
    if not passage:
        return jsonify({"error": "Passage not found"}), 404
    return jsonify({"passage": passage})

@lesson_bp.route('/vocab/<passage_id>', methods=['GET'])
def get_passage_vocab_api(passage_id):
    conn = get_db_connection()
    vocab = get_passage_vocab(conn, passage_id)
    conn.close()
    return jsonify({"passage_id": passage_id, "vocab": vocab})

@lesson_bp.route('/grammar/<passage_id>', methods=['GET'])
def get_passage_grammar(passage_id):
    try:
        parts = passage_id.split('_')
        hsk_level = parts[0].replace('H', '')
        lesson = parts[1]
        passage_number = parts[2]
        
        conn = get_db_connection()
        grammar = get_grammar_for_passage(conn, hsk_level, lesson, passage_number)
        conn.close()
        return jsonify({"grammar": grammar})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@lesson_bp.route('/start', methods=['POST'])
@login_required
def start_session():
    data = request.json
    passage_id = data.get("passage_id")
    passage_ids = data.get("passage_ids") or []
    if passage_id and not passage_ids:
        passage_ids = [passage_id]
    if not isinstance(passage_ids, list) or not passage_ids:
        return jsonify({"error": "passage_id or passage_ids is required"}), 400
    
    conn = get_db_connection()
    passages = []
    for pid in passage_ids:
        passage = get_passage_content(conn, pid)
        if passage:
            passages.append((pid, passage))
    if not passages:
        conn.close()
        return jsonify({"error": "Passage not found"}), 404
        
    global_vn_meanings = get_all_vn_meanings(conn)
    conn.close()
    
    line_items = []
    for pid, passage in passages:
        for line in passage.get("lines", []):
            line_items.append((pid, passage, line))
    
    # We will generate a mix of tasks for the lines in this passage
    tasks = []
    
    # Collect all Vietnamese meanings in this passage for distractors
    all_vn_meanings = [line["translations"]["vi"] for _, _, line in line_items]
    
    for line_passage_id, passage, line in line_items:
        line_id = line.get("line_id", 0)
        correct_meaning = line["translations"]["vi"]
        
        # 1. Meaning Task
        meaning_options = list(set([opt for opt in all_vn_meanings if opt != correct_meaning]))
        distractors = random.sample(meaning_options, min(3, len(meaning_options)))
        m_options = distractors + [correct_meaning]
        random.shuffle(m_options)
        
        tasks.append({
            "type": "meaning",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "options": m_options,
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "hsk_level": passage.get("hsk_level")
        })
        
        # 2. Listening Task
        tasks.append({
            "type": "listening",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "options": m_options, # Same options logic as meaning
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "content": line["content"], # provided for reveal
            "hsk_level": passage.get("hsk_level")
        })
        
        # 3. Reorder Task
        tokens = line.get("tokens", [])
        if len(tokens) > 1: # Only reorder if there are multiple tokens
            shuffled_tokens = tokens[:]
            random.shuffle(shuffled_tokens)
            tasks.append({
                "type": "reorder",
                "passage_id": line_passage_id,
                "line_id": line_id,
                "content": line["content"],
                "tokens": tokens,
                "shuffled_tokens": shuffled_tokens,
                "correct_answer": "".join(tokens),
                "audio_key": line.get("audio_key"),
                "hsk_level": passage.get("hsk_level")
            })
            
        # 4. Typing Task
        tasks.append({
            "type": "typing",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "correct_answer": line["content"],
            "audio_key": line.get("audio_key"),
            "pinyin": line.get("pinyin", ""),
            "hsk_level": passage.get("hsk_level")
        })
        
    random.shuffle(tasks)
    
    # We might want to limit the tasks if it's too long
    # Let's limit to 10 tasks per session by default
    limit = data.get("limit", 10)
    if str(limit).isdigit() and int(limit) > 0 and len(tasks) > int(limit):
        limit = int(limit)
        tasks = tasks[:limit]
        
    return jsonify({
        "session_id": int(time.time() * 1000),
        "tasks": tasks
    })

@lesson_bp.route('/submit', methods=['POST'])
@login_required
def submit_lesson():
    data = request.json
    session_id = data.get("session_id")
    passage_id = data.get("passage_id")
    line_id = data.get("line_id")
    mode_str = data.get("type")
    mode_map = {'meaning': 1, 'typing': 2, 'type': 2, 'reorder': 3, 'listening': 4, 'listen': 4}
    mode = mode_map.get(mode_str, 1)
    user_answer = data.get("user_answer")
    is_correct = data.get("is_correct")
    response_time_ms = data.get("response_time_ms", 0)
    game_info = data.get("game_info", "{}")
    
    db_conn = get_db_connection()
    if db_conn:
        insert_lesson_progress(
            conn=db_conn,
            user_id=current_user.id,
            session_id=session_id,
            passage_id=passage_id,
            line_id=line_id,
            mode=mode,
            game_info=json.dumps(game_info, ensure_ascii=False),
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            updated_at=datetime.now()
        )
        db_conn.close()
        
    return jsonify({"status": "success"})
