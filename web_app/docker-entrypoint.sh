#!/bin/sh
set -e

# Materialise the Google Cloud service-account key from a secret env var, if one
# is provided, so the storage client (avatar uploads) can authenticate. Public
# reads only need GCS_BUCKET_URL and work without any key.
if [ -n "$GCS_SA_KEY_JSON" ]; then
  CRED_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-/tmp/gcs-sa.json}"
  printf '%s' "$GCS_SA_KEY_JSON" > "$CRED_PATH"
  export GOOGLE_APPLICATION_CREDENTIALS="$CRED_PATH"
fi

# One eventlet worker by default: Flask-SocketIO needs a shared message queue
# (e.g. Redis) before it can run more than one, or rooms/broadcasts break.
exec gunicorn \
  --worker-class eventlet \
  --workers "${WEB_CONCURRENCY:-1}" \
  --bind "0.0.0.0:${PORT:-8080}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  app:app
