# Epic 10: Test Suite Review & Fixes

## Overview

Comprehensive review and cleanup of the test suite to ensure no regression on core and critical functionalities. This epic audits all test categories (unit, E2E, red team, evaluation, performance), identifies failing tests, removes unnecessary/redundant tests, and ensures best practices coverage without over-engineering.

## Prerequisites

- Epic 9 (Multilingual Fix) should be addressed first (may affect test expectations)
- All previous epics (1-8) completed
- Development environment functional (Docker, Qdrant, Ollama)

## Test Suite Inventory

| Category | Location | Files | Purpose |
|----------|----------|-------|---------|
| Unit Tests | `tests/test_*.py` | 16 | Component isolation testing |
| E2E Tests | `tests/e2e/` | 9 | End-to-end workflow validation |
| Red Team | `tests/red_team/` | 4 | Security/injection testing |
| Evaluation | `tests/evaluation/` | 6 | Quality metrics and benchmarks |
| Performance | `tests/performance/` | 3 | Speed and resource benchmarks |

## User Stories

---

## US 10.1: Test Audit & Inventory

**Status:** 🔶 In Progress

### Description

Perform a comprehensive audit of all tests to identify failures, duplicates, coverage gaps, and tests that are no longer needed. Create an inventory document with actionable findings.

### Context

Before fixing tests, we need to understand the current state:
- Which tests are failing and why?
- Are there duplicate tests covering the same functionality?
- What core functionality lacks test coverage?
- Are tests aligned with current implementation?

### Tasks

- [ ] Run full test suite and document results:
  - Execute `pytest tests/ -v --tb=short` and capture output
  - Categorize failures by type (import error, assertion, timeout, etc.)
  - Note skipped tests and reasons
- [ ] Create test inventory spreadsheet/table:
  - List each test file with test count
  - Mark status: passing, failing, skipped
  - Note dependencies (requires Ollama, Qdrant, etc.)
- [ ] Identify duplicate/redundant tests:
  - Tests covering identical functionality
  - Tests with overlapping assertions
  - Tests that could be parameterized
- [ ] Identify coverage gaps:
  - Core API endpoints without tests
  - Critical business logic untested
  - Edge cases not covered
- [ ] Create prioritized fix list:
  - P0: Blocking tests (prevent CI/CD)
  - P1: Core functionality tests
  - P2: Edge case and integration tests
  - P3: Nice-to-have improvements

### Acceptance Criteria

- [ ] Full test run completed and results documented
- [ ] Test inventory created with status for each test
- [ ] Duplicate tests identified and listed
- [ ] Coverage gaps documented
- [ ] Prioritized fix list created
- [ ] Findings documented in `tests/AUDIT.md`

### Files to Create/Modify

1. `tests/AUDIT.md` (new - audit findings and recommendations)

---

## US 10.2: Unit Test Fixes & Cleanup

**Status:** 🔲 Not Started

### Description

Fix failing unit tests, remove redundant tests, and ensure core component coverage. Unit tests should be fast, isolated, and not require external services (Qdrant, Ollama) to run.

### Context

Unit tests are the foundation of the test pyramid:
- Should run in <1 second each
- Should use mocks for external dependencies
- Should test one thing per test
- Should have clear naming: `test_<function>_<scenario>_<expected>`

### Tasks

- [ ] Fix failing unit tests (by file):
  - `test_chunking.py` - Text chunking logic
  - `test_embeddings.py` - Embedding generation
  - `test_classifier.py` - Intent classification
  - `test_context.py` - Context building
  - `test_retriever.py` - Retrieval logic
  - `test_guardrails.py` - Output validation
  - `test_pipeline.py` - RAG pipeline
  - `test_llm.py` - LLM client abstraction
  - `test_summarizer.py` - Summarization tool
  - `test_risk_detector.py` - Risk analysis tool
  - `test_diff.py` - Document comparison
  - `test_mcp.py` - MCP protocol
  - `test_sqlite.py` - Document registry
  - `test_agent_graph.py` - LangGraph state machine
  - `test_french_support.py` - French language support
  - `test_upload_progress.py` - Upload progress tracking
