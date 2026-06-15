#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/web_app"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_PATH="$APP_DIR/requirements.txt"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Cannot find web_app directory at $APP_DIR" >&2
  exit 1
fi

if [[ ! -f "$REQUIREMENTS_PATH" ]]; then
  echo "Cannot find requirements.txt at $REQUIREMENTS_PATH" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_VERSION="$("$VENV_PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
if [[ "$VENV_VERSION" != "3.12" ]]; then
  echo "Existing venv uses Python $VENV_VERSION, not 3.12. Recreate $VENV_DIR with Python 3.12." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_PATH"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg was not found on PATH. Speaking audio may fail to decode." >&2
fi

echo "Production environment is ready. Start the app with ./scripts/run-prod.sh."
