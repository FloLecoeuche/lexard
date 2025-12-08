# Epic 11: Streaming LLM Responses

## Overview

Implement real-time streaming of LLM responses to the UI, showing text as it's generated token-by-token instead of waiting for the complete response. This dramatically improves perceived performance and user experience, especially for longer responses like summaries and risk analyses.

## Problem Statement

Current behavior:
```
User asks question → Loading spinner for 5-15 seconds → Complete response appears
```

Target behavior:
```
User asks question → Text starts appearing immediately → Words stream in real-time
```

**User Impact**:
- Current: User stares at spinner, uncertain if system is working
- Target: User sees response building, feels engaged and informed

## Technical Context

### Current Architecture

1. **LLM Clients** (`src/rag/llm.py`):
   - `OllamaClient.generate()` uses `"stream": False`
   - `OpenAICompatibleClient.generate()` doesn't support streaming
   - Returns complete `LLMResponse` after full generation

2. **API Endpoints** (`src/api/routes/`):
   - `/query`, `/summarize`, `/risks` return JSON after complete processing
   - No streaming endpoints exist for LLM responses

3. **Web UI** (`ui/index.html`):
   - Uses `fetch()` to get complete JSON response
   - Shows loading spinner during wait
   - SSE already used for upload progress (can reuse pattern)

### Streaming Technologies

| Technology | Pros | Cons | Best For |
|------------|------|------|----------|
| **Server-Sent Events (SSE)** | Simple, built-in browser support, automatic reconnection | Unidirectional only | Text streaming |
| **WebSockets** | Bidirectional, low latency | More complex, no auto-reconnect | Chat applications |
| **HTTP Chunked Transfer** | Simple HTTP | Less control over chunks | File downloads |

**Decision**: Use **SSE** (same as upload progress) for consistency and simplicity.

## Prerequisites

- Epic 9 (Multilingual Fix) completed or in progress
- SSE infrastructure already exists (upload progress)
- Both Ollama and OpenAI-compatible APIs support streaming

## Important Design Notes

### SSE Status Code Convention
All SSE streaming endpoints MUST return HTTP 200, even for errors. Errors are communicated via `error` events in the stream, not HTTP status codes. This is standard SSE behavior and ensures consistent client handling.

### Guardrails and Streaming
**Important:** Streaming responses bypass some guardrails that require full response text (e.g., hallucination detection, PII redaction on complete responses). This is an acceptable tradeoff for:
- Improved perceived latency (time to first token)
- Better user experience (real-time feedback)

For high-security use cases requiring full guardrails, use the non-streaming endpoints which remain available.

### Cancellation Handling
All streaming operations must support proper cancellation via `AbortController` (UI) and async generator cleanup (backend) to prevent resource leaks.

## User Stories

---

## US 11.1: Streaming LLM Client

**Status:** 🔲 Not Started

### Description

Add streaming support to LLM clients (`OllamaClient` and `OpenAICompatibleClient`) with a new `generate_stream()` method that yields tokens as they're generated.

### Context

Both Ollama and OpenAI-compatible APIs support streaming:
- **Ollama**: Set `"stream": true` in request, response is NDJSON
- **OpenAI**: Set `"stream": true`, response uses SSE format

### Tasks

- [ ] Add `generate_stream()` to `OllamaClient`:
  - Accept same parameters as `generate()`
  - Yield `StreamChunk` objects (token, done flag)
  - Handle connection errors gracefully
  - Support cancellation
- [ ] Add `generate_stream()` to `OpenAICompatibleClient`:
  - Same interface as Ollama
  - Parse SSE `data: [DONE]` termination
- [ ] Create `StreamChunk` dataclass:
  - `token: str` - Text fragment
  - `done: bool` - Whether generation is complete
  - `finish_reason: str | None` - Why generation stopped
- [ ] Add async versions for FastAPI compatibility:
  - `async_generate_stream()` using `httpx.AsyncClient`
- [ ] Update `create_llm_client()` factory if needed
- [ ] Add unit tests for streaming

### Implementation Details

#### StreamChunk Dataclass

```python
# src/rag/llm.py

@dataclass
class StreamChunk:
    """A chunk of streamed LLM output."""
    token: str
    done: bool = False
    finish_reason: str | None = None
```

#### Ollama Streaming

