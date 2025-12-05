"""PII (Personally Identifiable Information) filtering.

Detects and redacts sensitive information from text including:
- IBAN numbers
- SSN (Social Security Numbers)
- Phone numbers
- Email addresses
- Credit card numbers
- IP addresses
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default PII patterns with named groups for identification
DEFAULT_PII_PATTERNS: dict[str, str] = {
    "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}

# French-specific PII patterns
FRENCH_PII_PATTERNS: dict[str, str] = {
    "fr_ssn": r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",  # French SSN (Numéro de sécurité sociale)
    "fr_phone": r"(\+33|0)[1-9](\s?\d{2}){4}",  # French phone numbers
}

# Combined patterns (English + French)
ALL_PII_PATTERNS: dict[str, str] = {**DEFAULT_PII_PATTERNS, **FRENCH_PII_PATTERNS}

# Default redaction placeholder
DEFAULT_PLACEHOLDER = "[REDACTED]"


@dataclass
class PIIMatch:
    """Represents a PII match found in text.

    Attributes:
        pattern_name: Name of the matched pattern (e.g., "email", "ssn")
        matched_text: The actual text that was matched
        start: Start position in the original text
        end: End position in the original text
    """

    pattern_name: str
    matched_text: str
    start: int
    end: int


@dataclass
class PIIFilterResult:
    """Result of PII filtering operation.

    Attributes:
        original_text: The original input text
        filtered_text: Text with PII redacted
        matches: List of PII matches found
        was_filtered: Whether any PII was detected and filtered
    """

    original_text: str
    filtered_text: str
    matches: list[PIIMatch] = field(default_factory=list)
    was_filtered: bool = False

    @property
    def match_count(self) -> int:
        """Number of PII matches found."""
        return len(self.matches)

    @property
    def patterns_found(self) -> set[str]:
        """Set of pattern names that were matched."""
        return {m.pattern_name for m in self.matches}


class PIIFilter:
    """Filters PII from text using configurable regex patterns.

    Supports custom patterns and placeholder tokens for redaction.

    Attributes:
        enabled: Whether PII filtering is active
        patterns: Dictionary of pattern name -> regex pattern
        placeholder: Token used to replace PII
    """

    def __init__(
        self,
        enabled: bool = True,
        patterns: dict[str, str] | None = None,
        placeholder: str = DEFAULT_PLACEHOLDER,
    ):
        """Initialize PIIFilter.

        Args:
            enabled: Whether to enable PII filtering
            patterns: Custom patterns dict. Uses ALL_PII_PATTERNS (EN+FR) if None.
            placeholder: Text to replace PII with. Use {type} for pattern name.
        """
        self.enabled = enabled
        self.patterns = patterns if patterns is not None else ALL_PII_PATTERNS.copy()
        self.placeholder = placeholder

        # Compile patterns for performance
        self._compiled: dict[str, re.Pattern] = {}
        for name, pattern in self.patterns.items():
            try:
                self._compiled[name] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{name}': {e}")

    def detect(self, text: str) -> list[PIIMatch]:
        """Detect all PII in text without modifying it.

        Args:
            text: Text to scan for PII

        Returns:
            List of PIIMatch objects for each PII found
        """
        if not self.enabled or not text:
            return []

        matches: list[PIIMatch] = []

        for name, pattern in self._compiled.items():
            for match in pattern.finditer(text):
                matches.append(
                    PIIMatch(
                        pattern_name=name,
                        matched_text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Sort by position
        matches.sort(key=lambda m: m.start)

        if matches:
            logger.info(
                "PII detected",
                extra={
                    "match_count": len(matches),
                    "patterns": list({m.pattern_name for m in matches}),
                },
            )

        return matches

    def redact(self, text: str) -> PIIFilterResult:
        """Detect and redact all PII from text.

        Args:
            text: Text to filter

        Returns:
            PIIFilterResult with filtered text and match details
        """
        if not self.enabled or not text:
            return PIIFilterResult(
                original_text=text,
                filtered_text=text,
                matches=[],
                was_filtered=False,
            )

        matches = self.detect(text)

        if not matches:
            return PIIFilterResult(
                original_text=text,
                filtered_text=text,
                matches=[],
                was_filtered=False,
            )

        # Build filtered text by replacing matches in reverse order
        # (to preserve positions)
        filtered = text
        for match in reversed(matches):
            # Support {type} placeholder
            replacement = self.placeholder.replace("{type}", match.pattern_name.upper())
            filtered = filtered[: match.start] + replacement + filtered[match.end :]

        logger.info(
            "PII redacted",
            extra={
                "original_length": len(text),
                "filtered_length": len(filtered),
                "redaction_count": len(matches),
            },
        )

        return PIIFilterResult(
            original_text=text,
            filtered_text=filtered,
            matches=matches,
            was_filtered=True,
        )

    def add_pattern(self, name: str, pattern: str) -> bool:
        """Add a custom PII pattern.

        Args:
            name: Name for the pattern
            pattern: Regex pattern string

        Returns:
            True if pattern was added successfully
        """
        try:
            self._compiled[name] = re.compile(pattern, re.IGNORECASE)
            self.patterns[name] = pattern
            logger.info(f"Added PII pattern: {name}")
            return True
        except re.error as e:
            logger.error(f"Invalid regex pattern '{name}': {e}")
            return False

    def remove_pattern(self, name: str) -> bool:
        """Remove a PII pattern.

        Args:
            name: Name of pattern to remove

        Returns:
            True if pattern was removed
        """
        if name in self._compiled:
            del self._compiled[name]
            del self.patterns[name]
            logger.info(f"Removed PII pattern: {name}")
            return True
        return False


def redact_pii(text: str, patterns: dict[str, str] | None = None) -> str:
    """Convenience function to redact PII from text.

    Args:
        text: Text to filter
        patterns: Optional custom patterns

    Returns:
        Text with PII redacted
    """
    filter = PIIFilter(patterns=patterns)
    result = filter.redact(text)
    return result.filtered_text
