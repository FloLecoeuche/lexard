# End-to-End Testing Guide

## Overview

Lexard includes a comprehensive end-to-end (E2E) test suite that validates the complete system functionality through nominal use cases. These tests verify the entire pipeline from document upload to query responses, in both English and French.

## Test Coverage

The E2E test suite covers the following scenarios:

### 1. Document Upload and Query (`test_upload_query.py`)

- Upload English documents (PDF and DOCX)
- Query uploaded documents
- Document summarization (executive and detailed)
- Multiple queries on the same document
- Confidence level validation
- Citation quality checks

### 2. Multilingual Support (`test_multilingual.py`)

- French document upload and query (PDF and DOCX)
- French summarization
- Cross-language quality comparison
- Automatic language detection
- Mixed language document handling

### 3. Risk Analysis & Summarization (`test_analysis.py`)

- Risk analysis for English and French documents
- Executive summary generation
- Detailed summary generation
- Risk severity level categorization
- Key points extraction
- Complete analysis workflow

### 4. Document Comparison (`test_comparison.py`)

- Compare two English documents
- Compare English and French documents
- Compare two French documents
- Comparison difference details
- Same document comparison
- Multi-document comparison workflow

### 5. Guardrails Validation (`test_guardrails.py`)

- Prompt injection detection (English and French)
- Hallucination prevention
- Out-of-scope question handling
- PII redaction in responses
- Citation requirement enforcement
- Malformed input rejection
- Confidence threshold enforcement

### 6. Error Handling (`test_error_handling.py`)

- Query non-existent document
- Upload invalid file formats
- Upload empty files
- Missing required fields
- Invalid document ID formats
- Malformed JSON requests
- Health endpoint availability
- Error response trace_id validation

### 7. Upload Progress Tracking (`test_upload_progress.py`)

- Upload returns task_id
- Progress tracking through all stages
- Stage progression validation
- Multiple concurrent uploads
- Completion message includes document ID
- Error handling in progress

## Prerequisites

### Required Services

E2E tests require the following services to be running:

1. **Qdrant** - Vector database (port 6333)
2. **Ollama** - LLM service (port 11434) with `mistral:7b-instruct` model

### Test Fixtures

Test fixtures are located in `data/test/`:

- `contract_nda_en.pdf` / `contract_nda_en.docx` - English NDA contract
- `contract_service_en.pdf` / `contract_service_en.docx` - English service contract
- `contrat_nda_fr.pdf` / `contrat_nda_fr.docx` - French NDA contract
- `contrat_service_fr.pdf` / `contrat_service_fr.docx` - French service contract

## Running Tests Locally

### 1. Start Required Services

```bash
# Start Qdrant and Ollama
docker-compose up -d

# Verify services are healthy
curl http://localhost:6333/health
curl http://localhost:11434/api/tags

# Pull the LLM model (if not already present)
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

### 2. Install Test Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"
```

### 3. Run E2E Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v -m e2e

# Run specific test file
pytest tests/e2e/test_upload_query.py -v

# Run specific test
pytest tests/e2e/test_upload_query.py::test_upload_and_query_english_pdf -v

# Run with detailed output
pytest tests/e2e/ -v -m e2e -s

# Run with maximum 5 failures
pytest tests/e2e/ -v -m e2e --maxfail=5
```

### 4. Run Tests with Coverage

```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage report
pytest tests/e2e/ -v -m e2e --cov=src --cov-report=html --cov-report=term

# View HTML coverage report
open htmlcov/index.html
```

## Test Markers

Tests are organized using pytest markers defined in `pytest.ini`:

- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.requires_services` - Tests requiring external services

### Running Specific Test Categories

```bash
# Run only E2E tests
pytest -m e2e

# Run all except E2E tests
pytest -m "not e2e"

# Run slow tests only
pytest -m slow

# Run tests requiring services
pytest -m requires_services
```

## Continuous Integration

E2E tests run automatically in GitHub Actions on:

- Push to `develop` or `main` branches
- Pull requests to `develop` or `main` branches

The CI workflow (`.github/workflows/e2e-tests.yml`):

1. Starts Qdrant and Ollama services
2. Pulls the required LLM model
3. Runs the E2E test suite
4. Generates and uploads test reports
5. Cleans up services

### Viewing CI Test Results

1. Navigate to the GitHub Actions tab
2. Select the workflow run
3. Download test artifacts:
   - `e2e-test-results` - JUnit XML results
   - `e2e-test-report` - HTML test report

## Test Fixtures and Helpers

### Fixtures (`tests/e2e/conftest.py`)

