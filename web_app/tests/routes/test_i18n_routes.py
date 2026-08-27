import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.i18n.i18n_routes import i18n_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(i18n_bp)
    app.testing = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/i18n/translations
# ---------------------------------------------------------------------------

def test_get_translations_defaults_to_current_lang(client):
    with patch("routes.i18n.i18n_routes.get_current_lang", return_value="en"), \
         patch("routes.i18n.i18n_routes.get_translations", return_value={"hello": "Hello"}) as mock_get:
        response = client.get("/api/i18n/translations")

    assert response.status_code == 200
    body = response.get_json()
    assert body == {"success": True, "data": {"lang": "en", "translations": {"hello": "Hello"}}}
    mock_get.assert_called_once_with("en")


def test_get_translations_explicit_lang_overrides_current_lang(client):
    with patch("routes.i18n.i18n_routes.get_current_lang", return_value="en"), \
         patch("routes.i18n.i18n_routes.get_translations", return_value={"hello": "Xin chao"}) as mock_get:
        response = client.get("/api/i18n/translations?lang=vi")

    assert response.status_code == 200
    body = response.get_json()
    assert body == {"success": True, "data": {"lang": "vi", "translations": {"hello": "Xin chao"}}}
    mock_get.assert_called_once_with("vi")


def test_get_translations_rejects_unsupported_lang(client):
    response = client.get("/api/i18n/translations?lang=fr")

    assert response.status_code == 400
    body = response.get_json()
    assert body == {"success": False, "error": "Unsupported language: fr"}
