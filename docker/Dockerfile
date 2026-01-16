# Cub Sandbox Docker Image
#
# Multi-stage build for minimal image size.
# Contains cub and essential system dependencies for AI coding assistants.
#
# Usage:
#   docker build -t cub:latest docker/
#   docker run -v $(pwd):/workspace cub:latest cub status

# Stage 1: Builder - install dependencies and build
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install cub
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install cub in the virtual environment
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir .

# Stage 2: Runtime - minimal image with cub installed
FROM python:3.11-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set up cub directories
RUN mkdir -p /root/.config/cub /root/.local/share/cub

# Create non-root user for security (optional, can run as root if needed)
RUN useradd --create-home --shell /bin/bash cub
USER cub
WORKDIR /home/cub

# Create cub config directories for non-root user
RUN mkdir -p /home/cub/.config/cub /home/cub/.local/share/cub

# Working directory for project mount
WORKDIR /workspace

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD cub --version || exit 1

# Default command
CMD ["cub", "--help"]
