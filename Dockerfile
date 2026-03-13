# Synapse MCP Server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir hatch && \
    pip install --no-cache-dir -e .

# Copy source code
COPY synapse/ ./synapse/

# Expose MCP port
EXPOSE 47780

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:47780/health || exit 1

# Run MCP server
CMD ["python", "-m", "synapse.mcp_server.main"]
