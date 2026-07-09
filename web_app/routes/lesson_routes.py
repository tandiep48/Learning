import os
import re
import sys
import uuid
import random
import json
import time
import logging
import unicodedata
from logging.handlers import RotatingFileHandler
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
    mark_passage_words_mastered,
    recompute_user_level,
)
from number_part import NUMBER_PART_ID, is_number_part, number_vocab_rows

lesson_bp = Blueprint('lesson', __name__, url_prefix='/api/lesson')

# ── Lesson-trainer diagnostic log ────────────────────────────────────────────
# Appends one JSON line per answered task to help debug the reorder issues
# (answers marked wrong despite looking identical, and text appearing to grow on
# review). Override the path with LESSON_TRAINER_LOG.
_LESSON_LOG_PATH = os.getenv("LESSON_TRAINER_LOG") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "lesson_trainer.log"
)


def _build_lesson_logger():
    logger = logging.getLogger("lesson_trainer")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        os.makedirs(os.path.dirname(_LESSON_LOG_PATH), exist_ok=True)
        handler = RotatingFileHandler(
            _LESSON_LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    except Exception as e:
        print(f"[WARN] lesson_trainer log init failed: {e}")
    return logger


_lesson_logger = _build_lesson_logger()


# Mirror of the client's ANSWER_PUNCT_MAP so normalized_equal matches answersMatch.
_ANSWER_PUNCT_MAP = {
    '、': ',', '。': '.', '｡': '.', '【': '[', '】': ']', '《': '<', '》': '>',
    '「': '"', '」': '"', '『': '"', '』': '"', '“': '"', '”': '"', '‘': "'", '’': "'",
    '～': '~', '—': '-', '–': '-', '‧': '', '·': '', '・': '',
}
_WS_RE = re.compile(r"[\s​‌‍﻿]")


def _normalize_answer(value):
    """Mirror the client's normalizeAnswer: NFKC, fold CJK punctuation to ASCII, then
    drop whitespace/zero-width chars. Lets normalized_equal cross-check is_correct."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = "".join(_ANSWER_PUNCT_MAP.get(ch, ch) for ch in text)
    return _WS_RE.sub("", text)


def _codepoints(value):
    return [f"U+{ord(ch):04X}" for ch in str(value or "")]


def log_lesson_event(user_id, session_id, passage_id, line_id, task_type,
                     user_answer, correct_answer, is_correct, response_time_ms, tokens):
    """Record one answered task. Adds codepoint dumps when the result is wrong or when
    the raw strings look identical, so invisible/lookalike differences are visible."""
    try:
        event = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user_id": user_id,
            "session_id": session_id,
            "passage_id": passage_id,
            "line_id": line_id,
            "type": task_type,
            "is_correct": is_correct,
            "response_time_ms": response_time_ms,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "tokens": tokens,
        }
        if user_answer is not None and correct_answer is not None:
            raw_equal = user_answer == correct_answer
            event["raw_equal"] = raw_equal
            event["normalized_equal"] = _normalize_answer(user_answer) == _normalize_answer(correct_answer)
            # The interesting cases: marked wrong, or strings that look the same.
            if not is_correct or raw_equal:
                event["user_codepoints"] = _codepoints(user_answer)
                event["correct_codepoints"] = _codepoints(correct_answer)
        _lesson_logger.info(json.dumps(event, ensure_ascii=False))
    except Exception as e:
        print(f"[WARN] lesson_trainer log write failed: {e}")

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

    # A part only counts as complete when the round was perfect. The client sends the
    # score; guard here so a non-100% run never marks the lesson done.
    try:
        total = int(data.get('total', 0))
        correct = int(data.get('correct', 0))
    except (TypeError, ValueError):
        total, correct = 0, 0
    if total <= 0 or correct < total:
        return jsonify({"status": "incomplete", "passage_id": passage_id}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        if not mark_lesson_part_completed(conn, current_user.id, passage_id):
            return jsonify({"error": "Could not save lesson progress"}), 500
        # 100% completion grants mastery of the passage's words.
        mastered = mark_passage_words_mastered(conn, current_user.id, passage_id)
        # Finishing a part may complete a lesson/level, so re-derive the HSK level.
        new_level = recompute_user_level(conn, current_user.id)
        if new_level:
            current_user.level = new_level
        return jsonify({"status": "success", "passage_id": passage_id,
                        "mastered_words": mastered, "level": new_level})
    finally:
        conn.close()

@lesson_bp.route('/passage/<passage_id>', methods=['GET'])
def get_passage_detail(passage_id):
    if is_number_part(passage_id):
        return jsonify({"passage": {
            "passage_id": NUMBER_PART_ID,
            "hsk_level": "HSK1",
            "lines": [],
            "title": "Number",
        }})
    conn = get_db_connection()
    passage = get_passage_content(conn, passage_id)
    conn.close()
    if not passage:
        return jsonify({"error": "Passage not found"}), 404
    return jsonify({"passage": passage})

@lesson_bp.route('/vocab/<passage_id>', methods=['GET'])
def get_passage_vocab_api(passage_id):
    if is_number_part(passage_id):
        return jsonify({"passage_id": passage_id, "vocab": number_vocab_rows()})
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
    correct_answer = data.get("correct_answer")
    is_correct = data.get("is_correct")
    response_time_ms = data.get("response_time_ms", 0)
    game_info = data.get("game_info", "{}")

    tokens = game_info.get("tokens") if isinstance(game_info, dict) else None
    log_lesson_event(
        user_id=current_user.id,
        session_id=session_id,
        passage_id=passage_id,
        line_id=line_id,
        task_type=mode_str,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        response_time_ms=response_time_ms,
        tokens=tokens,
    )

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
