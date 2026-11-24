# syntax=docker/dockerfile:1
# Build stage: resolve the locked runtime dependencies into /app/.venv (no dev tools, no compilers in the result).
# Base images should be pinned by digest in production (Leitfaden Kap. 4); the CI resolves and updates them.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY main.py gunicorn.conf.py ./
COPY app ./app

# Runtime stage: slim Python, non-root user, read-only root filesystem friendly (only /tmp is written).
FROM python:3.13-slim-bookworm
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
USER 10001
EXPOSE 8000 9000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]
