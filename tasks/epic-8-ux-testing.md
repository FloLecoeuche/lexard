# Epic 8: UX & Testing Enhancements

## Overview

Enhance user experience with real-time upload progress tracking and validate system reliability with comprehensive end-to-end tests covering all nominal use cases.

## Prerequisites

- Epic 7 (Multilingual Support) completed
- All core functionality working in English and French
- System stable and ready for production

## User Stories

---

## US 8.1: Upload Progress Tracking

**Status:** ✅ Completed

### Description

Implement real-time progress tracking for document uploads in the Web UI, showing parsing, chunking, embedding, and indexing stages to improve user experience.

### Context

Current upload UX limitations:

- No feedback during long-running uploads
- Users don't know if upload is still processing
- No visibility into which stage is running
- Timeouts with large documents (50MB, 500+ pages)

Large documents can take 30+ seconds to process through:
1. Upload (file transfer)
2. Parsing (PDF extraction)
3. Chunking (text splitting)
4. Embedding (generate vectors)
5. Indexing (store in Qdrant)

Users need:

- Real-time progress updates
- Stage-by-stage feedback
- Estimated completion time (optional)
- Error handling with clear messages
- Ability to cancel uploads

### Architecture

Use **Server-Sent Events (SSE)** for real-time updates:

```
User uploads file → Backend processes → SSE stream → UI updates progress bar
```

**Alternatives considered:**

- WebSockets: Overkill for one-way communication
- Polling: Inefficient, delays in updates
- SSE: Perfect for server → client streaming

### Tasks

- [ ] Create backend progress tracking system:
  - `src/api/progress.py` - Progress tracker with SSE support
  - Thread-safe tracker for concurrent uploads
  - Support multiple simultaneous uploads
  - Stage enumeration and state management
- [ ] Update upload endpoint:
  - `src/api/routes/documents.py` - Add progress endpoints
  - Return task_id immediately on upload
  - Process document in background task
  - Emit progress events during processing
  - Handle cancellation requests
- [ ] Create SSE streaming endpoint:
  - `/upload/progress/{task_id}` - SSE stream
  - `/upload/status/{task_id}` - Polling fallback
  - Handle client disconnections
  - Clean up completed tasks
- [ ] Update Web UI:
  - `ui/src/components/UploadProgress.tsx` - Progress component
  - Connect to SSE endpoint
  - Display stage-by-stage progress bar
  - Show percentage completion
  - Add cancel button
  - Handle errors inline
- [ ] Add progress hooks to ingestion pipeline:
  - Hook into parsing stage
  - Hook into chunking stage
  - Hook into embedding stage (with batch progress)
  - Hook into indexing stage
- [ ] Add error handling:
  - Display errors clearly in UI
  - Allow retry on failure
  - Clean up partial uploads on error

### Progress Tracker Implementation

