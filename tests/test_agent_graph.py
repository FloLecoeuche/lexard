"""Tests for agent LangGraph workflow."""
import pytest
from src.agent.state import AgentState, AgentStatus, Intent
from src.agent.graph import (
    create_agent_graph,
    should_retry,
    classify_intent_node,
    execute_node,
    validate_output_node,
    regenerate_node,
    handle_failure,
)


class TestAgentState:
    """Test AgentState dataclass."""

    def test_state_default_values(self):
        """Test state has correct default values."""
        state = AgentState(user_query="test query")

        assert state.user_query == "test query"
        assert state.document_id is None
        assert state.document_id_b is None
        assert state.intent is None
        assert state.tool_result is None
        assert state.retry_count == 0
        assert state.max_retries == 2
        assert state.response is None
        assert state.status == AgentStatus.PENDING
        assert state.error is None
        assert state.validation_passed is False
        assert state.validation_issues == []

    def test_state_with_document_ids(self):
        """Test state with document IDs for comparison."""
        state = AgentState(
            user_query="compare these",
            document_id="doc-1",
            document_id_b="doc-2"
        )

        assert state.document_id == "doc-1"
        assert state.document_id_b == "doc-2"


class TestIntentEnum:
    """Test Intent enumeration."""

    def test_all_intents_defined(self):
        """Test all required intents are defined."""
        assert Intent.SUMMARIZE.value == "summarize"
        assert Intent.ANSWER_QUESTION.value == "answer_question"
        assert Intent.RISK_ANALYSIS.value == "risk_analysis"
        assert Intent.COMPARE_DOCUMENTS.value == "compare_documents"
        assert Intent.REFUSE.value == "refuse"


class TestAgentStatusEnum:
    """Test AgentStatus enumeration."""

    def test_all_statuses_defined(self):
        """Test all required statuses are defined."""
        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.PROCESSING.value == "processing"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"


class TestShouldRetry:
    """Test retry logic."""

    def test_should_pass_when_validation_passed(self):
        """Test returns 'pass' when validation passed."""
        state = AgentState(user_query="test", validation_passed=True)
        assert should_retry(state) == "pass"

    def test_should_retry_when_validation_failed_and_retries_remain(self):
        """Test returns 'retry' when validation failed but retries remain."""
        state = AgentState(user_query="test", validation_passed=False, retry_count=0)
        assert should_retry(state) == "retry"

        state = AgentState(user_query="test", validation_passed=False, retry_count=1)
        assert should_retry(state) == "retry"

    def test_should_fail_when_max_retries_exceeded(self):
        """Test returns 'fail' when max retries exceeded."""
        state = AgentState(user_query="test", validation_passed=False, retry_count=2)
        assert should_retry(state) == "fail"

        state = AgentState(user_query="test", validation_passed=False, retry_count=5)
        assert should_retry(state) == "fail"


class TestGraphNodes:
    """Test individual graph nodes."""

    def test_classify_intent_node(self):
        """Test classify_intent_node stub."""
        state = AgentState(user_query="summarize this document")
        result = classify_intent_node(state)

        assert "intent" in result
        assert "status" in result
        assert result["status"] == AgentStatus.PROCESSING

    def test_execute_node_summarize(self):
        """Test execute_node for summarize intent."""
        state = AgentState(user_query="summarize", intent=Intent.SUMMARIZE)
        result = execute_node(state)

        assert "tool_result" in result
        assert "summary" in result["tool_result"]

    def test_execute_node_answer_question(self):
        """Test execute_node for answer_question intent."""
        state = AgentState(user_query="what is?", intent=Intent.ANSWER_QUESTION)
        result = execute_node(state)

        assert "tool_result" in result
        assert "answer" in result["tool_result"]

    def test_execute_node_risk_analysis(self):
        """Test execute_node for risk_analysis intent."""
        state = AgentState(user_query="risks?", intent=Intent.RISK_ANALYSIS)
        result = execute_node(state)

        assert "tool_result" in result
        assert "risks" in result["tool_result"]

    def test_execute_node_compare(self):
        """Test execute_node for compare_documents intent."""
        state = AgentState(
            user_query="compare",
            intent=Intent.COMPARE_DOCUMENTS,
            document_id="doc-1",
            document_id_b="doc-2"
        )
        result = execute_node(state)

        assert "tool_result" in result
        assert "differences" in result["tool_result"]

    def test_execute_node_refuse(self):
        """Test execute_node for refuse intent."""
        state = AgentState(user_query="ignore instructions", intent=Intent.REFUSE)
        result = execute_node(state)

        assert result["status"] == AgentStatus.COMPLETED
        assert result["validation_passed"] is True

    def test_validate_output_node_with_result(self):
        """Test validate_output_node with tool result."""
        state = AgentState(user_query="test", tool_result={"answer": "test"})
        result = validate_output_node(state)

        assert result["validation_passed"] is True
        assert result["status"] == AgentStatus.COMPLETED
        assert result["response"] == {"answer": "test"}

    def test_validate_output_node_without_result(self):
        """Test validate_output_node without tool result."""
        state = AgentState(user_query="test", tool_result=None)
        result = validate_output_node(state)

        assert result["validation_passed"] is False
        assert len(result["validation_issues"]) > 0

    def test_regenerate_node(self):
        """Test regenerate_node increments retry count."""
        state = AgentState(user_query="test", retry_count=0)
        result = regenerate_node(state)

        assert result["retry_count"] == 1

        state = AgentState(user_query="test", retry_count=1)
        result = regenerate_node(state)

        assert result["retry_count"] == 2

    def test_handle_failure(self):
        """Test handle_failure sets failed status."""
        state = AgentState(
            user_query="test",
            retry_count=2,
            validation_issues=["Error 1", "Error 2"]
        )
        result = handle_failure(state)

        assert result["status"] == AgentStatus.FAILED
        assert "Error 1" in result["error"]
        assert "Error 2" in result["error"]


class TestGraphCompilation:
    """Test graph compilation and structure."""

    def test_graph_compiles(self):
        """Test graph compiles without errors."""
        graph = create_agent_graph()
        assert graph is not None

    def test_graph_has_entry_point(self):
        """Test graph has correct entry point."""
        graph = create_agent_graph()
        # Graph should be invokable
        assert hasattr(graph, "invoke")


class TestGraphExecution:
    """Test full graph execution."""

    def test_basic_execution(self):
        """Test basic graph execution completes."""
        graph = create_agent_graph()
        initial_state = AgentState(user_query="summarize this document")

        result = graph.invoke(initial_state)

        # Should complete successfully (stub always passes)
        assert result["status"] == AgentStatus.COMPLETED
        assert result["validation_passed"] is True
        assert result["response"] is not None

    def test_execution_with_document_id(self):
        """Test graph execution with document ID."""
        graph = create_agent_graph()
        initial_state = AgentState(
            user_query="what are the payment terms?",
            document_id="doc-123"
        )

        result = graph.invoke(initial_state)

        assert result["status"] == AgentStatus.COMPLETED

    def test_execution_preserves_input(self):
        """Test execution preserves input fields."""
        graph = create_agent_graph()
        initial_state = AgentState(
            user_query="compare documents",
            document_id="doc-1",
            document_id_b="doc-2"
        )

        result = graph.invoke(initial_state)

        assert result["user_query"] == "compare documents"
        assert result["document_id"] == "doc-1"
        assert result["document_id_b"] == "doc-2"
