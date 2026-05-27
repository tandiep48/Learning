import os
import sys
import ast
import json

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from db import get_db_connection, insert_practice_progress, get_recommended_practices

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

practice_bp = Blueprint('practice', __name__, url_prefix='/api/practice')

# Base directory: web_app/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sharing_file is two levels up from web_app
SHARING_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'sharing_file'))


def parse_options(raw):
    """Safely parse options whether it's already a dict or a Python-style string like \"{'A': True}\"."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return {}


def parse_audio_key(raw):
    """Audio key can be a string or a list of strings."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]


@practice_bp.route('/<int:number>', methods=['GET'])
@login_required
def get_practice_lessons(number):
    """Load practice-{number}.json and return unique available lessons."""
    json_path = os.path.join(SHARING_DIR, 'practice', f'practice-{number}.json')
    if not os.path.exists(json_path):
        return jsonify({'error': f'Practice file {number} not found'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    lessons = set()
    for item in raw_data:
        lesson = item.get('lesson')
        if lesson is not None:
            lessons.add(str(lesson))

    # Try to sort numerically if possible, otherwise alphabetically
    sorted_lessons = sorted(list(lessons), key=lambda x: int(x) if x.isdigit() else x)
    
    return jsonify({
        'number': number,
        'lessons': sorted_lessons
    })

@practice_bp.route('/<int:number>/<lesson_id>', methods=['GET'])
@login_required
def get_practice_details(number, lesson_id):
    """Load practice-{number}.json, filter by lesson, group questions by progress."""
    json_path = os.path.join(SHARING_DIR, 'practice', f'practice-{number}.json')

    if not os.path.exists(json_path):
        return jsonify({'error': f'Practice file {number} not found'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Filter and Normalize each question
    questions = []
    for item in raw_data:
        if str(item.get('lesson', '')) != str(lesson_id):
            continue
            
        questions.append({
            'level':     item.get('level'),
            'lesson':    item.get('lesson'),
            'no':        item.get('no'),
            'skill':     item.get('skill', 'listening'),
            'type':      item.get('type'),
            'content':   item.get('content'),
            'question':  item.get('question'),
            'answer':    str(item.get('answer', '')),
            'audio_key': parse_audio_key(item.get('audio_key')),
            'image':     item.get('image'),
            'options':   parse_options(item.get('options')),
            'progress':  str(item.get('progress', '')),
        })

    if not questions:
        return jsonify({'error': f'No questions found for lesson {lesson_id}'}), 404

    # Group questions by progress
    groups_order = []
    groups_map = {}
    for q in questions:
        group_key = q['progress']
        if group_key not in groups_map:
            groups_map[group_key] = []
            groups_order.append(group_key)
        groups_map[group_key].append(q)

    groups = [{'progress': k, 'lesson': groups_map[k][0]['lesson'], 'questions': groups_map[k]} for k in groups_order]

    level = raw_data[0].get('level', number) if raw_data else number

    return jsonify({
        'number': number,
        'level': level,
        'lesson': lesson_id,
        'total_groups': len(groups),
        'groups': groups
    })

@practice_bp.route('/submit', methods=['POST'])
@login_required
def submit_practice():
    data = request.json
    session_id = data.get("session_id")
    hsk_level = data.get("hsk_level")
    lesson = data.get("lesson")
    user_answers = data.get("answers", []) # list of { question_no, skill, type, user_answer, is_correct }
    
    db_conn = get_db_connection()
    if db_conn:
        for ans in user_answers:
            insert_practice_progress(
                conn=db_conn,
                user_id=current_user.id,
                session_id=session_id,
                hsk_level=hsk_level,
                lesson=lesson,
                question_no=ans.get("question_no"),
                skill=ans.get("skill"),
                question_type=ans.get("type"),
                user_answer=ans.get("user_answer"),
                is_correct=ans.get("is_correct")
            )
        db_conn.close()
        
    return jsonify({"status": "success"})


@practice_bp.route('/recommend', methods=['GET'])
@login_required
def get_recommendations():
    """Return ranked practice progress groups the user is ready for (coverage >= 0.75).
    Data comes entirely from question_bank + learning_units + vocab_records.
    """
    
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        groups = get_recommended_practices(db_conn, current_user.id, threshold=0.75)
    finally:
        db_conn.close()

    # groups already contain full question data — just serialise options
    results = []
    for g in groups:
        qs = []
        for q in g['questions']:
            qs.append({
                'no':       q['no'],
                'skill':    q['skill'],
                'type':     q['type'],
                'content':  q['content'],
                'question': q['question'],
                'answer':   q['answer'],
                'audio_key': q['audio_key'],
                'image':    q['image'],
                'options':  q['options'],   # already a dict from JSONB
                'progress': q['progress'],
                'unit_id':  q['unit_id'],
            })
        results.append({
            'level':        g['level'],
            'lesson':       g['lesson'],
            'progress':     g['progress'],
            'skill':        g['skill'],
            'type':         g['type'],
            'unit_ids':     g['unit_ids'],
            'total_words':  g['total_words'],
            'known_words':  g['known_words'],
            'coverage_pct': g['coverage_pct'],
            'questions':    qs,
        })

    return jsonify({'recommendations': results})


@practice_bp.route('/<int:level>/<int:lesson>/<path:progress>', methods=['GET'])
@login_required
def get_progress_group(level, lesson, progress):
    """Return all questions for a specific progress group from question_bank."""
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT no, skill, type, content, question, answer,
                       audio_key, image, options, progress, unit_id
                FROM question_bank
                WHERE category = 'practice' AND level = %s
                  AND lesson = %s AND progress = %s
                ORDER BY no
            """, (level, lesson, progress))
            cols = ['no','skill','type','content','question','answer',
                    'audio_key','image','options','progress','unit_id']
            questions = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        db_conn.close()

    if not questions:
        return jsonify({'error': 'Group not found'}), 404

    return jsonify({
        'level':    level,
        'lesson':   lesson,
        'progress': progress,
        'questions': questions,
    })