```python
# src/api/progress.py
"""Real-time progress tracking for document processing."""
import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import AsyncIterator
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class ProcessingStage(str, Enum):
    """Document processing stages."""
    UPLOADING = "uploading"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    """Progress update event."""
    task_id: str
    stage: ProcessingStage
    progress: float  # 0.0 to 1.0
    message: str
    timestamp: datetime = None
    error: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class ProgressTracker:
    """Track progress of document processing tasks.

    Thread-safe tracker that supports multiple concurrent uploads.
    """

    def __init__(self):
        self._tasks: dict[str, ProgressUpdate] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def create_task(self, initial_message: str = "Starting upload...") -> str:
        """Create a new progress tracking task.

        Args:
            initial_message: Initial progress message

        Returns:
            Task ID (UUID)
        """
        task_id = str(uuid4())
        self._tasks[task_id] = ProgressUpdate(
            task_id=task_id,
            stage=ProcessingStage.UPLOADING,
            progress=0.0,
            message=initial_message
        )
        self._subscribers[task_id] = []
        logger.info(f"Created progress task: {task_id}")
        return task_id

    async def update(
        self,
        task_id: str,
        stage: ProcessingStage,
        progress: float,
        message: str,
        error: str | None = None,
    ) -> None:
        """Update task progress and notify subscribers.

        Args:
            task_id: Task identifier
            stage: Current processing stage
            progress: Progress percentage (0.0 to 1.0)
            message: Human-readable status message
            error: Optional error message
        """
        async with self._lock:
            update = ProgressUpdate(
                task_id=task_id,
                stage=stage,
                progress=progress,
                message=message,
                error=error,
            )
            self._tasks[task_id] = update

            # Notify all subscribers
            if task_id in self._subscribers:
                for queue in self._subscribers[task_id]:
                    try:
                        await queue.put(update)
                    except Exception as e:
                        logger.error(f"Failed to notify subscriber: {e}")

        logger.debug(f"Task {task_id}: {stage.value} ({progress:.0%}) - {message}")

    async def subscribe(self, task_id: str) -> AsyncIterator[ProgressUpdate]:
        """Subscribe to progress updates for a task.

        Args:
            task_id: Task identifier

        Yields:
            Progress updates as they occur
        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found")
            return

        queue: asyncio.Queue[ProgressUpdate] = asyncio.Queue()

        async with self._lock:
            self._subscribers[task_id].append(queue)

            # Send current state immediately
            if task_id in self._tasks:
                await queue.put(self._tasks[task_id])

        try:
            while True:
                update = await queue.get()
                yield update

                # Stop after completion or failure
                if update.stage in (ProcessingStage.COMPLETE, ProcessingStage.FAILED):
                    break
        finally:
            # Cleanup
            async with self._lock:
                if task_id in self._subscribers:
                    try:
                        self._subscribers[task_id].remove(queue)
                    except ValueError:
                        pass

    def get_status(self, task_id: str) -> ProgressUpdate | None:
        """Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Current progress update or None if not found
        """
        return self._tasks.get(task_id)

    async def mark_complete(
        self,
        task_id: str,
        message: str,
        document_id: str | None = None,
    ) -> None:
        """Mark task as complete.

        Args:
            task_id: Task identifier
            message: Completion message
            document_id: Optional document ID to include in message
        """
        final_message = message
        if document_id:
            final_message = f"{message} (Document ID: {document_id})"

        await self.update(
            task_id,
            ProcessingStage.COMPLETE,
            1.0,
            final_message
        )

    async def mark_failed(
        self,
        task_id: str,
        error: str,
    ) -> None:
        """Mark task as failed.

        Args:
            task_id: Task identifier
            error: Error message
        """
        await self.update(
            task_id,
            ProcessingStage.FAILED,
            0.0,
            "Upload failed",
            error=error
        )

    async def cleanup(self, task_id: str, delay_seconds: int = 300) -> None:
        """Clean up completed task after delay.

        Args:
            task_id: Task identifier
            delay_seconds: Delay before cleanup (default: 5 minutes)
        """
        await asyncio.sleep(delay_seconds)
        async with self._lock:
            self._tasks.pop(task_id, None)
            self._subscribers.pop(task_id, None)
        logger.debug(f"Cleaned up task: {task_id}")


# Global progress tracker instance
progress_tracker = ProgressTracker()
```

### Updated Upload Endpoint

