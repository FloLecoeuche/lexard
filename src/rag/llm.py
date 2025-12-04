"""Ollama LLM client for local inference.

Provides a client for interacting with Ollama's API for LLM generation
with proper error handling, timeouts, and response parsing.
"""

import logging
from dataclasses import dataclass

import httpx

from src.config import LLMConfig

logger = logging.getLogger(__name__)


# Custom exceptions for LLM operations
class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    pass


class LLMConnectionError(LLMError):
    """Raised when connection to LLM service fails."""

    pass


class LLMGenerationError(LLMError):
    """Raised when LLM generation fails."""

    pass


@dataclass
class LLMResponse:
    """Response from LLM generation."""

    content: str
    model: str
    total_tokens: int | None
    finish_reason: str


# Prompt templates
QA_SYSTEM_PROMPT = """You are an enterprise contract analyst assistant.

RULES:
1. ONLY answer based on the retrieved document chunks provided
2. ALWAYS cite the specific chunk(s) that support your answer using [1], [2], etc.
3. If no chunk supports the answer, respond: "I cannot find information about this in the provided documents."
4. NEVER fabricate information, clauses, or terms
5. When uncertain, express uncertainty rather than guessing

FORMAT:
- Provide clear, concise answers
- List citations at the end as [Chunk X, Page Y]
"""


class OllamaClient:
    """Client for interacting with Ollama LLM API.

    Args:
        config: LLM configuration from settings
    """

    def __init__(self, config: LLMConfig):
        self.base_url = config.base_url
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout = config.timeout_seconds

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate response from Ollama.

        Args:
            prompt: User prompt with context
            system_prompt: Optional system instructions

        Returns:
            LLMResponse with generated text

        Raises:
            LLMTimeoutError: If request times out
            LLMConnectionError: If Ollama is unavailable
            LLMGenerationError: If generation fails
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(
            "Generating LLM response",
            extra={
                "model": self.model,
                "prompt_length": len(prompt),
                "has_system_prompt": system_prompt is not None,
            },
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("message", {}).get("content", "")
                if not content:
                    raise LLMGenerationError("Empty response from LLM")

                llm_response = LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    total_tokens=data.get("eval_count"),
                    finish_reason=data.get("done_reason", "stop"),
                )

                logger.debug(
                    "LLM generation complete",
                    extra={
                        "model": llm_response.model,
                        "tokens": llm_response.total_tokens,
                        "response_length": len(llm_response.content),
                    },
                )

                return llm_response

        except httpx.TimeoutException as e:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise LLMTimeoutError(
                f"Ollama request timed out after {self.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}")
            raise LLMConnectionError(
                f"Failed to connect to Ollama at {self.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama returned error status: {e.response.status_code}")
            raise LLMGenerationError(
                f"Ollama returned error: {e.response.status_code}"
            ) from e

    def health_check(self) -> bool:
        """Check if Ollama is accessible and model is available.

        Returns:
            True if Ollama is healthy and model is available, False otherwise
        """
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    # Check if our model (or base model name) is available
                    model_base = self.model.split(":")[0]
                    is_available = any(
                        m.get("name", "").startswith(model_base) for m in models
                    )
                    logger.debug(
                        f"Ollama health check: model={self.model}, available={is_available}"
                    )
                    return is_available
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
        return False


def build_qa_prompt(question: str, context: str) -> str:
    """Build a Q&A prompt with context.

    Args:
        question: User's question
        context: Formatted context from retrieved chunks

    Returns:
        Formatted prompt string
    """
    return f"""Based on the following document excerpts, answer the question.

DOCUMENT EXCERPTS:
{context}

QUESTION: {question}

Provide a clear answer with citations to the relevant excerpts."""
