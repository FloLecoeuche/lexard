"""Prompt injection detection for user inputs.

Detects and blocks common prompt injection patterns that attempt to:
- Override system instructions
- Extract system prompts
- Bypass safety guidelines
- Manipulate AI behavior
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class InjectionSeverity(str, Enum):
    """Severity level of detected injection attempt."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Injection patterns with severity levels
# Patterns are checked case-insensitively
INJECTION_PATTERNS: list[tuple[str, InjectionSeverity, str]] = [
    # Critical: Direct instruction overrides
    (
        r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?",
        InjectionSeverity.CRITICAL,
        "Attempts to override system instructions",
    ),
    (
        r"disregard\s+.{0,30}(rules|guidelines|instructions|constraints)",
        InjectionSeverity.CRITICAL,
        "Attempts to disregard safety rules",
    ),
    (
        r"forget\s+(everything|all)\s+(you\s+)?(know|learned|were\s+told)",
        InjectionSeverity.CRITICAL,
        "Attempts to reset AI context",
    ),
    # High: Role manipulation
    (
        r"pretend\s+(you\s+are|to\s+be)\s+",
        InjectionSeverity.HIGH,
        "Attempts to change AI persona",
    ),
    (
        r"act\s+as\s+(if|though)\s+",
        InjectionSeverity.HIGH,
        "Attempts to alter AI behavior",
    ),
    (
        r"you\s+are\s+now\s+(a|an)\s+",
        InjectionSeverity.HIGH,
        "Attempts to redefine AI identity",
    ),
    (
        r"roleplay\s+as\s+",
        InjectionSeverity.HIGH,
        "Attempts roleplay to bypass restrictions",
    ),
    # High: System prompt extraction
    (
        r"(show|reveal|display|tell|repeat)\s+.{0,20}(system\s+prompt|instructions|initial\s+prompt)",
        InjectionSeverity.HIGH,
        "Attempts to extract system prompt",
    ),
    (
        r"what\s+(are|were)\s+(your|the)\s+(exact\s+)?instructions",
        InjectionSeverity.HIGH,
        "Attempts to reveal instructions",
    ),
    (
        r"output\s+.{0,20}(prompt|instructions|rules)",
        InjectionSeverity.HIGH,
        "Attempts to output system configuration",
    ),
    # Medium: Indirect manipulation
    (
        r"the\s+document\s+(says|states|mentions)\s+(you\s+should|to)\s+ignore",
        InjectionSeverity.MEDIUM,
        "Claims document contains override instructions",
    ),
    (
        r"(user|admin|developer)\s+(says|wants|requires)\s+you\s+to\s+ignore",
        InjectionSeverity.MEDIUM,
        "Impersonates authority to override",
    ),
    (
        r"this\s+is\s+(a\s+)?test.{0,20}ignore\s+",
        InjectionSeverity.MEDIUM,
        "Uses 'test' framing to bypass",
    ),
    # Medium: Encoding bypass attempts
    (
        r"ign0re|1gnore|ignor3",
        InjectionSeverity.MEDIUM,
        "Character substitution bypass attempt",
    ),
    (
        r"syst[e3]m\s+pr[o0]mpt",
        InjectionSeverity.MEDIUM,
        "Encoded system prompt reference",
    ),
    # Low: Suspicious but context-dependent
    (
        r"without\s+(any\s+)?restrictions",
        InjectionSeverity.LOW,
        "Requests unrestricted output",
    ),
    (
        r"bypass\s+(the\s+)?(safety|security|filter)",
        InjectionSeverity.LOW,
        "Mentions bypassing safety",
    ),
    (
        r"jailbreak",
        InjectionSeverity.LOW,
        "Contains jailbreak terminology",
    ),
]


@dataclass
class InjectionDetectionResult:
    """Result of prompt injection detection.

    Attributes:
        is_injection: Whether an injection attempt was detected
        severity: Severity level if injection detected
        matched_pattern: The pattern that matched
        description: Description of the attack type
        input_snippet: Snippet of input that matched (truncated for logging)
    """

    is_injection: bool
    severity: InjectionSeverity | None
    matched_pattern: str | None
    description: str | None
    input_snippet: str | None


