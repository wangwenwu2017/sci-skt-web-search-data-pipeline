FROM node:24-bookworm-slim@sha256:2fe369e969550cde8e867afc3fe370b260140cab4a23d467074295b42163d553

ARG CODEX_VERSION=0.154.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv git curl ca-certificates ripgrep \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@${CODEX_VERSION}
RUN mkdir -p /workspace/output && chown -R node:node /workspace
WORKDIR /workspace
