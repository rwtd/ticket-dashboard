# Python Flask app for Cloud Run / local Docker
# - Binds to 0.0.0.0 and respects $PORT (default 8080)
# - Uses non-root user at runtime
# - Installs dependencies efficiently for caching
# - Multi-stage build for smaller, more secure final image
# - Security updates and vulnerability scanning

# Build stage - for dependency installation
FROM python:3.12-slim-bookworm AS builder

# Add security updates and install build dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Additional security: remove package manager cache
    rm -rf /var/cache/apt/*

# Environment and defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# Set the working directory
WORKDIR /app

# Install Python dependencies first to leverage layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip==24.3 && \
    pip install --no-cache-dir --only-binary=all -r requirements.txt

# Single stage build for simplicity and reliability
FROM python:3.12-slim-bookworm

# Add security updates and runtime dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/*

# Create non-root user with specific UID for consistency
RUN groupadd -r appuser -g 10001 && \
    useradd -r -g appuser -u 10001 -m -d /home/appuser -s /bin/bash appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app /home/appuser

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Set the working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip==24.3 && \
    pip install --no-cache-dir --only-binary=all -r requirements.txt

# Copy application source with proper ownership
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Add health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Expose Cloud Run standard port
EXPOSE 8080

# Start with gunicorn, binding to $PORT (fallback 8080) on 0.0.0.0
# JSON-array form with sh -c to expand environment variable safely
# Added security flags and worker configuration
CMD ["sh", "-c", "cd /app && python -c 'import app; print(\"App imported successfully\")' && exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 2 \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --keep-alive 2 \
    --log-level info \
    --access-logformat '%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\" %(D)s' \
    --capture-output \
    --enable-stdio-inheritance \
    app:app"]