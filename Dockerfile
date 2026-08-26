# Multi-stage production Dockerfile for Ovarian Ultrasound AI Decision Support
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Install minimal OS dependencies for OpenCV, DICOM and PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY templates/ /app/templates/
COPY knowledge/ /app/knowledge/
COPY checkpoints/ /app/checkpoints/
COPY data/ /app/data/
COPY pyproject.toml MODEL_CARD.md /app/

# Ensure runtime directories exist
RUN mkdir -p /app/data/uploads /app/data/reports

# Create non-root unprivileged user for clinical safety
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose API port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start application with Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
