"""LLM clients for local inference.

Provides clients for interacting with:
- Ollama's API for LLM generation
- OpenAI-compatible APIs (llama.cpp, vLLM, etc.)

With proper error handling, timeouts, and response parsing.
Also provides language detection utilities for multilingual support.
"""

import logging
from dataclasses import dataclass

import httpx

from src.config import LLMConfig

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language of input text (en or fr).

    Uses langdetect library to identify language. Supports French and English,
    defaulting to English if detection fails or language is neither.

    Args:
        text: Input text to detect language from

    Returns:
        'fr' for French, 'en' for English (default)

    Examples:
        >>> detect_language("What is the notice period?")
        'en'
        >>> detect_language("Quelle est la période de préavis?")
        'fr'
    """
    if not text or not text.strip():
        return "en"

    try:
        from langdetect import detect

        lang = detect(text)
        return "fr" if lang == "fr" else "en"
    except Exception as e:
        logger.debug("Language detection failed: %s. Defaulting to English.", e)
        return "en"


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


# Prompt templates - Bilingual (English and French)
QA_SYSTEM_PROMPTS = {
    "en": """You are an enterprise contract analyst assistant.

RULES:
1. ONLY answer based on the retrieved document chunks provided
2. ALWAYS cite the specific chunk(s) that support your answer using [1], [2], etc.
3. If no chunk supports the answer, respond: "I cannot find information about this in the provided documents."
4. NEVER fabricate information, clauses, or terms
5. When uncertain, express uncertainty rather than guessing

FORMAT:
- Provide clear, concise answers
- List citations at the end as [Chunk X, Page Y]
""",
    "fr": """Vous êtes un assistant d'analyse de contrats d'entreprise.

RÈGLES:
1. Répondez UNIQUEMENT en vous basant sur les extraits de documents fournis
2. CITEZ TOUJOURS les extraits spécifiques qui appuient votre réponse avec [1], [2], etc.
3. Si aucun extrait ne permet de répondre, dites: "Je ne trouve pas cette information dans les documents fournis."
4. Ne JAMAIS inventer d'informations, de clauses ou de termes
5. En cas d'incertitude, exprimez votre doute plutôt que de deviner

FORMAT:
- Fournissez des réponses claires et concises
- Listez les citations à la fin sous forme [Extrait X, Page Y]
""",
}

QA_USER_PROMPTS = {
    "en": """Based on the following document excerpts, answer the question.

DOCUMENT EXCERPTS:
{context}

QUESTION: {question}

Provide a clear answer with citations to the relevant excerpts.""",
    "fr": """En vous basant sur les extraits de documents suivants, répondez à la question.

EXTRAITS DE DOCUMENTS:
{context}

QUESTION: {question}

