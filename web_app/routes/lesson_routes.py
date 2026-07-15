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
    get_passage_vocab,
    get_grammar_for_lesson,
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

# ── Lesson-trainer question mix ──────────────────────────────────────────────
# A round samples a fixed number of tasks (so the learner no longer answers every
# possible question) split across the four task types. "part" = one part; "master"
# = the whole lesson (all parts).
LESSON_TASK_DISTRIBUTION = [
    ("listening", 0.30),
    ("meaning", 0.30),
    ("typing", 0.30),
    ("reorder", 0.10),
]

LESSON_PART_COUNTS = {
    "HSK1": 10, "HSK2": 12, "HSK3": 15,
    "HSK4": 18, "HSK5": 21, "HSK6": 24,
}

LESSON_MASTER_COUNTS = {
    "HSK1": 24, "HSK2": 36, "HSK3": 48,
    "HSK4": 54, "HSK5": 75, "HSK6": 90,
}

DEFAULT_LESSON_TASK_COUNT = 10

# A part counts as complete (updates the lesson progress bar) at or above this
# fraction correct. Word mastery still requires a perfect round.
LESSON_PASS_THRESHOLD = 0.70


def _normalize_hsk_level(raw):
    """Coerce values like 'HSK1', 'H1', '1' to the canonical 'HSK1' form."""
    s = str(raw or "").upper().strip()
    if s.startswith("HSK"):
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    return f"HSK{digits}" if digits else ""


def _allocate_task_counts(total, distribution):
    """Split `total` across the distribution, using largest-remainder rounding so
    the per-type counts always sum back to `total`."""
    raw = [(name, total * pct) for name, pct in distribution]
    counts = {name: int(value) for name, value in raw}
    remainder = total - sum(counts.values())
    # Hand the leftover slots to the types with the biggest fractional parts.
    by_frac = sorted(raw, key=lambda item: item[1] - int(item[1]), reverse=True)
    for name, _ in by_frac[:remainder]:
        counts[name] += 1
    return counts


def _sample_task_pool(pool, count):
    """Pick `count` tasks from `pool`. Prefers unique tasks; only repeats when the
    pool is smaller than the requested count."""
    if count <= 0 or not pool:
        return []
    if count <= len(pool):
        return random.sample(pool, count)
    return pool[:] + random.choices(pool, k=count - len(pool))


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

    # A part counts as complete at or above the pass threshold. The client sends the
    # score; guard here so a low run never marks the lesson done.
    try:
        total = int(data.get('total', 0))
        correct = int(data.get('correct', 0))
    except (TypeError, ValueError):
        total, correct = 0, 0
    if total <= 0 or (correct / total) < LESSON_PASS_THRESHOLD:
        return jsonify({"status": "incomplete", "passage_id": passage_id}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        if not mark_lesson_part_completed(conn, current_user.id, passage_id):
            return jsonify({"error": "Could not save lesson progress"}), 500
        # Only a perfect round grants mastery of the passage's words.
        mastered = []
        if correct >= total:
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

        # Show every grammar rule in the lesson (all parts), not just this part.
        conn = get_db_connection()
        grammar = get_grammar_for_lesson(conn, hsk_level, lesson)
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
        
    conn.close()

    line_items = []
    for pid, passage in passages:
        for line in passage.get("lines", []):
            line_items.append((pid, passage, line))

    # Only quiz lines that introduce a new word (flag == 1), so learners skip
    # review-only lines. Fall back to every line if a part has no flagged lines,
    # so a directly-selected part is never empty.
    flagged_items = [item for item in line_items if item[2].get("flag", 1) == 1]
    if flagged_items:
        line_items = flagged_items

    # Build a pool of candidate tasks per type, one per line, then sample from each
    # pool to hit the target count and 30/30/30/10 mix.
    pools = {"listening": [], "meaning": [], "typing": [], "reorder": []}

    # Collect all Vietnamese meanings in this session for multiple-choice distractors.
    all_vn_meanings = [line["translations"]["vi"] for _, _, line in line_items]

    for line_passage_id, passage, line in line_items:
        line_id = line.get("line_id", 0)
        correct_meaning = line["translations"]["vi"]

        meaning_options = list(set([opt for opt in all_vn_meanings if opt != correct_meaning]))
        distractors = random.sample(meaning_options, min(3, len(meaning_options)))
        m_options = distractors + [correct_meaning]
        random.shuffle(m_options)

        pools["meaning"].append({
            "type": "meaning",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "options": m_options,
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "hsk_level": passage.get("hsk_level")
        })

        pools["listening"].append({
            "type": "listening",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "options": m_options,  # Same options logic as meaning
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "content": line["content"],  # provided for reveal
            "hsk_level": passage.get("hsk_level")
        })

        tokens = line.get("tokens", [])
        if len(tokens) > 1:  # Only reorder if there are multiple tokens
            shuffled_tokens = tokens[:]
            random.shuffle(shuffled_tokens)
            pools["reorder"].append({
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

        pools["typing"].append({
            "type": "typing",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "correct_answer": line["content"],
            "audio_key": line.get("audio_key"),
            "pinyin": line.get("pinyin", ""),
            "hsk_level": passage.get("hsk_level")
        })

    # Target count depends on the mode (part vs master) and the lesson's HSK level.
    mode = "master" if data.get("mode") == "master" else "part"
    hsk_level = _normalize_hsk_level(passages[0][1].get("hsk_level"))
    count_table = LESSON_MASTER_COUNTS if mode == "master" else LESSON_PART_COUNTS
    target_total = count_table.get(hsk_level, DEFAULT_LESSON_TASK_COUNT)

    targets = _allocate_task_counts(target_total, LESSON_TASK_DISTRIBUTION)

    # If a type has no candidates (e.g. no multi-token lines → no reorder), move its
    # share to the first type that does have material.
    for name in ("reorder", "typing", "meaning", "listening"):
        if targets.get(name) and not pools[name]:
            moved = targets[name]
            targets[name] = 0
            for fallback in ("meaning", "listening", "typing"):
                if pools[fallback]:
                    targets[fallback] += moved
                    break

    tasks = []
    for name, _ in LESSON_TASK_DISTRIBUTION:
        tasks.extend(_sample_task_pool(pools[name], targets.get(name, 0)))
    random.shuffle(tasks)

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
