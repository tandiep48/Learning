import os
import sys
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from routes.chinese_stroke_info_routes import chinese_stroke_info_bp
from entity.chinese_stroke_info.service import ChineseStrokeInfoServiceError


class FakeUser(UserMixin):
    def __init__(self, id):
        self.id = id

    def get_id(self):
        return str(self.id)


STROKE_INFO_DICT = {
    "cn": "你好", "zh": "你好", "total_strokes_cn": 9, "total_strokes_zh": 9,
    "strokes_cn": "3,6", "strokes_zh": "3,6", "word_length": 2,
    "strokes_difficult_cn": 3.5, "strokes_difficult_cn_norm": 0.5,
    "strokes_difficult_zh": 3.5, "strokes_difficult_zh_norm": 0.5,
}


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.testing = True
    app.register_blueprint(chinese_stroke_info_bp)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return FakeUser(user_id)

    return app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True
    return client


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_get_stroke_info_endpoint_requires_login(client):
    resp = client.get("/api/chinese_stroke_info/你好")
    assert resp.status_code == 401


def test_batch_endpoint_requires_login(client):
    resp = client.get("/api/chinese_stroke_info?words=你好")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/chinese_stroke_info/<cn>
# ---------------------------------------------------------------------------

def test_get_stroke_info_endpoint_found(logged_in_client):
    with patch("routes.chinese_stroke_info_routes.get_stroke_info", return_value=STROKE_INFO_DICT):
        resp = logged_in_client.get("/api/chinese_stroke_info/你好")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["cn"] == "你好"


def test_get_stroke_info_endpoint_not_found(logged_in_client):
    with patch(
        "routes.chinese_stroke_info_routes.get_stroke_info",
        side_effect=ChineseStrokeInfoServiceError("Chinese stroke info for 'xyz' not found.", 404),
    ):
        resp = logged_in_client.get("/api/chinese_stroke_info/xyz")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "not found" in body["error"]


# ---------------------------------------------------------------------------
# GET /api/chinese_stroke_info (batch)
# ---------------------------------------------------------------------------

def test_batch_endpoint_success(logged_in_client):
    with patch(
        "routes.chinese_stroke_info_routes.get_stroke_info_batch",
        return_value=[STROKE_INFO_DICT],
    ) as mock_batch:
        resp = logged_in_client.get("/api/chinese_stroke_info?words=你好,谢谢")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"][0]["cn"] == "你好"
    mock_batch.assert_called_once_with(["你好", "谢谢"])


def test_batch_endpoint_rejects_missing_words_param(logged_in_client):
    resp = logged_in_client.get("/api/chinese_stroke_info")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
