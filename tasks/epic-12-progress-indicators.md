# Epic 12: Multi-Stage Progress Indicators

## Overview

Implement multi-stage progress indicators for LLM operations (query, summarize, risk analysis) to improve user experience during long-running operations. Instead of a generic spinner, users see discrete progress stages with real-time updates, making the wait feel shorter and more informative while preserving all guardrails.

## Problem Statement

Current behavior:
```
User asks question -> [Spinner "Loading..."] for 5-15 seconds -> Complete response
```

Target behavior:
```
User asks question -> Step 1: Finding relevant sections... [0.3s] ✓
                   -> Step 2: Building context... [0.1s] ✓
                   -> Step 3: Generating answer... [spinner]
                   -> Step 4: Validating response... [0.2s] ✓
                   -> Complete response with full guardrails
```

**User Impact**:
- Current: User stares at spinner, uncertain if system is working
- Target: User sees real progress through discrete stages, feels informed

## Why Not Streaming?

Streaming LLM responses would bypass guardrails that require full response text:
- Hallucination detection needs complete answer
- PII redaction patterns need full text
- Citation validation needs final response

**This epic prioritizes guardrails over perceived latency** while still dramatically improving UX through honest progress feedback.

## Prerequisites

- Epic 9 (Multilingual Fix) completed
- Epic 10 (Test Suite Review) completed
- Epic 11 (Document Preview) completed
- SSE infrastructure exists (upload progress) - will reuse pattern

## Technical Approach

### SSE Progress Events

Reuse the existing SSE pattern from upload progress:

```python
# Event types
{
    "stage": "retrieving" | "building_context" | "generating" | "validating" | "complete" | "failed",
    "progress": 0.0-1.0,
    "message": "Human-readable status",
    "timestamp": "ISO8601"
}
```

### Stage Breakdown

| Stage | Duration | Predictable | Progress |
|-------|----------|-------------|----------|
| Retrieving chunks | 0.2-0.5s | Yes | 0-25% |
| Building context | 0.1-0.2s | Yes | 25-35% |
| Generating (LLM) | 3-15s | No | 35-90% (animated) |
| Validating | 0.1-0.3s | Yes | 90-100% |

The "Generating" stage uses an animated progress bar (indeterminate or slow-moving) since LLM duration is unpredictable.

## User Stories

---

## US 12.1: Backend Progress Event Infrastructure

**Status:** ✅ Completed

### Description

Create a reusable progress event system for long-running operations, following the pattern established for upload progress but generalized for any operation type.

### Context

The upload progress system uses SSE to track file processing stages. We need a similar but more generic system for LLM operations that:
1. Tracks discrete stages
2. Emits SSE events
3. Handles errors gracefully
4. Supports cancellation

### Tasks

- [ ] Create `OperationProgress` dataclass in `src/api/progress.py`:
  - `operation_id: str` - UUID for tracking
  - `operation_type: str` - "query" | "summarize" | "risks"
  - `stage: str` - Current stage name
  - `progress: float` - 0.0 to 1.0
  - `message: str` - Human-readable status
  - `timestamp: datetime` - When event occurred
  - `error: str | None` - Error message if failed
- [ ] Create `ProgressTracker` class:
  - `start(operation_type)` -> operation_id
  - `update(operation_id, stage, progress, message)`
  - `complete(operation_id, result)`
  - `fail(operation_id, error)`
  - `subscribe(operation_id)` -> AsyncGenerator for SSE
- [ ] Add in-memory storage for active operations (with TTL cleanup)
- [ ] Create `/operations/{operation_id}/progress` SSE endpoint
- [ ] Add unit tests for progress tracking

### Implementation Details

#### OperationProgress Dataclass

```python
# src/api/progress.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import json
import asyncio
from uuid import uuid4


class OperationStage(str, Enum):
    """Stages for LLM operations."""
    PENDING = "pending"
    RETRIEVING = "retrieving"
    BUILDING_CONTEXT = "building_context"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class OperationProgress:
    """Progress state for a long-running operation."""
    operation_id: str
    operation_type: str
    stage: OperationStage
    progress: float
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None
    result: Any = None

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        data = {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "stage": self.stage.value,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.error:
            data["error"] = self.error
        return f"event: progress\ndata: {json.dumps(data)}\n\n"
```

