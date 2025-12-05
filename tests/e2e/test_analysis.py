"""End-to-end tests for risk analysis and summarization."""
import pytest

from tests.e2e.utils import (
    assert_summary_response_valid,
    assert_risk_response_valid,
)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risk_analysis_english(api_client, sample_contract_en_pdf):
    """Test risk analysis functionality for English document."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    assert response.status_code == 200
    data = response.json()

    assert_risk_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risk_analysis_french(api_client, sample_contract_fr_pdf):
    """Test risk analysis functionality for French document."""
    doc_id = sample_contract_fr_pdf

    response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    assert response.status_code == 200
    data = response.json()

    assert_risk_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_executive_summary(api_client, sample_contract_en_pdf):
    """Test executive summary generation."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_summary_response_valid(data)

    # Executive summary should be concise but informative
    summary_length = len(data["summary"])
    assert 100 <= summary_length <= 2000, \
        f"Executive summary length {summary_length} not in expected range [100-2000]"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_detailed_summary(api_client, sample_contract_en_pdf):
    """Test detailed summary generation."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "detailed"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_summary_response_valid(data)

    # Detailed summary should be longer
    summary_length = len(data["summary"])
    assert summary_length >= 200, \
        f"Detailed summary too short: {summary_length} chars"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risk_severity_levels(api_client, sample_contract_en_pdf):
    """Test that risks are categorized with appropriate severity levels."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    assert response.status_code == 200
    data = response.json()

    # Check that severity levels are valid
    valid_severities = ["low", "medium", "high", "critical"]

    for risk in data["risks"]:
        assert risk["severity"] in valid_severities, \
            f"Invalid severity level: {risk['severity']}"

        # Description should be substantial
        assert len(risk["description"]) > 20, \
            "Risk description too short"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risk_categories(api_client, sample_contract_en_pdf):
    """Test that risks are properly categorized."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    assert response.status_code == 200
    data = response.json()

    # Each risk should have a meaningful category
    for risk in data["risks"]:
        assert len(risk["category"]) > 0, "Risk category cannot be empty"
        assert isinstance(risk["category"], str), "Category must be string"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_summary_key_points(api_client, sample_contract_en_pdf):
    """Test that summaries include key points."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Should include key points
    if "key_points" in data:
        assert len(data["key_points"]) >= 3, \
            "Should have at least 3 key points"

        for point in data["key_points"]:
            assert len(point) > 10, "Key point too short"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_analysis_workflow_complete(api_client, sample_contract_en_pdf):
    """Test complete analysis workflow: summarize + risks."""
    doc_id = sample_contract_en_pdf

    # Get summary
    summary_response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive"
        }
    )

    # Get risks
    risks_response = await api_client.post(
        "/risks",
        json={"document_id": doc_id}
    )

    # Both should succeed
    assert summary_response.status_code == 200
    assert risks_response.status_code == 200

    summary_data = summary_response.json()
    risks_data = risks_response.json()

    # Validate both responses
    assert_summary_response_valid(summary_data)
    assert_risk_response_valid(risks_data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_risk_analysis(api_client, sample_contract_fr_pdf):
    """Test risk analysis returns French results for French documents."""
    doc_id = sample_contract_fr_pdf

    response = await api_client.post(
        "/risks",
        json={
            "document_id": doc_id,
            "language": "fr"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_risk_response_valid(data)

    # Risk descriptions should contain French text
    # (at least some French words should appear)
    if len(data["risks"]) > 0:
        all_text = " ".join(risk["description"] for risk in data["risks"])
        # Basic check: should contain common French words
        assert any(word in all_text.lower() for word in ["le", "la", "de", "et", "des"]), \
            "Risk analysis should contain French text for French document"
