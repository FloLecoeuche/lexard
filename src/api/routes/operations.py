"""Operations progress tracking routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.progress import (
    OperationProgress,
    OperationStage,
    get_operation_tracker,
)

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get(
    "/{operation_id}/progress",
    summary="Stream operation progress",
    description="""
Stream progress updates for an operation via Server-Sent Events (SSE).

The stream emits events in the format:
```
event: progress
data: {"operation_id": "...", "stage": "...", "progress": 0.5, "message": "..."}
```

Stages for query operations:
- `pending`: Operation starting
- `retrieving`: Finding relevant document sections
- `building_context`: Building context from sections
- `generating`: Generating answer with LLM
- `validating`: Running guardrails validation
- `complete`: Operation finished successfully
- `failed`: Operation encountered an error

The stream closes automatically when the operation reaches `complete` or `failed` state.
""",
    responses={
        200: {
            "description": "SSE stream of progress events",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Operation not found"},
    },
)
async def get_operation_progress(operation_id: str) -> StreamingResponse:
    """Stream progress updates for an operation via SSE."""
    tracker = get_operation_tracker()

    # Check if operation exists
    operation = tracker.get(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    async def event_stream():
        queue = await tracker.subscribe(operation_id)
        try:
            while True:
                progress: OperationProgress = await queue.get()
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


@router.get(
    "/{operation_id}/result",
    summary="Get operation result",
    description="""
Get the result of a completed operation.

Returns:
- `status: "processing"` - Operation still in progress
- `status: "complete"` with `result` - Operation finished successfully
- `status: "failed"` with `error` - Operation encountered an error
""",
    responses={
        200: {"description": "Operation status and result"},
        404: {"description": "Operation not found"},
    },
)
async def get_operation_result(operation_id: str) -> dict:
    """Get the result of a completed operation."""
    tracker = get_operation_tracker()
    operation = tracker.get(operation_id)

    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    if operation.stage == OperationStage.COMPLETE:
        return {
            "status": "complete",
            "result": operation.result,
        }
    elif operation.stage == OperationStage.FAILED:
        return {
            "status": "failed",
            "error": operation.error,
        }
    else:
        return {
            "status": "processing",
            "stage": operation.stage.value,
            "progress": operation.progress,
            "message": operation.message,
        }
