FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY synapse/ ./synapse/
COPY api/ ./api/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir \
      "fastapi>=0.115.0" \
      "uvicorn[standard]>=0.30.0" \
      "pydantic>=2.0.0" \
      "pydantic-settings>=2.0.0" \
      "python-dotenv>=1.0.0" \
      "sse-starlette>=2.0.0" \
      "httpx>=0.27.0"

COPY docker/patch_graphiti_core.sh /tmp/patch_graphiti_core.sh
RUN chmod +x /tmp/patch_graphiti_core.sh && \
    /tmp/patch_graphiti_core.sh && \
    rm /tmp/patch_graphiti_core.sh

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r synapse \
    && useradd -r -g synapse -d /app synapse

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY synapse/ ./synapse/
COPY api/ ./api/

RUN mkdir -p /app/.synapse && chown -R synapse:synapse /app

USER synapse

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
