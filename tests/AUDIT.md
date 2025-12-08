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

### Specialized Test Suites

| Suite       | Location           | Files                                         | Purpose          | Pytest Compatible |
| ----------- | ------------------ | --------------------------------------------- | ---------------- | ----------------- |
| Red Team    | tests/red_team/    | injection.py, hallucination.py, edge_cases.py | Security testing | ✅ Yes (83 tests) |
| Evaluation  | tests/evaluation/  | metrics.py, runner.py, dataset.py, report.py  | Quality metrics  | No (CLI runner)   |
| Performance | tests/performance/ | benchmarks.py, report.py                      | Speed benchmarks | No (CLI runner)   |

**Note:** Red team tests ARE pytest-compatible but not auto-discovered because files don't start with `test_`.
Run explicitly: `pytest tests/red_team/injection.py tests/red_team/hallucination.py tests/red_team/edge_cases.py -v`

#### How to Run Specialized Suites

**Red Team Tests (Pytest):**
```bash
# Run all red team pytest tests (83 tests, no services required)
pytest tests/red_team/injection.py tests/red_team/hallucination.py tests/red_team/edge_cases.py -v

# Alternative: Use the CLI runner for injection-only tests
python -m tests.red_team --injection-only

# Full API tests (requires running services + document)
python -m tests.red_team --document-id <DOC_ID> --dataset data/eval/red_team.yaml
```

**Evaluation Harness (CLI):**
```bash
# List available datasets
python -m tests.evaluation --list-datasets

# Dry run (show test cases without executing)
python -m tests.evaluation --dry-run --dataset contract_qa

# Full evaluation (requires running API + document)
python -m tests.evaluation --dataset contract_qa --document-id <DOC_ID>

# French evaluation
python -m tests.evaluation --dataset french_qa --document-id <DOC_ID>
```

**Performance Benchmarks (CLI):**
```bash
# Embeddings-only benchmark (no API required)
python -m tests.performance --embeddings-only --iterations 10

# Full benchmarks (requires running API + document)
python -m tests.performance --document-id <DOC_ID> --iterations 10

# With file upload benchmark
python -m tests.performance --document-id <DOC_ID> --file path/to/doc.pdf
```

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

## US 10.2: Unit Test Fixes & Cleanup

**Status:** ✅ Complete
**Date:** 2025-12-08

### Summary

All unit tests verified and passing. No fixes were needed - the test suite was already in good shape.

### Verification Results

| Criteria                               | Result | Notes                                    |
| -------------------------------------- | ------ | ---------------------------------------- |
| All unit tests pass                    | ✅     | 428 passed, 1 skipped                    |
| Unit tests run in <60 seconds          | ✅     | 11.96 seconds                            |
| No test requires Ollama/Qdrant running | ✅     | 1 test properly skipped (requires Qdrant)|
| Test names follow convention           | ✅     | `test_<function>_<scenario>` pattern     |
| Each test has clear purpose            | ✅     | All tests have docstrings                |
| Test isolation (no shared state)       | ✅     | Module-scoped fixtures are read-only     |

### Redundant Test Analysis

Duplicate tests were identified in US 10.1 but NOT removed because:
1. Unit tests (`test_french_support.py::TestLanguageDetection`) are faster than integration equivalents
2. Test removal requires explicit user approval (deferred to US 10.5)
3. Different test layers (unit vs integration) serve different purposes

### Key Findings

1. **All 428 unit tests pass** - No failing tests to fix
2. **Test isolation is good** - Module-scoped fixtures are read-only (embedding model)
3. **External service dependency properly handled** - 1 test skipped (requires Qdrant)
4. **Test naming is consistent** - All tests follow `test_<function>_<scenario>` pattern
5. **Docstrings present** - All tests have clear purpose documentation

### Recommendations for US 10.5

These tests are candidates for removal/consolidation (requires user approval):
- `test_french_support.py::TestLanguageDetection` (4 tests) - Covered by integration tests
- Consider parameterizing `test_classifier.py` (43 tests → ~20 tests)

