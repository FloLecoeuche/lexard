"""Real-time progress tracking for document processing."""
import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import AsyncIterator
from uuid import uuid4

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


# Global progress tracker instance
progress_tracker = ProgressTracker()
