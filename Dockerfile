# Synapse MCP Server - Production Dockerfile (CPU-only)
# Lighter weight image without CUDA

# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package files
COPY pyproject.toml README.md ./
COPY synapse/ ./synapse/

# Install Python dependencies (CPU-only PyTorch)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies and create user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r synapse && useradd -r -g synapse -d /app synapse

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY synapse/ ./synapse/

# Set ownership
RUN chown -R synapse:synapse /app

# Switch to non-root user
USER synapse

# Expose MCP port
EXPOSE 47780

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:47780/health || exit 1

# Run MCP server
CMD ["python", "-m", "synapse.mcp_server.main", "--config", "synapse/mcp_server/config/config.yaml", "--transport", "http", "--port", "47780"]