```python
# src/rag/llm.py

class OllamaClient:
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> Generator[StreamChunk, None, None]:
        """Generate response with streaming.

        Yields:
            StreamChunk objects as tokens are generated
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            with self.client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)

                    content = data.get("message", {}).get("content", "")
                    done = data.get("done", False)

                    yield StreamChunk(
                        token=content,
                        done=done,
                        finish_reason=data.get("done_reason") if done else None,
                    )

                    if done:
                        break

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama streaming timed out after {self.timeout}s")
        except httpx.ConnectError:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self.base_url}")

    async def async_generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Async streaming for FastAPI endpoints."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        ) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)

                    content = data.get("message", {}).get("content", "")
                    done = data.get("done", False)

                    yield StreamChunk(
                        token=content,
                        done=done,
                        finish_reason=data.get("done_reason") if done else None,
                    )

                    if done:
                        break
```

#### OpenAI-Compatible Streaming

```python
# src/rag/llm.py

class OpenAICompatibleClient:
    async def async_generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Async streaming for OpenAI-compatible APIs."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        ) as client:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        yield StreamChunk(token="", done=True, finish_reason="stop")
                        break

                    data = json.loads(data_str)
                    choices = data.get("choices", [])

                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = choices[0].get("finish_reason")

                        yield StreamChunk(
                            token=content,
                            done=finish_reason is not None,
                            finish_reason=finish_reason,
                        )
```

### Acceptance Criteria

- [ ] `OllamaClient.generate_stream()` yields tokens incrementally
- [ ] `OpenAICompatibleClient.generate_stream()` yields tokens incrementally
- [ ] Both clients have `async_generate_stream()` for FastAPI
- [ ] `StreamChunk` dataclass contains token, done flag, finish_reason
- [ ] Streaming handles connection errors gracefully
- [ ] Streaming respects timeout settings
- [ ] Unit tests pass for both sync and async streaming
- [ ] Non-streaming `generate()` still works (backward compatibility)

### Tests

- **Modified:** `tests/test_llm.py` - Add streaming generator tests
- **Run:** `pytest tests/test_llm.py -v -k streaming`

> Note: Use mock HTTP responses to test streaming parsing without real Ollama.

### Files to Modify

1. `src/rag/llm.py` - Add streaming methods and `StreamChunk`
2. `tests/test_llm.py` - Add streaming tests

---

## US 11.2: Streaming RAG Pipeline

**Status:** 🔲 Not Started

### Description

Add streaming support to the RAG pipeline, yielding answer tokens while preserving citation and metadata handling.

### Context

The RAG pipeline needs to:
1. Retrieve chunks (non-streaming, fast)
2. Build context (non-streaming, fast)
3. **Stream LLM generation** (this is the slow part)
4. Return metadata (citations, confidence, language)

Challenge: Citations and confidence are known before streaming starts, but traditionally returned with the answer.

**Solution**: Use SSE with multiple event types:
- `metadata` event: Send citations, confidence, language first
- `token` events: Stream answer tokens
- `done` event: Signal completion

### Tasks

- [ ] Add `query_stream()` to `RAGPipeline`:
  - Perform retrieval and context building (non-streaming)
  - Yield `RAGStreamEvent` objects
  - First yield metadata (citations, confidence, language)
  - Then yield tokens
  - Finally yield done signal
- [ ] Create `RAGStreamEvent` dataclass:
  - `event_type: str` - "metadata" | "token" | "done" | "error"
  - `data: dict` - Event-specific payload
- [ ] Handle errors gracefully:
  - Yield error event instead of raising
  - Include trace_id in error events
- [ ] Add unit tests for streaming pipeline

### Implementation Details

#### RAGStreamEvent

```python
# src/rag/pipeline.py

@dataclass
class RAGStreamEvent:
    """Event emitted during streaming RAG query."""
    event_type: str  # "metadata" | "token" | "done" | "error"
    data: dict

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"
```

#### Streaming Query Method