#### ProgressTracker Class

```python
# src/api/progress.py (continued)

class ProgressTracker:
    """Track and broadcast progress for long-running operations."""

    def __init__(self):
        self._operations: dict[str, OperationProgress] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def start(self, operation_type: str) -> str:
        """Start tracking a new operation."""
        operation_id = str(uuid4())
        progress = OperationProgress(
            operation_id=operation_id,
            operation_type=operation_type,
            stage=OperationStage.PENDING,
            progress=0.0,
            message="Starting...",
        )
        async with self._lock:
            self._operations[operation_id] = progress
            self._subscribers[operation_id] = []
        return operation_id

    async def update(
        self,
        operation_id: str,
        stage: OperationStage,
        progress: float,
        message: str,
    ) -> None:
        """Update operation progress and notify subscribers."""
        async with self._lock:
            if operation_id not in self._operations:
                return
            op = self._operations[operation_id]
            op.stage = stage
            op.progress = progress
            op.message = message
            op.timestamp = datetime.utcnow()

            # Notify all subscribers
            for queue in self._subscribers.get(operation_id, []):
                await queue.put(op)

    async def complete(self, operation_id: str, result: Any = None) -> None:
        """Mark operation as complete."""
        await self.update(
            operation_id,
            OperationStage.COMPLETE,
            1.0,
            "Complete",
        )
        async with self._lock:
            if operation_id in self._operations:
                self._operations[operation_id].result = result

    async def fail(self, operation_id: str, error: str) -> None:
        """Mark operation as failed."""
        async with self._lock:
            if operation_id not in self._operations:
                return
            op = self._operations[operation_id]
            op.stage = OperationStage.FAILED
            op.progress = op.progress  # Keep current progress
            op.message = "Failed"
            op.error = error
            op.timestamp = datetime.utcnow()

            for queue in self._subscribers.get(operation_id, []):
                await queue.put(op)

    async def subscribe(self, operation_id: str) -> asyncio.Queue:
        """Subscribe to progress updates for an operation."""
        queue = asyncio.Queue()
        async with self._lock:
            if operation_id in self._subscribers:
                self._subscribers[operation_id].append(queue)
                # Send current state immediately
                if operation_id in self._operations:
                    await queue.put(self._operations[operation_id])
        return queue

    async def unsubscribe(self, operation_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from progress updates."""
        async with self._lock:
            if operation_id in self._subscribers:
                try:
                    self._subscribers[operation_id].remove(queue)
                except ValueError:
                    pass


# Global instance
_progress_tracker: ProgressTracker | None = None


def get_progress_tracker() -> ProgressTracker:
    """Get or create global progress tracker."""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker
```

### Acceptance Criteria

- [ ] `OperationProgress` dataclass stores all progress state
- [ ] `ProgressTracker` manages multiple concurrent operations
- [ ] SSE endpoint streams progress events
- [ ] Subscribers receive updates in real-time
- [ ] Operations are cleaned up after completion (TTL)
- [ ] Unit tests pass for progress tracking
- [ ] Thread-safe for concurrent operations

### Tests

- **New:** `tests/test_progress.py` - Test progress tracker
- **Run:** `pytest tests/test_progress.py -v`

### Files to Create/Modify

1. `src/api/progress.py` - New progress tracking module
2. `src/api/routes/operations.py` - New SSE endpoint for progress
3. `src/api/main.py` - Register new router
4. `tests/test_progress.py` - Unit tests

---

## US 12.2: Progress-Aware RAG Pipeline

**Status:** ✅ Completed

### Description

Modify the RAG pipeline to emit progress events during query execution, allowing the UI to show which stage is currently active.

### Context

The RAG pipeline has distinct stages:
1. **Retrieval** - Find relevant chunks (fast, predictable)
2. **Context Building** - Assemble context (fast, predictable)
3. **LLM Generation** - Generate answer (slow, unpredictable)
4. **Validation** - Run guardrails (fast, predictable)