```python
# src/api/routes/documents.py
import asyncio
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from src.api.progress import progress_tracker, ProcessingStage

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """Upload and process a document with progress tracking.

    Returns:
        Task ID and URLs for progress tracking
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Create progress task
    task_id = progress_tracker.create_task(f"Uploading {file.filename}...")

    # Start background processing
    background_tasks.add_task(
        process_document_with_progress,
        file,
        task_id
    )

    return {
        "task_id": task_id,
        "filename": file.filename,
        "progress_url": f"/upload/progress/{task_id}",
        "status_url": f"/upload/status/{task_id}",
    }


@router.get("/upload/progress/{task_id}")
async def stream_upload_progress(task_id: str):
    """Stream real-time progress updates via Server-Sent Events.

    Args:
        task_id: Progress task identifier

    Returns:
        SSE stream of progress updates
    """
    async def event_generator():
        """Generate SSE events from progress updates."""
        async for update in progress_tracker.subscribe(task_id):
            yield {
                "event": "progress",
                "data": json.dumps(update.to_dict()),
            }

    return EventSourceResponse(event_generator())


@router.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    """Get current upload status (polling alternative to SSE).

    Args:
        task_id: Progress task identifier

    Returns:
        Current progress status

    Raises:
        HTTPException: If task not found
    """
    status = progress_tracker.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status.to_dict()


async def process_document_with_progress(file: UploadFile, task_id: str):
    """Process document and emit progress updates.

    Args:
        file: Uploaded file
        task_id: Progress task ID
    """
    try:
        # Stage 1: Parsing (0-20%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.PARSING,
            0.0,
            f"Parsing {file.filename}..."
        )

        # Read file content
        content = await file.read()
        text = await parse_document(content, file.filename)

        await progress_tracker.update(
            task_id,
            ProcessingStage.PARSING,
            0.2,
            f"Extracted {len(text)} characters"
        )

        # Stage 2: Chunking (20-40%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.CHUNKING,
            0.2,
            "Splitting into chunks..."
        )

        chunks = await chunking_service.chunk_text(text)

        await progress_tracker.update(
            task_id,
            ProcessingStage.CHUNKING,
            0.4,
            f"Created {len(chunks)} chunks"
        )

        # Stage 3: Embedding (40-80%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.EMBEDDING,
            0.4,
            f"Generating embeddings for {len(chunks)} chunks..."
        )

        # Generate embeddings with progress
        embeddings = embedding_service.embed_documents(
            [chunk.content for chunk in chunks],
            batch_size=32,
            show_progress=False,
        )

        await progress_tracker.update(
            task_id,
            ProcessingStage.EMBEDDING,
            0.8,
            f"Generated {len(embeddings)} embeddings"
        )

        # Stage 4: Indexing (80-100%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.INDEXING,
            0.8,
            "Indexing in vector database..."
        )

        # Create document record
        doc_id = str(uuid4())
        document = Document(
            id=doc_id,
            title=file.filename,
            upload_date=datetime.now(),
            chunk_count=len(chunks),
        )

        # Store in registry
        registry.add_document(document)

        # Index in Qdrant
        await qdrant_service.index_chunks(
            document_id=doc_id,
            chunks=chunks,
            embeddings=embeddings,
        )

        # Mark complete
        await progress_tracker.mark_complete(
            task_id,
            "Document uploaded successfully!",
            document_id=doc_id
        )

        # Schedule cleanup
        asyncio.create_task(progress_tracker.cleanup(task_id))

    except Exception as e:
        logger.error(f"Upload failed for task {task_id}: {e}")
        await progress_tracker.mark_failed(task_id, str(e))
```

### Web UI Component

