# syntax=docker/dockerfile:1

FROM node:20-alpine AS client-builder
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

FROM python:3.15-alpine AS runtime

WORKDIR /app
COPY server/requirements.txt ./
RUN set -eu; \
    apk upgrade --no-cache; \
    python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt; \
    python -m pip uninstall -y pip setuptools wheel; \
    python_stdlib="$(python -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"; \
    rm -rf "${python_stdlib}/ensurepip"; \
    if python -c 'import pip' >/dev/null 2>&1; then \
        echo "pip is still importable after removal" >&2; \
        exit 1; \
    fi; \
    if python -c 'import ensurepip' >/dev/null 2>&1; then \
        echo "ensurepip is still importable after removal" >&2; \
        exit 1; \
    fi; \
    if python -c 'import multipart' >/dev/null 2>&1; then \
        echo "unused python-multipart package is installed" >&2; \
        exit 1; \
    fi; \
    python -c 'import sys; print("Monstr Python:", sys.version.split()[0]); assert sys.version_info >= (3, 15, 0), "Python 3.15.0 or newer is required"'; \
    python -c 'import sqlite3; print("Monstr SQLite:", sqlite3.sqlite_version)'; \
    python -B -c 'import fastapi, greenlet, httpx, pydantic, sqlalchemy, uvicorn; print("Monstr dependencies imported")'; \
    apk list --installed sqlite-libs

# Image metadata (OCI labels)
# - org.opencontainers.image.description: short description of the image
# - org.opencontainers.licenses: SPDX license identifier
# - org.opencontainers.source: URL to the source repository
LABEL org.opencontainers.image.description="Monstr - Monitor STORJ by logfiles"
LABEL org.opencontainers.licenses="MIT"
LABEL org.opencontainers.source="https://github.com/hwmland/monstr"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MONSTR_API_HOST=0.0.0.0 \
    MONSTR_FRONTEND_DIST_DIR=/app/client/dist
COPY server /app/server
COPY --from=client-builder /app/client/dist /app/client/dist
RUN python -B -c 'import server.src.cli; print("Monstr application imported")'
EXPOSE 8000
CMD ["python", "-m", "server.src.cli"]