Each stage should emit progress events so the UI can show real progress.

### Tasks

- [ ] Add optional `progress_tracker` and `operation_id` parameters to `RAGPipeline.query()`
- [ ] Emit progress events at each stage:
  - "retrieving" (0-25%)
  - "building_context" (25-35%)
  - "generating" (35-90%)
  - "validating" (90-100%)
- [ ] Handle errors at each stage with appropriate progress events
- [ ] Add `query_with_progress()` method that creates operation and tracks progress
- [ ] Ensure backward compatibility (progress tracking is optional)
- [ ] Add unit tests for progress emission

### Implementation Details

```python
# src/rag/pipeline.py (modifications)

from src.api.progress import ProgressTracker, OperationStage, get_progress_tracker


class RAGPipeline:
    async def query_with_progress(
        self,
        question: str,
        document_id: str | None = None,
    ) -> tuple[str, RAGResult]:
        """Execute RAG query with progress tracking.

        Returns:
            Tuple of (operation_id, result) for progress subscription.
        """
        tracker = get_progress_tracker()
        operation_id = await tracker.start("query")

        try:
            result = await self._query_with_events(
                question=question,
                document_id=document_id,
                tracker=tracker,
                operation_id=operation_id,
            )
            await tracker.complete(operation_id, result)
            return operation_id, result
        except Exception as e:
            await tracker.fail(operation_id, str(e))
            raise

    async def _query_with_events(
        self,
        question: str,
        document_id: str | None,
        tracker: ProgressTracker,
        operation_id: str,
    ) -> RAGResult:
        """Internal query with progress events."""
        # Stage 1: Retrieval (0-25%)
        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.1,
            "Finding relevant sections...",
        )

        chunks = self.retriever.retrieve(question, document_id)

        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.25,
            f"Found {len(chunks)} relevant sections",
        )

        if not chunks:
            # Return early with no-results response
            return RAGResult(
                answer="I could not find relevant information...",
                citation_chunks=[],
                confidence=Confidence.LOW,
                language="en",
            )

        # Stage 2: Context Building (25-35%)
        await tracker.update(
            operation_id,
            OperationStage.BUILDING_CONTEXT,
            0.30,
            "Building context from sections...",
        )

        context = self.context_builder.build(chunks)
        language = detect_language_from_chunks(chunks)

        await tracker.update(
            operation_id,
            OperationStage.BUILDING_CONTEXT,
            0.35,
            f"Context ready ({language.upper()})",
        )

        # Stage 3: LLM Generation (35-90%)
        await tracker.update(
            operation_id,
            OperationStage.GENERATING,
            0.40,
            "Generating answer...",
        )

        prompt = build_qa_prompt(question, context.context_text, language=language)
        system_prompt = get_qa_system_prompt(language=language)

        # LLM call - this is the slow part
        llm_response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        await tracker.update(
            operation_id,
            OperationStage.GENERATING,
            0.85,
            "Answer generated",
        )

        # Stage 4: Validation (90-100%)
        await tracker.update(
            operation_id,
            OperationStage.VALIDATING,
            0.90,
            "Validating response...",
        )

        # Run guardrails
        validated_answer = self._validate_response(llm_response.text)

        await tracker.update(
            operation_id,
            OperationStage.VALIDATING,
            0.95,
            "Building citations...",
        )

        # Build final result
        confidence = self._calculate_confidence(chunks)
        citation_chunks = self._build_citation_chunks(chunks, context)

        return RAGResult(
            answer=validated_answer,
            citation_chunks=citation_chunks,
            confidence=confidence,
            language=language,
        )
```

### Acceptance Criteria

- [ ] `query_with_progress()` returns operation_id for tracking
- [ ] Progress events emitted at each stage
- [ ] Stage names and percentages match spec
- [ ] Errors at any stage emit fail event
- [ ] Backward compatible - existing `query()` still works
- [ ] Unit tests pass

### Tests

