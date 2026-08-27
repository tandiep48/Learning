"""
routes/i18n/i18n_routes.py
----------------------------
Read-only API for UI translation strings, built for the Next.js frontend.

Wraps the existing `service.i18n_service` module as-is (no logic changes).

Prefix: /api/i18n

Endpoints:
    GET /api/i18n/translations            -> translations for the caller's current language
    GET /api/i18n/translations?lang=vi     -> translations for an explicit language
"""
from flask import Blueprint, jsonify, request

from service.i18n_service import get_translations, get_current_lang, SUPPORTED_LANGUAGES

i18n_bp = Blueprint('i18n', __name__, url_prefix='/api/i18n')


@i18n_bp.route('/translations', methods=['GET'])
def get_ui_translations():
    lang = request.args.get('lang') or get_current_lang()
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"success": False, "error": f"Unsupported language: {lang}"}), 400

    return jsonify({"success": True, "data": {"lang": lang, "translations": get_translations(lang)}}), 200
