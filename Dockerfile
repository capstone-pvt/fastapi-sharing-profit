# Multi-stage build for production

# Stage 1: Builder stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies + git-lfs for model files
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    git-lfs \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    WORKERS=1 \
    MAX_WORKERS=8 \
    TIMEOUT=300 \
    CLASSIFY_ONLY=false \
    YOLO_CONFIG_DIR=/tmp \
    MPLCONFIGDIR=/tmp \
    UPLOAD_ROOT=uploads \
    MODEL_ROOT=app/models \
    CLASSIFIER_MODEL_PATH=app/models/classifier/best.pt \
    DETECTOR_MODEL_PATH=app/models/detector/best.pt \
    WEIGHT_MODEL_PATH=app/models/weight/weight_model.joblib \
    PRICE_MODEL_PATH=app/models/price/price_model.joblib \
    DETECTOR_CONFIDENCE=0.25 \
    DETECTOR_IOU=0.45 \
    PRELOAD_MODELS=true \
    STORAGE_BACKEND=local \
    CLOUDINARY_URL="" \
    AUTO_TRAIN_ON_SAMPLE=false \
    OPENWEATHER_API_KEY=""

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgcc-s1 \
    libstdc++6 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p uploads app/models/classifier app/models/detector app/models/weight app/models/price logs && \
    chown -R appuser:appuser /app

# Verify model files are real binaries (not LFS pointers)
RUN if [ -f app/models/classifier/best.pt ] && head -1 app/models/classifier/best.pt | grep -q "version https://git-lfs"; then \
      echo "WARNING: Model files are LFS pointers, not actual binaries."; \
      echo "Ensure git-lfs is configured in your CI/CD pipeline."; \
    else \
      echo "Model files OK"; \
    fi

# Switch to non-root user
USER appuser

# Expose port (Render assigns PORT dynamically)
EXPOSE ${PORT}

# Health check with retry logic — hits /health which verifies DB + model status
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the application with production settings
# --forwarded-allow-ips is set to the Docker bridge network range (nginx proxy)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --timeout-keep-alive ${TIMEOUT} --proxy-headers --forwarded-allow-ips='127.0.0.1,172.16.0.0/12'"]