```tsx
// ui/src/components/UploadProgress.tsx
import React, { useEffect, useState } from 'react';
import './UploadProgress.css';

interface ProgressUpdate {
  task_id: string;
  stage: string;
  progress: number;
  message: string;
  timestamp: string;
  error?: string;
}

interface UploadProgressProps {
  taskId: string;
  onComplete?: (documentId: string) => void;
  onError?: (error: string) => void;
}

const STAGE_LABELS: Record<string, string> = {
  uploading: 'Uploading',
  parsing: 'Parsing document',
  chunking: 'Splitting into chunks',
  embedding: 'Generating embeddings',
  indexing: 'Indexing',
  complete: 'Complete',
  failed: 'Failed',
};

const STAGE_ICONS: Record<string, string> = {
  uploading: '📤',
  parsing: '📄',
  chunking: '✂️',
  embedding: '🧮',
  indexing: '💾',
  complete: '✅',
  failed: '❌',
};

export const UploadProgress: React.FC<UploadProgressProps> = ({
  taskId,
  onComplete,
  onError,
}) => {
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  useEffect(() => {
    // Connect to SSE endpoint
    const es = new EventSource(`/api/upload/progress/${taskId}`);

    es.addEventListener('progress', (event) => {
      const update: ProgressUpdate = JSON.parse(event.data);
      setProgress(update);

      // Handle completion
      if (update.stage === 'complete' && onComplete) {
        // Extract document ID from message
        const match = update.message.match(/Document ID: ([a-f0-9-]+)/);
        if (match) {
          onComplete(match[1]);
        }
        es.close();
      }

      // Handle failure
      if (update.stage === 'failed' && onError) {
        onError(update.error || update.message);
        es.close();
      }
    });

    es.onerror = (error) => {
      console.error('SSE connection error:', error);
      if (onError) {
        onError('Connection to server lost');
      }
      es.close();
    };

    setEventSource(es);

    // Cleanup
    return () => {
      es.close();
    };
  }, [taskId, onComplete, onError]);

  if (!progress) {
    return (
      <div className="upload-progress">
        <div className="loading">Initializing...</div>
      </div>
    );
  }

  const progressPercent = Math.round(progress.progress * 100);
  const stageLabel = STAGE_LABELS[progress.stage] || progress.stage;
  const stageIcon = STAGE_ICONS[progress.stage] || '⏳';

  return (
    <div className="upload-progress">
      {/* Stage indicator */}
      <div className="stage-header">
        <span className="stage-icon">{stageIcon}</span>
        <span className="stage-label">{stageLabel}</span>
      </div>

      {/* Progress bar */}
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{
            width: `${progressPercent}%`,
            backgroundColor: progress.stage === 'failed' ? '#f44336' : '#4caf50',
          }}
        />
      </div>

      {/* Progress details */}
      <div className="progress-details">
        <span className="progress-percent">{progressPercent}%</span>
        <span className="progress-message">{progress.message}</span>
      </div>

      {/* Error message */}
      {progress.error && (
        <div className="error-message">
          <strong>Error:</strong> {progress.error}
        </div>
      )}

      {/* Timestamp */}
      <div className="progress-timestamp">
        Updated: {new Date(progress.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
};
```

```css
/* ui/src/components/UploadProgress.css */
.upload-progress {
  padding: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  max-width: 600px;
  margin: 20px auto;
}

.stage-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.stage-icon {
  font-size: 24px;
}

.stage-label {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.progress-bar-container {
  width: 100%;
  height: 24px;
  background-color: #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-bar-fill {
  height: 100%;
  background-color: #4caf50;
  transition: width 0.3s ease;
  border-radius: 12px;
}

.progress-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.progress-percent {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.progress-message {
  font-size: 14px;
  color: #666;
}

.error-message {
  padding: 10px;
  background-color: #ffebee;
  border: 1px solid #f44336;
  border-radius: 4px;
  color: #d32f2f;
  margin-top: 10px;
}

.progress-timestamp {
  font-size: 12px;
  color: #999;
  text-align: right;
  margin-top: 10px;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #666;
}
```

### Acceptance Criteria

- [ ] Upload returns task_id and progress URLs immediately
- [ ] SSE endpoint streams real-time progress updates
- [ ] Progress tracked through all stages (parsing, chunking, embedding, indexing)
- [ ] Web UI displays progress bar with percentage
- [ ] Stage-by-stage labels and icons shown in UI
- [ ] Errors displayed clearly with error messages
- [ ] Progress continues during long operations (50MB files, 30+ seconds)
- [ ] Multiple simultaneous uploads tracked independently
- [ ] Polling endpoint available as SSE fallback
- [ ] Progress tasks cleaned up after 5 minutes
- [ ] UI responsive and updates smoothly
- [ ] No memory leaks with long-running uploads

### Files to Create/Modify

1. `src/api/progress.py` (new)
2. `src/api/routes/documents.py` (modify - add progress endpoints)
3. `ui/src/components/UploadProgress.tsx` (new)
4. `ui/src/components/UploadProgress.css` (new)
5. `ui/src/pages/Upload.tsx` (modify - integrate progress component)
6. `requirements.txt` (add `sse-starlette`)
7. `package.json` (ensure TypeScript types for SSE)
8. `docs/api.md` (update with progress endpoints)
9. `tests/test_upload_progress.py` (new)

---

## US 8.2: End-to-End Test Suite

**Status:** 🔲 Not Started

