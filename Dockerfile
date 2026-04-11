# Optimized build — targets < 4GB for Railway free tier

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ git git-lfs \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

COPY requirements.txt .

# Install to venv — CPU-only torch from requirements.txt
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Post-install cleanup: strip test/debug files from torch & ultralytics
RUN find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -name "*.pyo" -delete 2>/dev/null || true && \
    rm -rf /opt/venv/lib/python3.11/site-packages/torch/test \
           /opt/venv/lib/python3.11/site-packages/torch/include \
           /opt/venv/lib/python3.11/site-packages/torch/share \
           /opt/venv/lib/python3.11/site-packages/caffe2 \
           /opt/venv/lib/python3.11/site-packages/nvidia 2>/dev/null || true

# Stage 2: Production
FROM python:3.11-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

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

# Runtime deps only (OpenCV needs libgl1 + glib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    libgomp1 libgcc-s1 libstdc++6 \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy app code
COPY --chown=appuser:appuser . .

# Create dirs
RUN mkdir -p uploads app/models/classifier app/models/detector app/models/weight app/models/price logs && \
    chown -R appuser:appuser /app

# Verify model files
RUN if [ -f app/models/classifier/best.pt ] && head -1 app/models/classifier/best.pt | grep -q "version https://git-lfs"; then \
      echo "WARNING: Model files are LFS pointers, not actual binaries."; \
    else \
      echo "Model files OK"; \
    fi

USER appuser

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --timeout-keep-alive ${TIMEOUT} --proxy-headers --forwarded-allow-ips='127.0.0.1,172.16.0.0/12'"]
