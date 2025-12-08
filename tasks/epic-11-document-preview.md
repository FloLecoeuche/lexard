# Epic 11: Document Preview Modal

## Overview

Add a quick document preview feature to the Web UI, allowing users to view original documents (PDF, DOCX, TXT) in a modal overlay before performing queries, risk analysis, summaries, or comparisons.

## Prerequisites

- Epic 5 (Interfaces) completed - Web UI functional
- Document upload and storage working

## Architecture Decision

**Storage: SQLite BLOB** (not filesystem)

Original document files are stored as BLOBs in the SQLite database (`file_content` column) rather than on the filesystem. This ensures:
- Multi-client access: Documents available from any machine connecting to the API
- Single backup: One `lexard.db` file contains all data
- ACID consistency: Document metadata and content always in sync
- Sovereignty: No external storage dependencies

## User Stories

---

## US 11.1: Document File Serving Endpoint

**Status:** ✅ Completed

### Description

Create a backend endpoint to serve original document files with proper Content-Type headers, enabling client-side rendering of documents.

### Context

Current system stores documents but doesn't expose the original files for viewing. Users can only interact with processed content (queries, summaries). To preview documents, the UI needs access to the raw file bytes.

Requirements:
- Serve original file with correct MIME type
- Support PDF, DOCX, TXT formats
- Handle missing files gracefully
- No external API calls (sovereignty preserved)

### Tasks

- [ ] Add file content storage to document registry:
  - Add `file_content BLOB` column to documents table in `src/db/sqlite.py`
  - Add migration for existing databases
  - Update `Document` dataclass to NOT include file_content (keep it separate for performance)
- [ ] Add registry methods for file content:
  - `store_file_content(doc_id: str, content: bytes)` - Store file bytes
  - `get_file_content(doc_id: str) -> bytes | None` - Retrieve file bytes
- [ ] Create file serving endpoint:
  - `GET /documents/{doc_id}/file` - Return original file from database
  - Set correct `Content-Type` header based on file extension
  - Return `Content-Disposition: inline` for browser display
  - Handle 404 for missing documents/files
- [ ] Update upload endpoint:
  - Store original file content in SQLite BLOB column
  - Preserve original filename for display
