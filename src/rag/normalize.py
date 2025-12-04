"""Text normalization utilities for extracted document text."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize extracted text.

    Applies:
    - Unicode NFKC normalization
    - Multiple whitespace reduction to single space
    - Leading/trailing whitespace removal
    - Line break normalization

    Args:
        text: Raw extracted text.

    Returns:
        Normalized text.
    """
    if not text:
        return ""

    # Unicode NFKC normalization (compatibility decomposition + canonical composition)
    text = unicodedata.normalize("NFKC", text)

    # Normalize line endings to Unix style
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Replace multiple spaces/tabs with single space (within lines)
    text = re.sub(r"[ \t]+", " ", text)

    # Remove spaces at the beginning/end of lines
    text = re.sub(r"^ +| +$", "", text, flags=re.MULTILINE)

    # Strip leading/trailing whitespace from entire text
    text = text.strip()

    return text


def normalize_whitespace_only(text: str) -> str:
    """Light normalization that only handles whitespace.

    Useful when unicode normalization might cause issues.

    Args:
        text: Raw text.

    Returns:
        Text with normalized whitespace.
    """
    if not text:
        return ""

    # Replace multiple whitespace with single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()