- **Modified:** `tests/test_pipeline.py` - Add progress tracking tests
- **Run:** `pytest tests/test_pipeline.py -v -k progress`

### Files to Modify

1. `src/rag/pipeline.py` - Add progress-aware query methods
2. `tests/test_pipeline.py` - Add tests for progress events

---

## US 12.3: Progress-Aware API Endpoints

**Status:** ✅ Completed

### Description

Create new API endpoints that return an operation ID immediately and allow progress tracking via SSE, plus update agent tools (Summarizer, RiskDetector) to support progress tracking.

### Context

New endpoint pattern:
1. `POST /query` - Returns `{ operation_id, ... }` immediately after starting
2. `GET /operations/{operation_id}/progress` - SSE stream of progress events
3. `GET /operations/{operation_id}/result` - Get final result (when complete)

This is similar to how upload works but for LLM operations.

### Tasks

#### API Endpoints

- [ ] Modify `/query` endpoint to use progress-aware pipeline:
  - Start operation, return operation_id immediately
  - Background task continues processing
  - Return operation_id in response
- [ ] Create `/operations/{operation_id}/progress` SSE endpoint:
  - Stream progress events
  - Handle client disconnection
  - Close stream on complete/fail
- [ ] Create `/operations/{operation_id}/result` endpoint:
  - Return cached result if complete
  - Return 202 Accepted if still processing
  - Return error details if failed
- [ ] Modify `/summarize` endpoint similarly
- [ ] Modify `/risks` endpoint similarly
- [ ] Document new endpoints in OpenAPI schema

#### Agent Tools

- [ ] Add `summarize_with_progress()` to SummarizerTool:
  - Emit progress for each chunk processed
  - Emit progress for aggregation
  - Track validation stage
- [ ] Add `analyze_with_progress()` to RiskDetectorTool:
  - Emit progress for document loading
  - Emit progress for risk identification
  - Track validation stage
- [ ] Ensure language detection still works with progress

### Implementation Details

#### Modified Query Endpoint

```python
# src/api/routes/query.py

from fastapi import BackgroundTasks
from src.api.progress import get_progress_tracker


@router.post("/query", response_model=QueryResponse)
async def query_document(
    query: QueryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> QueryResponse:
    """Query a document using RAG with progress tracking."""
    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists (fast check)
    registry = get_document_registry()
    doc = registry.get(query.document_id)

    if not doc:
        raise HTTPException(status_code=404, ...)

    if doc.status != "processed":
        raise HTTPException(status_code=400, ...)

    # Start operation and get ID
    tracker = get_progress_tracker()
    operation_id = await tracker.start("query")

    # Start background processing
    background_tasks.add_task(
        execute_query_with_progress,
        operation_id=operation_id,
        question=query.question,
        document_id=query.document_id,
    )

    # Return operation ID immediately
    # Client should poll /operations/{operation_id}/progress
    return QueryResponse(
        operation_id=operation_id,
        status="processing",
        message="Query started. Subscribe to progress for updates.",
    )


async def execute_query_with_progress(
    operation_id: str,
    question: str,
    document_id: str,
) -> None:
    """Background task to execute query with progress tracking."""
    tracker = get_progress_tracker()
    pipeline = get_rag_pipeline()

    try:
        # Use the progress-aware query
        await pipeline._query_with_events(
            question=question,
            document_id=document_id,
            tracker=tracker,
            operation_id=operation_id,
        )
    except Exception as e:
        await tracker.fail(operation_id, str(e))
```

#### Progress SSE Endpoint

```python
# src/api/routes/operations.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from src.api.progress import get_progress_tracker, OperationStage

router = APIRouter(tags=["operations"])


@router.get("/operations/{operation_id}/progress")
async def get_operation_progress(operation_id: str) -> StreamingResponse:
    """Stream progress updates for an operation via SSE."""
    tracker = get_progress_tracker()

    async def event_stream():
        queue = await tracker.subscribe(operation_id)
        try:
            while True:
                progress = await queue.get()
                yield progress.to_sse()

                # Stop streaming on terminal states
                if progress.stage in (OperationStage.COMPLETE, OperationStage.FAILED):
                    break
        finally:
            await tracker.unsubscribe(operation_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/operations/{operation_id}/result")
async def get_operation_result(operation_id: str):
    """Get the result of a completed operation."""
    tracker = get_progress_tracker()
    operation = tracker.get(operation_id)

    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    if operation.stage == OperationStage.COMPLETE:
        return {"status": "complete", "result": operation.result}
    elif operation.stage == OperationStage.FAILED:
        return {"status": "failed", "error": operation.error}
    else:
        return {"status": "processing", "stage": operation.stage.value}
```

