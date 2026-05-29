FROM python:3.12-slim

USER root

RUN mkdir -p /app && chown 1001:1001 /app
WORKDIR /app

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

ENV UV_CACHE_DIR=/tmp/uv-cache

RUN uv sync

RUN chmod -R 777 /tmp/uv-cache && \
    chown -R 1001:1001 /app/.venv

USER 1001

CMD ["echo", "Image is live!"]