## US 10.4: Specialized Test Suites Review

**Status:** ✅ Complete
**Date:** 2025-12-08

### Summary

All three specialized test suites (Red Team, Evaluation, Performance) reviewed and verified functional.

### Red Team Tests

| Test Category        | Tests | Status | Notes                          |
| -------------------- | ----- | ------ | ------------------------------ |
| Injection Detection  | 41    | ✅ PASS | Detects prompt injection       |
| Hallucination Tests  | 17    | ✅ PASS | Validates grounding/citations  |
| Edge Cases           | 25    | ✅ PASS | Security edge cases (XSS, SQL) |
| **Total**            | 83    | ✅ PASS | All pytest tests passing       |

**Key Finding:** Red team tests ARE pytest-compatible (83 tests) and can be run with:
```bash
pytest tests/red_team/injection.py tests/red_team/hallucination.py tests/red_team/edge_cases.py -v
```

### Evaluation Harness

| Feature           | Status | Notes                              |
| ----------------- | ------ | ---------------------------------- |
| Module imports    | ✅     | All imports successful             |
| CLI help          | ✅     | `--help` works correctly           |
| Dataset listing   | ✅     | 3 datasets: contract_qa, red_team, french_qa |
| Dry run mode      | ✅     | Shows 25 test cases                |
| API check         | ✅     | Properly checks API availability   |

**Run instruction:** `python -m tests.evaluation --help`

### Performance Benchmarks

| Feature             | Status | Notes                           |
| ------------------- | ------ | ------------------------------- |
| Module imports      | ✅     | All imports successful          |
| CLI help            | ✅     | `--help` works correctly        |
| Embeddings benchmark| ✅     | Works without API               |
| Target validation   | ✅     | Compares against PRD targets    |

**Run instruction:** `python -m tests.performance --embeddings-only`

**Note:** First run may show slower times due to model cold start (loading sentence-transformers).
Run with `--iterations 10` or more for accurate P95 measurements.

### Documentation Updated

Run instructions added to:
1. `tests/AUDIT.md` (this file) - How to run each suite
2. Each suite's `__main__.py` already has comprehensive help via `--help`

### Recommendations

1. **Red team tests should be included in CI** - They are pytest-compatible and fast
2. **Evaluation/Performance are optional** - Require services, better for manual QA
3. **Consider adding warmup iteration** for performance benchmarks to avoid cold start skewing

## US 10.5: Unnecessary Tests Removal

**Status:** ✅ Complete
**Date:** 2025-12-08
**User Decision:** No tests removed

### Summary

After comprehensive analysis, **no tests were recommended for removal**. The test suite is well-organized and not redundant.

### Key Findings

1. **"Duplicate" tests are actually complementary:**
   - Language detection: Unit tests (4) test function isolation, Integration tests (12) test content variations
   - Bilingual prompts: Three test files test different components (agent API vs RAG API vs integration)

2. **No trivial, dead code, over-mocked, or flaky tests found**

3. **Parameterization not recommended:**
   - Time savings would be <1s
   - Individual test names are more debuggable
   - Current test count (469) is not excessive

### Metrics

| Metric | Value |
|--------|-------|
| Tests analyzed | 469 |
| Tests removed | 0 |
| CI time | ~12.2s |

### Detailed Report

See [REMOVAL_REPORT.md](./REMOVAL_REPORT.md) for full analysis.

---

## Epic 10 Complete

All User Stories for Epic 10 (Test Suite Review) have been completed:

| US | Name | Status |
|----|------|--------|
| 10.1 | Test Audit & Inventory | ✅ |
| 10.2 | Unit Test Fixes & Cleanup | ✅ |
| 10.3 | E2E & Integration Test Fixes | ✅ |
| 10.4 | Specialized Test Suites Review | ✅ |
| 10.5 | Unnecessary Tests Removal | ✅ |
