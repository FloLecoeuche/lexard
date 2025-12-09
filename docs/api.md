# API Reference

Complete REST API documentation for Lexard.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is implemented (MVP). For production deployment, implement API key authentication or OAuth2.

## Interactive Documentation

Lexard provides interactive API documentation:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Response Format

All endpoints return JSON responses.

### Success Response

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Error Response

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "trace_id": "request-trace-id"
  }
}
```

## Endpoints

### Health & Monitoring

#### GET /health

Check service health and external dependencies.

**Response: 200 OK**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "qdrant": "connected",
    "ollama": "connected"
  }
}
```

**Status Values:**

- `healthy` - All services connected
- `degraded` - Some services unavailable
- `unhealthy` - All services unavailable

---

#### GET /guardrails/metrics

Get guardrails pipeline metrics.

**Response: 200 OK**

```json
{
  "total_inputs": 1000,
  "total_outputs": 950,
  "injection_blocks": 10,
  "hallucination_blocks": 15,
  "schema_failures": 5,
  "pii_redactions": 20,
  "input_block_rate": 0.01,
  "output_block_rate": 0.02
}
```

---

#### GET /performance/metrics

Get performance metrics for all operations.

**Response: 200 OK**

```json
{
  "metrics": {
    "rag_query": {
      "count": 100,
      "avg_time_ms": 2500.0,
      "min_time_ms": 1200.0,
      "max_time_ms": 4500.0,
      "error_rate": 0.02
    }
  }
}
```

---

### Document Management

#### POST /upload

Upload a document for processing.

**Request**

- Content-Type: `multipart/form-data`
- Body: `file` (max 50MB)
- Supported formats: PDF, DOCX, TXT

**cURL Example**

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@contract.pdf"
```

**Response: 200 OK**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "contract",
  "page_count": 10,
  "chunk_count": 45,
  "version": 1,
  "uploaded_at": "2025-12-05T10:30:00Z"
}
```

**Errors:**

- `413 Payload Too Large` - File exceeds 50MB
- `415 Unsupported Media Type` - Invalid file format
- `422 Unprocessable Entity` - Failed to parse document

---

#### GET /documents

List all uploaded documents.

**Query Parameters:**

- `limit` (int, default: 100) - Maximum documents to return
- `offset` (int, default: 0) - Number of documents to skip

**cURL Example**

```bash
curl http://localhost:8000/documents?limit=10&offset=0
```

**Response: 200 OK**

```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "contract",
      "filename": "contract.pdf",
      "page_count": 10,
      "chunk_count": 45,
      "version": 1,
      "uploaded_at": "2025-12-05T10:30:00Z",
      "status": "processed"
    }
  ],
  "total": 1
}
```

---

#### GET /documents/{document_id}

Get detailed information about a specific document.

**cURL Example**

```bash
curl http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000
```

**Response: 200 OK**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "contract",
  "filename": "contract.pdf",
  "file_hash": "abc123...",
  "page_count": 10,
  "chunk_count": 45,
  "version": 1,
  "parent_document_id": null,
  "uploaded_at": "2025-12-05T10:30:00Z",
  "status": "processed"
}
```

**Errors:**

- `404 Not Found` - Document does not exist

---

#### DELETE /documents/{document_id}

Delete a document and all associated data.

**cURL Example**

```bash
curl -X DELETE http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000
```

**Response: 200 OK**

```json
{
  "success": true,
  "message": "Document deleted successfully"
}
```

**Errors:**

- `404 Not Found` - Document does not exist

---

#### GET /documents/{document_id}/file

Retrieve the original document file for preview.

**cURL Example**

```bash
curl http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000/file \
  -o document.pdf
```

**Response: 200 OK**

Returns the original file with appropriate headers:

- `Content-Type`: MIME type based on file extension
  - PDF: `application/pdf`
  - DOCX: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - TXT: `text/plain; charset=utf-8`
- `Content-Disposition`: `inline; filename="original_filename.ext"`

**Errors:**

- `404 Not Found` - Document does not exist (`DOCUMENT_NOT_FOUND`)
- `404 Not Found` - File content not available (`FILE_NOT_FOUND`) - This occurs for documents uploaded before preview support was added

**Note:** Documents uploaded before the preview feature was added will not have file content stored. Re-upload the document to enable preview functionality.

---

### Query

#### POST /query

Ask a question about a document.

**Request Body**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "What is the termination notice period?"
}
```

**cURL Example**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "question": "What is the termination notice period?"
  }'
```

**Response: 200 OK**

```json
{
  "answer": "The termination notice period is 30 days. Either party may terminate this agreement by providing written notice at least 30 days in advance.",
  "citation_chunks": [
    {
      "content": "Either party may terminate this agreement by providing written notice at least thirty (30) days in advance...",
      "page": 5,
      "chunk_index": 12,
      "score": 0.89
    }
  ],
  "confidence": "high"
}
```

**Confidence Levels:**

- `high` - Strong evidence with high-scoring citations
- `medium` - Moderate evidence with good citations
- `low` - Weak evidence or low-scoring citations

**Errors:**

- `404 Not Found` - Document does not exist
- `400 Bad Request` - Document not processed yet
- `503 Service Unavailable` - LLM service is unavailable

---

### Analysis

#### POST /summarize

Generate a document summary.

**Request Body**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "style": "executive"
}
```

