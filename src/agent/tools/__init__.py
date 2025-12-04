"""Agent tools for document analysis.

Provides specialized tools for:
- Document summarization (SummarizerTool)
- Risk detection (RiskDetectorTool) - US 4.4
- Document comparison (DiffTool) - US 4.5
"""

from src.agent.tools.summarizer import SummarizerTool, SummaryResult

__all__ = ["SummarizerTool", "SummaryResult"]
