# Deployment Guide

Production deployment strategies for Lexard.

## Overview

Lexard is designed for self-hosted, sovereign deployment with no external API dependencies. This guide covers various deployment options.

## Deployment Options

1. **Docker Compose** - Simple single-server deployment
2. **Kubernetes** - Scalable cluster deployment
3. **VM/Bare Metal** - Traditional server deployment

---

## 1. Docker Compose Deployment (Recommended)

Simplest production deployment for small to medium workloads.

### Prerequisites

- Linux server with Docker & Docker Compose
- 8GB RAM minimum (16GB recommended)
- 50GB disk space
- GPU (optional):
  - **NVIDIA**: CUDA toolkit and nvidia-docker
  - **AMD RDNA3/RDNA4**: Vulkan SDK (see [AMD GPU Setup](#amd-gpu-deployment))

### Setup

#### 1. Clone repository on server

```bash
git clone https://github.com/yourusername/lexard.git
cd lexard
```

#### 2. Create production configuration

```bash
cp config/config.yaml config/config.prod.yaml
```

Edit `config/config.prod.yaml`:

```yaml
app:
  environment: 'production'
  log_level: 'info'

llm:
  base_url: 'http://ollama:11434'
  timeout_seconds: 60

qdrant:
  host: 'qdrant'

server:
  workers: 8  # Set to number of CPU cores
```

#### 3. Create production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: lexard-qdrant
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    healthcheck:
      test: ['CMD-SHELL', 'bash -c "echo > /dev/tcp/localhost/6333"']
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - lexard

  ollama:
    image: ollama/ollama:latest
    container_name: lexard-ollama
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ['CMD-SHELL', 'bash -c "echo > /dev/tcp/localhost/11434"']
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - lexard
    # Uncomment for GPU support
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: lexard-api
    ports:
      - "8000:8000"
    volumes:
      - ./config/config.prod.yaml:/app/config/config.yaml:ro
      - uploads:/app/data/uploads
      - db:/app/data
    environment:
      - LEXARD_CONFIG_FILE=/app/config/config.yaml
    depends_on:
      - qdrant
      - ollama
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8000/health']
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - lexard

  nginx:
    image: nginx:alpine
    container_name: lexard-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: always
    networks:
      - lexard

volumes:
  qdrant_data:
  ollama_data:
  uploads:
  db:

networks:
  lexard:
    driver: bridge
```

#### 4. Create Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/
COPY config/ ./config/
COPY ui/ ./ui/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p /app/data/uploads

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 5. Configure nginx (Optional but recommended)

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream lexard {
        server api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL certificates
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Max upload size
        client_max_body_size 50M;

        location / {
            limit_req zone=api burst=20 nodelay;

            proxy_pass http://lexard;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts for long-running requests
            proxy_read_timeout 120s;
            proxy_connect_timeout 120s;
        }
    }
}
```

#### 6. Generate SSL certificates

Using Let's Encrypt:

```bash
# Install certbot
apt-get install certbot

# Generate certificate
certbot certonly --standalone -d your-domain.com

# Copy certificates
mkdir -p ssl
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
```

#### 7. Deploy

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Pull LLM model
docker exec -it lexard-ollama ollama pull mistral:7b-instruct

# Verify health
curl http://localhost:8000/health
```

---

## AMD GPU Deployment

AMD RDNA3/RDNA4 GPUs have issues with ROCm's HIP backend (100% idle GPU usage bug). The recommended approach is to use llama.cpp with the Vulkan backend.

### Prerequisites

```bash
# Install Vulkan development libraries
sudo apt-get install -y libvulkan-dev glslc

# Verify Vulkan is working
vulkaninfo --summary
```

### Build llama.cpp with Vulkan

```bash
# Clone llama.cpp
cd /opt
git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Build with Vulkan support
cmake -B build -DGGML_VULKAN=ON -DLLAMA_CURL=OFF
cmake --build build --config Release -j$(nproc)

# Download a model
curl -L -o /opt/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

### Create systemd service for llama-server

Create `/etc/systemd/system/llama-server.service`:

```ini
[Unit]
Description=llama.cpp Server with Vulkan
After=network.target

[Service]
Type=simple
User=lexard
Environment="GGML_VK_DEVICE=0"
ExecStart=/opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --host 0.0.0.0 --port 8080 -ngl 99 -c 8192
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable llama-server
systemctl start llama-server

# Verify
curl http://localhost:8080/health
```

### Docker Compose for AMD GPU

Use `docker-compose.yml` which connects to llama-server on the host:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: lexard-qdrant
    ports:
      - '6333:6333'
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  api:
    build: .
    container_name: lexard-api
    ports:
      - '8000:8000'
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
    environment:
      - CONFIG_PATH=/app/config/config.docker.yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Access host llama-server
    depends_on:
      - qdrant
    restart: unless-stopped

volumes:
  qdrant_data:
```

Configure `config/config.docker.yaml`:

```yaml
llm:
  provider: 'openai'  # OpenAI-compatible API
  model: 'mistral'
  base_url: 'http://host.docker.internal:8080'  # llama-server on host
  timeout_seconds: 60

embeddings:
  device: 'cpu'  # CPU for embeddings (avoids HIP issues)
```

### Verify GPU Usage

Check that the GPU idles correctly (should be ~5%, not 100%):

```bash
# For AMD GPUs
amd-smi monitor -p -u

# Expected idle output:
# GPU  POWER  GFX%
#   0   15 W    5 %
```

---

## 2. Kubernetes Deployment

For scalable, high-availability deployments.

### Prerequisites

- Kubernetes cluster (version 1.25+)
- kubectl configured
- Helm (optional)

### Kubernetes Manifests

#### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lexard
```

#### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lexard-config
  namespace: lexard
data:
  config.yaml: |
    app:
      environment: production
      log_level: info
    llm:
      base_url: http://ollama-service:11434
    qdrant:
      host: qdrant-service
```

#### Qdrant Deployment

```yaml
# k8s/qdrant.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  namespace: lexard
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: qdrant/qdrant:latest
        ports:
        - containerPort: 6333
        volumeMounts:
        - name: qdrant-data
          mountPath: /qdrant/storage
      volumes:
      - name: qdrant-data
        persistentVolumeClaim:
          claimName: qdrant-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: qdrant-service
  namespace: lexard
spec:
  selector:
    app: qdrant
  ports:
  - port: 6333
    targetPort: 6333
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-pvc
  namespace: lexard
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

#### Ollama Deployment

```yaml
# k8s/ollama.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: lexard
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
      - name: ollama
        image: ollama/ollama:latest
        ports:
        - containerPort: 11434
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama
      volumes:
      - name: ollama-data
        persistentVolumeClaim:
          claimName: ollama-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-service
  namespace: lexard
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-pvc
  namespace: lexard
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

#### API Deployment

```yaml
# k8s/api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lexard-api
  namespace: lexard
spec:
  replicas: 3
  selector:
    matchLabels:
      app: lexard-api
  template:
    metadata:
      labels:
        app: lexard-api
    spec:
      containers:
      - name: api
        image: your-registry/lexard:latest
        ports:
        - containerPort: 8000
        env:
        - name: LEXARD_CONFIG_FILE
          value: /config/config.yaml
        volumeMounts:
        - name: config
          mountPath: /config
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: lexard-config
---
apiVersion: v1
kind: Service
metadata:
  name: lexard-api-service
  namespace: lexard
spec:
  type: LoadBalancer
  selector:
    app: lexard-api
  ports:
  - port: 80
    targetPort: 8000
```

#### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Deploy services
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/qdrant.yaml
kubectl apply -f k8s/ollama.yaml
kubectl apply -f k8s/api.yaml

# Check status
kubectl get pods -n lexard

# Pull LLM model
kubectl exec -it -n lexard deployment/ollama -- ollama pull mistral:7b-instruct
```

---

## 3. VM/Bare Metal Deployment

Traditional server deployment without containers.

### Setup

#### 1. Install dependencies

```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Python 3.11
apt-get install -y python3.11 python3.11-venv python3-pip

# Install Qdrant
wget https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
mv qdrant /usr/local/bin/

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

#### 2. Create system user

```bash
useradd -r -s /bin/bash -d /opt/lexard lexard
```

#### 3. Install Lexard

```bash
# Clone repository
cd /opt/lexard
git clone https://github.com/yourusername/lexard.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

#### 4. Create systemd services

**Qdrant service** (`/etc/systemd/system/qdrant.service`):

```ini
[Unit]
Description=Qdrant Vector Database
After=network.target

[Service]
Type=simple
User=lexard
ExecStart=/usr/local/bin/qdrant
WorkingDirectory=/opt/lexard/data/qdrant
Restart=always

[Install]
WantedBy=multi-user.target
```

**Ollama service** (`/etc/systemd/system/ollama.service`):

```ini
[Unit]
Description=Ollama LLM Service
After=network.target

[Service]
Type=simple
User=lexard
ExecStart=/usr/local/bin/ollama serve
Restart=always

[Install]
WantedBy=multi-user.target
```

**Lexard API service** (`/etc/systemd/system/lexard-api.service`):

```ini
[Unit]
Description=Lexard API Server
After=network.target qdrant.service ollama.service
Requires=qdrant.service ollama.service

[Service]
Type=simple
User=lexard
WorkingDirectory=/opt/lexard
Environment="PATH=/opt/lexard/venv/bin"
ExecStart=/opt/lexard/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 5. Start services

```bash
# Reload systemd
systemctl daemon-reload

# Enable and start services
systemctl enable qdrant ollama lexard-api
systemctl start qdrant ollama

# Pull LLM model
ollama pull mistral:7b-instruct

# Start API
systemctl start lexard-api

# Check status
systemctl status lexard-api
```

---

## Security Hardening

### 1. Firewall Configuration

```bash
# Allow only necessary ports
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp # HTTPS
ufw enable
```

### 2. API Authentication (TODO)

Currently no authentication. Implement API key or OAuth2 for production:

```python
# Future: Add authentication middleware
from fastapi.security import HTTPBearer
```

### 3. HTTPS Only

Always use HTTPS in production with valid SSL certificates.

### 4. Environment Variables

Never commit secrets. Use environment variables:

```bash
export LEXARD_API_KEY=your-secret-key
```

---

## Monitoring

### Health Checks

```bash
# API health
curl https://your-domain.com/health

# Guardrails metrics
curl https://your-domain.com/guardrails/metrics

# Performance metrics
curl https://your-domain.com/performance/metrics
```

### Logging

Logs are JSON-formatted for easy parsing:

```json
{
  "timestamp": "2025-12-05T10:30:00Z",
  "level": "info",
  "message": "Document processed",
  "trace_id": "abc123",
  "document_id": "xyz789"
}
```

Ship logs to your monitoring stack (ELK, Loki, etc.).

---

## Backup & Recovery

### Backup

```bash
# Backup Qdrant data
tar czf qdrant-backup-$(date +%Y%m%d).tar.gz /path/to/qdrant/storage

# Backup SQLite database
cp /path/to/data/documents.db documents-backup-$(date +%Y%m%d).db

# Backup Ollama models
tar czf ollama-backup-$(date +%Y%m%d).tar.gz /path/to/.ollama
```

### Recovery

```bash
# Restore Qdrant
tar xzf qdrant-backup-YYYYMMDD.tar.gz -C /

# Restore SQLite
cp documents-backup-YYYYMMDD.db /path/to/data/documents.db

# Restart services
systemctl restart qdrant lexard-api
```

---

## Scaling Considerations

### Vertical Scaling

- Add more CPU cores → increase workers
- Add more RAM → increase batch sizes
- Add GPU:
  - NVIDIA → enable CUDA for embeddings and LLM
  - AMD RDNA3/RDNA4 → use llama-server with Vulkan (see [AMD GPU Deployment](#amd-gpu-deployment))

### Horizontal Scaling

- Run multiple API instances behind load balancer
- Share Qdrant and Ollama across instances
- Use external Qdrant cluster for high availability

---

## Next Steps

- [Configuration Guide](configuration.md) - Tune production settings
- [Troubleshooting](troubleshooting.md) - Common production issues
- [API Reference](api.md) - Complete API documentation
