FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install SDK first (better caching)
COPY python-sdk/ /app/python-sdk/
RUN pip install --no-cache-dir ./python-sdk psycopg2-binary

# Copy runtime
COPY synrix_runtime/ /app/synrix_runtime/
COPY synrix/ /app/synrix/

# Install runtime deps
RUN pip install --no-cache-dir fastapi uvicorn flask sentence-transformers numpy

# Expose API port
EXPOSE 8000

# Environment
ENV SYNRIX_BACKEND=postgres
ENV SYNRIX_API_PORT=8000
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD curl -f http://localhost:8000/health || exit 1

# Start API server
CMD ["python", "-m", "synrix_runtime.start", "--api-port", "8000", "--no-browser"]
