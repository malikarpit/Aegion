# Aegion Backend - Production Dockerfile
# Multi-stage build for optimal image size

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.12-slim-bookworm as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev deps, no virtualenv in container)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim-bookworm as runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd -r aegion && useradd -r -g aegion aegion

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/

# Install runtime dependencies (curl required for HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set ownership
RUN chown -R aegion:aegion /app

# Switch to non-root user
USER aegion

# Environment variables
# PORT is injected by Cloud Run at runtime (default 8080).
# Setting a local default here so the image also works with docker-compose.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    ENVIRONMENT=production

# Expose port (documentation only — Cloud Run uses $PORT)
EXPOSE 8080

# Health check against the dynamic port
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health/ready || exit 1

# Shell-form CMD so $PORT is expanded at runtime by the shell.
# Cloud Run sets $PORT to 8080 by default; docker-compose can override it.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
