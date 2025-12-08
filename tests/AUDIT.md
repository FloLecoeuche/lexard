# Test Suite Audit Report

**Date:** 2025-12-08
**Epic:** 10 - Test Suite Review
**US:** 10.1 - Test Audit & Inventory

## Executive Summary

Total tests collected: **541 tests** across unit, integration, and E2E test suites.

| Category          | Tests | Status                    |
| ----------------- | ----- | ------------------------- |
| Unit Tests        | 429   | All passing               |
| Integration Tests | 40    | All passing               |
| E2E Tests         | 72    | Require running services  |
| Red Team          | N/A   | Script-based (not pytest) |
| Evaluation        | N/A   | Script-based (not pytest) |
| Performance       | N/A   | Script-based (not pytest) |

## Test Suite Inventory

### Unit Tests (429 tests total)

| File                    | Tests | Status | Dependencies                        |
| ----------------------- | ----- | ------ | ----------------------------------- |
| test_agent_graph.py     | 22    | PASS   | None (mocked)                       |
| test_chunking.py        | 13    | PASS   | None                                |
| test_classifier.py      | 43    | PASS   | None                                |
| test_context.py         | 20    | PASS   | None                                |
| test_diff.py            | 40    | PASS   | None (mocked)                       |
| test_embeddings.py      | 21    | PASS   | sentence-transformers (lazy loaded) |
| test_french_support.py  | 33    | PASS   | langdetect                          |
| test_guardrails.py      | 28    | PASS   | None                                |
| test_llm.py             | 46    | PASS   | None (mocked)                       |
| test_mcp.py             | 13    | PASS   | None (mocked)                       |
| test_migration.py       | 5     | PASS   | None (mocked)                       |
| test_pipeline.py        | 23    | PASS   | None (mocked)                       |
| test_retriever.py       | 17    | PASS   | None (mocked)                       |
| test_risk_detector.py   | 44    | PASS   | None (mocked)                       |
| test_sqlite.py          | 23    | PASS   | SQLite (in-memory)                  |
| test_summarizer.py      | 30    | PASS   | None (mocked)                       |
| test_upload_progress.py | 8     | PASS   | None                                |

### Integration Tests (40 tests)

| File                                | Tests | Status | Dependencies |
| ----------------------------------- | ----- | ------ | ------------ |
| integration/test_french_workflow.py | 40    | PASS   | langdetect   |

### E2E Tests (72 tests)

| File                        | Tests | Status            | Dependencies        |
| --------------------------- | ----- | ----------------- | ------------------- |
| e2e/test_analysis.py        | 9     | Requires services | Ollama, Qdrant, API |
| e2e/test_comparison.py      | 7     | Requires services | Ollama, Qdrant, API |
| e2e/test_error_handling.py  | 14    | Requires services | API                 |
| e2e/test_french_workflow.py | 20    | Requires services | Ollama, Qdrant, API |
| e2e/test_guardrails.py      | 5     | Requires services | Ollama, Qdrant, API |
| e2e/test_multilingual.py    | 5     | Requires services | Ollama, Qdrant, API |
| e2e/test_upload_progress.py | 5     | Requires services | API                 |
| e2e/test_upload_query.py    | 7     | Requires services | Ollama, Qdrant, API |

### Specialized Test Suites (Non-pytest)

These test suites use custom runners and are not pytest-compatible:

| Suite       | Location           | Files                                         | Purpose          |
| ----------- | ------------------ | --------------------------------------------- | ---------------- |
| Red Team    | tests/red_team/    | injection.py, hallucination.py, edge_cases.py | Security testing |
| Evaluation  | tests/evaluation/  | metrics.py, runner.py, dataset.py, report.py  | Quality metrics  |
| Performance | tests/performance/ | benchmarks.py, report.py                      | Speed benchmarks |

**Note:** These suites collected 0 tests via pytest because they don't use pytest test functions - they use custom runner classes.

## Duplicate/Redundant Tests Analysis

### Identified Overlaps

1. **French Language Detection Tests (Potential Duplication)**

   - `test_french_support.py::TestLanguageDetection` (4 tests)
   - `integration/test_french_workflow.py::TestLanguageDetection` (12 tests)
   - **Overlap:** Both test `detect_language()` function
   - **Recommendation:** Integration tests are more thorough; unit tests may be redundant

2. **Bilingual Prompt Tests (Potential Duplication)**

   - `test_french_support.py::TestFrenchPrompts` (9 tests)
   - `test_llm.py::TestBilingualPrompts` (7 tests)
   - `integration/test_french_workflow.py::TestBilingualPrompts` (10 tests)
   - **Overlap:** All test prompt selection by language
   - **Recommendation:** Consolidate - keep integration tests, review unit tests for unique value

3. **Classifier Tests (Well-organized but verbose)**

   - `test_classifier.py` has 43 tests
   - Many are simple keyword detection tests that could be parameterized
   - **Recommendation:** Consider parameterizing similar test cases

4. **Risk Detector Tests (Extensive)**
   - `test_risk_detector.py` has 44 tests
   - Good coverage but some overlap with E2E tests
   - **Status:** Keep as is - comprehensive unit testing is valuable

