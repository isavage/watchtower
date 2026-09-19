# Watchtower

A lightweight, self-hosted **VPS / server monitor** with a modern web UI.
Runs as a single Docker container on your server and reports the **host's**
CPU, memory, disk I/O, network throughput, uptime and process count — with
time-range selectors and live-updating charts.

![stack](https://img.shields.io/badge/FastAPI-009688) ![stack](https://img.shields.io/badge/React-61DAFB) ![stack](https://img.shields.io/badge/Docker-2496ED)

## Features

- **Host metrics** — reads the host's `/proc` & `/sys` (mounted read-only) so
  you monitor the VPS itself, not the container.
- **Charts + time selectors** — 5m / 15m / 1h / 6h / 24h / 7d, with
  server-side downsampling so long ranges stay fast.
- **Live** — summary values refresh every 3s, charts every 10s.
- **Auth** — single admin login, server-side sessions in SQLite, HttpOnly
  cookie with sliding expiry.
- **Tiny footprint** — one image (~180 MB), SQLite storage, 7-day retention.

## Quick start (Docker — on your server)

```bash
cp .env.example .env      # set WT_ADMIN_USER / WT_ADMIN_PASSWORD / WT_SECRET_KEY
# generate a secret:  openssl rand -hex 32
docker compose up -d --build
```

Open `http://<your-server>:8080` and sign in. Put it behind a reverse proxy
with TLS for real use (see below).

### Running on a subdomain behind a reverse proxy

Say `watchtower.example.com` → nginx/Caddy/Traefik on the VPS → this app.
Set these in Doppler (or `.env`):

| Var                | Value    | Why                                                    |
| ------------------ | -------- | ------------------------------------------------------ |
| `WT_COOKIE_SECURE` | `true`   | HTTPS-only session cookie                              |
| `WT_BIND_ADDR`     | `127.0.0.1` | Publish the port on loopback only, so nobody bypasses the proxy |

No other changes are needed: the frontend uses relative `/api` URLs, so it
works on any hostname/subpath, and there are no redirects that depend on the
Host header. Make sure your proxy forwards `Host` and `X-Forwarded-*`
headers, e.g. nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name watchtower.example.com;
    # ssl_certificate ... / ssl_certificate_key ...

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With `WT_BIND_ADDR=127.0.0.1`, also close the port in your firewall
(`ufw deny 8080` / security group) as defense in depth, and keep the app up
to date — the monitor itself has no rate limiting on login.

## CI/CD — automatic deploy from GitHub Actions

Pushes to `main`/`master` deploy to the VPS via
[`isavage/deploy`](https://github.com/marketplace/actions/zero-config-vps-docker-deploy)
(workflow: `.github/workflows/deploy.yml`). Secrets are managed in
**Doppler**: the action installs the Doppler CLI on the VPS and runs
`doppler run -- docker compose up -d`, injecting variables in memory — no
`.env` file is ever written to disk.

**1. Doppler** — create a project and add these config variables:

| Doppler var         | Example                        |
| ------------------- | ------------------------------ |
| `WT_ADMIN_USER`     | `admin`                        |
| `WT_ADMIN_PASSWORD` | strong password                |
| `WT_SECRET_KEY`     | `openssl rand -hex 32` output  |
| `WT_COOKIE_SECURE`  | `true` behind TLS, else `false`|
| `WT_BIND_ADDR`      | `127.0.0.1` when a reverse proxy runs on the same host |

Copy a **Service Token** (`dp.st.…`) for your production config.

**2. GitHub** — add repository secrets:

| Secret          | Purpose                                  |
| --------------- | ---------------------------------------- |
| `VPS_HOST`      | hostname/IP of the server                |
| `VPS_USER`      | SSH user (root or sudo-enabled)          |
| `VPS_SSH_KEY`   | private SSH key                          |
| `DOPPLER_TOKEN` | the `dp.st.…` service token              |

**3. Ship** — merge to `main`. The action rsyncs the repo to
`/docker/<repo>` on the VPS, builds the image there, brings the stack up, and
verifies the `watchtower` container is healthy (streaming logs on failure).
You can also trigger a deploy manually from the Actions tab, optionally with
`--no-cache`.


## Local development

```bash
# backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed                                   # optional demo history
uvicorn app.main:app --reload --port 8080

# frontend (new terminal) — proxies /api to :8080
cd web && npm install && npm run dev                 # http://localhost:5173
```

To run the whole stack from one process, build the UI once and let FastAPI
serve it:

```bash
cd web && npm run build && cd ..
uvicorn app.main:app --port 8080                      # http://localhost:8080
```

Default dev login: `admin` / `demo1234` (set via env, never in production).

## Configuration (env vars)

| Variable             | Default                | Purpose                                   |
| -------------------- | ---------------------- | ----------------------------------------- |
| `WT_ADMIN_USER`      | `admin`                | Login username                            |
| `WT_ADMIN_PASSWORD`  | `changeme`             | Login password (change it!)               |
| `WT_SECRET_KEY`      | generated              | Set to a stable 32+ hex string in prod    |
| `WT_DB_PATH`         | `data/watchtower.db`   | SQLite location (a volume in Docker)      |
| `WT_HOST_ROOT`       | *(empty)*              | Host mount root, `/host` in Docker        |
| `WT_SAMPLE_INTERVAL` | `2`                    | Seconds between samples                   |
| `WT_SESSION_DAYS`    | `7`                    | Session sliding-expiry window             |
| `WT_COOKIE_SECURE`   | `false`                | Enable when served over HTTPS             |
| `WT_BIND_ADDR`       | `0.0.0.0`              | Set `127.0.0.1` behind a local proxy      |
| `WT_PORT`            | `8080`                 | Host port published by compose            |

## API

| Endpoint                | Method | Description                          |
| ----------------------- | ------ | ------------------------------------ |
| `/api/auth/login`       | POST   | `{username, password}` → sets cookie |
| `/api/auth/logout`      | POST   | Invalidates the session              |
| `/api/auth/me`          | GET    | Current user or 401                  |
| `/api/summary`          | GET    | Latest live values                   |
| `/api/series?range=1h`  | GET    | Downsampled series for the range     |
| `/api/health`           | GET    | Liveness                             |

## Notes on host monitoring

`docker-compose.yml` mounts the host filesystem read-only and shares the host
PID namespace:

```yaml
pid: host
volumes:
  - /:/host:ro
  - /proc:/host/proc:ro
  - /sys:/host/sys:ro
```

If your reverse proxy terminates TLS, forward the original scheme and set
`WT_COOKIE_SECURE=true` so the session cookie is only sent over HTTPS.

## License

MIT
