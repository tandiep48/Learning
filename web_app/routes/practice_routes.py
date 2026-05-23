import os
import sys
import ast
import json

from flask import Blueprint, jsonify

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


@practice_bp.route('/<int:number>')
def get_practice(number):
    """Load practice-{number}.json, group questions by progress, return structured data."""
    json_path = os.path.join(SHARING_DIR, 'practice', f'practice-{number}.json')

    if not os.path.exists(json_path):
        return jsonify({'error': f'Practice file {number} not found'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Normalize each question
    questions = []
    for item in raw_data:
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

    # Group questions by lesson + progress (composite key to separate same progress across lessons)
    groups_order = []
    groups_map = {}
    for q in questions:
        group_key = f"{q['lesson']}_{q['progress']}"
        if group_key not in groups_map:
            groups_map[group_key] = []
            groups_order.append(group_key)
        groups_map[group_key].append(q)

    groups = [{'progress': groups_map[k][0]['progress'], 'lesson': groups_map[k][0]['lesson'], 'questions': groups_map[k]} for k in groups_order]

    level = raw_data[0].get('level', number) if raw_data else number

    return jsonify({
        'number': number,
        'level': level,
        'total_groups': len(groups),
        'groups': groups
    })
