# Use uv's official Python base with build cache baked in
FROM ghcr.io/astral-sh/uv:python3.11-bookworm

WORKDIR /app

# Copy project metadata first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtualenv managed by uv
# --frozen ensures uv.lock is respected for reproducible builds
RUN uv sync --frozen --no-install-project

# Now copy the source
COPY src ./src
COPY web ./web
COPY README.md ./README.md

ENV PYTHONUNBUFFERED=1

# Default command is overridden per-service in docker-compose.yml
CMD ["uv", "run", "python", "-m", "src.main.service"]
