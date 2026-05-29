FROM python:3.12-slim

USER root

RUN mkdir -p /app && chown 1001:1001 /app
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz \
    | tar xzf - -C /usr/local/bin oc kubectl && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

USER 1001

RUN uv sync --no-cache

CMD ["echo", "Image is live!"]
