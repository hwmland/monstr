# syntax=docker/dockerfile:1

FROM node:20-alpine AS client-builder
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

FROM python:3.11-slim AS server-builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /app
COPY server/requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY server /app/server

FROM python:3.11-slim AS runtime

# Image metadata (OCI labels)
# - org.opencontainers.image.description: short description of the image
# - org.opencontainers.licenses: SPDX license identifier
# - org.opencontainers.source: URL to the source repository
LABEL org.opencontainers.image.description="Monstr - Monitor STORJ by logfiles"
LABEL org.opencontainers.licenses="MIT"
LABEL org.opencontainers.source="https://github.com/hwmland/monstr"

ENV VIRTUAL_ENV=/opt/venv
COPY --from=server-builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MONSTR_API_HOST=0.0.0.0 \
    MONSTR_FRONTEND_DIST_DIR=/app/client/dist
WORKDIR /app
COPY --from=server-builder /app/server /app/server
COPY --from=client-builder /app/client/dist /app/client/dist
EXPOSE 8000
CMD ["python", "-m", "server.src.cli"]