```python
# src/rag/pipeline.py

class RAGPipeline:
    async def query_stream(
        self,
        question: str,
        document_id: str | None = None,
        language: str | None = None,
    ) -> AsyncGenerator[RAGStreamEvent, None]:
        """Execute RAG query with streaming response.

        Yields:
            RAGStreamEvent objects in order:
            1. metadata - citations, confidence, language
            2. token (multiple) - answer text chunks
            3. done - completion signal

        Note:
            Language is detected from document chunks, not query.
        """
        from src.rag.llm import (
            detect_language_from_chunks,
            get_qa_system_prompt,
            build_qa_prompt,
        )

        try:
            # 1. Retrieve relevant chunks (fast, non-streaming)
            chunks = self.retriever.retrieve(question, document_id)

            # 2. Handle no results
            if not chunks:
                yield RAGStreamEvent(
                    event_type="metadata",
                    data={
                        "citation_chunks": [],
                        "confidence": "low",
                        "has_relevant_content": False,
                        "language": "en",
                    }
                )
                yield RAGStreamEvent(
                    event_type="token",
                    data={"token": "I could not find relevant information in the provided documents."}
                )
                yield RAGStreamEvent(event_type="done", data={})
                return

            # 3. Detect language from document chunks
            if language is None:
                language = detect_language_from_chunks(chunks)

            # 4. Build context (fast, non-streaming)
            context = self.context_builder.build(chunks)

            # 5. Calculate confidence and build citations
            confidence = self._calculate_confidence(chunks)
            citation_chunks = self._build_citation_chunks(chunks, context)

            # 6. Yield metadata FIRST (before streaming starts)
            yield RAGStreamEvent(
                event_type="metadata",
                data={
                    "citation_chunks": [
                        {
                            "content": c.content,
                            "page": c.page,
                            "chunk_index": c.chunk_index,
                            "score": c.score,
                        }
                        for c in citation_chunks
                    ],
                    "confidence": confidence.value,
                    "has_relevant_content": True,
                    "language": language,
                }
            )

            # 7. Stream LLM generation
            prompt = build_qa_prompt(question, context.context_text, language=language)
            system_prompt = get_qa_system_prompt(language=language)

            async for chunk in self.llm_client.async_generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
            ):
                if chunk.token:
                    yield RAGStreamEvent(
                        event_type="token",
                        data={"token": chunk.token}
                    )

                if chunk.done:
                    yield RAGStreamEvent(
                        event_type="done",
                        data={"finish_reason": chunk.finish_reason}
                    )

        except Exception as e:
            logger.error(f"Streaming query error: {e}")
            yield RAGStreamEvent(
                event_type="error",
                data={"message": str(e)}
            )
```

### Acceptance Criteria

- [ ] `RAGPipeline.query_stream()` yields events in correct order
- [ ] Metadata (citations, confidence, language) sent before tokens
- [ ] Tokens streamed as they're generated
- [ ] Error events include helpful messages
- [ ] Non-streaming `query()` still works
- [ ] Unit tests pass for streaming pipeline

### Tests

- **Modified:** `tests/test_pipeline.py` - Add `query_stream()` tests
- **Run:** `pytest tests/test_pipeline.py -v -k stream`

> Note: Test event ordering (metadata → tokens → done) and error handling.

### Files to Modify

1. `src/rag/pipeline.py` - Add `query_stream()` and `RAGStreamEvent`
2. `tests/test_rag_pipeline.py` - Add streaming tests

---

## US 11.3: Streaming API Endpoints & Agent Tools

**Status:** 🔲 Not Started

### Description

Create SSE streaming endpoints for query, summarize, and risk analysis, along with the streaming agent tools that power them. This US combines API endpoints with their underlying tool implementations since they are tightly coupled.

### Context

New endpoints alongside existing ones:
- `/query/stream` - Streaming version of `/query`
- `/summarize/stream` - Streaming version of `/summarize`
- `/risks/stream` - Streaming version of `/risks`

These endpoints depend on streaming agent tools:
- **Summarizer**: Can stream each chunk summary, then final aggregation
- **Risk Detector**: Can stream each identified risk as it's found

### Tasks

#### API Endpoints

- [ ] Create `/query/stream` endpoint:
  - Accept same request body as `/query`
  - Return `StreamingResponse` with SSE content type
  - Stream `RAGStreamEvent` objects
  - Handle client disconnection
- [ ] Create `/summarize/stream` endpoint:
  - Stream chunk summaries as they're generated
  - Final aggregation may be non-streaming or streamed
- [ ] Create `/risks/stream` endpoint:
  - Stream individual risk analyses as found
  - Final aggregation at end
