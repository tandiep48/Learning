"""Request rate limiting for the JSON API (Flask-Limiter).

One shared `limiter` is created here and attached to the app by
`init_rate_limiting(app)`. Routes opt into a tighter budget with
`@limiter.limit(...)` using the named limits below; every other route falls back to
the generous per-client default, which only stops a runaway client.

Until `init_rate_limiting` is called the decorators are inert, so blueprint-level
tests that build their own Flask app are unaffected.

Configuration (all optional):
  RATELIMIT_ENABLED       "false" turns limiting off entirely (default on)
  RATELIMIT_DEFAULT       default budget for every route (";"-separated)
  RATELIMIT_STORAGE_URI   counter store; "memory://" is exact for the single
                          gunicorn worker we run, use "redis://host:6379" once
                          WEB_CONCURRENCY > 1 so workers share their counts
  TRUSTED_PROXY_COUNT     reverse proxies in front of the app whose X-Forwarded-For
                          entry is trusted for the client IP (default 1; 0 = none)
"""
import os

from flask import jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

DEFAULT_LIMIT = "300 per minute;5000 per hour"

# Credential checks: slows password guessing and account-creation spam.
AUTH_LIMIT = "10 per minute;60 per hour"
# State-changing account / write endpoints a human uses occasionally.
SENSITIVE_WRITE_LIMIT = "10 per minute;60 per hour"
# CPU- or storage-heavy endpoints (speech scoring, large list queries).
HEAVY_LIMIT = "30 per minute;600 per hour"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.getenv("RATELIMIT_DEFAULT", DEFAULT_LIMIT)],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    headers_enabled=True,
)


def _too_many_requests(exc):
    response = jsonify({
        "success": False,
        "error": "Too many requests. Please slow down and try again shortly.",
    })
    response.status_code = 429
    retry_after = getattr(exc, "retry_after", None)
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


def init_rate_limiting(app):
    """Attach the limiter, trusted-proxy client-IP handling and the JSON 429."""
    proxies = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))
    if proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies)
    app.config["RATELIMIT_ENABLED"] = os.getenv("RATELIMIT_ENABLED", "true").lower() != "false"
    limiter.init_app(app)
    app.register_error_handler(429, _too_many_requests)
