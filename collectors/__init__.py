"""Host collectors: the code that actually reads the host.

A shared library, owned by neither container image:

* ``hostproxy`` — the sidecar imports these and serves them over the
  allow-listed API (the Docker deployment: only the proxy has host mounts).
* ``app`` — imports them directly ONLY as the local-dev fallback when
  ``WT_HOST_PROXY_URL`` is empty (single-process mode), where reading /proc
  on this machine is legitimate.

Both Dockerfiles copy just this package plus what they need; the app image
never contains the proxy server, and the proxy image never contains the UI,
auth or DB code.
"""