- [ ] Add proper error handling:
  - Yield error events for exceptions
  - Include trace_id in errors
  - **All endpoints MUST return HTTP 200** (errors via events)
- [ ] Add request validation (document exists, etc.)
- [ ] Document endpoints in OpenAPI schema

#### Agent Tools

- [ ] Add `summarize_stream()` to SummarizerTool:
  - Yield progress events as chunks are processed
  - Yield chunk summaries as they're generated
  - Stream final aggregation
- [ ] Add `analyze_stream()` to RiskDetectorTool:
  - Yield each risk as it's identified
  - Stream overall assessment at end
- [ ] Create `ToolStreamEvent` dataclass:
  - `event_type: str` - "progress" | "chunk" | "result" | "done" | "error"
  - `data: dict` - Event payload
- [ ] Update tools to use language-aware streaming
- [ ] Add tests for streaming tools

### Implementation Details

#### Streaming Query Endpoint

```python
# src/api/routes/query.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["query"])


@router.post(
    "/query/stream",
    summary="Query document with streaming response",
    description="Ask a question and receive the answer streamed in real-time via SSE.",
    responses={
        200: {
            "description": "SSE stream of answer tokens",
            "content": {"text/event-stream": {}},
        },
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def query_document_stream(
    query: QueryRequest,
    request: Request,
) -> StreamingResponse:
    """Query a document with streaming response."""
    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists
    registry = get_document_registry()
    doc = registry.get(query.document_id)

    if not doc:
        # For SSE, we return error as an event
        async def error_stream():
            yield RAGStreamEvent(
                event_type="error",
                data={
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document with ID {query.document_id} not found",
                    "trace_id": trace_id,
                }
            ).to_sse()

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            status_code=200,  # SSE always returns 200, errors in stream
        )

    if doc.status != "processed":
        async def error_stream():
            yield RAGStreamEvent(
                event_type="error",
                data={
                    "code": "INVALID_REQUEST",
                    "message": f"Document is not ready for queries (status: {doc.status})",
                    "trace_id": trace_id,
                }
            ).to_sse()

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            status_code=200,  # SSE always returns 200, errors in stream
        )

    # Get streaming pipeline
    pipeline = get_rag_pipeline()

    async def generate_stream():
        try:
            async for event in pipeline.query_stream(
                question=query.question,
                document_id=query.document_id,
            ):
                yield event.to_sse()
        except Exception as e:
            yield RAGStreamEvent(
                event_type="error",
                data={"message": str(e), "trace_id": trace_id}
            ).to_sse()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

#### Streaming Summarize Endpoint

```python
# src/api/routes/analysis.py

@router.post(
    "/summarize/stream",
    summary="Summarize document with streaming response",
    description="Generate a summary with real-time streaming via SSE.",
)
async def summarize_document_stream(
    req: SummarizeRequest,
    request: Request,
) -> StreamingResponse:
    """Summarize document with streaming response."""
    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists
    registry = get_document_registry()
    doc = registry.get(req.document_id)

    if not doc or doc.status != "processed":
        # Return error in stream (always 200 for SSE)
        async def error_stream():
            yield SummaryStreamEvent(
                event_type="error",
                data={"code": "DOCUMENT_NOT_FOUND", "trace_id": trace_id}
            ).to_sse()
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            status_code=200,
        )

    summarizer = SummarizerTool(...)

    async def generate_stream():
        # Stream chunk-by-chunk summaries, then aggregation
        async for event in summarizer.summarize_stream(
            document_id=req.document_id,
            style=req.style,
        ):
            yield event.to_sse()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        status_code=200,  # Always 200 for SSE
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

#### Streaming Summarizer Tool

