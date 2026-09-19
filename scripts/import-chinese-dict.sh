#!/usr/bin/env bash
#
# Bulk-upsert the word dictionary spreadsheet into vocabulary /
# chinese_stroke_info / sematic_diffculty on a Linux host, using the app's venv.
# Safe to re-run — nothing is deleted, existing words are updated in place.
#
# Usage:
#   ./scripts/import-chinese-dict.sh                 # dry-run (default, writes nothing)
#   ./scripts/import-chinese-dict.sh --apply         # import for real
#   ./scripts/import-chinese-dict.sh --apply --chunk-size 10000
#   DICT_FILE=/data/chinese_dict_new.xlsx ./scripts/import-chinese-dict.sh --apply
#   DICT_FILE=/data ./scripts/import-chinese-dict.sh --apply   # folder holding the xlsx
#
# DB_* connection vars are read from web_app/.env (same as the app).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/web_app"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
VENV_PYTHON="$VENV_DIR/bin/python"

# Workbook to import, or the folder holding it. Defaults to the copy at the repo
# root; override with DICT_FILE=/path.
DICT_FILE="${DICT_FILE:-$ROOT_DIR/chinese_dict_new.xlsx}"

# Default to a dry-run; everything else is forwarded to the Python importer.
MODE="--dry-run"
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --apply) MODE="--apply" ;;
    --dry-run) MODE="--dry-run" ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Virtual environment was not found at $VENV_DIR. Run ./scripts/run-pre-prod.sh first." >&2
  exit 1
fi

if [[ ! -e "$DICT_FILE" ]]; then
  echo "Dictionary path not found: $DICT_FILE" >&2
  echo "Set DICT_FILE to the xlsx you want to import, or to the folder holding it." >&2
  exit 1
fi

cd "$APP_DIR"
echo "Importing dictionary ($MODE) from $DICT_FILE"
exec "$VENV_PYTHON" scripts/import_chinese_dict.py "$MODE" --file "$DICT_FILE" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