- [ ] Remove redundant tests:
  - Consolidate duplicate assertions
  - Parameterize similar test cases
  - Remove tests for deleted code
- [ ] Add missing mocks:
  - Mock Ollama calls in LLM tests
  - Mock Qdrant calls in retriever tests
  - Mock file I/O where appropriate
- [ ] Ensure test isolation:
  - No shared state between tests
  - Proper setup/teardown fixtures
  - No dependency on test execution order

### Implementation Guidelines

```python
# Good: Isolated unit test with mocks
@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock(spec=OllamaClient)
    client.generate.return_value = LLMResponse(
        content="Test response",
        model="test",
        tokens_used=10
    )
    return client

def test_summarizer_generates_summary(mock_llm_client):
    """Test that summarizer calls LLM and returns formatted summary."""
    summarizer = SummarizerTool(llm_client=mock_llm_client)
    result = summarizer.summarize("Test content")

    mock_llm_client.generate.assert_called_once()
    assert result.summary is not None

# Bad: Test depends on external service
def test_summarizer_with_real_ollama():  # DON'T DO THIS IN UNIT TESTS
    summarizer = SummarizerTool()
    result = summarizer.summarize("Test content")
    assert result.summary is not None
```

### Acceptance Criteria

- [ ] All unit tests pass (`pytest tests/test_*.py`)
- [ ] Unit tests run in <60 seconds total
- [ ] No unit test requires Ollama or Qdrant running
- [ ] Redundant tests removed or consolidated
- [ ] Test names follow convention
- [ ] Each test has clear purpose documented

### Files to Modify

1. `tests/test_*.py` (all 16 unit test files)
2. `tests/conftest.py` (shared fixtures)

---

## US 10.3: E2E & Integration Test Fixes

**Status:** 🔲 Not Started

### Description

Fix failing E2E tests that validate real user workflows. E2E tests may require external services but should use test fixtures and have reasonable timeouts.

### Context

E2E tests validate complete user journeys:
- Upload document → Query → Get answer with citations
- Upload → Summarize → Get summary
- Upload → Risk analysis → Get risk report
- Upload two docs → Compare → Get comparison

These tests are slower but critical for confidence in deployments.

### Tasks

- [ ] Fix E2E test infrastructure:
  - Update `tests/e2e/conftest.py` fixtures
  - Ensure test documents exist in `tests/fixtures/`
  - Configure appropriate timeouts (Ollama can be slow)
- [ ] Fix E2E tests by file:
  - `test_upload_query.py` - Upload and query workflow
  - `test_analysis.py` - Risk analysis and summarization
  - `test_comparison.py` - Document comparison
  - `test_error_handling.py` - Error scenarios
  - `test_guardrails.py` - Security guardrails in E2E
  - `test_multilingual.py` - French/English workflows
  - `test_french_workflow.py` - French-specific scenarios
  - `test_upload_progress.py` - SSE progress tracking
- [ ] Update test expectations:
  - Align with current API response schemas
  - Update for multilingual responses
  - Handle confidence level variations
- [ ] Add skip markers for service-dependent tests:
  - `@pytest.mark.requires_ollama`
  - `@pytest.mark.requires_qdrant`
  - Enable selective test runs

### Implementation Guidelines

```python
# Good: E2E test with proper markers and timeout
@pytest.mark.e2e
@pytest.mark.requires_ollama
@pytest.mark.timeout(120)
async def test_upload_and_query_english_pdf(api_client, test_data_dir):
    """Test complete upload → query workflow for English PDF."""
    # Upload document
    doc_id = await upload_document(api_client, test_data_dir / "sample_contract_en.pdf")

    # Query document
    response = await api_client.post("/query", json={
        "document_id": doc_id,
        "question": "What is the termination notice period?"
    })

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data.get("citations", [])) > 0
```

### Acceptance Criteria