```python
# src/agent/tools/summarizer.py

@dataclass
class SummaryStreamEvent:
    """Event emitted during streaming summarization."""
    event_type: str  # "progress" | "chunk_summary" | "aggregating" | "token" | "done" | "error"
    data: dict

    def to_sse(self) -> str:
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"


class SummarizerTool:
    async def summarize_stream(
        self,
        document_id: str,
        style: str = "executive",
        language: str | None = None,
    ) -> AsyncGenerator[SummaryStreamEvent, None]:
        """Stream document summarization.

        Yields events:
        1. progress - Overall progress updates
        2. chunk_summary - Individual chunk summaries
        3. aggregating - Starting final aggregation
        4. token - Streaming aggregation tokens
        5. done - Completion with metadata
        """
        chunks = await self.qdrant_service.get_chunks_by_document(document_id)
        if not chunks:
            yield SummaryStreamEvent(
                event_type="error",
                data={"message": f"No chunks found for document {document_id}"}
            )
            return

        # Detect language from document chunks
        if language is None:
            language = detect_language_from_chunks(chunks)

        yield SummaryStreamEvent(
            event_type="progress",
            data={
                "total_chunks": len(chunks),
                "language": language,
                "message": f"Processing {len(chunks)} sections...",
            }
        )

        # Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            prompt = get_prompt("chunk_summary", language, content=chunk.content)

            # Stream chunk summary
            summary_parts = []
            async for token_chunk in self.llm_client.async_generate_stream(prompt):
                if token_chunk.token:
                    summary_parts.append(token_chunk.token)

            chunk_summary = "".join(summary_parts)
            chunk_summaries.append(chunk_summary)

            yield SummaryStreamEvent(
                event_type="chunk_summary",
                data={
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "summary": chunk_summary,
                }
            )

        # Aggregate summaries
        yield SummaryStreamEvent(
            event_type="aggregating",
            data={"message": "Generating final summary..."}
        )

        combined = "\n\n".join(chunk_summaries)
        aggregation_prompt = get_prompt("aggregation", language, summaries=combined)

        full_summary = ""
        async for token_chunk in self.llm_client.async_generate_stream(aggregation_prompt):
            if token_chunk.token:
                full_summary += token_chunk.token
                yield SummaryStreamEvent(
                    event_type="token",
                    data={"token": token_chunk.token}
                )

        yield SummaryStreamEvent(
            event_type="done",
            data={
                "summary": full_summary,
                "key_points": self._extract_key_points(full_summary),
                "word_count": len(full_summary.split()),
                "language": language,
            }
        )
```

### Acceptance Criteria

#### API Endpoints
- [ ] `/query/stream` streams answer tokens via SSE
- [ ] `/summarize/stream` streams summary generation
- [ ] `/risks/stream` streams risk analysis
- [ ] All endpoints validate document exists first
- [ ] All endpoints return HTTP 200 (errors via `error` events)
- [ ] Error events include trace_id
- [ ] Proper SSE headers set (no caching, no buffering)
- [ ] Endpoints documented in OpenAPI
- [ ] Client disconnection handled gracefully

#### Agent Tools
- [ ] `SummarizerTool.summarize_stream()` yields chunk-by-chunk progress
- [ ] Final summary streams token-by-token
- [ ] `RiskDetectorTool.analyze_stream()` yields risks as found
- [ ] All streaming respects detected document language
- [ ] Error events include helpful messages
- [ ] Non-streaming methods still work

### Files to Create/Modify

1. `src/api/routes/query.py` - Add `/query/stream`
2. `src/api/routes/analysis.py` - Add `/summarize/stream`, `/risks/stream`
3. `src/agent/tools/summarizer.py` - Add `summarize_stream()` and `SummaryStreamEvent`
4. `src/agent/tools/risk_detector.py` - Add `analyze_stream()` and `RiskStreamEvent`

### Tests

- **New:** `tests/test_streaming_endpoints.py` - Test SSE response format and headers
- **Modified:** `tests/test_summarizer.py` - Add `summarize_stream()` tests
- **Modified:** `tests/test_risk_detector.py` - Add `analyze_stream()` tests
- **Run:** `pytest tests/test_streaming_endpoints.py tests/test_summarizer.py tests/test_risk_detector.py -v -k stream`

> Note: Use TestClient with httpx to consume SSE streams. Verify headers, event format, and event sequence.

---

## US 11.4: Web UI Streaming Integration

**Status:** 🔲 Not Started

### Description

Update the Web UI to consume streaming endpoints and display LLM responses incrementally as they're generated.

### Context

The UI already uses SSE for upload progress, so the pattern is familiar. Key changes:
1. Connect to `/query/stream` instead of `/query`
2. Handle multiple event types (metadata, token, done, error)
3. Append tokens to answer display as they arrive
4. Show citations immediately (from metadata event)

### Tasks

