"""Rate limiting (service/rate_limit.py): per-client budgets, JSON 429, trusted-proxy
client IPs, the on/off switch, and that the credential routes carry the auth budget."""
import os
import sys

import pytest
from flask import Flask, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from service import rate_limit
from service.rate_limit import limiter


def make_app(monkeypatch, *, enabled="true", proxies="1"):
    monkeypatch.setenv("RATELIMIT_ENABLED", enabled)
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", proxies)
    app = Flask(__name__)

    @app.route("/limited")
    @limiter.limit("2 per minute")
    def limited():
        return jsonify({"ok": True})

    @app.route("/free")
    @limiter.exempt
    def free():
        return jsonify({"ok": True})

    rate_limit.init_rate_limiting(app)
    limiter.reset()
    return app


def hit(client, path="/limited", ip="1.1.1.1", **headers):
    return client.get(path, environ_base={"REMOTE_ADDR": ip}, headers=headers)


def test_blocks_after_the_budget_with_a_json_429(monkeypatch):
    client = make_app(monkeypatch).test_client()
    assert hit(client).status_code == 200
    assert hit(client).status_code == 200

    blocked = hit(client)
    assert blocked.status_code == 429
    assert blocked.get_json()["success"] is False
    assert int(blocked.headers["Retry-After"]) > 0


def test_budgets_are_per_client(monkeypatch):
    client = make_app(monkeypatch, proxies="0").test_client()
    for _ in range(3):
        hit(client, ip="1.1.1.1")
    assert hit(client, ip="1.1.1.1").status_code == 429
    assert hit(client, ip="2.2.2.2").status_code == 200


def test_trusted_proxy_header_identifies_the_client(monkeypatch):
    client = make_app(monkeypatch, proxies="1").test_client()
    # Same proxy address, different real clients behind it: separate budgets.
    for _ in range(3):
        hit(client, ip="10.0.0.1", **{"X-Forwarded-For": "5.5.5.5"})
    assert hit(client, ip="10.0.0.1", **{"X-Forwarded-For": "5.5.5.5"}).status_code == 429
    assert hit(client, ip="10.0.0.1", **{"X-Forwarded-For": "6.6.6.6"}).status_code == 200


def test_spoofed_forwarded_entries_do_not_buy_a_fresh_budget(monkeypatch):
    client = make_app(monkeypatch, proxies="1").test_client()
    # Only the entry the trusted proxy appended (rightmost) counts.
    for i in range(3):
        hit(client, ip="10.0.0.1", **{"X-Forwarded-For": f"9.9.9.{i}, 5.5.5.5"})
    assert hit(client, ip="10.0.0.1", **{"X-Forwarded-For": "9.9.9.200, 5.5.5.5"}).status_code == 429


def test_exempt_routes_are_never_limited(monkeypatch):
    client = make_app(monkeypatch).test_client()
    assert all(hit(client, "/free").status_code == 200 for _ in range(20))


def test_can_be_switched_off(monkeypatch):
    client = make_app(monkeypatch, enabled="false").test_client()
    assert all(hit(client).status_code == 200 for _ in range(10))


def test_login_carries_the_auth_budget(monkeypatch):
    from routes.auth import auth_routes

    monkeypatch.setattr(auth_routes, "get_user_by_username", lambda name: None)
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "0")
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(auth_routes.auth_bp)
    rate_limit.init_rate_limiting(app)
    limiter.reset()
    client = app.test_client()

    body = {"username": "x", "password": "y"}
    statuses = [client.post("/api/auth/login", json=body).status_code for _ in range(11)]
    assert 429 not in statuses[:10]
    assert statuses[10] == 429
    # The mobile token route shares the credential budget bucket per route, so it is
    # limited on its own count rather than inheriting the login route's.
    assert client.post("/api/auth/token", json=body).status_code != 429


@pytest.fixture(autouse=True)
def _reset_limiter():
    yield
    limiter.reset()
