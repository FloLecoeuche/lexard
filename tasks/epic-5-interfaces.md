# Epic 5: Interfaces

## Overview

Implement the complete REST API, MCP server, and minimal web UI for demo purposes.

## Prerequisites

- Epic 4 (Agent System) completed
- All agent tools (summarizer, risk detector, diff) working
- RAG pipeline functional

## User Stories

---

## US 5.1: Complete REST API

**Status:** 🔶 In Progress

### Description

Finalize all REST API endpoints with proper request/response schemas, error handling, and OpenAPI documentation.

### Context

The API serves as the primary interface for:

- Document upload and management
- RAG queries with citations
- Document summarization
- Document comparison
- Health and status checks

### Tasks

- [ ] Create `src/api/routes/documents.py` with:
  - `POST /upload` - Document upload (multipart/form-data)
  - `GET /documents` - List all documents
  - `GET /documents/{id}` - Get document metadata
  - `DELETE /documents/{id}` - Delete document
- [ ] Create `src/api/routes/query.py` with:
  - `POST /query` - RAG query with citations
- [ ] Create `src/api/routes/analysis.py` with:
  - `POST /summarize` - Document summarization
  - `POST /compare` - Document comparison
  - `POST /risks` - Risk analysis
- [ ] Create `src/api/routes/__init__.py` with router aggregation
- [ ] Update `src/api/main.py` to include all routers
- [ ] Create comprehensive request/response schemas in `src/api/schemas.py`
- [ ] Add OpenAPI metadata (tags, descriptions, examples)

### API Specifications

**POST /upload**

```
Content-Type: multipart/form-data
Body: file (PDF, DOCX, or TXT)
```

Response:

```json
{
  "document_id": "uuid",
  "title": "string",
  "page_count": 10,
  "chunk_count": 45,
  "version": 1,
  "uploaded_at": "iso8601"
}
```

**GET /documents**

```json
{
  "documents": [
    {
      "id": "uuid",
      "title": "string",
      "filename": "string",
      "page_count": 10,
      "chunk_count": 45,
      "version": 1,
      "uploaded_at": "iso8601",
      "status": "processed"
    }
  ],
  "total": 15
}
```

**GET /documents/{id}**

```json
{
  "id": "uuid",
  "title": "string",
  "filename": "string",
  "file_hash": "string",
  "page_count": 10,
  "chunk_count": 45,
  "version": 1,
  "parent_document_id": "uuid|null",
  "uploaded_at": "iso8601",
  "status": "processed"
}
```

**DELETE /documents/{id}**

```json
{
  "success": true,
  "message": "Document deleted successfully"
}
```

**POST /query**
Request:

```json
{
  "document_id": "uuid",
  "question": "What are the termination conditions?"
}
```

Response:

```json
{
  "answer": "string",
  "citation_chunks": [
    {
      "content": "string",
      "page": 5,
      "chunk_index": 12,
      "score": 0.92
    }
  ],
  "confidence": "high"
}
```

**POST /summarize**
Request:

```json
{
  "document_id": "uuid",
  "style": "executive|detailed"
}
```

Response:

```json
{
  "summary": "string",
  "key_points": ["string"],
  "word_count": 150
}
```

**POST /compare**
Request:

```json
{
  "doc_a": "uuid",
  "doc_b": "uuid"
}
```

Response:

```json
{
  "differences": [
    {
      "section": "Termination Clause",
      "doc_a_excerpt": "string",
      "doc_b_excerpt": "string",
      "change_type": "added|removed|modified",
      "similarity": 0.75
    }
  ],
  "overall_similarity": 0.85
}
```

**POST /risks**
Request:

```json
{
  "document_id": "uuid"
}
```

Response:

```json
{
  "risks": [
    {
      "category": "financial|legal|data_protection|termination|ambiguity",
      "severity": "low|medium|high",
      "description": "string",
      "clause_excerpt": "string",
      "page": 5,
      "recommendation": "string"
    }
  ],
  "overall_risk_level": "low|medium|high"
}
```

### Error Response Schema