- [ ] All E2E tests pass with services running
- [ ] Tests have appropriate timeouts
- [ ] Service-dependent tests are skipped when services unavailable
- [ ] Test fixtures (sample documents) are complete
- [ ] Tests cover both English and French workflows
- [ ] Error handling scenarios validated

### Files to Modify

1. `tests/e2e/*.py` (all 9 E2E test files)
2. `tests/e2e/conftest.py` (fixtures)
3. `tests/e2e/utils.py` (helper functions)
4. `tests/fixtures/` (test documents)

---

## US 10.4: Specialized Test Suites Review

**Status:** 🔲 Not Started

### Description

Review and fix the red team, evaluation, and performance test suites. These are less critical for day-to-day development but important for security validation and quality benchmarking.

### Context

These specialized suites serve specific purposes:
- **Red Team**: Validate security against prompt injection, hallucination, edge cases
- **Evaluation**: Measure RAG quality metrics (precision, recall, faithfulness)
- **Performance**: Benchmark response times and resource usage

### Tasks

- [ ] Review red team tests (`tests/red_team/`):
  - `injection.py` - Prompt injection attempts
  - `hallucination.py` - Hallucination detection
  - `edge_cases.py` - Boundary conditions
  - Fix failing tests or update expectations
  - Remove tests for scenarios no longer relevant
  - Ensure tests are deterministic
- [ ] Review evaluation harness (`tests/evaluation/`):
  - `metrics.py` - Quality metrics calculation
  - `runner.py` - Evaluation runner
  - `dataset.py` - Test dataset handling
  - `report.py` - Report generation
  - `french_report.py` - French evaluation
  - Fix import errors and dependencies
  - Update for current API schemas
- [ ] Review performance tests (`tests/performance/`):
  - `benchmarks.py` - Performance benchmarks
  - `report.py` - Performance report
  - Fix or update benchmark thresholds
  - Ensure benchmarks are meaningful
- [ ] Document how to run each suite:
  - Add run instructions to each `__main__.py`
  - Document required services
  - Document expected runtime

### Acceptance Criteria

- [ ] Red team tests execute without errors
- [ ] Evaluation harness produces meaningful metrics
- [ ] Performance benchmarks complete with reports
- [ ] Each suite has documented run instructions
- [ ] Flaky tests identified and stabilized
- [ ] Unnecessary tests removed

### Files to Modify

1. `tests/red_team/*.py` (4 files)
2. `tests/evaluation/*.py` (6 files)
3. `tests/performance/*.py` (3 files)
4. `tests/red_team/__main__.py`
5. `tests/evaluation/__main__.py`
6. `tests/performance/__main__.py`

---

## US 10.5: Unnecessary Tests Removal (User Approval Required)

**Status:** 🔲 Not Started

### Description

Generate a comprehensive report of tests that are unnecessary, redundant, or over-engineered, then **present to the user for approval before any deletion**. This ensures no valuable tests are accidentally removed.

### Context

Too many tests is NOT a best practice:
- Increases maintenance burden
- Slows CI/CD pipelines
- Creates false sense of security (quantity ≠ quality)
- Can mask real issues with noise

Tests that may be candidates for removal:
- **Duplicate tests**: Multiple tests verifying identical behavior
- **Trivial tests**: Testing obvious behavior (e.g., getter returns value)
- **Over-mocked tests**: So many mocks that nothing real is tested
- **Dead code tests**: Tests for removed/deprecated features
- **Flaky tests**: Intermittently failing tests that provide no confidence
- **Over-specific tests**: Testing implementation details instead of behavior

### Tasks

- [ ] Generate removal report (`tests/REMOVAL_REPORT.md`):
  - List each test recommended for removal
  - Explain WHY it should be removed (category from above)
  - Show what functionality (if any) is still covered elsewhere
  - Group by test file for easy review
- [ ] Calculate impact metrics:
  - Number of tests to remove
  - Estimated CI time savings
  - Remaining coverage of core functionality
- [ ] **STOP and present report to user**:
  - Show full report in conversation
  - Ask: "Do you approve removing these X tests?"
  - Wait for explicit user confirmation