- `api_client` - Async HTTP client for API calls
- `test_data_dir` - Path to test data directory (`data/test/`)
- `sample_contract_en_pdf` - Uploaded English NDA PDF (returns doc_id)
- `sample_contract_en_docx` - Uploaded English NDA DOCX (returns doc_id)
- `sample_contract_fr_pdf` - Uploaded French NDA PDF (returns doc_id)
- `sample_contract_fr_docx` - Uploaded French NDA DOCX (returns doc_id)

### Helper Functions (`tests/e2e/utils.py`)

- `assert_query_response_valid(data)` - Validate query response structure
- `assert_summary_response_valid(data)` - Validate summary response
- `assert_risk_response_valid(data)` - Validate risk analysis response
- `assert_comparison_response_valid(data)` - Validate comparison response
- `assert_error_response_valid(data, expected_code)` - Validate error response
- `contains_french_text(text)` - Check if text is in French

## Writing New E2E Tests

### Test Template

```python
import pytest
from tests.e2e.utils import assert_query_response_valid


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_my_new_feature(api_client, sample_contract_en_pdf):
    """Test description."""
    doc_id = sample_contract_en_pdf

    # Make API call
    response = await api_client.post(
        "/endpoint",
        json={"document_id": doc_id, "param": "value"}
    )

    # Validate response
    assert response.status_code == 200
    data = response.json()

    # Use helper to validate structure
    assert_query_response_valid(data)

    # Additional assertions
    assert "expected_field" in data
```

### Best Practices

1. **Use fixtures** - Leverage existing fixtures for document upload
2. **Use helpers** - Use validation helpers from `utils.py`
3. **Mark tests** - Always add `@pytest.mark.e2e` and `@pytest.mark.asyncio`
4. **Descriptive names** - Use clear test function names
5. **Document tests** - Add docstrings explaining what is tested
6. **Assert meaningfully** - Include helpful assertion messages
7. **Clean up** - Clean up any temporary files created during tests

## Troubleshooting

### Tests Fail with "Connection Refused"

**Cause:** Services not running or not ready

**Solution:**

```bash
# Check service status
docker-compose ps

# Check service logs
docker-compose logs qdrant
docker-compose logs ollama

# Restart services
docker-compose restart
```

### Tests Timeout During Upload

**Cause:** LLM model not loaded or slow embedding generation

**Solution:**

```bash
# Verify model is loaded
docker exec -it lexard-ollama ollama list

# Pull model if missing
docker exec -it lexard-ollama ollama pull mistral:7b-instruct

# Increase timeout in test if needed (edit conftest.py)
```

### Fixture Upload Fails

**Cause:** Corrupted or missing test fixtures

**Solution:**

```bash
# Verify fixtures exist
ls -lh data/test/contract_*.pdf
ls -lh data/test/contrat_*.pdf

# Re-add fixtures if missing
```

### Import Errors

**Cause:** Dependencies not installed or virtual environment not activated

**Solution:**

```bash
# Activate virtual environment
source .venv/bin/activate

# Reinstall dependencies
pip install -e ".[dev]"
```

## Performance Benchmarks

Expected execution times (on standard hardware with CPU inference):

- Individual upload test: 15-25 seconds
- Individual query test (with LLM): 60-180 seconds (varies by CPU speed)
- Complete test suite: 30-60 minutes
- CI pipeline: 45-90 minutes (includes service setup)

**Note:** LLM query tests are slow due to CPU-based inference in Ollama. The timeout is set to 180 seconds to accommodate slower systems. Tests with GPU acceleration will be significantly faster.

Tests exceeding these times should be investigated for:

- Service availability issues
- Network connectivity problems
- Resource constraints (ensure Docker has 24GB+ RAM for Ollama)
- Inefficient test implementation
- Concurrent test execution causing resource contention

## Test Data Privacy

**Important:** Test fixtures should NOT contain real PII or sensitive data. All test documents should use:

- Fictional names and addresses
- Fake SSNs, phone numbers, IBANs
- Sample contract terms
- Public domain or generated content

## Maintenance

### Updating Test Fixtures

When updating test fixtures:

1. Update files in `data/test/`
2. Ensure new files maintain naming convention (English: `contract_*_en.*`, French: `contrat_*_fr.*`)
3. Verify all tests still pass
4. Update this documentation if structure changes

### Adding New Test Scenarios

When adding new scenarios:

1. Create new test file in `tests/e2e/`
2. Follow naming convention: `test_<scenario>.py`
3. Add necessary fixtures to `conftest.py`
4. Add helper functions to `utils.py` if needed
5. Update this documentation

### Reviewing Test Coverage

```bash
# Generate coverage report
pytest tests/e2e/ -m e2e --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html

# Review uncovered lines and add tests as needed
```

## Support

For issues with E2E tests:

1. Check this documentation
2. Review test logs and error messages
3. Verify service health and connectivity
4. Check GitHub Actions logs for CI failures
5. Report issues at the project's GitHub repository
