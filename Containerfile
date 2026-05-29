FROM python:3.12-slim

USER root

RUN mkdir -p /app && chown 1001:1001 /app
WORKDIR /app

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

USER 1001

ENV UV_CACHE_DIR=/tmp/uv-cache

RUN uv sync

CMD ["echo", "Image is live!"]