### Tests That Could Be Parameterized

| File                   | Current Tests | Could Reduce To                      |
| ---------------------- | ------------- | ------------------------------------ |
| test_classifier.py     | 43            | ~20 (using @pytest.mark.parametrize) |
| test_french_support.py | 33            | ~20 (using @pytest.mark.parametrize) |

## Coverage Gaps

### Source Files Without Dedicated Tests

| Source File                        | Test Coverage           | Gap                        |
| ---------------------------------- | ----------------------- | -------------------------- |
| src/api/exceptions.py              | Implicit (via routes)   | No dedicated tests         |
| src/api/logging.py                 | None                    | Missing tests              |
| src/api/main.py                    | None                    | Missing tests (app config) |
| src/api/middleware.py              | Implicit (via routes)   | No dedicated tests         |
| src/api/progress.py                | test_upload_progress.py | Partial                    |
| src/api/routes/analysis.py         | E2E only                | No unit tests              |
| src/api/routes/documents.py        | E2E only                | No unit tests              |
| src/api/routes/query.py            | E2E only                | No unit tests              |
| src/api/routes/static.py           | None                    | Missing tests              |
| src/api/schemas.py                 | Implicit                | No dedicated tests         |
| src/config.py                      | None                    | Missing tests              |
| src/db/qdrant.py                   | Implicit (mocked)       | No dedicated tests         |
| src/guardrails/hallucination.py    | test_guardrails.py      | Partial                    |
| src/guardrails/pii.py              | test_french_support.py  | Partial                    |
| src/guardrails/prompt_injection.py | test_classifier.py      | Partial                    |
| src/guardrails/schema.py           | None                    | Missing tests              |
| src/mcp/errors.py                  | test_mcp.py             | Partial                    |
| src/mcp/methods.py                 | test_mcp.py             | Partial                    |
| src/mcp/schemas.py                 | None                    | Missing tests              |
| src/mcp/server.py                  | test_mcp.py             | Partial                    |
| src/rag/extractors/\*.py           | None                    | Missing tests              |
| src/rag/normalize.py               | None                    | Missing tests              |
| src/agent/prompts.py               | Implicit                | No dedicated tests         |
| src/agent/state.py                 | test_agent_graph.py     | Partial                    |

### Critical Gaps (P0)

1. **No API route unit tests** - All API testing is E2E
2. **No text extractor tests** - PDF, DOCX, TXT extractors untested
3. **No config validation tests** - Config loading/validation untested

### Important Gaps (P1)

1. **No Qdrant service tests** - Only mocked in other tests
2. **No logging tests** - Structured logging untested
3. **No middleware tests** - Error handling middleware untested

## Prioritized Fix List

### P0 - Blocking Issues

| Issue                                                 | Impact           | Recommendation                                     |
| ----------------------------------------------------- | ---------------- | -------------------------------------------------- |
| Red team/evaluation/performance not pytest-compatible | Cannot run in CI | Convert to pytest or add **main** run instructions |

### P1 - Core Functionality

| Issue                        | Impact                    | Recommendation               |
| ---------------------------- | ------------------------- | ---------------------------- |
| Missing text extractor tests | PDF/DOCX parsing untested | Add tests/test_extractors.py |
| Missing config tests         | Config errors not caught  | Add tests/test_config.py     |
| Missing Qdrant tests         | DB operations untested    | Add tests/test_qdrant.py     |

### P2 - Edge Cases & Integration

| Issue                    | Impact                 | Recommendation                      |
| ------------------------ | ---------------------- | ----------------------------------- |
| Duplicate language tests | Maintenance burden     | Consolidate to integration tests    |
| Verbose classifier tests | Slow test runs         | Parameterize test cases             |
| Missing API route tests  | Routes only E2E tested | Add unit tests with mocked services |

### P3 - Nice-to-Have

| Issue                 | Impact                      | Recommendation                    |
| --------------------- | --------------------------- | --------------------------------- |
| Missing logging tests | Structured logging untested | Add tests if time permits         |
| Missing schema tests  | Pydantic models untested    | Low priority - Pydantic validates |

## Test Execution Summary

```
Test Run: 2025-12-08
Command: pytest tests/ -v --ignore=tests/e2e --ignore=tests/red_team --ignore=tests/evaluation --ignore=tests/performance

Results: 469 passed, 0 failed, 0 skipped
Duration: ~45 seconds

Unit + Integration tests: ALL PASSING
E2E tests: Require running services (Ollama, Qdrant, API)
```

## Recommendations Summary

1. **Keep all existing passing tests** - No functional tests should be removed
2. **Convert specialized suites to pytest** - Or document how to run them
3. **Add missing coverage for extractors and config** - Critical gaps
4. **Consider parameterizing verbose test classes** - Reduce maintenance
5. **Review duplicate French language tests** - Consolidate where appropriate

## Next Steps

- US 10.2: Fix any failing unit tests (none found)
- US 10.3: Ensure E2E tests run with services
- US 10.4: Review specialized test suites
- US 10.5: Present removal recommendations (with user approval)
