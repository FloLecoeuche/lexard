"""Tests for LLM operation progress tracking."""
import asyncio
import json
import pytest

from src.api.progress import (
    OperationProgress,
    OperationProgressTracker,
    OperationStage,
    get_operation_tracker,
)


class TestOperationStage:
    """Tests for OperationStage enum."""

    def test_all_stages_exist(self):
        """Verify all expected stages are defined."""
        stages = [s.value for s in OperationStage]
        assert "pending" in stages
        assert "retrieving" in stages
        assert "building_context" in stages
        assert "generating" in stages
        assert "validating" in stages
        assert "complete" in stages
        assert "failed" in stages

    def test_stage_is_string_enum(self):
        """Verify stages can be used as strings."""
        assert OperationStage.PENDING == "pending"
        assert OperationStage.RETRIEVING == "retrieving"
        assert OperationStage.COMPLETE == "complete"


class TestOperationProgress:
    """Tests for OperationProgress dataclass."""

    def test_create_progress(self):
        """Test creating a progress instance."""
        progress = OperationProgress(
            operation_id="test-123",
            operation_type="query",
            stage=OperationStage.PENDING,
            progress=0.0,
            message="Starting...",
        )

        assert progress.operation_id == "test-123"
        assert progress.operation_type == "query"
        assert progress.stage == OperationStage.PENDING
        assert progress.progress == 0.0
        assert progress.message == "Starting..."
        assert progress.error is None
        assert progress.result is None
        assert progress.timestamp is not None

    def test_to_sse_format(self):
        """Test SSE format output."""
        progress = OperationProgress(
            operation_id="test-456",
            operation_type="summarize",
            stage=OperationStage.GENERATING,
            progress=0.5,
            message="Generating summary...",
        )

        sse = progress.to_sse()

        # Verify SSE format
        assert sse.startswith("event: progress\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")

        # Extract and parse JSON data
        data_line = sse.split("data: ")[1].strip()
        data = json.loads(data_line)

        assert data["operation_id"] == "test-456"
        assert data["operation_type"] == "summarize"
        assert data["stage"] == "generating"
        assert data["progress"] == 0.5
        assert data["message"] == "Generating summary..."
        assert "timestamp" in data
        assert "error" not in data

    def test_to_sse_with_error(self):
        """Test SSE format includes error when present."""
        progress = OperationProgress(
            operation_id="test-789",
            operation_type="risks",
            stage=OperationStage.FAILED,
            progress=0.3,
            message="Failed",
            error="LLM timeout",
        )

        sse = progress.to_sse()
        data_line = sse.split("data: ")[1].strip()
        data = json.loads(data_line)

        assert data["error"] == "LLM timeout"

    def test_to_dict(self):
        """Test converting progress to dict."""
        progress = OperationProgress(
            operation_id="test-abc",
            operation_type="query",
            stage=OperationStage.RETRIEVING,
            progress=0.25,
            message="Finding sections...",
        )

        data = progress.to_dict()

        assert data["operation_id"] == "test-abc"
        assert data["operation_type"] == "query"
        assert data["stage"] == "retrieving"
        assert data["progress"] == 0.25
        assert data["message"] == "Finding sections..."
        assert "timestamp" in data