- [ ] Only after user approval:
  - Delete approved tests
  - Update `tests/AUDIT.md` with removal summary
  - Commit with clear message listing removed tests

### Report Format

```markdown
# Test Removal Report

## Summary

- **Total tests analyzed:** X
- **Recommended for removal:** Y
- **Estimated CI time savings:** Z seconds

## Removal Recommendations

### Category 1: Duplicate Tests (X tests)

| Test File | Test Name | Reason | Covered By |
|-----------|-----------|--------|------------|
| test_foo.py | test_bar_works | Duplicate | test_bar_success |

### Category 2: Trivial Tests (X tests)

| Test File | Test Name | Reason |
|-----------|-----------|--------|
| test_config.py | test_setting_exists | Tests obvious getter |

### Category 3: Dead Code Tests (X tests)

| Test File | Test Name | Reason |
|-----------|-----------|--------|
| test_old_feature.py | test_deprecated_api | Feature removed in Epic 5 |

### Category 4: Over-Mocked Tests (X tests)

| Test File | Test Name | Reason |
|-----------|-----------|--------|
| test_integration.py | test_full_pipeline | 100% mocked, tests nothing real |

### Category 5: Flaky Tests (X tests)

| Test File | Test Name | Reason |
|-----------|-----------|--------|
| test_async.py | test_race_condition | Fails 20% of runs |

## Tests to KEEP (Justification)

Brief explanation of why remaining tests are valuable.

---

**ACTION REQUIRED:** Review this report and confirm removal.
```

### Acceptance Criteria

- [ ] Removal report generated with all categories
- [ ] Each recommendation has clear justification
- [ ] Report shows what coverage remains after removal
- [ ] **Report presented to user before any deletion**
- [ ] **User explicitly approves removal**
- [ ] Only approved tests are deleted
- [ ] Deletion commit has descriptive message
- [ ] `tests/AUDIT.md` updated with removal summary

### Tests

- **None:** This US is about reviewing/removing tests, not adding them
- **Run:** After removal, run `pytest tests/ -v` to ensure no breakage

> Note: **CRITICAL** - Never delete tests without user approval. Present report and WAIT.

### Files to Create/Modify

1. `tests/REMOVAL_REPORT.md` (new - removal recommendations)
2. `tests/AUDIT.md` (modify - add removal summary)
3. Various `tests/*.py` files (delete approved tests only)

---

## Definition of Done (Epic 10)

- [ ] All User Stories completed (5/5)
- [ ] Test audit document created (`tests/AUDIT.md`)
- [ ] All unit tests pass
- [ ] All E2E tests pass (with services)
- [ ] Specialized test suites functional
- [ ] No redundant tests remain
- [ ] Test coverage maintains core functionality
- [ ] Tests follow best practices (naming, isolation, mocking)
- [ ] CI-compatible (can run without manual intervention)
- [ ] Documentation updated

## Test Best Practices Reference

### Naming Convention
```
test_<function/feature>_<scenario>_<expected_result>
```
Examples:
- `test_chunker_empty_input_returns_empty_list`
- `test_query_nonexistent_document_returns_404`
- `test_guardrails_injection_attempt_blocked`

### Test Pyramid
```
        /\
       /  \  E2E (few, slow, high confidence)
      /----\
     /      \ Integration (some, moderate speed)
    /--------\
   /          \ Unit (many, fast, isolated)
  /______________\
```

### What NOT to Test
- External library internals (trust them to work)
- Trivial getters/setters
- Framework behavior (FastAPI routing works)
- Implementation details (test behavior, not structure)

### What TO Test
- Business logic
- Edge cases and error handling
- Integration points
- Security boundaries
- User-facing behavior

## Dependencies

```
US 10.1 (Audit)
    ↓
US 10.2 (Unit Tests) ←→ US 10.3 (E2E Tests)
    ↓                     ↓
US 10.4 (Specialized Suites)
```

US 10.1 must be completed first to inform the other stories.
US 10.2 and 10.3 can be done in parallel after the audit.
US 10.4 can start after 10.2 and 10.3 provide stable foundations.
