import json
import os

from flask import session
from flask_login import current_user

# Loads and looks up UI translation strings from web_app/i18n/<lang>.json.
_I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'i18n')
SUPPORTED_LANGUAGES = ('en', 'vi')
DEFAULT_LANGUAGE = 'en'

_translations = {}


def _load_translations():
    for lang in SUPPORTED_LANGUAGES:
        path = os.path.join(_I18N_DIR, f'{lang}.json')
        with open(path, encoding='utf-8') as f:
            _translations[lang] = json.load(f)


_load_translations()


def get_translations(lang):
    return _translations.get(lang) or _translations[DEFAULT_LANGUAGE]


def translate(key, lang):
    node = get_translations(lang)
    for part in key.split('.'):
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]

    if isinstance(node, str):
        return node
    if lang != DEFAULT_LANGUAGE:
        return translate(key, DEFAULT_LANGUAGE)
    return key


def get_current_lang():
    # Logged-in users carry their saved preference; guests fall back to the session cookie.
    if current_user.is_authenticated:
        return getattr(current_user, 'ui_language', None) or DEFAULT_LANGUAGE
    return session.get('ui_language', DEFAULT_LANGUAGE)


def t(key, **vars):
    text = translate(key, get_current_lang())
    for name, value in vars.items():
        text = text.replace(f'{{{name}}}', str(value))
    return text
