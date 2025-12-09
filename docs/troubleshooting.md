# Troubleshooting Guide

Common issues and solutions for Lexard.

## Installation Issues

### Virtual Environment Error (macOS)

**Error:**

```
error: externally-managed-environment
```

**Cause:** macOS blocks system-wide pip installs.

**Solution:**
Always use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

### Docker Services Not Starting

**Error:**

```
Cannot connect to the Docker daemon
```

**Solutions:**

1. Check Docker is running:

   ```bash
   docker ps
   ```

2. Start Docker Desktop (macOS/Windows)

3. Start Docker service (Linux):

   ```bash
   sudo systemctl start docker
   ```

4. Check Docker Compose version:
   ```bash
   docker-compose --version
   # Should be v2.0+
   ```

---

### Port Already in Use

**Error:**

```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Solutions:**

1. Find process using the port:

   ```bash
   # macOS/Linux
   lsof -i :8000

   # Windows
   netstat -ano | findstr :8000
   ```

2. Kill the process:

   ```bash
   kill -9 <PID>
   ```

3. Or change the port in `docker-compose.yml` or start command:
   ```bash
   uvicorn src.api.main:app --port 8001
   ```

---

## Runtime Issues

### LLM Service Unavailable

**Error:**

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "LLM service is unavailable"
  }
}
```

**Solutions for Ollama:**

1. Check Ollama is running:

   ```bash
   docker ps | grep ollama
   ```

2. Check Ollama health:

   ```bash
   curl http://localhost:11434/api/tags
   ```

3. Restart Ollama:

   ```bash
   docker-compose restart ollama
   ```

4. Check model is pulled:

   ```bash
   docker exec -it lexard-ollama ollama list
   ```

5. Pull model if missing:
   ```bash
   docker exec -it lexard-ollama ollama pull mistral:7b-instruct
   ```

**Solutions for llama-server (Vulkan) - AMD RDNA4 Workaround:**

> **Note:** llama-server with Vulkan is a workaround for AMD RDNA4 GPUs (gfx1201) due to a [ROCm HIP backend bug](https://github.com/ROCm/ROCm/issues/5706) that causes 100% idle GPU usage with Ollama.

1. Check llama-server is running:

   ```bash
   pgrep -f llama-server
   ```

2. Check llama-server health:

   ```bash
   curl http://localhost:8080/health
   ```

3. Start llama-server if not running:

   ```bash
   cd /tmp/llama.cpp
   GGML_VK_DEVICE=0 ./build/bin/llama-server \
     -m /tmp/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
     --host 0.0.0.0 --port 8080 -ngl 99 -c 8192
   ```

4. Check GPU is detected:
   ```bash
   vulkaninfo --summary | grep deviceName
   ```

See [Quickstart - AMD GPU Setup](quickstart.md#amd-gpu-setup-vulkan) for full setup instructions.

---

### Qdrant Connection Failed

**Error:**

```
ConnectionError: Cannot connect to Qdrant
```

**Solutions:**

1. Check Qdrant is running:

   ```bash
   docker ps | grep qdrant
   ```

2. Check Qdrant health:

   ```bash
   curl http://localhost:6333/healthz
   ```

3. Check Qdrant logs:

   ```bash
   docker-compose logs qdrant
   ```

4. Restart Qdrant:

   ```bash
   docker-compose restart qdrant
   ```

5. Reset Qdrant data (WARNING: deletes all documents):
   ```bash
   docker-compose down
   docker volume rm lexard_qdrant_data
   docker-compose up -d
   ```

---

### Document Upload Fails

**Error:**

```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File exceeds maximum size of 50MB"
  }
}
```

**Solutions:**

1. Check file size:

   ```bash
   ls -lh your-file.pdf
   ```

2. Increase max size in `config/config.yaml`:

   ```yaml
   storage:
     max_file_size_mb: 100
   ```

3. For unsupported formats (413), ensure file is PDF, DOCX, or TXT

---

### Query Returns "Cannot Find Information"

**Symptoms:** All queries return "I cannot find relevant information"

**Causes & Solutions:**

1. **Document not processed:**

   ```bash
   curl http://localhost:8000/documents/{document_id}
   # Check status is "processed"
   ```

2. **Chunks not indexed:**
   Check `chunk_count` in document metadata:

   ```bash
   curl http://localhost:8000/documents/{document_id}
   # chunk_count should be > 0
   ```

3. **Score threshold too high:**
   Lower in `config/config.yaml`:

   ```yaml
   retrieval:
     score_threshold: 0.5 # Down from 0.7
   ```

4. **Query doesn't match document content:**
   Try more specific questions matching actual document text

---

### Slow Query Performance

**Symptoms:** Queries take > 5 seconds

**Solutions:**

1. **Check service health:**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Reduce top_k:**

   ```yaml
   retrieval:
     top_k: 5 # Down from 8
   ```

3. **Enable batch processing:**

   ```yaml
   embeddings:
     batch_size: 64 # Up from 32
   ```

4. **Check system resources:**

   ```bash
   # Monitor CPU/Memory
   docker stats
   ```

5. **Use GPU for embeddings (if available):**
   ```yaml
   embeddings:
     device: 'cuda'
   ```

---

### Hallucination Detection Blocking Valid Answers

**Symptoms:** Valid answers rejected with hallucination error

**Solutions:**

1. **Lower hallucination threshold:**

   ```yaml
   guardrails:
     hallucination_threshold: 0.7 # Down from 0.8
   ```

2. **Check citation quality:**
   Review `citation_chunks` in responses - low scores indicate poor grounding

3. **Increase retrieval chunks:**
   ```yaml
   retrieval:
     top_k: 12 # Up from 8
   ```

---

### PII Not Being Redacted

**Symptoms:** Sensitive information appears in responses

**Solutions:**

1. **Verify PII filter is enabled:**

   ```yaml
   guardrails:
     enable_pii_filter: true
   ```

2. **Check patterns match your data:**
   Edit `src/guardrails/pii.py` to add custom patterns

3. **Test manually:**

   ```python
   from src.guardrails.pii import PIIFilter

   pii = PIIFilter()
   result = pii.redact("My SSN is 123-45-6789")
   print(result)  # Should show [REDACTED_SSN]
   ```

---

## Performance Issues

### High Memory Usage

**Symptoms:** System runs out of memory

**Solutions:**

1. **Reduce embedding batch size:**

   ```yaml
   embeddings:
     batch_size: 16 # Down from 32
   ```

2. **Reduce worker count:**

   ```yaml
   server:
     workers: 2 # Down from 4
   ```

3. **Limit concurrent requests:**
   Use nginx rate limiting (see [deployment.md](deployment.md))

4. **Monitor memory:**
   ```bash
   docker stats --no-stream
   ```

---

### Disk Space Full

**Symptoms:** Cannot upload documents

**Solutions:**

1. **Check disk usage:**

   ```bash
   df -h
   ```

2. **Clean old Docker images:**

   ```bash
   docker system prune -a
   ```

3. **Remove unused volumes:**

   ```bash
   docker volume prune
   ```

4. **Clear upload directory:**
   ```bash
   rm -rf data/uploads/*
   ```

---

## Development Issues

### Import Errors

**Error:**

```python
ModuleNotFoundError: No module named 'src'
```

**Solutions:**

1. **Install in editable mode:**

   ```bash
   pip install -e ".[dev]"
   ```

2. **Verify virtual environment active:**

   ```bash
   which python
   # Should show .venv/bin/python
   ```

3. **Check PYTHONPATH:**
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

---

### Tests Failing

**Error:**

```
pytest: error: unrecognized arguments
```

**Solutions:**

1. **Install dev dependencies:**

   ```bash
   pip install -e ".[dev]"
   ```

2. **Run from project root:**

   ```bash
   cd /path/to/lexard
   pytest tests/
   ```

3. **Check test dependencies:**
   ```bash
   pip list | grep pytest
   ```

---

### Type Checking Errors

**Error:**

```
mypy: error: Cannot find implementation or library stub
```

**Solutions:**

1. **Install type stubs:**

   ```bash
   pip install types-PyYAML types-requests
   ```

2. **Skip external libraries:**
   Add to `pyproject.toml`:
   ```toml
   [tool.mypy]
   ignore_missing_imports = true
   ```

---

## Web UI Issues

### UI Not Loading

**Symptoms:** Blank page at `http://localhost:8000`

**Solutions:**

1. **Check API is running:**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Clear browser cache**

3. **Check browser console for errors**

4. **Verify static files exist:**
   ```bash
   ls ui/static/
   # Should show index.html, style.css, app.js
   ```

---

### Upload Not Working in UI

**Symptoms:** File upload button does nothing

**Solutions:**

1. **Check file size < 50MB**

2. **Check file format (PDF, DOCX, TXT only)**

3. **Open browser console:**
   Look for CORS or network errors

4. **Check API logs:**
   ```bash
   # Terminal running uvicorn
   ```

---

## MCP Issues

### MCP Server Not Responding

**Error:**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  }
}
```

**Solutions:**

1. **Verify JSON-RPC 2.0 format:**

   ```json
   {
     "jsonrpc": "2.0",
     "method": "tools/list",
     "id": 1
   }
   ```

2. **Check endpoint:**

   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
   ```

