import os
import sys
import ast
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from db import get_db_connection, insert_practice_progress, get_recommended_practices

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

practice_bp = Blueprint('practice', __name__, url_prefix='/api/practice')


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
    """Audio key can be a string, a list of strings, or a JSON array string."""
    import json
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith('['):
            try:
                return json.loads(raw)
            except Exception:
                pass
        return [raw]
    return []


@practice_bp.route('/<int:number>', methods=['GET'])
@login_required
def get_practice_lessons(number):
    """Return unique available lessons for practice level <number> from question_bank."""
    category = request.args.get('category', 'practice')
    if category not in ('practice', 'exam'):
        category = 'practice'
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT lesson
                FROM question_bank
                WHERE category = %s AND level = %s
                ORDER BY lesson
            """, (category, number))
            lessons = [str(row[0]) for row in cur.fetchall()]
    finally:
        db_conn.close()

    if not lessons:
        return jsonify({'error': f'No lessons found for {category} {number}'}), 404

    return jsonify({'number': number, 'category': category, 'lessons': lessons})

@practice_bp.route('/<int:number>/<lesson_id>', methods=['GET'])
@login_required
def get_practice_details(number, lesson_id):
    """Return all questions for level <number> lesson <lesson_id>, grouped by progress."""
    category = request.args.get('category', 'practice')
    if category not in ('practice', 'exam'):
        category = 'practice'
    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT level, lesson, no, skill, type, content, question,
                       answer, audio_key, image, options, progress, unit_id, category
                FROM question_bank
                WHERE category = %s AND level = %s AND lesson = %s
                ORDER BY no
            """, (category, number, lesson_id))
            cols = ['level', 'lesson', 'no', 'skill', 'type', 'content', 'question',
                    'answer', 'audio_key', 'image', 'options', 'progress', 'unit_id', 'category']
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        db_conn.close()

    if not rows:
        return jsonify({'error': f'No {category} questions found for lesson {lesson_id}'}), 404

    # Normalise and group by progress
    groups_order = []
    groups_map = {}
    for item in rows:
        q = {
            'level':     item['level'],
            'lesson':    item['lesson'],
            'no':        item['no'],
            'skill':     item['skill'] or 'listening',
            'type':      item['type'],
            'content':   item['content'],
            'question':  item['question'],
            'answer':    str(item['answer'] or ''),
            'audio_key': parse_audio_key(item['audio_key']),
            'image':     item['image'],
            'options':   parse_options(item['options']),
            'progress':  str(item['progress'] or ''),
            'category':  item['category'],
        }
        key = q['progress']
        if key not in groups_map:
            groups_map[key] = []
            groups_order.append(key)
        groups_map[key].append(q)

    groups = [{'progress': k, 'lesson': groups_map[k][0]['lesson'],
               'questions': groups_map[k]} for k in groups_order]

    return jsonify({
        'number': number,
        'level': rows[0]['level'],
        'lesson': lesson_id,
        'total_groups': len(groups),
        'groups': groups
    })

@practice_bp.route('/multi', methods=['POST'])
@login_required
def get_practice_multi():
    """Fetch combined questions for multiple selected practice groups."""
    data = request.json
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'No items selected'}), 400

    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        where_clauses = []
        params = []
        for item in items:
            where_clauses.append("(category = %s AND level = %s AND lesson = %s AND progress = %s)")
            params.extend([item.get('category', 'practice'), item['level'], item['lesson'], item['progress']])

        questions_sql = f"""
            SELECT level, lesson, no, skill, type, content, question,
                   answer, audio_key, image, options, progress, unit_id, category
            FROM question_bank
            WHERE {' OR '.join(where_clauses)}
            ORDER BY level, lesson, progress, no
        """
        
        with db_conn.cursor() as cur:
            cur.execute(questions_sql, params)
            cols = ['level', 'lesson', 'no', 'skill', 'type', 'content', 'question',
                    'answer', 'audio_key', 'image', 'options', 'progress', 'unit_id', 'category']
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        db_conn.close()

    if not rows:
        return jsonify({'error': 'No questions found for the selected items'}), 404

    # Group by (level, lesson, progress, category) to maintain proper question type boundaries
    groups_order = []
    groups_map = {}
    for item in rows:
        q = {
            'level':     item['level'],
            'lesson':    item['lesson'],
            'no':        item['no'],
            'skill':     item['skill'] or 'listening',
            'type':      item['type'],
            'content':   item['content'],
            'question':  item['question'],
            'answer':    str(item['answer'] or ''),
            'audio_key': parse_audio_key(item['audio_key']),
            'image':     item['image'],
            'options':   parse_options(item['options']),
            'progress':  str(item['progress'] or ''),
            'category':  item['category'],
            'unit_id':   item['unit_id']
        }
        key = f"{q['category']}-{q['level']}-{q['lesson']}-{q['progress']}"
        if key not in groups_map:
            groups_map[key] = []
            groups_order.append(key)
        groups_map[key].append(q)

    groups = []
    for k in groups_order:
        groups.append({
            'progress': groups_map[k][0]['progress'],
            'lesson': groups_map[k][0]['lesson'],
            'category': groups_map[k][0]['category'],
            'questions': groups_map[k]
        })

    return jsonify({
        'number': 'Multi',
        'level': 'Multi',
        'lesson': 'Multi',
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
                hsk_level=ans.get("hsk_level", hsk_level),
                lesson=str(ans.get("lesson", lesson)),
                question_no=ans.get("question_no"),
                skill=ans.get("skill"),
                question_type=ans.get("type"),
                user_answer=ans.get("user_answer"),
                is_correct=ans.get("is_correct"),
                response_time_ms=ans.get("response_time_ms"),
                category=ans.get("category", "practice")
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
                'audio_key': parse_audio_key(q['audio_key']),
                'image':    q['image'],
                'options':  q['options'],   # already a dict from JSONB
                'progress': q['progress'],
                'unit_id':  q['unit_id'],
                'category': q.get('category', 'practice'),
            })
        results.append({
            'level':        g['level'],
            'lesson':       g['lesson'],
            'progress':     g['progress'],
            'skill':        g['skill'],
            'type':         g['type'],
            'category':     g.get('category', 'practice'),
            'unit_ids':     g['unit_ids'],
            'total_words':  g['total_words'],
            'known_words':  g['known_words'],
            'coverage_pct': g['coverage_pct'],
            'matched_words': g.get('matched_words', []),
            'recent_matched_words': g.get('recent_matched_words', []),
            'newest_learned_at': g.get('newest_learned_at'),
            'recent_score': g.get('recent_score', 0),
            'status':       g.get('status', 'Not start'),
            'questions':    qs,
        })

    return jsonify({'recommendations': results})


@practice_bp.route('/<int:level>/<int:lesson>/<path:progress>', methods=['GET'])
@login_required
def get_progress_group(level, lesson, progress):
    """Return all questions for a specific progress group from question_bank."""
    category = request.args.get('category', 'practice')

    db_conn = get_db_connection()
    if not db_conn:
        return jsonify({'error': 'Database unavailable'}), 503

    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT no, skill, type, content, question, answer,
                       audio_key, image, options, progress, unit_id, level, category
                FROM question_bank
                WHERE category = %s AND level = %s
                  AND lesson = %s AND progress = %s
                ORDER BY no
            """, (category, level, lesson, progress))
            cols = ['no','skill','type','content','question','answer',
                    'audio_key','image','options','progress','unit_id','level','category']
            questions = [dict(zip(cols, r)) for r in cur.fetchall()]
            for q in questions:
                q['audio_key'] = parse_audio_key(q['audio_key'])
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
