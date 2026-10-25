"""
service/token_service.py
-------------------------
Stateless bearer tokens for the mobile client (Flutter `chinese_learning`).

Cookie sessions are awkward on mobile, so the app authenticates once via
`POST /api/auth/token` and then sends `Authorization: Bearer <token>` on every
request. The token is a signed, timed `itsdangerous` payload carrying only the
`user_id` — no server-side session store, no new dependency (itsdangerous ships
with Flask). The signature is keyed on `app.secret_key`, so a token cannot be
forged or tampered with, and it expires after `TOKEN_MAX_AGE_SECONDS`.

Used by the `/api/auth/token` endpoint (mint) and the `request_loader` in
`app.py` (verify), which together let every existing `@login_required` route
accept the token transparently alongside session-cookie auth.
"""

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Long-lived token: the mobile slice re-logs in on expiry rather than carrying
# refresh-token machinery (see the port plan's open question on expiry).
TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days

_SALT = "yi-chinese-mobile-auth"


def _serializer() -> URLSafeTimedSerializer:
    # Keyed on the app secret so tokens survive config reloads but not a key
    # rotation; must be called within an app context.
    return URLSafeTimedSerializer(current_app.secret_key, salt=_SALT)


def generate_auth_token(user_id) -> str:
    """Mint a signed bearer token for the given user id."""
    return _serializer().dumps({"user_id": user_id})


def load_auth_token(token: str, max_age: int = TOKEN_MAX_AGE_SECONDS):
    """Return the `user_id` from a valid token, or None if the token is
    missing, tampered, or expired. Never raises for bad input."""
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    return payload.get("user_id")