### Acceptance Criteria

#### API Endpoints
- [ ] `/query` returns operation_id immediately
- [ ] `/operations/{id}/progress` streams SSE events
- [ ] `/operations/{id}/result` returns final result
- [ ] `/summarize` supports progress tracking
- [ ] `/risks` supports progress tracking
- [ ] All endpoints documented in OpenAPI
- [ ] Backward compatibility maintained (non-progress endpoints still work)

#### Agent Tools
- [ ] SummarizerTool emits progress per chunk
- [ ] RiskDetectorTool emits progress during analysis
- [ ] Language detection preserved
- [ ] All guardrails still run

### Tests

- **New:** `tests/test_progress_endpoints.py` - Test SSE progress streaming
- **Modified:** `tests/test_summarizer.py` - Add progress tests
- **Modified:** `tests/test_risk_detector.py` - Add progress tests
- **Run:** `pytest tests/test_progress_endpoints.py tests/test_summarizer.py tests/test_risk_detector.py -v -k progress`

### Files to Create/Modify

1. `src/api/routes/query.py` - Modify for progress tracking
2. `src/api/routes/analysis.py` - Modify summarize/risks for progress
3. `src/api/routes/operations.py` - New operations router
4. `src/api/main.py` - Register operations router
5. `src/agent/tools/summarizer.py` - Add `summarize_with_progress()`
6. `src/agent/tools/risk_detector.py` - Add `analyze_with_progress()`
7. `tests/test_progress_endpoints.py` - New endpoint tests
8. `tests/test_summarizer.py` - Add progress tests
9. `tests/test_risk_detector.py` - Add progress tests

---

## US 12.4: Web UI Progress Display

**Status:** 🔲 Not Started

### Description

Update the Web UI to display multi-stage progress for query, summarize, and risk analysis operations instead of a generic spinner.

### Context

The UI already has SSE handling for upload progress. We'll use the same pattern for LLM operations, showing discrete stages with visual progress indicators.

### Tasks

- [ ] Create `showOperationProgress(operationId, operationType)` function:
  - Connect to SSE endpoint
  - Render stage-based progress UI
  - Handle all stage transitions
  - Show completion/error states
- [ ] Update `askQuestion()` to use progress display:
  - Start operation via POST
  - Subscribe to progress SSE
  - Show staged progress UI
  - Display final result on complete
- [ ] Update `summarizeDocument()` similarly
- [ ] Update `analyzeRisks()` similarly
- [ ] Add CSS for progress stages:
  - Stage icons (checkmark, spinner, pending)
  - Progress bar (determinate for known stages, animated for LLM)
  - Stage labels with timestamps
- [ ] Handle SSE connection errors gracefully
- [ ] Add cancel button (optional - nice to have)

### Implementation Details

#### Progress UI HTML Structure

```html
<!-- Progress stages template -->
<div class="operation-progress" id="operation-progress">
    <div class="progress-stages">
        <div class="stage" data-stage="retrieving">
            <span class="stage-icon">○</span>
            <span class="stage-label">Finding relevant sections</span>
            <span class="stage-time"></span>
        </div>
        <div class="stage" data-stage="building_context">
            <span class="stage-icon">○</span>
            <span class="stage-label">Building context</span>
            <span class="stage-time"></span>
        </div>
        <div class="stage" data-stage="generating">
            <span class="stage-icon">○</span>
            <span class="stage-label">Generating answer</span>
            <span class="stage-time"></span>
        </div>
        <div class="stage" data-stage="validating">
            <span class="stage-icon">○</span>
            <span class="stage-label">Validating response</span>
            <span class="stage-time"></span>
        </div>
    </div>
    <div class="progress-bar-container">
        <div class="progress-bar-fill" style="width: 0%"></div>
    </div>
    <div class="progress-message">Starting...</div>
</div>
```

