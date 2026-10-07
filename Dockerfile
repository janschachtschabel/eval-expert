FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.7.13 AS uv
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DEEPEVAL_TELEMETRY_OPT_OUT=1 DEEPEVAL_DISABLE_PROGRESS_BAR=1 \
    EVAL_DATA_DIR=/data EVAL_FRONTEND_DIR=/app/frontend \
    HOME=/tmp PATH=/app/.venv/bin:$PATH
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --python /usr/local/bin/python
COPY backend/app ./app
COPY --from=frontend /build/dist/browser ./frontend
RUN groupadd --gid 10001 eval && useradd --uid 10001 --gid eval --no-create-home eval \
    && mkdir /data && chown eval:eval /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
