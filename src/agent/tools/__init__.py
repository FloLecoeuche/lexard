"""Agent tools for document analysis.

Provides specialized tools for:
- Document summarization (SummarizerTool)
- Risk detection (RiskDetectorTool)
- Document comparison (DiffTool)
"""

from src.agent.tools.diff import (
    ChangeType,
    ComparisonResult,
    Difference,
    DiffTool,
)
from src.agent.tools.risk_detector import (
    Risk,
    RiskAnalysisResult,
    RiskCategory,
    RiskDetectorTool,
    RiskSeverity,
)
from src.agent.tools.summarizer import SummarizerTool, SummaryResult

__all__ = [
    "SummarizerTool",
    "SummaryResult",
    "RiskDetectorTool",
    "RiskAnalysisResult",
    "Risk",
    "RiskCategory",
    "RiskSeverity",
    "DiffTool",
    "ComparisonResult",
    "Difference",
    "ChangeType",
]