### Description

Create comprehensive end-to-end tests that validate the complete system functionality through nominal use cases, from document upload to query responses, in both English and French.

### Context

Current testing gaps:

- Unit tests exist for individual components
- No end-to-end validation of full workflows
- Manual testing required for each release
- Risk of integration bugs between components
- No automated multilingual validation

Need automated E2E tests for:

- Complete document ingestion pipeline
- Query processing with citations (EN/FR)
- Risk analysis workflow
- Document summarization
- Document comparison
- Guardrails validation
- Error handling scenarios
- Upload progress tracking

### Test Scenarios

#### Scenario 1: Happy Path - English Document

1. Upload English contract (PDF)
2. Wait for ingestion to complete
3. Query the document
4. Verify answer quality and citations
5. Check confidence levels

#### Scenario 2: Happy Path - French Document

1. Upload French contract (PDF)
2. Query in French
3. Verify French response quality
4. Check citation accuracy

#### Scenario 3: Multi-Document Workflow

1. Upload multiple contracts
2. Query each document separately
3. Compare two documents
4. Verify differences identified

#### Scenario 4: Risk Analysis & Summarization

1. Upload contract
2. Request risk analysis
3. Request summary (executive and detailed)
4. Verify output quality

#### Scenario 5: Guardrails Validation

1. Submit prompt injection attempt
2. Verify rejection
3. Query about non-existent info
4. Verify refusal to hallucinate
5. Check PII redaction

#### Scenario 6: Error Handling

1. Upload invalid file format
2. Query non-existent document
3. Submit malformed requests
4. Verify appropriate error responses

#### Scenario 7: Upload Progress

1. Upload large document
2. Connect to progress stream
3. Verify all stages reported
4. Verify completion notification

### Tasks

- [ ] Create `tests/e2e/` directory structure
- [ ] Set up test fixtures:
  - `tests/e2e/fixtures/` - Sample documents (EN, FR)
  - `tests/e2e/conftest.py` - Pytest fixtures
  - Test helper utilities
- [ ] Create scenario tests:
  - `tests/e2e/test_upload_query.py` - Document upload and query
  - `tests/e2e/test_multilingual.py` - French document processing
  - `tests/e2e/test_analysis.py` - Risk analysis and summarization
  - `tests/e2e/test_comparison.py` - Document comparison
  - `tests/e2e/test_guardrails.py` - Guardrails validation
  - `tests/e2e/test_error_handling.py` - Error scenarios
  - `tests/e2e/test_upload_progress.py` - Progress tracking
- [ ] Create test utilities:
  - `tests/e2e/utils.py` - Helper functions
  - Test data generators
  - Response validators
- [ ] Add CI integration:
  - `.github/workflows/e2e-tests.yml` - GitHub Actions
  - Docker Compose setup for CI
  - Test result reporting
- [ ] Create E2E test documentation:
  - `docs/testing.md` - E2E testing guide
  - Document test scenarios
  - Instructions for running locally

### Test Implementation

