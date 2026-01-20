# Dockerfile for Telegram Agent Daemon
# Containerizes the sales agent with all dependencies for production deployment

FROM python:3.12-slim AS base

# Set working directory
WORKDIR /app

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Set pip to not cache packages
    PIP_NO_CACHE_DIR=1 \
    # Disable pip version check
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv package manager
RUN pip install --no-cache-dir uv

# =============================================================================
# Builder stage - install dependencies
# =============================================================================
FROM base AS builder

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev

# =============================================================================
# Runtime stage - final slim image
# =============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Add virtual environment to PATH
    PATH="/app/.venv/bin:$PATH" \
    # Set Python path for imports
    PYTHONPATH="/app/src:/app/.claude/skills/telegram/scripts"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy uv for runtime use
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/lib/python3.12/site-packages/uv* /usr/local/lib/python3.12/site-packages/

# Copy pyproject.toml and uv.lock (needed for uv run)
COPY pyproject.toml uv.lock ./

# Copy application source code
COPY src/ ./src/

# Copy skills directories (required for tone-of-voice, how-to-communicate, telegram_fetch)
COPY .claude/skills/tone-of-voice/ ./.claude/skills/tone-of-voice/
COPY .claude/skills/how-to-communicate/ ./.claude/skills/how-to-communicate/
COPY .claude/skills/telegram/scripts/ ./.claude/skills/telegram/scripts/

# Copy knowledge base
COPY knowledge_base_final/ ./knowledge_base_final/

# Copy migrations
COPY src/sales_agent/migrations/ ./src/sales_agent/migrations/

# Create directories for credentials (will be mounted as volumes)
RUN mkdir -p /root/.telegram_dl /root/.zoom_credentials

# Create non-root user for security (optional, comment out if credentials need root)
# RUN useradd --create-home --shell /bin/bash agent && \
#     chown -R agent:agent /app
# USER agent

# Health check - verifies the Python environment and imports work
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from sales_agent.daemon import TelegramDaemon; print('OK')" || exit 1

# Expose no ports (daemon uses outbound connections only)

# Labels for container metadata
LABEL org.opencontainers.image.title="Telegram Agent Daemon" \
      org.opencontainers.image.description="Sales agent daemon for Telegram prospect outreach" \
      org.opencontainers.image.vendor="True Real Estate" \
      org.opencontainers.image.source="https://github.com/TrueRealEstate/Classifier"

# Run the daemon using uv
CMD ["uv", "run", "python", "src/sales_agent/daemon.py"]
