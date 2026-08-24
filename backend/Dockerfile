FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies (including WeasyPrint requirements for PDF generation)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create non-root user and storage directory
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/storage \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# ---------------------------------------------------------------------------
# dev — runtime image plus the test toolchain (pytest, ruff) from the
# `dev` extra. docker-compose.yml builds this target, so
# `docker-compose exec backend python -m pytest` works out of the box
# instead of needing a manual pip install after every container recreate.
#
# Declared BEFORE `prod` on purpose: a build with no --target uses the last
# stage, and docker-compose.coolify.yml builds without one. Keeping `prod`
# last is what stops the test toolchain from shipping to production.
# ---------------------------------------------------------------------------
FROM base AS dev
USER root
RUN pip install --no-cache-dir ".[dev]"
USER appuser

# ---------------------------------------------------------------------------
# prod — default target: the runtime image, no test toolchain. Must stay the
# last stage in this file.
# ---------------------------------------------------------------------------
FROM base AS prod
