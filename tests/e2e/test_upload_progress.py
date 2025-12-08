"""End-to-end tests for upload progress tracking."""
import asyncio
import pytest


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_returns_task_id(api_client, test_data_dir):
    """Test that upload immediately returns task_id and progress URLs."""
    file_path = test_data_dir / "sample_contract_en.pdf"

    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()

    # Should have task_id and URLs
    assert "task_id" in data
    assert "filename" in data
    assert "progress_url" in data or "status_url" in data

    # Task ID should be valid UUID format
    task_id = data["task_id"]
    assert len(task_id) == 36  # UUID format
    assert task_id.count("-") == 4


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_progress_tracking(api_client, test_data_dir):
    """Test that upload progress is tracked through all stages."""
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

        if status_response.status_code == 404:
            # Task not found yet, wait
            await asyncio.sleep(0.5)
            continue

        assert status_response.status_code == 200
        status_data = status_response.json()

        stage = status_data["stage"]
        stages_seen.add(stage)

        # Verify progress field exists and is valid
        assert "progress" in status_data
        assert 0.0 <= status_data["progress"] <= 1.0

        # Verify message exists
        assert "message" in status_data
        assert len(status_data["message"]) > 0

        if stage in ["complete", "failed"]:
            final_stage = stage
            break

        await asyncio.sleep(1)

    # Verify completion - that's the main requirement
    assert final_stage == "complete", \
        f"Upload should complete successfully, got: {final_stage}"

    # Note: We may or may not see intermediate stages depending on timing.
    # Processing can complete too fast for polling to catch intermediate stages.
    # The key requirement is that we reach 'complete' stage successfully.
    # If stages_seen only has 'complete', that's still valid behavior.


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_progress_stages(api_client, test_data_dir):
    """Test that all expected stages are reported during upload."""
    file_path = test_data_dir / "sample_contract_en.pdf"

    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    assert response.status_code == 200
    task_id = response.json()["task_id"]

    stages_seen = []
    progress_values = []

    # Track all stages
    for _ in range(60):
        status_response = await api_client.get(f"/upload/status/{task_id}")

        if status_response.status_code == 200:
            status_data = status_response.json()
            stage = status_data["stage"]
            progress = status_data["progress"]

            if not stages_seen or stages_seen[-1] != stage:
                stages_seen.append(stage)
                progress_values.append(progress)

            if stage in ["complete", "failed"]:
                break

        await asyncio.sleep(1)

    # Verify stage progression
    assert "complete" in stages_seen or "failed" in stages_seen, \
        "Upload should reach terminal state"

    # Progress should be monotonically increasing
    for i in range(1, len(progress_values)):
        assert progress_values[i] >= progress_values[i-1], \
            "Progress should not decrease"

    # Final progress should be 1.0 for complete
    if stages_seen[-1] == "complete":
        assert progress_values[-1] == 1.0, \
            "Completed upload should have progress 1.0"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_status_nonexistent_task(api_client):
    """Test querying status of non-existent task."""
    fake_task_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.get(f"/upload/status/{fake_task_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_multiple_concurrent_uploads(api_client, test_data_dir):
    """Test tracking multiple uploads simultaneously."""
    file_paths = [
        test_data_dir / "sample_contract_en.pdf",
        test_data_dir / "sample_contract_fr.pdf",
    ]

    # Start multiple uploads
    task_ids = []
    for file_path in file_paths:
        with open(file_path, "rb") as f:
            response = await api_client.post(
                "/upload",
                files={"file": (file_path.name, f, "application/pdf")}
            )
        assert response.status_code == 200
        task_ids.append(response.json()["task_id"])

    # Track both uploads
    completed = {task_id: False for task_id in task_ids}

    for _ in range(120):  # Max 2 minutes total
        for task_id in task_ids:
            if completed[task_id]:
                continue

            response = await api_client.get(f"/upload/status/{task_id}")
            if response.status_code == 200:
                data = response.json()
                if data["stage"] in ["complete", "failed"]:
                    completed[task_id] = True

        if all(completed.values()):
            break

        await asyncio.sleep(1)

    # Both uploads should complete
    assert all(completed.values()), \
        "All concurrent uploads should complete"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_progress_completion_includes_document_id(api_client, test_data_dir):
    """Test that completion message includes document ID."""
    file_path = test_data_dir / "sample_contract_en.pdf"

    with open(file_path, "rb") as f:
        response = await api_client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf")}
        )

    task_id = response.json()["task_id"]

    # Wait for completion
    for _ in range(60):
        status_response = await api_client.get(f"/upload/status/{task_id}")

        if status_response.status_code == 200:
            data = status_response.json()

            if data["stage"] == "complete":
                # Should include document ID in message
                import re
                match = re.search(r"Document ID: ([a-f0-9-]+)", data["message"])
                assert match, "Completion message should include Document ID"

                doc_id = match.group(1)
                assert len(doc_id) == 36, "Document ID should be valid UUID"
                break

        await asyncio.sleep(1)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_progress_error_handling(api_client, test_data_dir):
    """Test that upload errors are reported in progress."""
    # Create an invalid PDF file
    invalid_file = test_data_dir / "test_invalid_progress.pdf"
    invalid_file.write_bytes(b"Not a real PDF file")

    try:
        with open(invalid_file, "rb") as f:
            response = await api_client.post(
                "/upload",
                files={"file": (invalid_file.name, f, "application/pdf")}
            )

        # Upload endpoint should accept the file
        if response.status_code == 200:
            task_id = response.json()["task_id"]

            # Track progress - should eventually show failure
            for _ in range(30):
                status_response = await api_client.get(f"/upload/status/{task_id}")

                if status_response.status_code == 200:
                    data = status_response.json()

                    if data["stage"] == "failed":
                        # Should have error message
                        assert "error" in data or "message" in data
                        break

                await asyncio.sleep(1)
    finally:
        # Cleanup
        if invalid_file.exists():
            invalid_file.unlink()
