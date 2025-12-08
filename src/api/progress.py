"""Real-time progress tracking for document processing and LLM operations."""
import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator
from uuid import uuid4

logger = logging.getLogger(__name__)


class ProcessingStage(str, Enum):
    """Document processing stages (for upload)."""

    UPLOADING = "uploading"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETE = "complete"
    FAILED = "failed"


class OperationStage(str, Enum):
    """Stages for LLM operations (query, summarize, risks)."""

    PENDING = "pending"
    RETRIEVING = "retrieving"
    BUILDING_CONTEXT = "building_context"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    """Progress update event."""

    task_id: str
    stage: ProcessingStage
    progress: float  # 0.0 to 1.0
    message: str
    timestamp: datetime | None = None
    error: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class OperationProgress:
    """Progress state for a long-running LLM operation."""

    operation_id: str
    operation_type: str  # "query" | "summarize" | "risks"
    stage: OperationStage
    progress: float  # 0.0 to 1.0
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
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

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
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
            message=initial_message,
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

        await self.update(task_id, ProcessingStage.COMPLETE, 1.0, final_message)

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
            task_id, ProcessingStage.FAILED, 0.0, "Upload failed", error=error
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


# Global progress tracker instance (for uploads)
progress_tracker = ProgressTracker()


class OperationProgressTracker:
    """Track progress of LLM operations (query, summarize, risks).

    Thread-safe tracker that supports multiple concurrent operations
    with automatic TTL-based cleanup.
    """

    # Default TTL for completed operations (5 minutes)
    DEFAULT_TTL_SECONDS = 300

    def __init__(self):
        self._operations: dict[str, OperationProgress] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def start(self, operation_type: str) -> str:
        """Start tracking a new operation.

        Args:
            operation_type: Type of operation ("query", "summarize", "risks")

        Returns:
            Operation ID (UUID)
        """
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
        logger.info(f"Started operation: {operation_id} ({operation_type})")
        return operation_id

    async def update(
        self,
        operation_id: str,
        stage: OperationStage,
        progress: float,
        message: str,
    ) -> None:
        """Update operation progress and notify subscribers.

        Args:
            operation_id: Operation identifier
            stage: Current operation stage
            progress: Progress percentage (0.0 to 1.0)
            message: Human-readable status message
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Operation {operation_id} not found for update")
                return

            op = self._operations[operation_id]
            op.stage = stage
            op.progress = progress
            op.message = message
            op.timestamp = datetime.now()

            # Notify all subscribers
            for queue in self._subscribers.get(operation_id, []):
                try:
                    await queue.put(op)
                except Exception as e:
                    logger.error(f"Failed to notify subscriber: {e}")

        logger.debug(f"Operation {operation_id}: {stage.value} ({progress:.0%}) - {message}")

    async def complete(self, operation_id: str, result: Any = None) -> None:
        """Mark operation as complete.

        Args:
            operation_id: Operation identifier
            result: Optional result data to store
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Operation {operation_id} not found for completion")
                return

            op = self._operations[operation_id]
            op.stage = OperationStage.COMPLETE
            op.progress = 1.0
            op.message = "Complete"
            op.timestamp = datetime.now()
            op.result = result

            # Notify all subscribers
            for queue in self._subscribers.get(operation_id, []):
                try:
                    await queue.put(op)
                except Exception as e:
                    logger.error(f"Failed to notify subscriber: {e}")

        logger.info(f"Operation {operation_id} completed")

        # Schedule cleanup
        asyncio.create_task(self._cleanup_after_ttl(operation_id))

    async def fail(self, operation_id: str, error: str) -> None:
        """Mark operation as failed.

        Args:
            operation_id: Operation identifier
            error: Error message
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Operation {operation_id} not found for failure")
                return

            op = self._operations[operation_id]
            op.stage = OperationStage.FAILED
            # Keep current progress to show where it failed
            op.message = "Failed"
            op.error = error
            op.timestamp = datetime.now()

            # Notify all subscribers
            for queue in self._subscribers.get(operation_id, []):
                try:
                    await queue.put(op)
                except Exception as e:
                    logger.error(f"Failed to notify subscriber: {e}")

        logger.error(f"Operation {operation_id} failed: {error}")

        # Schedule cleanup
        asyncio.create_task(self._cleanup_after_ttl(operation_id))

    async def subscribe(self, operation_id: str) -> asyncio.Queue:
        """Subscribe to progress updates for an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            Queue that receives progress updates
        """
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if operation_id not in self._subscribers:
                logger.warning(f"Operation {operation_id} not found for subscription")
                return queue

            self._subscribers[operation_id].append(queue)

            # Send current state immediately
            if operation_id in self._operations:
                await queue.put(self._operations[operation_id])

        return queue

    async def unsubscribe(self, operation_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from progress updates.

        Args:
            operation_id: Operation identifier
            queue: Queue to remove
        """
        async with self._lock:
            if operation_id in self._subscribers:
                try:
                    self._subscribers[operation_id].remove(queue)
                except ValueError:
                    pass

    def get(self, operation_id: str) -> OperationProgress | None:
        """Get current status of an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            Current operation progress or None if not found
        """
        return self._operations.get(operation_id)

    async def _cleanup_after_ttl(
        self,
        operation_id: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Clean up operation after TTL expires.

        Args:
            operation_id: Operation identifier
            ttl_seconds: TTL in seconds (default: DEFAULT_TTL_SECONDS)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS
        await asyncio.sleep(ttl)
        async with self._lock:
            self._operations.pop(operation_id, None)
            self._subscribers.pop(operation_id, None)
        logger.debug(f"Cleaned up operation: {operation_id}")


# Global operation progress tracker instance (for LLM operations)
_operation_tracker: OperationProgressTracker | None = None


def get_operation_tracker() -> OperationProgressTracker:
    """Get or create global operation progress tracker.

    Returns:
        Global OperationProgressTracker instance
    """
    global _operation_tracker
    if _operation_tracker is None:
        _operation_tracker = OperationProgressTracker()
    return _operation_tracker
