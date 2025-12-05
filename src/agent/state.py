"""Agent state schema for LangGraph workflow."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    """User intent categories."""
    SUMMARIZE = "summarize"
    ANSWER_QUESTION = "answer_question"
    RISK_ANALYSIS = "risk_analysis"
    COMPARE_DOCUMENTS = "compare_documents"
    REFUSE = "refuse"


class AgentStatus(str, Enum):
    """Agent processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentState:
    """State schema for agent workflow.

    Captures all data needed throughout the agent workflow:
    - Input: user query and document references
    - Processing: classified intent, tool results, retry tracking
    - Output: final response and status
    - Guardrails: validation results
    """
    # Input
    user_query: str
    document_id: str | None = None
    document_id_b: str | None = None  # For comparison
    language: str = "en"  # Detected language ('en' or 'fr')

    # Processing
    intent: Intent | None = None
    tool_result: Any = None
    retry_count: int = 0
    max_retries: int = 2

    # Output
    response: Any = None
    status: AgentStatus = AgentStatus.PENDING
    error: str | None = None

    # Guardrails
    validation_passed: bool = False
    validation_issues: list[str] = field(default_factory=list)
