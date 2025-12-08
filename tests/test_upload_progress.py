"""Tests for upload progress tracking."""
import asyncio
import pytest
from src.api.progress import ProcessingStage, ProgressTracker, ProgressUpdate


@pytest.mark.asyncio
async def test_progress_tracker_create_task():
    """Test creating a progress tracking task."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    assert task_id is not None
    assert len(task_id) > 0

    status = tracker.get_status(task_id)
    assert status is not None
    assert status.stage == ProcessingStage.UPLOADING
    assert status.progress == 0.0
    assert status.message == "Test upload"


@pytest.mark.asyncio
async def test_progress_tracker_update():
    """Test updating progress."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    await tracker.update(
        task_id,
        ProcessingStage.PARSING,
        0.2,
        "Parsing document...",
    )

    status = tracker.get_status(task_id)
    assert status.stage == ProcessingStage.PARSING
    assert status.progress == 0.2
    assert status.message == "Parsing document..."


@pytest.mark.asyncio
async def test_progress_tracker_mark_complete():
    """Test marking task as complete."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    await tracker.mark_complete(
        task_id,
        "Upload complete",
        document_id="test-doc-123",
    )

    status = tracker.get_status(task_id)
    assert status.stage == ProcessingStage.COMPLETE
    assert status.progress == 1.0
    assert "test-doc-123" in status.message


@pytest.mark.asyncio
async def test_progress_tracker_mark_failed():
    """Test marking task as failed."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    await tracker.mark_failed(task_id, "Test error")

    status = tracker.get_status(task_id)
    assert status.stage == ProcessingStage.FAILED
    assert status.error == "Test error"


@pytest.mark.asyncio
async def test_progress_tracker_subscribe():
    """Test subscribing to progress updates."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    updates_received = []

    async def collect_updates():
        async for update in tracker.subscribe(task_id):
            updates_received.append(update)
            if update.stage == ProcessingStage.COMPLETE:
                break

    # Start subscription in background
    subscription_task = asyncio.create_task(collect_updates())

    # Wait a bit for subscription to start
    await asyncio.sleep(0.1)

    # Send updates
    await tracker.update(task_id, ProcessingStage.PARSING, 0.2, "Parsing...")
    await tracker.update(task_id, ProcessingStage.CHUNKING, 0.4, "Chunking...")
    await tracker.mark_complete(task_id, "Done")

    # Wait for subscription to complete
    await subscription_task

    # Verify we received updates
    assert len(updates_received) > 0
    assert updates_received[-1].stage == ProcessingStage.COMPLETE


@pytest.mark.asyncio
async def test_progress_tracker_cleanup():
    """Test cleanup of completed tasks."""
    tracker = ProgressTracker()
    task_id = tracker.create_task("Test upload")

    await tracker.mark_complete(task_id, "Done")

    # Verify task exists
    status = tracker.get_status(task_id)
    assert status is not None

    # Cleanup with minimal delay
    await tracker.cleanup(task_id, delay_seconds=0)

    # Verify task removed
    status = tracker.get_status(task_id)
    assert status is None


@pytest.mark.asyncio
async def test_progress_update_to_dict():
    """Test converting progress update to dict."""
    update = ProgressUpdate(
        task_id="test-123",
        stage=ProcessingStage.PARSING,
        progress=0.5,
        message="Test message",
        error=None,
    )

    data = update.to_dict()

    assert data["task_id"] == "test-123"
    assert data["stage"] == "parsing"
    assert data["progress"] == 0.5
    assert data["message"] == "Test message"
    assert "timestamp" in data
    assert data["error"] is None


@pytest.mark.asyncio
async def test_multiple_concurrent_uploads():
    """Test tracking multiple uploads simultaneously."""
    tracker = ProgressTracker()

    task1 = tracker.create_task("Upload 1")
    task2 = tracker.create_task("Upload 2")

    await tracker.update(task1, ProcessingStage.PARSING, 0.2, "Parsing 1")
    await tracker.update(task2, ProcessingStage.CHUNKING, 0.4, "Chunking 2")

    status1 = tracker.get_status(task1)
    status2 = tracker.get_status(task2)

    assert status1.stage == ProcessingStage.PARSING
    assert status2.stage == ProcessingStage.CHUNKING
    assert status1.message == "Parsing 1"
    assert status2.message == "Chunking 2"
