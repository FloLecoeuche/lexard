# Lexard API with ROCm support for AMD GPUs
FROM rocm/pytorch:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY ui/ ./ui/

# Install Python dependencies (skip torch since it's in base image)
RUN pip install --no-cache-dir -e "." \
    --extra-index-url https://download.pytorch.org/whl/rocm6.2

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/db

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
