FROM python:3.12-slim

USER root

RUN mkdir -p /app /home/harbor/.cache && chown -R 1001:1001 /app /home/harbor
WORKDIR /app
ENV HOME=/home/harbor

RUN apt-get update && apt-get install -y --no-install-recommends bash curl git openssh-client && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz \
    | tar xzf - -C /usr/local/bin oc kubectl && \
    curl -sSL https://storage.eu-north1.nebius.cloud/cli/install.sh | bash && \
    ln -s /home/harbor/.nebius/bin/nebius /usr/local/bin/nebius && \
    chown -R 1001:1001 /home/harbor/.nebius && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

USER 1001

RUN uv sync --no-cache

CMD ["echo", "Image is live!"]
