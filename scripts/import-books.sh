#!/usr/bin/env bash
#
# Import the cover-book lessons (AML, CHE, ...) into lesson_passages/lesson_lines
# on a Linux host, using the app's venv. Safe to re-run — a passage's lines are
# fully replaced each apply.
#
# Usage:
#   ./scripts/import-books.sh                 # dry-run (default, writes nothing)
#   ./scripts/import-books.sh --apply         # import for real
#   ./scripts/import-books.sh --apply --codes AML,CHE
#   SOURCE_DIR=/data/content_info/Final ./scripts/import-books.sh --apply
#   RUN_SCHEMA=1 ./scripts/import-books.sh --apply   # add book_code column first
#
# DB_* connection vars are read from web_app/.env (same as the app).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT_DIR/web_app"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
VENV_PYTHON="$VENV_DIR/bin/python"

# Folder holding the {CODE}.json files. Defaults next to the repo
# (YiChinese/content_info/Final); override with SOURCE_DIR=/path.
SOURCE_DIR="${SOURCE_DIR:-$ROOT_DIR/../content_info/Final}"

# Default to a dry-run; everything is forwarded to the Python importer.
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

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source folder not found: $SOURCE_DIR" >&2
  echo "Set SOURCE_DIR to the folder holding {CODE}.json (e.g. content_info/Final)." >&2
  exit 1
fi

# Optionally ensure the book_code column/index exists first (idempotent).
if [[ "${RUN_SCHEMA:-0}" == "1" ]]; then
  echo "Applying schema (book_code column + index)..."
  ( cd "$ROOT_DIR/schema_sql_file" && "$VENV_PYTHON" update_schema.py )
fi

cd "$APP_DIR"
echo "Importing book lessons ($MODE) from $SOURCE_DIR"
exec "$VENV_PYTHON" scripts/import_book_lessons.py "$MODE" --source "$SOURCE_DIR" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