#### JavaScript Implementation

```javascript
// ui/index.html (additions)

const STAGE_CONFIG = {
    query: {
        stages: ['retrieving', 'building_context', 'generating', 'validating'],
        labels: {
            retrieving: 'Finding relevant sections',
            building_context: 'Building context',
            generating: 'Generating answer',
            validating: 'Validating response',
        }
    },
    summarize: {
        stages: ['loading', 'processing_chunks', 'aggregating', 'validating'],
        labels: {
            loading: 'Loading document',
            processing_chunks: 'Processing sections',
            aggregating: 'Creating summary',
            validating: 'Validating response',
        }
    },
    risks: {
        stages: ['loading', 'analyzing', 'evaluating', 'validating'],
        labels: {
            loading: 'Loading document',
            analyzing: 'Analyzing clauses',
            evaluating: 'Evaluating risks',
            validating: 'Validating response',
        }
    }
};

function showOperationProgress(container, operationType) {
    const config = STAGE_CONFIG[operationType];
    const stagesHtml = config.stages.map(stage => `
        <div class="stage" data-stage="${stage}">
            <span class="stage-icon pending">○</span>
            <span class="stage-label">${config.labels[stage]}</span>
            <span class="stage-time"></span>
        </div>
    `).join('');

    container.innerHTML = `
        <div class="operation-progress">
            <div class="progress-stages">${stagesHtml}</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
            <div class="progress-message">Starting...</div>
        </div>
    `;
}

function updateProgressUI(container, progressData) {
    const progressBar = container.querySelector('.progress-bar-fill');
    const message = container.querySelector('.progress-message');
    const stages = container.querySelectorAll('.stage');

    // Update progress bar
    progressBar.style.width = `${Math.round(progressData.progress * 100)}%`;

    // Add animation class for LLM generation stage
    if (progressData.stage === 'generating') {
        progressBar.classList.add('animated');
    } else {
        progressBar.classList.remove('animated');
    }

    // Update message
    message.textContent = progressData.message;

    // Update stage icons
    const stageOrder = ['retrieving', 'building_context', 'generating', 'validating'];
    const currentIndex = stageOrder.indexOf(progressData.stage);

    stages.forEach((stageEl, index) => {
        const icon = stageEl.querySelector('.stage-icon');
        const stageName = stageEl.dataset.stage;
        const stageIndex = stageOrder.indexOf(stageName);

        if (stageIndex < currentIndex) {
            // Completed
            icon.className = 'stage-icon complete';
            icon.textContent = '✓';
        } else if (stageIndex === currentIndex) {
            // Current
            icon.className = 'stage-icon active';
            icon.innerHTML = '<span class="mini-spinner"></span>';
        } else {
            // Pending
            icon.className = 'stage-icon pending';
            icon.textContent = '○';
        }
    });
}

async function askQuestion() {
    if (!selectedDocumentId) {
        alert('Please select a document first');
        return;
    }

    const question = document.getElementById('question').value.trim();
    if (!question) {
        alert('Please enter a question');
        return;
    }

    const resultBox = document.getElementById('query-result');

    // Show progress UI
    showOperationProgress(resultBox, 'query');

    try {
        // Start the query operation
        const response = await fetch('/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document_id: selectedDocumentId,
                question: question
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error?.message || 'Query failed');
        }

        const data = await response.json();

        // If operation_id present, track progress via SSE
        if (data.operation_id) {
            await trackOperationProgress(data.operation_id, resultBox, renderAnswer);
        } else {
            // Fallback: direct result (backward compatibility)
            renderAnswer(data);
        }
    } catch (error) {
        showError(resultBox, error.message);
    }
}

async function trackOperationProgress(operationId, container, renderResult) {
    return new Promise((resolve, reject) => {
        const eventSource = new EventSource(`/operations/${operationId}/progress`);

        eventSource.addEventListener('progress', (event) => {
            const progress = JSON.parse(event.data);
            updateProgressUI(container, progress);

            if (progress.stage === 'complete') {
                eventSource.close();
                // Fetch final result
                fetch(`/operations/${operationId}/result`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.status === 'complete') {
                            renderResult(data.result);
                            resolve(data.result);
                        } else {
                            throw new Error(data.error || 'Operation failed');
                        }
                    })
                    .catch(reject);
            }

            if (progress.stage === 'failed') {
                eventSource.close();
                showError(container, progress.error || 'Operation failed');
                reject(new Error(progress.error));
            }
        });

        eventSource.onerror = () => {
            eventSource.close();
            reject(new Error('Connection lost'));
        };
    });
}
```