**Style Options:**

- `executive` - Brief executive summary (default)
- `detailed` - Comprehensive detailed summary

**cURL Example**

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "style": "executive"
  }'
```

**Response: 200 OK**

```json
{
  "summary": "This is a standard non-disclosure agreement between Company A and Company B...",
  "key_points": [
    "Confidentiality period: 2 years",
    "Termination notice: 30 days",
    "Jurisdiction: Delaware"
  ],
  "word_count": 1250
}
```

**Errors:**

- `404 Not Found` - Document does not exist
- `400 Bad Request` - Document not processed yet
- `503 Service Unavailable` - LLM service is unavailable

---

#### POST /risks

Analyze document for potential risks.

**Request Body**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**cURL Example**

```bash
curl -X POST http://localhost:8000/risks \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response: 200 OK**

```json
{
  "risks": [
    {
      "category": "financial",
      "severity": "high",
      "description": "Unlimited liability clause without cap",
      "clause_excerpt": "The party shall be liable for all damages...",
      "page": 3,
      "recommendation": "Consider adding a liability cap"
    }
  ],
  "overall_risk_level": "medium"
}
```

**Risk Categories:**

- `legal` - Legal compliance issues
- `financial` - Financial exposure
- `operational` - Operational constraints
- `compliance` - Regulatory compliance

**Severity Levels:**

- `critical` - Immediate attention required
- `high` - Significant risk
- `medium` - Moderate risk
- `low` - Minor risk

**Overall Risk Levels:**

- `high`, `medium`, `low`

**Errors:**

- `404 Not Found` - Document does not exist
- `400 Bad Request` - Document not processed yet
- `503 Service Unavailable` - LLM service is unavailable

---

#### POST /compare

Compare two documents.

**Request Body**

```json
{
  "doc_a": "550e8400-e29b-41d4-a716-446655440000",
  "doc_b": "660e8400-e29b-41d4-a716-446655440001"
}
```

**cURL Example**

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "doc_a": "550e8400-e29b-41d4-a716-446655440000",
    "doc_b": "660e8400-e29b-41d4-a716-446655440001"
  }'
```

**Response: 200 OK**

```json
{
  "differences": [
    {
      "section": "Termination",
      "doc_a_excerpt": "30 days notice required",
      "doc_b_excerpt": "60 days notice required",
      "change_type": "modified",
      "similarity": 0.75
    }
  ],
  "overall_similarity": 0.82
}
```

**Change Types:**

- `added` - Present in doc_b but not doc_a
- `removed` - Present in doc_a but not doc_b
- `modified` - Different between documents

**Errors:**

- `404 Not Found` - One or both documents do not exist
- `400 Bad Request` - Document not processed yet

---

### Operations Progress

#### GET /operations/{operation_id}/progress

Stream progress updates for long-running operations using Server-Sent Events (SSE).

**cURL Example**

```bash
curl -N http://localhost:8000/operations/op-123/progress
```

**Response: 200 OK (text/event-stream)**

```
data: {"stage": "extracting", "progress": 0.25, "message": "Extracting text from document..."}

data: {"stage": "chunking", "progress": 0.50, "message": "Splitting into chunks..."}

data: {"stage": "embedding", "progress": 0.75, "message": "Generating embeddings..."}

data: {"stage": "indexing", "progress": 0.90, "message": "Indexing in vector database..."}

data: {"stage": "complete", "progress": 1.0, "message": "Document processed successfully", "document_id": "uuid-here"}
```

**Progress Stages:**

- `pending` - Operation queued
- `extracting` - Extracting text from document
- `chunking` - Splitting text into chunks
- `embedding` - Generating vector embeddings
- `indexing` - Storing in vector database
- `complete` - Successfully completed
- `failed` - Operation failed

**Errors:**

- `404 Not Found` - Operation ID not found

---

#### GET /operations/{operation_id}/status

Get the current status of an operation (non-streaming).

**cURL Example**

```bash
curl http://localhost:8000/operations/op-123/status
```

**Response: 200 OK**

```json
{
  "operation_id": "op-123",
  "stage": "embedding",
  "progress": 0.75,
  "message": "Generating embeddings...",
  "started_at": "2025-12-05T10:30:00Z"
}
```

---

## Rate Limiting

No rate limiting is currently implemented. For production deployment, consider implementing rate limiting based on your requirements.

## CORS

CORS is enabled for all origins in development mode. Configure appropriately for production deployment.

## Next Steps

- [Configuration Guide](configuration.md) - Customize API settings
- [Development Guide](development.md) - Set up for development
- [MCP Protocol](mcp.md) - Model Context Protocol reference
