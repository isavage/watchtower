"""watchtower-host-proxy: the only container with host visibility.

Serves a tiny, read-only, allow-listed JSON API over an internal Docker
network. The UI/app container holds no host mounts and no `pid: host` —
it queries this service instead, exactly like it queries
docker-socket-proxy for the Docker API.
"""