```python
# tests/e2e/conftest.py
"""Pytest fixtures for E2E tests."""
import asyncio
import pytest
import httpx
from pathlib import Path
from typing import AsyncGenerator

from src.api.main import app
from src.config import get_settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture(scope="session")
def test_data_dir():
    """Get test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API."""
    async with httpx.AsyncClient(
        app=app,
        base_url="http://test",
        timeout=120.0  # Long timeout for E2E tests
    ) as client:
        yield client


@pytest.fixture
async def sample_contract_en(api_client, test_data_dir):
    """Upload sample English contract and return document ID."""
    file_path = test_data_dir / "sample_contract_en.pdf"

    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()

    # Wait for processing to complete
    task_id = data["task_id"]
    await wait_for_upload_completion(api_client, task_id)

    # Extract document ID
    status = await api_client.get(f"/upload/status/{task_id}")
    status_data = status.json()

    # Parse document ID from message
    import re
    match = re.search(r"Document ID: ([a-f0-9-]+)", status_data["message"])
    assert match, "Could not extract document ID"

    return match.group(1)


@pytest.fixture
async def sample_contract_fr(api_client, test_data_dir):
    """Upload sample French contract and return document ID."""
    file_path = test_data_dir / "sample_contract_fr.pdf"

    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()

    # Wait for processing
    task_id = data["task_id"]
    await wait_for_upload_completion(api_client, task_id)

    # Extract document ID
    status = await api_client.get(f"/upload/status/{task_id}")
    status_data = status.json()

    import re
    match = re.search(r"Document ID: ([a-f0-9-]+)", status_data["message"])
    assert match

    return match.group(1)


async def wait_for_upload_completion(
    client: httpx.AsyncClient,
    task_id: str,
    timeout: int = 120
) -> None:
    """Wait for upload to complete by polling status.

    Args:
        client: HTTP client
        task_id: Upload task ID
        timeout: Maximum wait time in seconds
    """
    import time
    start = time.time()

    while time.time() - start < timeout:
        response = await client.get(f"/upload/status/{task_id}")
        data = response.json()

        if data["stage"] == "complete":
            return
        elif data["stage"] == "failed":
            raise RuntimeError(f"Upload failed: {data.get('error')}")

        await asyncio.sleep(1)

    raise TimeoutError(f"Upload did not complete within {timeout}s")
```

```python
# tests/e2e/test_upload_query.py
"""End-to-end tests for document upload and query."""
import pytest


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_query_english(api_client, sample_contract_en):
    """Test complete workflow: upload English document and query it."""
    doc_id = sample_contract_en

    # Query the document
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "What is the termination notice period?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "answer" in data
    assert "confidence" in data
    assert "citation_chunks" in data

    # Verify answer quality
    assert len(data["answer"]) > 0
    assert data["confidence"] in ["low", "medium", "high"]
    assert len(data["citation_chunks"]) > 0

    # Verify citations have required fields
    for citation in data["citation_chunks"]:
        assert "content" in citation
        assert "page" in citation
        assert "score" in citation
        assert citation["score"] >= 0.7  # Above threshold


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_summarize(api_client, sample_contract_en):
    """Test document summarization."""
    doc_id = sample_contract_en

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert len(data["summary"]) > 100  # Substantial summary
    assert "key_points" in data
    assert len(data["key_points"]) >= 3


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risk_analysis(api_client, sample_contract_en):
    """Test risk analysis functionality."""
    doc_id = sample_contract_en

    response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    assert response.status_code == 200
    data = response.json()

    assert "risks" in data
    assert isinstance(data["risks"], list)

    if len(data["risks"]) > 0:
        for risk in data["risks"]:
            assert "category" in risk
            assert "severity" in risk
            assert "description" in risk
            assert risk["severity"] in ["low", "medium", "high", "critical"]
```

```python
# tests/e2e/test_multilingual.py
"""End-to-end tests for multilingual support."""
import pytest


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_document_upload_and_query(api_client, sample_contract_fr):
    """Test French document processing end-to-end."""
    doc_id = sample_contract_fr

    # Query in French
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "Quelle est la période de préavis de résiliation?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response
    assert data["answer"]
    assert len(data["citation_chunks"]) > 0

    # Response should be in French (basic check)
    # Look for French articles or common words
    answer_lower = data["answer"].lower()
    french_indicators = ["le", "la", "de", "et", "est", "des", "les"]
    assert any(word in answer_lower for word in french_indicators)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_cross_language_quality(
    api_client,
    sample_contract_en,
    sample_contract_fr
):
    """Verify both English and French documents work well."""

    # English query
    en_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_en,
            "question": "What are the payment terms?"
        }
    )

    # French query
    fr_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_fr,
            "question": "Quelles sont les conditions de paiement?"
        }
    )

    # Both should succeed
    assert en_response.status_code == 200
    assert fr_response.status_code == 200

    # Both should have citations
    assert len(en_response.json()["citation_chunks"]) > 0
    assert len(fr_response.json()["citation_chunks"]) > 0

    # Both should have reasonable confidence
    assert en_response.json()["confidence"] in ["medium", "high"]
    assert fr_response.json()["confidence"] in ["medium", "high"]
```

