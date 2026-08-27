# Multi-stage build: install dependencies with uv (reproducible, from
# uv.lock) in a builder stage, then copy only the resulting venv + source
# into a slim runtime image. Keeps the final image free of build tools and
# the uv binary itself.

FROM python:3.12-slim AS builder

# uv is installed via pip here (no curl/network-installer step) so the
# build doesn't depend on an external script's availability at build time.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy only the dependency manifests first so Docker's layer cache is
# invalidated only when dependencies actually change, not on every source
# edit.
COPY pyproject.toml uv.lock ./

# --no-dev: this image runs the web app, not the test suite — dev
# dependencies (pytest, ruff, pip-audit, ...) don't belong in the runtime
# image. --frozen: install exactly what uv.lock pins, never resolve/update
# it at build time (reproducibility).
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY config ./config
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

# Runs as a non-root user — the app has no reason to run as root, and
# doesn't need to (no privileged ports, no system-level file access).
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/config ./config
COPY scripts/run_chat_web.py ./scripts/run_chat_web.py

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000

# HOST=0.0.0.0 is required here (a container's own loopback is only
# reachable from inside the container) — this does NOT reopen the
# localhost-only security posture described in
# docs/security/APP_SECURITY.md: docker-compose.yml binds the published
# port to the host's own 127.0.0.1, not 0.0.0.0, so the net effect on the
# host machine is unchanged (still only reachable from localhost) unless an
# operator deliberately changes that port mapping.

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)" || exit 1

CMD ["python", "scripts/run_chat_web.py"]