#### CSS for Progress Stages

```css
/* Operation progress styles */
.operation-progress {
    padding: 1.5rem;
}

.progress-stages {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.stage {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.875rem;
}

.stage-icon {
    width: 1.5rem;
    height: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: 0.875rem;
}

.stage-icon.pending {
    color: #94a3b8;
}

.stage-icon.active {
    color: #2563eb;
}

.stage-icon.complete {
    background: #10b981;
    color: white;
}

.stage-label {
    flex: 1;
    color: #475569;
}

.stage.active .stage-label {
    color: #1e293b;
    font-weight: 500;
}

.stage-time {
    font-size: 0.75rem;
    color: #94a3b8;
}

.mini-spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid #e2e8f0;
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

/* Animated progress bar for LLM generation */
.progress-bar-fill.animated {
    background: linear-gradient(
        90deg,
        #2563eb 0%,
        #60a5fa 50%,
        #2563eb 100%
    );
    background-size: 200% 100%;
    animation: shimmer 2s ease-in-out infinite;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

.progress-message {
    font-size: 0.875rem;
    color: #64748b;
    margin-top: 0.5rem;
}
```

### Acceptance Criteria

- [ ] Query shows 4-stage progress (retrieve, context, generate, validate)
- [ ] Summarize shows progress per chunk + aggregation
- [ ] Risk analysis shows staged progress
- [ ] Completed stages show checkmark
- [ ] Current stage shows spinner
- [ ] LLM generation stage uses animated progress bar
- [ ] Final result renders correctly after completion
- [ ] Errors display clearly with stage where failure occurred
- [ ] SSE disconnection handled gracefully
- [ ] Works alongside existing upload progress (no conflicts)

### Tests

- **None:** UI-only changes (no Python backend tests)
- **Manual:** Test progress display in browser
- **Run:** Manual browser testing with real queries

### Files to Modify

1. `ui/index.html` - Add progress UI JavaScript and CSS

---

## Definition of Done (Epic 12)

- [ ] All 4 User Stories completed
- [ ] Progress tracking infrastructure created
- [ ] RAG pipeline emits progress events
- [ ] API endpoints support progress tracking via SSE
- [ ] Agent tools (Summarizer, RiskDetector) emit progress
- [ ] Web UI displays multi-stage progress
- [ ] All guardrails preserved (no bypassing)
- [ ] Backward compatibility maintained
- [ ] All tests pass
- [ ] Documentation updated

## UX Improvement Targets

| Metric | Before | After |
|--------|--------|-------|
| User feedback | Generic spinner | Discrete stages with progress |
| Perceived wait | Long, uncertain | Informative, staged |
| Guardrails | Full | Full (preserved) |
| Error clarity | "Query failed" | "Failed at: Generating answer" |

## Dependencies

```
US 12.1 (Progress Infrastructure)
    ↓
US 12.2 (RAG Pipeline Progress)
    ↓
US 12.3 (API Endpoints + Agent Tools)
    ↓
US 12.4 (Web UI)
```

## Rollback Plan

All progress features are additive:
- Original endpoints remain functional
- UI can fall back to simple spinner if SSE fails
- No changes to core RAG/guardrails logic

If issues arise, simply disable progress endpoints and revert UI to basic loading state.
