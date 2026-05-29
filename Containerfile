FROM python:3.12-slim

USER root

RUN mkdir -p /app && chown 1001:1001 /app
WORKDIR /app

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

USER 1001

RUN uv sync --no-cache

CMD ["echo", "Image is live!"]