@pytest.mark.asyncio
class TestOperationProgressTracker:
    """Tests for OperationProgressTracker class."""

    async def test_start_operation(self):
        """Test starting a new operation."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("query")

        assert operation_id is not None
        assert len(operation_id) == 36  # UUID format

        operation = tracker.get(operation_id)
        assert operation is not None
        assert operation.operation_type == "query"
        assert operation.stage == OperationStage.PENDING
        assert operation.progress == 0.0
        assert operation.message == "Starting..."

    async def test_update_progress(self):
        """Test updating operation progress."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("query")

        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.25,
            "Finding relevant sections...",
        )

        operation = tracker.get(operation_id)
        assert operation.stage == OperationStage.RETRIEVING
        assert operation.progress == 0.25
        assert operation.message == "Finding relevant sections..."

    async def test_complete_operation(self):
        """Test completing an operation."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("summarize")

        result = {"summary": "Test summary", "language": "en"}
        await tracker.complete(operation_id, result=result)

        operation = tracker.get(operation_id)
        assert operation.stage == OperationStage.COMPLETE
        assert operation.progress == 1.0
        assert operation.message == "Complete"
        assert operation.result == result

    async def test_fail_operation(self):
        """Test failing an operation."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("risks")

        await tracker.update(
            operation_id,
            OperationStage.GENERATING,
            0.5,
            "Generating...",
        )
        await tracker.fail(operation_id, "LLM connection timeout")

        operation = tracker.get(operation_id)
        assert operation.stage == OperationStage.FAILED
        assert operation.progress == 0.5  # Progress preserved
        assert operation.error == "LLM connection timeout"

    async def test_subscribe_to_updates(self):
        """Test subscribing to progress updates."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("query")

        updates_received = []

        async def collect_updates():
            queue = await tracker.subscribe(operation_id)
            while True:
                update = await asyncio.wait_for(queue.get(), timeout=1.0)
                updates_received.append(update)
                if update.stage in (OperationStage.COMPLETE, OperationStage.FAILED):
                    break

        # Start subscription in background
        subscription_task = asyncio.create_task(collect_updates())

        # Wait for subscription to be established
        await asyncio.sleep(0.05)

        # Send updates with small delays to ensure queue processing
        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.25,
            "Retrieving...",
        )
        await asyncio.sleep(0.01)

        await tracker.update(
            operation_id,
            OperationStage.GENERATING,
            0.5,
            "Generating...",
        )
        await asyncio.sleep(0.01)

        await tracker.complete(operation_id)

        # Wait for subscription to complete
        await subscription_task

        # Verify updates received - at minimum we should receive the final complete state
        assert len(updates_received) >= 1
        assert updates_received[-1].stage == OperationStage.COMPLETE

    async def test_unsubscribe(self):
        """Test unsubscribing from updates."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("query")

        queue = await tracker.subscribe(operation_id)
        await tracker.unsubscribe(operation_id, queue)

        # Updates should not be sent to unsubscribed queue
        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.25,
            "Test",
        )

        # Queue should only have initial state (before unsubscribe)
        assert queue.qsize() == 1

    async def test_get_nonexistent_operation(self):
        """Test getting a non-existent operation returns None."""
        tracker = OperationProgressTracker()
        operation = tracker.get("nonexistent-id")
        assert operation is None

    async def test_update_nonexistent_operation(self):
        """Test updating a non-existent operation is handled gracefully."""
        tracker = OperationProgressTracker()
        # Should not raise
        await tracker.update(
            "nonexistent-id",
            OperationStage.RETRIEVING,
            0.25,
            "Test",
        )

    async def test_multiple_concurrent_operations(self):
        """Test tracking multiple operations simultaneously."""
        tracker = OperationProgressTracker()

        op1 = await tracker.start("query")
        op2 = await tracker.start("summarize")
        op3 = await tracker.start("risks")

        await tracker.update(op1, OperationStage.RETRIEVING, 0.25, "Query retrieval")
        await tracker.update(op2, OperationStage.GENERATING, 0.5, "Summarizing")
        await tracker.update(op3, OperationStage.VALIDATING, 0.9, "Validating risks")

        assert tracker.get(op1).stage == OperationStage.RETRIEVING
        assert tracker.get(op2).stage == OperationStage.GENERATING
        assert tracker.get(op3).stage == OperationStage.VALIDATING

    async def test_ttl_cleanup(self):
        """Test automatic cleanup after TTL."""
        tracker = OperationProgressTracker()
        operation_id = await tracker.start("query")

        # Complete with very short TTL
        await tracker._cleanup_after_ttl(operation_id, ttl_seconds=0)

        # Operation should be cleaned up
        assert tracker.get(operation_id) is None

    async def test_operation_types(self):
        """Test different operation types."""
        tracker = OperationProgressTracker()

        query_op = await tracker.start("query")
        summarize_op = await tracker.start("summarize")
        risks_op = await tracker.start("risks")

        assert tracker.get(query_op).operation_type == "query"
        assert tracker.get(summarize_op).operation_type == "summarize"
        assert tracker.get(risks_op).operation_type == "risks"


@pytest.mark.asyncio
class TestGetOperationTracker:
    """Tests for the global tracker singleton."""

    async def test_returns_same_instance(self):
        """Test that get_operation_tracker returns the same instance."""
        tracker1 = get_operation_tracker()
        tracker2 = get_operation_tracker()
        assert tracker1 is tracker2

    async def test_tracker_is_functional(self):
        """Test that the global tracker works correctly."""
        tracker = get_operation_tracker()
        operation_id = await tracker.start("query")

        await tracker.update(
            operation_id,
            OperationStage.RETRIEVING,
            0.25,
            "Test",
        )

        operation = tracker.get(operation_id)
        assert operation is not None
        assert operation.stage == OperationStage.RETRIEVING