- [ ] Add MIME type mapping:
  - `.pdf` → `application/pdf`
  - `.docx` → `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `.txt` → `text/plain; charset=utf-8`

### Implementation

```python
# src/db/sqlite.py - Add to schema
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    ...
    file_content BLOB,  -- Original file bytes for preview
    ...
);
"""

# src/db/sqlite.py - Add methods
def store_file_content(self, doc_id: str, content: bytes) -> bool:
    """Store file content as BLOB."""
    conn = self._get_connection()
    cursor = conn.execute(
        "UPDATE documents SET file_content = ? WHERE id = ?",
        (content, doc_id),
    )
    conn.commit()
    return cursor.rowcount > 0

def get_file_content(self, doc_id: str) -> bytes | None:
    """Retrieve file content from BLOB."""
    conn = self._get_connection()
    cursor = conn.execute(
        "SELECT file_content FROM documents WHERE id = ?",
        (doc_id,),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else None
```

```python
# src/api/routes/documents.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pathlib import Path

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}


@router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str, request: Request):
    """Serve original document file for preview from database."""
    registry = get_document_registry()

    # Get document metadata
    document = registry.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND"})

    # Get file content from database
    content = registry.get_file_content(doc_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND"})

    # Determine MIME type from filename
    suffix = Path(document.filename).suffix.lower()
    media_type = MIME_TYPES.get(suffix, "application/octet-stream")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'}
    )
```

### Acceptance Criteria

- [ ] `GET /documents/{doc_id}/file` endpoint exists
- [ ] PDF files served with `application/pdf` Content-Type
- [ ] DOCX files served with correct MIME type
- [ ] TXT files served with `text/plain; charset=utf-8`
- [ ] 404 returned for non-existent documents
- [ ] 404 returned if file content not stored in database
- [ ] Original filename preserved in Content-Disposition header
- [ ] No file path traversal vulnerabilities
- [ ] Endpoint documented in OpenAPI spec

### Tests

- **New:** `tests/test_document_file_endpoint.py` - Test file serving endpoint
- **Run:** `pytest tests/test_document_file_endpoint.py -v`

> Note: Test MIME types, 404 handling, and path traversal protection.

### Files to Create/Modify

1. `src/db/sqlite.py` (modify - add file_content BLOB column, store/get methods)
2. `src/api/routes/documents.py` (modify - add file endpoint, update upload to store BLOB)
3. `tests/test_document_file_endpoint.py` (new)

---

## US 11.2: Preview Modal UI Component

**Status:** 🔶 In Progress

### Description

Add a preview button (eye icon) to each document in the sidebar that opens a modal overlay displaying the document content. Support PDF rendering with PDF.js, DOCX rendering with docx-preview, and TXT display with styled `<pre>` tag.

### Context

Users need to verify document content before performing analysis operations. A quick preview modal allows them to:
- Confirm they selected the correct document
- Review specific sections before querying
- Check document quality after upload

UX requirements:
- Eye icon appears on hover over document item
- Click opens full-screen modal overlay
- Modal has close button (X) and click-outside-to-close
- Document renders based on file type
- Loading state while fetching/rendering
- Error state if rendering fails

### Tasks

- [ ] Add preview button to document list:
  - Eye icon (👁 or SVG) on document item hover
  - Click handler opens modal
  - Prevent triggering document selection
- [ ] Create modal overlay component:
  - Full-screen overlay with dark backdrop
  - White content area (90% width/height)
  - Header with document title and close button
  - Body for document content
  - Close on X click, Escape key, or backdrop click
- [ ] Integrate PDF.js for PDF rendering:
  - Load PDF.js from local bundle (no CDN for sovereignty)
  - Render PDF pages in scrollable container
  - Show page numbers
  - Handle multi-page documents
- [ ] Integrate docx-preview for DOCX rendering:
  - Load docx-preview library
  - Render DOCX content in container
  - Style to match document appearance
- [ ] Add TXT rendering:
  - Display in `<pre>` tag with monospace font
  - Preserve whitespace and line breaks
  - Add horizontal scroll for long lines
- [ ] Add loading and error states:
  - Spinner while fetching file
  - Error message if fetch fails
  - Error message if rendering fails

### Implementation

```html
<!-- Add to ui/index.html - CSS -->
<style>
/* Preview button on document item */
.preview-btn {
    background: none;
    border: none;
    color: #64748b;
    cursor: pointer;
    padding: 0.25rem;
    opacity: 0;
    transition: opacity 0.2s;
    font-size: 1rem;
}

.document-item:hover .preview-btn {
    opacity: 0.6;
}

.preview-btn:hover {
    opacity: 1;
    color: #2563eb;
}

/* Modal overlay */
.preview-modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s, visibility 0.2s;
}

.preview-modal.active {
    opacity: 1;
    visibility: visible;
}

.preview-modal-content {
    background: white;
    width: 90%;
    height: 90%;
    max-width: 1200px;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.preview-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e2e8f0;
}

.preview-modal-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.preview-modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #64748b;
    cursor: pointer;
    padding: 0.25rem;
    line-height: 1;
}

.preview-modal-close:hover {
    color: #1e293b;
}

.preview-modal-body {
    flex: 1;
    overflow: auto;
    padding: 1rem;
    background: #f8fafc;
}

/* Document viewer containers */
.pdf-viewer {
    width: 100%;
    height: 100%;
}

.pdf-viewer canvas {
    display: block;
    margin: 0 auto 1rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.docx-viewer {
    background: white;
    padding: 2rem;
    min-height: 100%;
}

.txt-viewer {
    background: white;
    padding: 1.5rem;
    border-radius: 6px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 0.875rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-x: auto;
}

/* Loading state */
.preview-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #64748b;
}

.preview-loading .spinner {
    width: 40px;
    height: 40px;
    margin-bottom: 1rem;
}

/* Error state */
.preview-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #991b1b;
    text-align: center;
}

.preview-error-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}
</style>
```

```html
<!-- Add to ui/index.html - Modal HTML (before </body>) -->
<div id="preview-modal" class="preview-modal">
    <div class="preview-modal-content">
        <div class="preview-modal-header">
            <span class="preview-modal-title" id="preview-title">Document Preview</span>
            <button class="preview-modal-close" id="preview-close">&times;</button>
        </div>
        <div class="preview-modal-body" id="preview-body">
            <!-- Document content rendered here -->
        </div>
    </div>
</div>
```

```javascript
// Add to ui/index.html - JavaScript

// Preview modal state
let previewModal = null;
let pdfJsLib = null;

// Initialize preview functionality
function setupPreview() {
    previewModal = document.getElementById('preview-modal');
    const closeBtn = document.getElementById('preview-close');

    // Close on X button
    closeBtn.addEventListener('click', closePreviewModal);

    // Close on backdrop click
    previewModal.addEventListener('click', (e) => {
        if (e.target === previewModal) {
            closePreviewModal();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && previewModal.classList.contains('active')) {
            closePreviewModal();
        }
    });
}

function openPreviewModal(docId, filename) {
    const modal = document.getElementById('preview-modal');
    const title = document.getElementById('preview-title');
    const body = document.getElementById('preview-body');

    // Set title
    title.textContent = filename;

    // Show loading state
    body.innerHTML = `
        <div class="preview-loading">
            <div class="spinner"></div>
            <span>Loading document...</span>
        </div>
    `;

    // Show modal
    modal.classList.add('active');

    // Fetch and render document
    renderDocumentPreview(docId, filename, body);
}

function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    modal.classList.remove('active');

    // Clear content to free memory
    const body = document.getElementById('preview-body');
    body.innerHTML = '';
}

async function renderDocumentPreview(docId, filename, container) {
    try {
        const response = await fetch(`/documents/${docId}/file`);

        if (!response.ok) {
            throw new Error('Failed to fetch document');
        }

        const blob = await response.blob();
        const extension = filename.split('.').pop().toLowerCase();

        switch (extension) {
            case 'pdf':
                await renderPdfPreview(blob, container);
                break;
            case 'docx':
                await renderDocxPreview(blob, container);
                break;
            case 'txt':
                await renderTxtPreview(blob, container);
                break;
            default:
                throw new Error(`Unsupported file type: ${extension}`);
        }
    } catch (error) {
        container.innerHTML = `
            <div class="preview-error">
                <span class="preview-error-icon">⚠️</span>
                <p>Failed to load document preview</p>
                <p style="font-size: 0.875rem; color: #64748b;">${escapeHtml(error.message)}</p>
            </div>
        `;
    }
}

async function renderPdfPreview(blob, container) {
    // Load PDF.js if not already loaded
    if (!pdfJsLib) {
        pdfJsLib = window['pdfjs-dist/build/pdf'];
        pdfJsLib.GlobalWorkerOptions.workerSrc = '/static/js/pdf.worker.min.js';
    }

    const arrayBuffer = await blob.arrayBuffer();
    const pdf = await pdfJsLib.getDocument({ data: arrayBuffer }).promise;

    container.innerHTML = '<div class="pdf-viewer" id="pdf-container"></div>';
    const pdfContainer = document.getElementById('pdf-container');

    // Render all pages
    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        const scale = 1.5;
        const viewport = page.getViewport({ scale });

        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({
            canvasContext: context,
            viewport: viewport
        }).promise;

        pdfContainer.appendChild(canvas);
    }
}

async function renderDocxPreview(blob, container) {
    // docx-preview library
    container.innerHTML = '<div class="docx-viewer" id="docx-container"></div>';
    const docxContainer = document.getElementById('docx-container');

    await docx.renderAsync(blob, docxContainer, null, {
        className: 'docx-content',
        inWrapper: true,
        ignoreWidth: false,
        ignoreHeight: false,
        ignoreFonts: false,
        breakPages: true,
        useBase64URL: true
    });
}

async function renderTxtPreview(blob, container) {
    const text = await blob.text();
    container.innerHTML = `<pre class="txt-viewer">${escapeHtml(text)}</pre>`;
}

// Update renderDocuments to include preview button
function renderDocuments() {
    if (documents.length === 0) {
        documentList.innerHTML = '<li class="empty-state">No documents uploaded</li>';
        return;
    }

    documentList.innerHTML = documents.map(doc => `
        <li class="document-item ${doc.id === selectedDocumentId ? 'selected' : ''}" data-id="${doc.id}">
            <div>
                <div class="title">${escapeHtml(doc.title || doc.filename)}</div>
                <div class="meta">${doc.page_count || 0} pages</div>
            </div>
            <div style="display: flex; gap: 0.25rem;">
                <button class="preview-btn" data-id="${doc.id}" data-filename="${escapeHtml(doc.title || doc.filename)}" title="Preview">👁</button>
                <button class="delete-btn" data-id="${doc.id}" title="Delete">&#x2715;</button>
            </div>
        </li>
    `).join('');

    // Add click handlers
    documentList.querySelectorAll('.document-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('delete-btn') &&
                !e.target.classList.contains('preview-btn')) {
                selectDocument(item.dataset.id);
            }
        });
    });

    documentList.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteDocument(btn.dataset.id);
        });
    });

    // Add preview handlers
    documentList.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openPreviewModal(btn.dataset.id, btn.dataset.filename);
        });
    });
}

// Add to init()
async function init() {
    setupTabs();
    setupUploadHandlers();
    setupDragDrop();
    setupButtons();
    setupPreview();  // Add this line

    await checkHealth();
    await loadDocuments();

    setInterval(checkHealth, 30000);
}
```

### Library Integration

Add PDF.js and docx-preview to the project:

```bash
# Download PDF.js (place in ui/static/js/)
# https://mozilla.github.io/pdf.js/getting_started/#download
# Files needed:
#   - pdf.min.js
#   - pdf.worker.min.js

# For docx-preview, use CDN or bundle:
# https://github.com/VolodymyrBayworker/docxjs
```

Add script tags to index.html:
```html
<head>
    <!-- ... existing styles ... -->

    <!-- PDF.js -->
    <script src="/static/js/pdf.min.js"></script>

    <!-- docx-preview -->
    <script src="/static/js/docx-preview.min.js"></script>
</head>
```

### Acceptance Criteria

- [ ] Eye icon (👁) appears on document item hover
- [ ] Clicking eye icon opens modal overlay
- [ ] Modal displays document title in header
- [ ] Close button (X) closes modal
- [ ] Clicking backdrop closes modal
- [ ] Escape key closes modal
- [ ] PDF files render correctly with all pages
- [ ] DOCX files render with formatting preserved
- [ ] TXT files display in monospace font
- [ ] Loading spinner shown while fetching/rendering
- [ ] Error message shown if preview fails
- [ ] Modal is responsive (works on different screen sizes)
- [ ] No external CDN calls (PDF.js and docx-preview bundled locally)
- [ ] Memory cleaned up when modal closes

### Tests

- **None:** UI-only changes (no Python backend tests)
- **Manual:** Test preview modal for PDF, DOCX, TXT files in browser
- **Run:** Manual browser testing

> Note: Verify modal opens/closes, documents render, and error states display correctly.

### Files to Create/Modify

1. `ui/index.html` (modify - add modal, styles, JavaScript)
2. `ui/static/js/pdf.min.js` (new - PDF.js library)
3. `ui/static/js/pdf.worker.min.js` (new - PDF.js worker)
4. `ui/static/js/docx-preview.min.js` (new - docx-preview library)
5. `src/api/routes/static.py` (modify - serve static JS files)

---

## US 11.3: Integration Testing & Polish

**Status:** 🔲 Not Started

### Description

Integration testing for the document preview feature, ensuring end-to-end functionality and handling edge cases.

### Context

With US 11.1 (backend BLOB storage) and US 11.2 (frontend modal) complete, this story validates the full preview workflow:
- Upload document → BLOB stored in SQLite
- Click preview → Modal fetches and renders
- Delete document → BLOB removed from database

### Tasks

- [ ] End-to-end integration tests:
  - Upload PDF → Preview → Verify renders
  - Upload DOCX → Preview → Verify renders
  - Upload TXT → Preview → Verify renders
- [ ] Edge case handling:
  - Large file preview (test with 10MB+ files)
  - Unicode content in TXT files
  - Multi-page PDF rendering
- [ ] Migration testing:
  - Existing documents (uploaded before BLOB feature) show graceful "preview unavailable" message
- [ ] Error handling polish:
  - Clear error messages for fetch failures
  - Loading state handles slow database reads
- [ ] Documentation:
  - Update API docs with file endpoint
  - Add preview feature to user guide

### Acceptance Criteria

- [ ] Full workflow tested: upload → preview → delete
- [ ] All file types (PDF, DOCX, TXT) preview correctly
- [ ] Large files handled without timeout
- [ ] Existing documents without BLOB show appropriate message
- [ ] Error states display user-friendly messages
- [ ] API documentation updated

### Tests

- **New:** `tests/test_preview_integration.py` - End-to-end preview tests
- **Run:** `pytest tests/test_preview_integration.py -v`

### Files to Create/Modify

1. `tests/test_preview_integration.py` (new - integration tests)
2. `docs/api.md` (modify - document file endpoint)
3. `ui/index.html` (modify - handle legacy documents gracefully)

---

## Definition of Done (Epic 11)

- [ ] All User Stories completed (3/3)
- [ ] Document file serving endpoint functional
- [ ] Preview modal opens and displays documents
- [ ] PDF, DOCX, TXT formats supported
- [ ] Original files stored and cleaned up properly
- [ ] No external CDN dependencies (sovereignty preserved)
- [ ] All acceptance criteria verified
- [ ] Tests pass
- [ ] Documentation updated
