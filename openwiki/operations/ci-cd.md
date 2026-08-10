---
type: component
title: CI/CD Pipeline
description: GitHub Actions workflows for building and pushing the container image, and for updating the OpenWiki documentation.
tags: [ci-cd, github-actions, container]
---

# CI/CD Pipeline

GitHub Actions workflows for building and deploying the coding-agent-bench container image and updating wiki documentation.

## Workflows

### Build and Push (`build-push.yml`)

Triggers on push to `main` or branches matching `CICD*`, and on manual dispatch.

**Pipeline:**

```mermaid
flowchart LR
    A[Checkout] --> B[Login to GHCR]
    B --> C[Set image tag]
    C --> D[Build and Push]
```

**Steps:**

1. **Checkout** — `actions/checkout@v4`
2. **Login to GHCR** — Uses `GITHUB_TOKEN` for `ghcr.io`
3. **Set image tag** — `latest` for `main`, sanitized branch name for feature branches
4. **Build and push** — `docker/build-push-action@v6` with:
   - Context: `.`
   - Dockerfile: `Containerfile`
   - Tags: `${IMAGE_NAME}:${branch}` and `${IMAGE_NAME}:${github.sha}`

**Image name:** `ghcr.io/${{ github.repository }}` → `ghcr.io/redhat-et/coding_agent_bench`

### Wiki Update (`openwiki-update.yml`)

Triggered on push to `main` — updates the OpenWiki documentation.

## Evidence

- Source: `.github/workflows/build-push.yml`, `.github/workflows/openwiki-update.yml`
- Container: `Containerfile`