3. **Check MCP logs:**
   Look for errors in API logs

---

## Logging & Debugging

### Enable Debug Logging

In `config/config.yaml`:

```yaml
app:
  log_level: 'debug'
```

Or via environment:

```bash
export LEXARD_APP__LOG_LEVEL=debug
```

---

### View Docker Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f qdrant
docker-compose logs -f ollama

# Last 100 lines
docker-compose logs --tail=100
```

---

### Check Service Health

```bash
# Overall health
curl http://localhost:8000/health | jq

# Guardrails metrics
curl http://localhost:8000/guardrails/metrics | jq

# Performance metrics
curl http://localhost:8000/performance/metrics | jq
```

---

## Getting Help

If issues persist:

1. **Check GitHub Issues:**
   [https://github.com/yourusername/lexard/issues](https://github.com/yourusername/lexard/issues)

2. **Enable debug logging and collect:**

   - Error messages
   - API logs
   - Docker logs
   - System info (OS, Python version, Docker version)

3. **Create minimal reproduction:**

   - Specific steps to reproduce
   - Expected vs actual behavior
   - Sample files (if applicable)

4. **Submit issue with:**
   - Clear description
   - Logs and error messages
   - Environment details
   - Steps to reproduce

---

## Preventive Maintenance

### Regular Checks

```bash
# Weekly: Check disk space
df -h

# Weekly: Clean Docker
docker system prune

# Monthly: Update dependencies
pip install --upgrade -r requirements.txt

# Monthly: Pull latest models
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

### Backup

```bash
# Backup Qdrant
docker exec lexard-qdrant tar czf - /qdrant/storage > qdrant-backup.tar.gz

# Backup SQLite
cp data/documents.db documents-backup-$(date +%Y%m%d).db
```

---

## Next Steps

- [Configuration Guide](configuration.md) - Tune settings
- [Development Guide](development.md) - Development setup
- [Deployment Guide](deployment.md) - Production deployment
- [API Reference](api.md) - API documentation