```python
# tests/e2e/test_upload_progress.py
"""End-to-end tests for upload progress tracking."""
import pytest
import asyncio
import json


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_progress_tracking(api_client, test_data_dir):
    """Test that upload progress is tracked correctly."""
    file_path = test_data_dir / "sample_contract_en.pdf"

    # Start upload
    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()
    task_id = data["task_id"]

    # Track progress
    stages_seen = set()
    final_stage = None

    # Poll status endpoint
    for _ in range(60):  # Max 60 seconds
        status_response = await api_client.get(f"/upload/status/{task_id}")
        status_data = status_response.json()

        stage = status_data["stage"]
        stages_seen.add(stage)

        if stage in ["complete", "failed"]:
            final_stage = stage
            break

        await asyncio.sleep(1)

    # Verify we saw multiple stages
    expected_stages = {"parsing", "chunking", "embedding", "indexing"}
    assert stages_seen & expected_stages, f"Expected to see stages, got: {stages_seen}"

    # Verify completion
    assert final_stage == "complete", f"Upload should complete, got: {final_stage}"
```

### CI Integration

```yaml
# .github/workflows/e2e-tests.yml
name: End-to-End Tests

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

      ollama:
        image: ollama/ollama:latest
        ports:
          - 11434:11434

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Cache Python dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Wait for services
        run: |
          sleep 10

      - name: Pull Ollama model
        run: |
          docker exec $(docker ps -q -f "ancestor=ollama/ollama:latest") \
            ollama pull mistral:7b-instruct

      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v -m e2e --maxfail=5 --tb=short
        env:
          LEXARD_QDRANT__HOST: localhost
          LEXARD_QDRANT__PORT: 6333
          LEXARD_LLM__BASE_URL: http://localhost:11434
          LEXARD_EMBEDDINGS__MODEL_NAME: intfloat/multilingual-e5-base

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-test-results
          path: |
            test-results/
            pytest-report.html

      - name: Generate test report
        if: always()
        run: |
          pytest tests/e2e/ --html=pytest-report.html --self-contained-html
```

### Acceptance Criteria

- [ ] E2E test suite covers all nominal use cases
- [ ] English document upload and query tested
- [ ] French document upload and query tested
- [ ] Risk analysis workflow tested
- [ ] Document summarization tested
- [ ] Document comparison tested
- [ ] Upload progress tracking tested
- [ ] Guardrails validation tested (injection, hallucination, PII)
- [ ] Error handling tested (invalid files, missing documents)
- [ ] All tests pass on clean system
- [ ] Tests run in CI pipeline
- [ ] Test execution time < 10 minutes
- [ ] Test documentation complete
- [ ] Sample test fixtures provided
- [ ] Test coverage > 80% for E2E scenarios

### Files to Create

1. `tests/e2e/__init__.py`
2. `tests/e2e/conftest.py`
3. `tests/e2e/test_upload_query.py`
4. `tests/e2e/test_multilingual.py`
5. `tests/e2e/test_analysis.py`
6. `tests/e2e/test_comparison.py`
7. `tests/e2e/test_guardrails.py`
8. `tests/e2e/test_error_handling.py`
9. `tests/e2e/test_upload_progress.py`
10. `tests/e2e/utils.py`
11. `tests/e2e/fixtures/sample_contract_en.pdf`
12. `tests/e2e/fixtures/sample_contract_fr.pdf`
13. `tests/e2e/fixtures/contract_with_pii.pdf`
14. `tests/e2e/fixtures/invalid.exe`
15. `.github/workflows/e2e-tests.yml`
16. `docs/testing.md`
17. `pytest.ini` (configure E2E markers)

---

## Definition of Done (Epic 8)

- [ ] Both User Stories completed
- [ ] Upload progress tracked and displayed in real-time
- [ ] E2E test suite covers all nominal use cases (EN/FR)
- [ ] All E2E tests pass in CI
- [ ] Documentation updated
- [ ] No performance regressions
- [ ] System validated end-to-end
- [ ] Ready for production deployment