All endpoints use consistent error format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "trace_id": "uuid"
  }
}
```

| HTTP Status | Error Code          | Description               |
| ----------- | ------------------- | ------------------------- |
| 400         | INVALID_REQUEST     | Malformed request         |
| 404         | DOCUMENT_NOT_FOUND  | Document ID doesn't exist |
| 413         | FILE_TOO_LARGE      | Exceeds 50MB limit        |
| 415         | UNSUPPORTED_FORMAT  | Not PDF/DOCX/TXT          |
| 500         | INTERNAL_ERROR      | Unexpected failure        |
| 503         | SERVICE_UNAVAILABLE | Qdrant or LLM unavailable |

### Acceptance Criteria

- [ ] All endpoints return correct status codes
- [ ] Request validation with Pydantic models
- [ ] Response schemas documented in OpenAPI
- [ ] Error responses include trace_id
- [ ] File upload validates size (max 50MB) and format
- [ ] OpenAPI docs available at `/docs`
- [ ] All endpoints have example requests/responses

### Files to Create/Modify

1. `src/api/routes/__init__.py`
2. `src/api/routes/documents.py`
3. `src/api/routes/query.py`
4. `src/api/routes/analysis.py`
5. `src/api/schemas.py` (extend existing)
6. `src/api/main.py` (update)

---

## US 5.2: MCP Server Implementation

**Status:** Not Started

### Description

Implement the Model Context Protocol (MCP) server with JSON-RPC 2.0 interface for external tool integration.

### Context

MCP allows external AI systems (like Claude Desktop) to:

- List available documents
- Analyze documents
- Ask questions about documents
- Compare documents

The server uses JSON-RPC 2.0 protocol over HTTP.

### Tasks

- [ ] Create `src/mcp/server.py` with JSON-RPC handler
- [ ] Create `src/mcp/methods.py` with MCP method implementations:
  - `list_documents`
  - `analyze_document`
  - `ask_question`
  - `compare`
- [ ] Create `src/mcp/schemas.py` with request/response models
- [ ] Create `src/mcp/errors.py` with JSON-RPC error codes
- [ ] Add MCP router to FastAPI app
- [ ] Implement request validation and error handling

### MCP Protocol Specification

**Endpoint:** `POST /mcp`

**Request format:**

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {},
  "id": 1
}
```

**Response format (success):**

```json
{
  "jsonrpc": "2.0",
  "result": {},
  "id": 1
}
```

**Response format (error):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid request",
    "data": "Additional error details"
  },
  "id": null
}
```

### Method Implementations

**1. list_documents**

```json
// Request
{
  "jsonrpc": "2.0",
  "method": "list_documents",
  "params": {},
  "id": 1
}

// Response
{
  "jsonrpc": "2.0",
  "result": {
    "documents": [
      {
        "id": "uuid",
        "title": "string",
        "uploaded_at": "iso8601",
        "page_count": 10,
        "version": 1
      }
    ]
  },
  "id": 1
}
```

**2. analyze_document**

```json
// Request
{
  "jsonrpc": "2.0",
  "method": "analyze_document",
  "params": {
    "document_id": "uuid",
    "analysis_type": "summary|risks|metadata"
  },
  "id": 2
}

// Response
{
  "jsonrpc": "2.0",
  "result": {
    "analysis": "string",
    "risk_level": "low|medium|high|null",
    "citations": ["string"]
  },
  "id": 2
}
```

**3. ask_question**

```json
// Request
{
  "jsonrpc": "2.0",
  "method": "ask_question",
  "params": {
    "document_id": "uuid",
    "question": "string"
  },
  "id": 3
}

// Response
{
  "jsonrpc": "2.0",
  "result": {
    "answer": "string",
    "citation_chunks": ["string"],
    "confidence": "high|medium|low"
  },
  "id": 3
}
```

**4. compare**

```json
// Request
{
  "jsonrpc": "2.0",
  "method": "compare",
  "params": {
    "doc_a": "uuid",
    "doc_b": "uuid"
  },
  "id": 4
}

// Response
{
  "jsonrpc": "2.0",
  "result": {
    "differences": [
      {
        "section": "string",
        "doc_a_content": "string",
        "doc_b_content": "string",
        "similarity_score": 0.75
      }
    ]
  },
  "id": 4
}
```

### Error Codes

| Error Code | Meaning            |
| ---------- | ------------------ |
| -32700     | Parse error        |
| -32600     | Invalid request    |
| -32601     | Method not found   |
| -32602     | Invalid params     |
| -32603     | Internal error     |
| -32000     | Document not found |
| -32001     | Analysis failed    |

### Acceptance Criteria

- [ ] `POST /mcp` accepts JSON-RPC requests
- [ ] All 4 methods implemented and functional
- [ ] Error responses follow JSON-RPC 2.0 spec
- [ ] Invalid methods return -32601
- [ ] Invalid params return -32602
- [ ] Request validation with proper error messages
- [ ] Methods integrate with existing agent tools

### Files to Create

1. `src/mcp/server.py`
2. `src/mcp/methods.py`
3. `src/mcp/schemas.py`
4. `src/mcp/errors.py`
5. `src/mcp/__init__.py` (update if needed)

### Verification

```python
import httpx

# Test list_documents
response = httpx.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "method": "list_documents",
    "params": {},
    "id": 1
})
assert response.json()["jsonrpc"] == "2.0"
assert "result" in response.json()

