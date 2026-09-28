# syntax=docker/dockerfile:1
# Flask + Socket.IO API for Yi Chinese, served by gunicorn's eventlet worker.
# Build context is web_app/ (App Platform source_dir). See DEPLOY.md.

FROM python:3.12-slim

# ffmpeg decodes browser audio for the Vosk speaking check (routes/vocab).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    SOCKETIO_ASYNC_MODE=eventlet \
    WEB_CONCURRENCY=1

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: bundle the small Chinese Vosk model so the speaking check works out of
# the box. Off by default — it keeps the image small and the build offline-safe,
# and the rest of the API runs fine without it (only that endpoint errors until a
# model is present). Enable with:  --build-arg INCLUDE_VOSK_MODEL=true
ARG INCLUDE_VOSK_MODEL=false
ARG VOSK_MODEL_ZIP_URL=https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
RUN if [ "$INCLUDE_VOSK_MODEL" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends curl unzip && \
      mkdir -p models && cd models && \
      curl -fsSL "$VOSK_MODEL_ZIP_URL" -o model.zip && unzip -q model.zip && rm model.zip && \
      apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .

# Normalise CRLF (repo is developed on Windows) and make the entrypoint runnable.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["docker-entrypoint.sh"]
