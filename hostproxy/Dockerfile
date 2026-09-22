# watchtower-host-proxy: the only container with host visibility.
# Independent of the UI image on purpose — smaller surface, own lifecycle.
# Build context is the repo root (it imports the shared collectors/ library).
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY hostproxy/requirements.txt ./hostproxy/requirements.txt
RUN pip install -r hostproxy/requirements.txt

# Host readings come from the shared collectors/ library (single source of
# truth, also used by the app's local-dev fallback). This image deliberately
# contains NO app/ code: no HTTP UI, no login, no DB — just collectors plus
# the thin allow-listed API in hostproxy/.
COPY collectors/ ./collectors/
COPY hostproxy/ ./hostproxy/

# Runs as root INSIDE the container (the default) — deliberately: the host's
# /var/log/auth.log is mode 640 root:adm on Debian/Ubuntu, and the whole point
# of this service is read-only access. The risk is capped by the compose
# hardening instead: cap_drop ALL, no-new-privileges, read_only rootfs, all
# mounts :ro, internal network. If you deny the Security endpoint
# (WT_ALLOW_SECURITY=0) and drop its mounts, you can safely add
# `user: "10001:10001"` + a non-root USER here.

EXPOSE 8090
CMD ["uvicorn", "hostproxy.main:app", "--host", "0.0.0.0", "--port", "8090"]
