import os
import re
import sys
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
    get_lesson_picker_progress,
    get_passages_summary,
    get_passage_content,
    get_passage_vocab,
    get_passage_book_code,
    get_user_saved_vocab,
    get_grammar_for_lesson,
    insert_lesson_progress,
    mark_lesson_part_completed,
    mark_passage_words_mastered,
    recompute_user_level,
    get_books_summary,
    get_book_lessons,
)
from number_part import NUMBER_PART_ID, is_number_part, number_vocab_rows
from service.i18n_service import get_current_lang
from service.lesson_task_service import build_lesson_tasks

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

# A part counts as complete (updates the lesson progress bar) at or above this
# fraction correct. Word mastery still requires a perfect round.
# The task-mix and sampling logic now lives in service/lesson_task_service.py so the
# multiplayer lesson mode can reuse it.
LESSON_PASS_THRESHOLD = 0.70


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
    passages = get_passages_summary(hsk_level, get_current_lang())
    return jsonify({"passages": passages})


@lesson_bp.route('/picker-progress', methods=['GET'])
@login_required
def get_picker_progress():
    hsk_level = request.args.get('hsk_level')
    if not hsk_level:
        return jsonify({"error": "hsk_level is required"}), 400

    return jsonify(get_lesson_picker_progress(current_user.id, hsk_level))


@lesson_bp.route('/books', methods=['GET'])
@login_required
def list_books():
    return jsonify({"books": get_books_summary(current_user.id, get_current_lang())})


@lesson_bp.route('/book/<code>', methods=['GET'])
@login_required
def get_book(code):
    detail = get_book_lessons(current_user.id, code, get_current_lang())
    if detail is None:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(detail)


@lesson_bp.route('/part-complete', methods=['POST'])
@login_required
def complete_lesson_part():
    data = request.get_json(silent=True) or {}
    passage_id = data.get('passage_id')
    if not passage_id:
        return jsonify({"error": "passage_id is required"}), 400

    try:
        total = int(data.get('total', 0))
        correct = int(data.get('correct', 0))
    except (TypeError, ValueError):
        total, correct = 0, 0
    if total <= 0:
        return jsonify({"status": "incomplete", "passage_id": passage_id}), 200

    mode = 'master' if data.get('mode') == 'master' else 'part'
    ratio = correct / total
    is_perfect = correct >= total
    score_pct = round(ratio * 100)

    # Master: record the score % as progress (no threshold); mark done + word mastery
    # only on a perfect round. Part (children): keep the pass-threshold completion.
    if mode == 'master':
        completed = is_perfect
        store_score = score_pct
    else:
        if ratio < LESSON_PASS_THRESHOLD:
            return jsonify({"status": "incomplete", "passage_id": passage_id}), 200
        completed = True
        store_score = None

    if not mark_lesson_part_completed(current_user.id, passage_id,
                                      completed=completed, score_pct=store_score):
        return jsonify({"error": "Could not save lesson progress"}), 500

    # Topic-book parts (passage_id like "AML_1_1") have no vocab and don't feed the HSK
    # level, so skip word mastery and the level recompute for them.
    is_hsk_passage = bool(re.match(r'^H\d', passage_id or ""))

    # Only a perfect round grants mastery of the passage's words.
    mastered = []
    if is_perfect and is_hsk_passage:
        mastered = mark_passage_words_mastered(current_user.id, passage_id)
    # Finishing a part may complete a lesson/level, so re-derive the HSK level.
    new_level = recompute_user_level(current_user.id) if is_hsk_passage else None
    if new_level:
        current_user.level = new_level
    return jsonify({"status": "success", "passage_id": passage_id,
                    "score_pct": score_pct, "mastered_words": mastered, "level": new_level})

@lesson_bp.route('/passage/<passage_id>', methods=['GET'])
def get_passage_detail(passage_id):
    if is_number_part(passage_id):
        return jsonify({"passage": {
            "passage_id": NUMBER_PART_ID,
            "hsk_level": "HSK1",
            "lines": [],
            "title": "Number",
        }})
    passage = get_passage_content(passage_id)
    if not passage:
        return jsonify({"error": "Passage not found"}), 404
    return jsonify({"passage": passage})

@lesson_bp.route('/vocab/<passage_id>', methods=['GET'])
def get_passage_vocab_api(passage_id):
    if is_number_part(passage_id):
        return jsonify({"passage_id": passage_id, "vocab": number_vocab_rows()})
    vocab = get_passage_vocab(passage_id)

    # Book-cover lessons have no curated vocab, so fold in the current user's
    # personal saved words (deduped by cn). Regular HSK summaries are untouched.
    if current_user.is_authenticated and get_passage_book_code(passage_id):
        seen = {row["cn"] for row in vocab}
        for row in get_user_saved_vocab(current_user.id, passage_id):
            if row["cn"] not in seen:
                seen.add(row["cn"])
                vocab.append(row)
        vocab.sort(key=lambda r: r["cn"])

    return jsonify({"passage_id": passage_id, "vocab": vocab})

@lesson_bp.route('/grammar/<passage_id>', methods=['GET'])
def get_passage_grammar(passage_id):
    try:
        parts = passage_id.split('_')
        hsk_level = parts[0].replace('H', '')
        lesson = parts[1]

        # Show every grammar rule in the lesson (all parts), not just this part.
        grammar = get_grammar_for_lesson(hsk_level, lesson)
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

    mode = "master" if data.get("mode") == "master" else "part"
    tasks = build_lesson_tasks(passage_ids, mode)
    if not tasks:
        return jsonify({"error": "Passage not found"}), 404

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

    insert_lesson_progress(
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

    return jsonify({"status": "success"})