Fournissez une réponse claire avec des citations vers les extraits pertinents.""",
}

# Legacy alias for backwards compatibility
QA_SYSTEM_PROMPT = QA_SYSTEM_PROMPTS["en"]


def get_qa_system_prompt(language: str = "en") -> str:
    """Get QA system prompt in specified language.

    Args:
        language: Language code ('en' or 'fr')

    Returns:
        System prompt in the specified language
    """
    return QA_SYSTEM_PROMPTS.get(language, QA_SYSTEM_PROMPTS["en"])


class OllamaClient:
    """Client for interacting with Ollama LLM API.

    Features connection pooling for improved performance with repeated requests.

    Args:
        config: LLM configuration from settings
    """

    def __init__(self, config: LLMConfig):
        self.base_url = config.base_url
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout = config.timeout_seconds

        # Connection pooling for improved performance
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create pooled HTTP client.

        Returns:
            Shared httpx.Client with connection pooling
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0,
                ),
            )
            logger.debug("Created pooled HTTP client for Ollama")
        return self._client

    def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()
            self._client = None
            logger.debug("Closed Ollama HTTP client")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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
            response = self.client.post(
                "/api/chat",
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
            # Use a separate short-timeout client for health checks
            with httpx.Client(base_url=self.base_url, timeout=5) as client:
                response = client.get("/api/tags")
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


class OpenAICompatibleClient:
    """Client for OpenAI-compatible LLM APIs (llama.cpp, vLLM, etc.).

    Features connection pooling for improved performance with repeated requests.

    Args:
        config: LLM configuration from settings
    """

    def __init__(self, config: LLMConfig):
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout = config.timeout_seconds

        # Connection pooling for improved performance
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create pooled HTTP client.

        Returns:
            Shared httpx.Client with connection pooling
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0,
                ),
            )
            logger.debug("Created pooled HTTP client for OpenAI-compatible API")
        return self._client

    def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()
            self._client = None
            logger.debug("Closed OpenAI-compatible HTTP client")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate response from OpenAI-compatible API.

        Args:
            prompt: User prompt with context
            system_prompt: Optional system instructions

        Returns:
            LLMResponse with generated text

        Raises:
            LLMTimeoutError: If request times out
            LLMConnectionError: If service is unavailable
            LLMGenerationError: If generation fails
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(
            "Generating LLM response via OpenAI-compatible API",
            extra={
                "model": self.model,
                "prompt_length": len(prompt),
                "has_system_prompt": system_prompt is not None,
            },
        )

        try:
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                raise LLMGenerationError("No choices in response from LLM")

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                raise LLMGenerationError("Empty response from LLM")

            usage = data.get("usage", {})
            llm_response = LLMResponse(
                content=content,
                model=data.get("model", self.model),
                total_tokens=usage.get("total_tokens"),
                finish_reason=choices[0].get("finish_reason", "stop"),
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
            logger.error(f"LLM request timed out after {self.timeout}s")
            raise LLMTimeoutError(
                f"LLM request timed out after {self.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to LLM at {self.base_url}")
            raise LLMConnectionError(
                f"Failed to connect to LLM at {self.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM returned error status: {e.response.status_code}")
            raise LLMGenerationError(
                f"LLM returned error: {e.response.status_code}"
            ) from e

    def health_check(self) -> bool:
        """Check if the OpenAI-compatible API is accessible.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            with httpx.Client(base_url=self.base_url, timeout=5) as client:
                response = client.get("/health")
                is_healthy = response.status_code == 200
                logger.debug(f"OpenAI-compatible API health check: healthy={is_healthy}")
                return is_healthy
        except Exception as e:
            logger.warning(f"OpenAI-compatible API health check failed: {e}")
        return False


def create_llm_client(config: LLMConfig) -> OllamaClient | OpenAICompatibleClient:
    """Factory function to create the appropriate LLM client.

    Args:
        config: LLM configuration from settings

    Returns:
        OllamaClient for 'ollama' provider, OpenAICompatibleClient for 'openai' provider
    """
    if config.provider == "openai":
        logger.info(f"Creating OpenAI-compatible client for {config.base_url}")
        return OpenAICompatibleClient(config)
    else:
        logger.info(f"Creating Ollama client for {config.base_url}")
        return OllamaClient(config)


def detect_language_from_chunks(chunks: list) -> str:
    """Detect language from retrieved document chunks.

    Samples text from multiple chunks to get reliable detection.
    This ensures response language matches document language,
    regardless of query language.

    Args:
        chunks: List of RetrievedChunk objects with 'content' attribute

    Returns:
        'fr' for French, 'en' for English (default)
    """
    if not chunks:
        return "en"

    # Sample text from first few chunks (more reliable than single chunk)
    sample_texts = [chunk.content for chunk in chunks[:3]]
    combined_sample = " ".join(sample_texts)[:1000]  # Limit to 1000 chars

    return detect_language(combined_sample)


def build_qa_prompt(question: str, context: str, language: str = "en") -> str:
    """Build a Q&A prompt with context in specified language.

    Args:
        question: User's question
        context: Formatted context from retrieved chunks
        language: Language code ('en' or 'fr')

    Returns:
        Formatted prompt string in the specified language
    """
    template = QA_USER_PROMPTS.get(language, QA_USER_PROMPTS["en"])
    return template.format(context=context, question=question)