- [ ] Update `askQuestion()` to use streaming:
  - Connect to `/query/stream` via `EventSource`
  - Handle `metadata` event: show citations, confidence
  - Handle `token` events: append to answer text
  - Handle `done` event: finalize display
  - Handle `error` events: show error message
- [ ] Update `summarizeDocument()` to use streaming:
  - Show progress as chunks are summarized
  - Display final summary as it streams
- [ ] Update `analyzeRisks()` to use streaming:
  - Show risks as they're identified
  - Update overall risk level at end
- [ ] Add visual feedback for streaming:
  - Typing indicator or cursor while streaming
  - Smooth text appearance animation (optional)
- [ ] Handle stream cancellation with AbortController:
  - Create AbortController for each streaming request
  - Wire "Stop" button to `controller.abort()`
  - Clean up on navigation away via `beforeunload` event
  - Handle `AbortError` gracefully in catch block
- [ ] Fallback to non-streaming on error:
  - If SSE fails, retry with regular endpoint

### Implementation Details

#### Streaming Query in UI

```javascript
// ui/index.html

// Global controller for cancellation
let currentStreamController = null;

async function askQuestionStreaming() {
    if (!selectedDocumentId) {
        alert('Please select a document first');
        return;
    }

    const question = document.getElementById('question').value.trim();
    if (!question) {
        alert('Please enter a question');
        return;
    }

    // Cancel any existing stream
    if (currentStreamController) {
        currentStreamController.abort();
    }

    // Create new AbortController for this request
    currentStreamController = new AbortController();

    const resultBox = document.getElementById('query-result');

    // Show initial streaming state with stop button
    resultBox.innerHTML = `
        <h3>Answer <button class="stop-btn" onclick="stopStreaming()">Stop</button></h3>
        <div class="answer-text" id="streaming-answer"><span class="typing-cursor"></span></div>
        <div class="citations" id="streaming-citations" style="display: none;">
            <h3>Citations</h3>
            <div id="citations-content"></div>
        </div>
    `;

    const answerDiv = document.getElementById('streaming-answer');
    const citationsDiv = document.getElementById('streaming-citations');
    const citationsContent = document.getElementById('citations-content');

    let fullAnswer = '';

    try {
        // Use fetch with POST and AbortController signal
        const response = await fetch('/query/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document_id: selectedDocumentId,
                question: question
            }),
            signal: currentStreamController.signal  // Enable cancellation
        });

        if (!response.ok) {
            throw new Error('Stream request failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE events from buffer
            const events = parseSSEEvents(buffer);
            buffer = events.remaining;

            for (const event of events.parsed) {
                handleStreamEvent(event, answerDiv, citationsDiv, citationsContent);
                if (event.type === 'token') {
                    fullAnswer += event.data.token;
                    answerDiv.innerHTML = escapeHtml(fullAnswer) + '<span class="typing-cursor"></span>';
                }
            }
        }

        // Remove cursor and stop button when done
        answerDiv.innerHTML = escapeHtml(fullAnswer);
        hideStopButton();

    } catch (error) {
        // Handle user cancellation gracefully
        if (error.name === 'AbortError') {
            console.log('Streaming cancelled by user');
            answerDiv.innerHTML = escapeHtml(fullAnswer) + ' <em>(stopped)</em>';
            hideStopButton();
            return;
        }

        // Fallback to non-streaming for other errors
        console.warn('Streaming failed, falling back to regular query:', error);
        await askQuestion();
    } finally {
        currentStreamController = null;
    }
}

function stopStreaming() {
    if (currentStreamController) {
        currentStreamController.abort();
    }
}

function hideStopButton() {
    const stopBtn = document.querySelector('.stop-btn');
    if (stopBtn) stopBtn.style.display = 'none';
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (currentStreamController) {
        currentStreamController.abort();
    }
});

function parseSSEEvents(buffer) {
    const events = [];
    const lines = buffer.split('\n');
    let remaining = '';
    let currentEvent = { type: null, data: null };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith('event: ')) {
            currentEvent.type = line.slice(7);
        } else if (line.startsWith('data: ')) {
            try {
                currentEvent.data = JSON.parse(line.slice(6));
            } catch (e) {
                currentEvent.data = line.slice(6);
            }
        } else if (line === '' && currentEvent.type) {
            events.push({ ...currentEvent });
            currentEvent = { type: null, data: null };
        }
    }

    // Keep incomplete event in buffer
    if (currentEvent.type || lines[lines.length - 1] !== '') {
        remaining = lines.slice(-2).join('\n');
    }

    return { parsed: events, remaining };
}

function handleStreamEvent(event, answerDiv, citationsDiv, citationsContent) {
    switch (event.type) {
        case 'metadata':
            // Show citations immediately
            if (event.data.citation_chunks && event.data.citation_chunks.length > 0) {
                citationsDiv.style.display = 'block';
                citationsContent.innerHTML = event.data.citation_chunks.map(c => `
                    <div class="citation">
                        <div>${escapeHtml(c.content)}</div>
                        <div class="citation-meta">Page ${c.page || 'N/A'} | Score: ${(c.score || 0).toFixed(2)}</div>
                    </div>
                `).join('');
            }

            // Show confidence badge
            if (event.data.confidence) {
                const badge = document.createElement('span');
                badge.className = `confidence-badge confidence-${event.data.confidence}`;
                badge.textContent = `Confidence: ${event.data.confidence}`;
                answerDiv.parentNode.insertBefore(badge, citationsDiv);
            }
            break;

        case 'token':
            // Handled in main loop
            break;

        case 'done':
            console.log('Stream complete:', event.data);
            break;

        case 'error':
            answerDiv.innerHTML = `<div class="error-message">Error: ${escapeHtml(event.data.message)}</div>`;
            break;
    }
}
```

