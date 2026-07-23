import os
import sys
from flask import Blueprint, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_connection, get_lesson_translations

translation_bp = Blueprint('translation', __name__, url_prefix='/api/translation')


@translation_bp.route('/lesson', methods=['GET'])
def get_lesson_translation():
    hsk_level = request.args.get('hsk_level')
    lesson = request.args.get('lesson')
    if not hsk_level or not lesson:
        return jsonify({"error": "hsk_level and lesson are required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        translations = get_lesson_translations(conn, hsk_level, lesson)
        return jsonify({"translations": translations})
    finally:
        conn.close()
