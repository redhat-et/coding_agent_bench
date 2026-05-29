FROM python:3.12-slim

USER root

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install uv

COPY --chown=1001:1001 . .

RUN uv sync

CMD ["echo", "Image is live!"]