#### CSS for Typing Cursor and Stop Button

```css
/* ui/index.html - Add to <style> */

.stop-btn {
    background: #ef4444;
    color: white;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    cursor: pointer;
    margin-left: 0.5rem;
    vertical-align: middle;
}

.stop-btn:hover {
    background: #dc2626;
}

.typing-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #2563eb;
    animation: blink 1s step-end infinite;
    margin-left: 2px;
    vertical-align: text-bottom;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.streaming-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #64748b;
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
}

.streaming-dot {
    width: 8px;
    height: 8px;
    background: #2563eb;
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.2); opacity: 0.7; }
}
```

### Acceptance Criteria

- [ ] Query responses stream token-by-token
- [ ] Citations appear immediately (before answer streams)
- [ ] Typing cursor shows during streaming
- [ ] Summary streams as it's generated
- [ ] Risk analysis streams individual risks
- [ ] "Stop" button cancels generation
- [ ] Graceful fallback to non-streaming on error
- [ ] No UI flicker or layout shifts
- [ ] Works on slow connections

### Tests

- **None:** UI-only changes (no Python backend tests)
- **Manual:** Test streaming display in browser with real queries
- **Run:** Manual browser testing

> Note: UI is a single HTML file. Verify typing cursor, fallback behavior, and stop button.

### Files to Modify

1. `ui/index.html` - Add streaming JavaScript and CSS

---

## Definition of Done (Epic 11)

- [ ] All 4 User Stories completed
- [ ] LLM clients support streaming generation
- [ ] RAG pipeline supports streaming queries
- [ ] SSE endpoints created for query, summarize, risks (with agent tool streaming)
- [ ] Web UI displays streaming responses with cancellation support
- [ ] Fallback to non-streaming works
- [ ] No regression in non-streaming functionality
- [ ] Performance improvement measurable (time to first token)
- [ ] All tests pass
- [ ] Documentation updated

## Performance Targets

| Metric | Before | After |
|--------|--------|-------|
| Time to first token | 3-15s | <500ms |
| Perceived latency | High (spinner) | Low (immediate feedback) |
| User engagement | Passive waiting | Active reading |

## Dependencies

```
US 11.1 (LLM Streaming)
    ↓
US 11.2 (RAG Pipeline Streaming)
    ↓
US 11.3 (API Endpoints & Agent Tools)
    ↓
US 11.4 (Web UI)
```

US 11.1 must be completed first (foundation).
US 11.2 depends on 11.1.
US 11.3 combines endpoints and agent tools (previously 11.3 + 11.5) since they are tightly coupled.
US 11.4 requires 11.3 (needs endpoints to consume).

## Rollback Plan

All streaming features are additive:
- New `/stream` endpoints don't replace existing endpoints
- UI can fallback to non-streaming on error
- Non-streaming methods remain unchanged

If issues arise, simply disable streaming endpoints and revert UI to non-streaming calls.
