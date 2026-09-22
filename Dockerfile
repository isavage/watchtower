# ---- Stage 1: build the React frontend ----
FROM node:22-alpine AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app/ ./app/
# collectors/ is imported only for the local-dev fallback (no WT_HOST_PROXY_URL);
# in Docker the app never reads host files — the host-proxy sidecar does.
COPY collectors/ ./collectors/
# static UI bundle produced by stage 1
COPY --from=webbuild /web/dist ./web/dist

# Drop root: the UI process has no business being PID 1 as root — cap_drop +
# read_only are much weaker if it is. Port 8080 is unprivileged, and /data is
# chowned here so the `watchtower-data` named volume inherits that ownership
# on first use (SQLite needs the directory writable, hence no `:ro`).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data && chown appuser:appuser /data
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
