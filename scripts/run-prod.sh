#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/web_app"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
VENV_PYTHON="$VENV_DIR/bin/python"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
WORKERS="${WEB_CONCURRENCY:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
LOG_LEVEL="${GUNICORN_LOG_LEVEL:-info}"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Cannot find web_app directory at $APP_DIR" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Virtual environment was not found at $VENV_DIR. Run ./scripts/run-pre-prod.sh first." >&2
  exit 1
fi

VENV_VERSION="$("$VENV_PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
if [[ "$VENV_VERSION" != "3.12" ]]; then
  echo "Existing venv uses Python $VENV_VERSION, not 3.12. Recreate $VENV_DIR with Python 3.12." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg was not found on PATH. Speaking audio may fail to decode." >&2
fi

cd "$APP_DIR"
exec "$VENV_PYTHON" -m gunicorn app:app \
  --bind "$HOST:$PORT" \
  --workers "$WORKERS" \
  --timeout "$TIMEOUT" \
  --log-level "$LOG_LEVEL" \
  --access-logfile - \
  --error-logfile -
