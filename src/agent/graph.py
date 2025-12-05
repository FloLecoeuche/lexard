"""LangGraph workflow for agent orchestration."""
from typing import Literal

from langgraph.graph import StateGraph, END

from src.agent.classifier import IntentClassifier
from src.agent.state import AgentState, AgentStatus, Intent


# Singleton classifier instance
_classifier = IntentClassifier()


def classify_intent_node(state: AgentState) -> dict:
    """Classify user intent using IntentClassifier and detect language.

    Uses keyword-based classification to determine the appropriate
    tool for handling the user's request. Also detects the language
    (English or French) from the query.
    """
    from src.rag.llm import detect_language

    result = _classifier.classify(state.user_query)
    language = detect_language(state.user_query)

    return {
        "intent": result.intent,
        "language": language,
        "status": AgentStatus.PROCESSING
    }


def route_to_tool_node(state: AgentState) -> dict:
    """Route to appropriate tool based on intent.

    This is a pass-through node - actual tool selection
    happens in execute_node based on intent.
    """
    return {}


def execute_node(state: AgentState) -> dict:
    """Execute the selected tool based on intent.

    Stub implementation - tools implemented in US 4.3-4.5.
    For now, generates placeholder response.
    """
    # Stub responses based on intent
    intent = state.intent
    response = None

    if intent == Intent.SUMMARIZE:
        response = {"summary": "Document summary placeholder"}
    elif intent == Intent.ANSWER_QUESTION:
        response = {"answer": "Answer placeholder", "citations": []}
    elif intent == Intent.RISK_ANALYSIS:
        response = {"risks": [], "overall_risk": "low"}
    elif intent == Intent.COMPARE_DOCUMENTS:
        response = {"differences": [], "similarity": 1.0}
    elif intent == Intent.REFUSE:
        response = {"message": "I cannot help with that request."}
        return {
            "tool_result": response,
            "response": response,
            "status": AgentStatus.COMPLETED,
            "validation_passed": True
        }

    return {"tool_result": response}


def validate_output_node(state: AgentState) -> dict:
    """Validate output with guardrails.

    Stub implementation - will integrate with guardrails from US 3.5.
    For now, always passes validation.
    """
    # Stub: will integrate with OutputValidator in later implementation
    tool_result = state.tool_result

    # For now, pass validation if we have a result
    if tool_result is not None:
        return {
            "response": tool_result,
            "status": AgentStatus.COMPLETED,
            "validation_passed": True,
            "validation_issues": []
        }

    return {
        "validation_passed": False,
        "validation_issues": ["No tool result produced"]
    }


def regenerate_node(state: AgentState) -> dict:
    """Prepare for retry by incrementing counter."""
    return {"retry_count": state.retry_count + 1}


def should_retry(state: AgentState) -> Literal["pass", "retry", "fail"]:
    """Determine if we should retry, pass, or fail.

    Returns:
        "pass" if validation passed
        "retry" if validation failed but retries remain
        "fail" if validation failed and max retries exceeded
    """
    if state.validation_passed:
        return "pass"
    elif state.retry_count < state.max_retries:
        return "retry"
    else:
        return "fail"


def handle_failure(state: AgentState) -> dict:
    """Handle terminal failure state."""
    issues = state.validation_issues or ["Unknown error"]
    return {
        "status": AgentStatus.FAILED,
        "error": f"Failed after {state.retry_count} retries: {'; '.join(issues)}"
    }


def create_agent_graph() -> StateGraph:
    """Create the agent workflow graph.

    Workflow:
    1. classify_intent - Determine user intent
    2. route_to_tool - Select tool based on intent
    3. execute - Run the selected tool
    4. validate_output - Check output with guardrails
    5. Conditional: pass -> END, retry -> regenerate, fail -> handle_failure -> END

    Returns:
        Compiled StateGraph for agent workflow
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("route_to_tool", route_to_tool_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("validate_output", validate_output_node)
    workflow.add_node("regenerate", regenerate_node)
    workflow.add_node("handle_failure", handle_failure)

    # Set entry point
    workflow.set_entry_point("classify_intent")

    # Add edges for normal flow
    workflow.add_edge("classify_intent", "route_to_tool")
    workflow.add_edge("route_to_tool", "execute")
    workflow.add_edge("execute", "validate_output")

    # Conditional edges for guardrails check
    workflow.add_conditional_edges(
        "validate_output",
        should_retry,
        {
            "pass": END,
            "retry": "regenerate",
            "fail": "handle_failure"
        }
    )

    # Retry loop
    workflow.add_edge("regenerate", "execute")

    # Failure terminates
    workflow.add_edge("handle_failure", END)

    return workflow.compile()


# Create a singleton graph instance
agent_graph = create_agent_graph()
