FROM python:3.12-slim

USER root

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install uv

COPY --chown=1001:1001 . .

ENV UV_CACHE_DIR=/tmp/uv-cache

RUN uv sync

USER 1001

CMD ["echo", "Image is live!"]
