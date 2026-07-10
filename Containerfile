FROM python:3.12-slim

USER root

RUN mkdir -p /app /home/harbor && chown 1001:1001 /app /home/harbor
WORKDIR /app
ENV HOME=/home/harbor

RUN apt-get update && apt-get install -y --no-install-recommends curl git && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz \
    | tar xzf - -C /usr/local/bin oc kubectl && \
    curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv

COPY --chown=1001:1001 . .

USER 1001

RUN uv sync --no-cache

# Install Brev
RUN bash -c "$(curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/bin/install-latest.sh)"

CMD ["echo", "Image is live!"]
