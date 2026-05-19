import os
import sys
import uuid
import random
import json
from datetime import datetime
from flask import Blueprint, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_connection, insert_lesson_progress, get_passages_summary, get_passage_content, get_all_vn_meanings

lesson_bp = Blueprint('lesson', __name__, url_prefix='/api/lesson')

USER_ID = "default_user_1"

@lesson_bp.route('/passages', methods=['GET'])
def get_passages():
    hsk_level = request.args.get('hsk_level')
    conn = get_db_connection()
    passages = get_passages_summary(conn, hsk_level)
    conn.close()
    return jsonify({"passages": passages})

@lesson_bp.route('/passage/<passage_id>', methods=['GET'])
def get_passage_detail(passage_id):
    conn = get_db_connection()
    passage = get_passage_content(conn, passage_id)
    conn.close()
    if not passage:
        return jsonify({"error": "Passage not found"}), 404
    return jsonify({"passage": passage})

@lesson_bp.route('/start', methods=['POST'])
def start_lesson():
    data = request.json
    passage_id = data.get("passage_id")
    
    conn = get_db_connection()
    passage = get_passage_content(conn, passage_id)
    if not passage:
        conn.close()
        return jsonify({"error": "Passage not found"}), 404
        
    global_vn_meanings = get_all_vn_meanings(conn)
    conn.close()
    
    lines = passage.get("lines", [])
    
    # We will generate a mix of tasks for the lines in this passage
    tasks = []
    
    # Collect all Vietnamese meanings in this passage for distractors
    all_vn_meanings = [l["translations"]["vi"] for l in lines]
    
    for line in lines:
        line_id = line.get("line_id", 0)
        correct_meaning = line["translations"]["vi"]
        
        # 1. Meaning Task
        meaning_options = list(set([opt for opt in all_vn_meanings if opt != correct_meaning]))
        if len(meaning_options) < 3:
            additional_distractors = list(set([opt for opt in global_vn_meanings if opt != correct_meaning and opt not in meaning_options]))
            needed = 3 - len(meaning_options)
            meaning_options.extend(random.sample(additional_distractors, min(needed, len(additional_distractors))))
        
        distractors = random.sample(meaning_options, min(3, len(meaning_options)))
        m_options = distractors + [correct_meaning]
        random.shuffle(m_options)
        
        tasks.append({
            "type": "meaning",
            "passage_id": passage_id,
            "line_id": line_id,
            "content": line["content"],
            "options": m_options,
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key")
        })
        
        # 2. Listening Task
        tasks.append({
            "type": "listening",
            "passage_id": passage_id,
            "line_id": line_id,
            "options": m_options, # Same options logic as meaning
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "content": line["content"] # provided for reveal
        })
        
        # 3. Reorder Task
        tokens = line.get("tokens", [])
        if len(tokens) > 1: # Only reorder if there are multiple tokens
            shuffled_tokens = tokens[:]
            random.shuffle(shuffled_tokens)
            tasks.append({
                "type": "reorder",
                "passage_id": passage_id,
                "line_id": line_id,
                "content": line["content"],
                "tokens": tokens,
                "shuffled_tokens": shuffled_tokens,
                "correct_answer": "".join(tokens),
                "audio_key": line.get("audio_key")
            })
            
        # 4. Typing Task
        tasks.append({
            "type": "typing",
            "passage_id": passage_id,
            "line_id": line_id,
            "content": line["content"],
            "correct_answer": line["content"],
            "audio_key": line.get("audio_key"),
            "pinyin": line.get("pinyin", "")
        })
        
    random.shuffle(tasks)
    
    # We might want to limit the tasks if it's too long
    # Let's limit to 10 tasks per session by default
    limit = data.get("limit", 10)
    if len(tasks) > limit:
        tasks = tasks[:limit]
        
    return jsonify({
        "session_id": str(uuid.uuid4()),
        "tasks": tasks
    })

@lesson_bp.route('/submit', methods=['POST'])
def submit_lesson():
    data = request.json
    session_id = data.get("session_id")
    passage_id = data.get("passage_id")
    line_id = data.get("line_id")
    mode = data.get("type")
    user_answer = data.get("user_answer")
    is_correct = data.get("is_correct")
    response_time_ms = data.get("response_time_ms", 0)
    game_info = data.get("game_info", "{}")
    
    db_conn = get_db_connection()
    if db_conn:
        insert_lesson_progress(
            conn=db_conn,
            user_id=USER_ID,
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