class InjectionDetector:
    """Detects prompt injection attempts in user inputs.

    Uses regex patterns to identify common injection techniques.
    Logs all detection attempts for security monitoring.

    Attributes:
        patterns: List of (pattern, severity, description) tuples
        block_threshold: Minimum severity to block (default: LOW blocks all)
    """

    def __init__(
        self,
        patterns: list[tuple[str, InjectionSeverity, str]] | None = None,
        block_threshold: InjectionSeverity = InjectionSeverity.LOW,
    ):
        """Initialize InjectionDetector.

        Args:
            patterns: Custom patterns or None for defaults
            block_threshold: Minimum severity level to block
        """
        self.patterns = patterns if patterns is not None else INJECTION_PATTERNS
        self.block_threshold = block_threshold

        # Compile patterns for performance
        self._compiled: list[tuple[re.Pattern, InjectionSeverity, str]] = []
        for pattern, severity, description in self.patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._compiled.append((compiled, severity, description))
            except re.error as e:
                logger.error(f"Invalid injection pattern: {e}")

        # Severity ordering for comparison
        self._severity_order = {
            InjectionSeverity.LOW: 0,
            InjectionSeverity.MEDIUM: 1,
            InjectionSeverity.HIGH: 2,
            InjectionSeverity.CRITICAL: 3,
        }

    def detect(self, text: str) -> InjectionDetectionResult:
        """Detect prompt injection attempts in text.

        Args:
            text: User input to check

        Returns:
            InjectionDetectionResult with detection status and details
        """
        if not text or not text.strip():
            return InjectionDetectionResult(
                is_injection=False,
                severity=None,
                matched_pattern=None,
                description=None,
                input_snippet=None,
            )

        # Check all patterns, return highest severity match
        highest_match: tuple[re.Pattern, InjectionSeverity, str, str] | None = None
        highest_severity = -1

        for pattern, severity, description in self._compiled:
            match = pattern.search(text)
            if match:
                severity_order = self._severity_order[severity]
                if severity_order > highest_severity:
                    highest_severity = severity_order
                    highest_match = (pattern, severity, description, match.group())

        if highest_match is None:
            return InjectionDetectionResult(
                is_injection=False,
                severity=None,
                matched_pattern=None,
                description=None,
                input_snippet=None,
            )

        pattern, severity, description, matched_text = highest_match

        # Check if severity meets block threshold
        should_block = self._severity_order[severity] >= self._severity_order[self.block_threshold]

        # Truncate snippet for logging
        snippet = matched_text[:50] + "..." if len(matched_text) > 50 else matched_text

        # Log the detection
        self._log_detection(text, severity, description, snippet)

        return InjectionDetectionResult(
            is_injection=should_block,
            severity=severity,
            matched_pattern=pattern.pattern,
            description=description,
            input_snippet=snippet,
        )

    def _log_detection(
        self,
        text: str,
        severity: InjectionSeverity,
        description: str,
        snippet: str,
    ) -> None:
        """Log injection detection for security monitoring.

        Args:
            text: Full input text (truncated in log)
            severity: Detected severity level
            description: Attack description
            snippet: Matched text snippet
        """
        # Truncate text for logging
        text_preview = text[:100] + "..." if len(text) > 100 else text

        log_data = {
            "event": "prompt_injection_detected",
            "severity": severity.value,
            "description": description,
            "matched_snippet": snippet,
            "input_preview": text_preview,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Use appropriate log level based on severity
        if severity == InjectionSeverity.CRITICAL:
            logger.critical("Prompt injection detected", extra=log_data)
        elif severity == InjectionSeverity.HIGH:
            logger.error("Prompt injection detected", extra=log_data)
        elif severity == InjectionSeverity.MEDIUM:
            logger.warning("Prompt injection detected", extra=log_data)
        else:
            logger.info("Possible prompt injection detected", extra=log_data)

    def add_pattern(
        self,
        pattern: str,
        severity: InjectionSeverity,
        description: str,
    ) -> bool:
        """Add a custom injection pattern.

        Args:
            pattern: Regex pattern string
            severity: Severity level for matches
            description: Description of attack type

        Returns:
            True if pattern was added successfully
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled.append((compiled, severity, description))
            self.patterns.append((pattern, severity, description))
            logger.info(f"Added injection pattern: {description}")
            return True
        except re.error as e:
            logger.error(f"Invalid injection pattern: {e}")
            return False


def detect_injection(text: str) -> tuple[bool, str | None]:
    """Convenience function to detect prompt injection.

    Args:
        text: Text to check

    Returns:
        Tuple of (is_injection, matched_pattern)
    """
    detector = InjectionDetector()
    result = detector.detect(text)
    return result.is_injection, result.matched_pattern
