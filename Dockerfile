# Single-stage Dockerfile for Form 13F AI Agent
# Updated: 2025-11-26 - 8,765 embeddings with UUID fix uploaded
# Build version: 5.0 - RAG FULLY OPERATIONAL
FROM python:3.11-slim

WORKDIR /app

# Install ALL dependencies (build + runtime) in one shot
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# FORCE CACHE INVALIDATION - timestamp changes every build
ARG CACHEBUST_V3=1
RUN echo "FORCE REBUILD v3: $(date +%s)" > /tmp/cachebust

# Copy application code (required for editable install)
COPY src/ ./src/
COPY schema/ ./schema/

# Install Python dependencies (must be AFTER copying src/ for editable install)
RUN uv sync --frozen --no-dev

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Create data directories
RUN mkdir -p data/raw data/processed data/cache && \
    chown -R appuser:appuser data/

USER appuser

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8080

# Default command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
