"""Intent classification for user queries."""
from dataclasses import dataclass

from src.agent.state import Intent


@dataclass
class ClassificationResult:
    """Result of intent classification.

    Attributes:
        intent: Classified intent category
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Optional explanation of classification
    """
    intent: Intent
    confidence: float
    reasoning: str | None = None


class IntentClassifier:
    """Classify user queries into intents.

    Uses keyword-based classification with support for:
    - Summarization requests
    - Risk analysis queries
    - Document comparison
    - General Q&A (default)
    - Out-of-scope request detection
    """

    # Keywords for each intent
    INTENT_KEYWORDS: dict[Intent, list[str]] = {
        Intent.SUMMARIZE: [
            "summarize", "summary", "overview", "brief",
            "key points", "main points", "tldr", "recap",
            "give me a summary", "summarise"
        ],
        Intent.RISK_ANALYSIS: [
            "risk", "risks", "danger", "concern", "warning",
            "liability", "issue", "problem", "red flag",
            "potential issues", "what could go wrong"
        ],
        Intent.COMPARE_DOCUMENTS: [
            "compare", "comparison", "difference", "differences",
            "differ", "versus", "vs", "changed", "changes",
            "between", "side by side"
        ],
    }

    # Phrases that indicate Q&A
    QA_INDICATORS: list[str] = [
        "what", "when", "where", "who", "why", "how",
        "is there", "are there", "does", "do",
        "tell me", "explain", "describe", "find",
        "show me", "list", "which", "can you"
    ]

    # Out of scope phrases (prompt injection / off-topic)
    REFUSE_INDICATORS: list[str] = [
        "write code", "generate code", "create a program",
        "ignore instructions", "ignore your instructions",
        "forget your instructions", "forget instructions",
        "pretend you are", "act as", "you are now",
        "disregard previous", "disregard instructions",
        "override", "bypass",
        "jailbreak", "dan mode", "developer mode"
    ]

    def classify(self, query: str) -> ClassificationResult:
        """Classify query intent.

        Args:
            query: User's query string

        Returns:
            ClassificationResult with intent and confidence
        """
        query_lower = query.lower().strip()

        # Check for refusal first (prompt injection protection)
        if self._matches_any(query_lower, self.REFUSE_INDICATORS):
            return ClassificationResult(
                intent=Intent.REFUSE,
                confidence=0.95,
                reasoning="Query contains out-of-scope or potentially harmful patterns"
            )

        # Check for specific intents by keywords
        intent_scores: dict[Intent, float] = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = self._calculate_keyword_score(query_lower, keywords)
            if score > 0:
                intent_scores[intent] = score

        # If specific intent found, return highest scoring
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            best_score = intent_scores[best_intent]
            return ClassificationResult(
                intent=best_intent,
                confidence=min(best_score, 0.95),
                reasoning=f"Matched keywords for {best_intent.value}"
            )

        # Default to answer_question for general queries
        if self._matches_any(query_lower, self.QA_INDICATORS):
            return ClassificationResult(
                intent=Intent.ANSWER_QUESTION,
                confidence=0.8,
                reasoning="Query appears to be a question"
            )

        # Fallback: treat as question with lower confidence
        return ClassificationResult(
            intent=Intent.ANSWER_QUESTION,
            confidence=0.6,
            reasoning="Default classification as question"
        )

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """Check if text contains any of the patterns.

        Args:
            text: Text to search in (should be lowercase)
            patterns: List of patterns to match

        Returns:
            True if any pattern is found in text
        """
        return any(pattern in text for pattern in patterns)

    def _calculate_keyword_score(
        self, text: str, keywords: list[str]
    ) -> float:
        """Calculate confidence score based on keyword matches.

        Args:
            text: Text to search in (should be lowercase)
            keywords: List of keywords to match

        Returns:
            Score between 0.0 and 0.95
        """
        matches = sum(1 for keyword in keywords if keyword in text)
        if matches == 0:
            return 0.0
        # Base score of 0.5 for first match, +0.15 for each additional
        return min(0.5 + (matches - 1) * 0.15, 0.95)