# Test invalid method
response = httpx.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "method": "invalid_method",
    "params": {},
    "id": 2
})
assert response.json()["error"]["code"] == -32601
```

---

## US 5.3: Web UI

**Status:** Not Started

### Description

Create a minimal single-page web UI for demo purposes that supports document upload, query, and viewing results.

### Context

The UI is for demonstration only, not production use. It should:

- Be simple and self-contained (single HTML file with embedded JS/CSS)
- Work without build tools or npm
- Show all core capabilities

### Tasks

- [ ] Create `ui/index.html` with:
  - Document upload form
  - Document list display
  - Query input and results display
  - Summarization trigger
  - Risk analysis display
  - Document comparison interface
- [ ] Style with minimal CSS (embedded or inline)
- [ ] Implement JavaScript for API calls (fetch API)
- [ ] Add loading states and error handling
- [ ] Create `src/api/routes/static.py` to serve the UI

### UI Components

**1. Header**

- Lexard logo/title
- Status indicator (API health)

**2. Document Panel (Left)**

- Upload button with drag-and-drop
- List of uploaded documents
- Document details on click
- Delete button per document

**3. Main Panel (Center)**

- Tab navigation: Query | Summarize | Risks | Compare
- Query tab:
  - Question input
  - Submit button
  - Answer display with citations
- Summarize tab:
  - Style selector (executive/detailed)
  - Generate button
  - Summary display
- Risks tab:
  - Analyze button
  - Risk list with severity badges
- Compare tab:
  - Document A selector
  - Document B selector
  - Compare button
  - Differences display

**4. Footer**

- Version info
- API docs link

### HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Lexard - Contract Analyst</title>
    <style>
      /* Embedded CSS */
    </style>
  </head>
  <body>
    <header>
      <h1>Lexard</h1>
      <span id="status">Checking...</span>
    </header>

    <main>
      <aside id="documents-panel">
        <h2>Documents</h2>
        <input type="file" id="file-input" accept=".pdf,.docx,.txt" />
        <button id="upload-btn">Upload</button>
        <ul id="document-list"></ul>
      </aside>

      <section id="main-panel">
        <nav>
          <button class="tab active" data-tab="query">Query</button>
          <button class="tab" data-tab="summarize">Summarize</button>
          <button class="tab" data-tab="risks">Risks</button>
          <button class="tab" data-tab="compare">Compare</button>
        </nav>

        <div id="query-panel" class="panel active">
          <input type="text" id="question" placeholder="Ask a question..." />
          <button id="ask-btn">Ask</button>
          <div id="answer"></div>
        </div>

        <!-- Other panels -->
      </section>
    </main>

    <script>
      // Embedded JavaScript
    </script>
  </body>
</html>
```

### JavaScript Functions

```javascript
// API base URL
const API_URL = '';

// Health check
async function checkHealth() { ... }

// Document operations
async function uploadDocument(file) { ... }
async function listDocuments() { ... }
async function deleteDocument(id) { ... }

// Query operations
async function askQuestion(docId, question) { ... }
async function summarizeDocument(docId, style) { ... }
async function analyzeRisks(docId) { ... }
async function compareDocuments(docA, docB) { ... }

// UI helpers
function showLoading(element) { ... }
function hideLoading(element) { ... }
function showError(message) { ... }
function renderDocuments(documents) { ... }
function renderAnswer(response) { ... }
function renderRisks(risks) { ... }
function renderComparison(differences) { ... }
```

### Styling Guidelines

- Clean, professional appearance
- Responsive layout (flex/grid)
- Color scheme:
  - Primary: #2563eb (blue)
  - Success: #10b981 (green)
  - Warning: #f59e0b (amber)
  - Error: #ef4444 (red)
  - Background: #f8fafc
  - Text: #1e293b
- Loading spinners for async operations
- Error messages in red
- Risk severity badges (colored)

### Acceptance Criteria

- [ ] UI loads at `http://localhost:8000/`
- [ ] Document upload works (drag-and-drop and file picker)
- [ ] Document list refreshes after upload
- [ ] Query returns answer with citations displayed
- [ ] Summarization generates and displays summary
- [ ] Risk analysis shows risks with severity
- [ ] Document comparison shows differences
- [ ] Loading states visible during API calls
- [ ] Errors displayed clearly to user
- [ ] Works in Chrome, Firefox, Safari

### Files to Create

1. `ui/index.html`
2. `src/api/routes/static.py`

### Static File Serving

```python
# src/api/routes/static.py
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

UI_DIR = Path(__file__).parent.parent.parent.parent / "ui"

@router.get("/")
async def serve_ui():
    return FileResponse(UI_DIR / "index.html")
```

---

## Definition of Done (Epic 5)

- [ ] All 3 User Stories completed
- [ ] All REST API endpoints functional with proper error handling
- [ ] MCP server accepts JSON-RPC requests
- [ ] Web UI demonstrates all core features
- [ ] OpenAPI documentation complete at `/docs`
- [ ] All endpoints tested manually
- [ ] Error responses consistent across all interfaces
