"""Tests for Ollama LLM client."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.rag.llm import (
    LLMConnectionError,
    LLMGenerationError,
    LLMResponse,
    LLMTimeoutError,
    OllamaClient,
    QA_SYSTEM_PROMPT,
    QA_SYSTEM_PROMPTS,
    QA_USER_PROMPTS,
    build_qa_prompt,
    detect_language_from_chunks,
    get_qa_system_prompt,
)


@pytest.fixture
def mock_llm_config():
    """Create mock LLM configuration."""

    @dataclass
    class MockLLMConfig:
        provider: str = "ollama"
        model: str = "mistral:7b-instruct"
        base_url: str = "http://localhost:11434"
        temperature: float = 0.1
        max_tokens: int = 2048
        timeout_seconds: int = 30

    return MockLLMConfig()


@pytest.fixture
def client(mock_llm_config):
    """Create OllamaClient with mock config."""
    return OllamaClient(mock_llm_config)


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_response_creation(self):
        """LLMResponse should store all fields correctly."""
        response = LLMResponse(
            content="Test answer",
            model="mistral:7b-instruct",
            total_tokens=150,
            finish_reason="stop",
        )

        assert response.content == "Test answer"
        assert response.model == "mistral:7b-instruct"
        assert response.total_tokens == 150
        assert response.finish_reason == "stop"

    def test_response_with_none_tokens(self):
        """LLMResponse should allow None for total_tokens."""
        response = LLMResponse(
            content="Answer",
            model="mistral",
            total_tokens=None,
            finish_reason="stop",
        )

        assert response.total_tokens is None


class TestOllamaClientInit:
    """Tests for OllamaClient initialization."""

    def test_client_uses_config_values(self, mock_llm_config):
        """Client should use values from config."""
        client = OllamaClient(mock_llm_config)

        assert client.base_url == "http://localhost:11434"
        assert client.model == "mistral:7b-instruct"
        assert client.temperature == 0.1
        assert client.max_tokens == 2048
        assert client.timeout == 30


class TestOllamaClientGenerate:
    """Tests for the generate method."""

    def test_generate_returns_response(self, client):
        """Generate should return LLMResponse on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "The answer is 42"},
            "model": "mistral:7b-instruct",
            "eval_count": 100,
            "done_reason": "stop",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            response = client.generate("What is the answer?")

            assert isinstance(response, LLMResponse)
            assert response.content == "The answer is 42"
            assert response.model == "mistral:7b-instruct"
            assert response.total_tokens == 100
            assert response.finish_reason == "stop"

    def test_generate_with_system_prompt(self, client):
        """Generate should include system prompt in messages."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Bonjour"},
            "model": "mistral",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.generate("Hello", system_prompt="Always respond in French")

            call_args = mock_client.post.call_args
            json_data = call_args[1]["json"]
            messages = json_data["messages"]

            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "Always respond in French"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Hello"

    def test_generate_without_system_prompt(self, client):
        """Generate without system prompt should only have user message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Response"},
            "model": "mistral",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.generate("Hello")

            call_args = mock_client.post.call_args
            json_data = call_args[1]["json"]
            messages = json_data["messages"]

            assert len(messages) == 1
            assert messages[0]["role"] == "user"

    def test_generate_sends_correct_options(self, client):
        """Generate should send correct temperature and max tokens."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Response"},
            "model": "mistral",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.generate("Test")

            call_args = mock_client.post.call_args
            json_data = call_args[1]["json"]

            assert json_data["model"] == "mistral:7b-instruct"
            assert json_data["stream"] is False
            assert json_data["options"]["temperature"] == 0.1
            assert json_data["options"]["num_predict"] == 2048

    def test_generate_calls_correct_endpoint(self, client):
        """Generate should POST to /api/chat endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Response"},
            "model": "mistral",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_closed = False
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.generate("Test")

            call_args = mock_client.post.call_args
            # With connection pooling, we use relative path with base_url
            assert call_args[0][0] == "/api/chat"


class TestOllamaClientErrors:
    """Tests for error handling."""

    def test_timeout_raises_llm_timeout_error(self, client):
        """Timeout should raise LLMTimeoutError."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMTimeoutError) as exc_info:
                client.generate("Test")

            assert "timed out" in str(exc_info.value).lower()
            assert "30s" in str(exc_info.value)

    def test_connection_error_raises_llm_connection_error(self, client):
        """Connection failure should raise LLMConnectionError."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMConnectionError) as exc_info:
                client.generate("Test")

            assert "localhost:11434" in str(exc_info.value)

    def test_http_error_raises_llm_generation_error(self, client):
        """HTTP error status should raise LLMGenerationError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMGenerationError) as exc_info:
                client.generate("Test")

            assert "500" in str(exc_info.value)

    def test_empty_response_raises_generation_error(self, client):
        """Empty response content should raise LLMGenerationError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": ""},
            "model": "mistral",
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMGenerationError) as exc_info:
                client.generate("Test")

            assert "Empty response" in str(exc_info.value)


class TestOllamaClientHealthCheck:
    """Tests for the health_check method."""

    def test_health_check_returns_true_when_model_available(self, client):
        """Health check should return True when model is listed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "mistral:7b-instruct"},
                {"name": "llama3:8b"},
            ]
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            assert client.health_check() is True

    def test_health_check_returns_true_for_base_model_match(self, client):
        """Health check should match base model name."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "mistral:latest"},  # Different tag, same base
            ]
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            assert client.health_check() is True

    def test_health_check_returns_false_when_model_not_available(self, client):
        """Health check should return False when model is not listed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:8b"},
            ]
        }

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            assert client.health_check() is False

    def test_health_check_returns_false_on_connection_error(self, client):
        """Health check should return False on connection error."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            assert client.health_check() is False

    def test_health_check_returns_false_on_non_200_status(self, client):
        """Health check should return False on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            assert client.health_check() is False

    def test_health_check_calls_correct_endpoint(self, client):
        """Health check should GET /api/tags endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.health_check()

            # Health check uses relative path with base_url
            mock_client.get.assert_called_once_with("/api/tags")


class TestPromptTemplates:
    """Tests for prompt templates."""

    def test_qa_system_prompt_exists(self):
        """QA system prompt should be defined."""
        assert QA_SYSTEM_PROMPT
        assert "contract analyst" in QA_SYSTEM_PROMPT.lower()
        assert "[1]" in QA_SYSTEM_PROMPT  # Citation marker example
        assert "NEVER" in QA_SYSTEM_PROMPT  # Strong instruction

    def test_qa_system_prompt_contains_rules(self):
        """QA system prompt should contain grounding rules."""
        assert "ONLY answer based on" in QA_SYSTEM_PROMPT
        assert "ALWAYS cite" in QA_SYSTEM_PROMPT
        assert "fabricate" in QA_SYSTEM_PROMPT.lower()

    def test_build_qa_prompt(self):
        """build_qa_prompt should format question and context."""
        context = "[1] Payment is due in 30 days.\n\n[2] Late fees apply."
        question = "When is payment due?"

        prompt = build_qa_prompt(question, context)

        assert question in prompt
        assert context in prompt
        assert "DOCUMENT EXCERPTS" in prompt
        assert "QUESTION" in prompt
        assert "citations" in prompt.lower()

    def test_build_qa_prompt_preserves_context_format(self):
        """build_qa_prompt should preserve context formatting."""
        context = "[1] First chunk\n\n[2] Second chunk"
        question = "Test?"

        prompt = build_qa_prompt(question, context)

        assert "[1] First chunk" in prompt
        assert "[2] Second chunk" in prompt


class TestLLMExceptions:
    """Tests for custom exception hierarchy."""

    def test_llm_timeout_error_message(self):
        """LLMTimeoutError should preserve message."""
        error = LLMTimeoutError("Request timed out after 30s")
        assert str(error) == "Request timed out after 30s"

    def test_llm_connection_error_message(self):
        """LLMConnectionError should preserve message."""
        error = LLMConnectionError("Failed to connect")
        assert str(error) == "Failed to connect"

    def test_llm_generation_error_message(self):
        """LLMGenerationError should preserve message."""
        error = LLMGenerationError("Model returned error")
        assert str(error) == "Model returned error"

    def test_exceptions_are_llm_error_subclasses(self):
        """All custom exceptions should inherit from LLMError."""
        from src.rag.llm import LLMError

        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMConnectionError, LLMError)
        assert issubclass(LLMGenerationError, LLMError)


class TestBilingualPrompts:
    """Tests for bilingual prompt templates."""

    def test_qa_system_prompts_has_both_languages(self):
        """QA_SYSTEM_PROMPTS should have both English and French."""
        assert "en" in QA_SYSTEM_PROMPTS
        assert "fr" in QA_SYSTEM_PROMPTS

    def test_qa_user_prompts_has_both_languages(self):
        """QA_USER_PROMPTS should have both English and French."""
        assert "en" in QA_USER_PROMPTS
        assert "fr" in QA_USER_PROMPTS

    def test_english_system_prompt_content(self):
        """English system prompt should contain key English instructions."""
        prompt = QA_SYSTEM_PROMPTS["en"]
        assert "contract analyst" in prompt.lower()
        assert "ONLY answer based on" in prompt
        assert "ALWAYS cite" in prompt
        assert "[1]" in prompt

    def test_french_system_prompt_content(self):
        """French system prompt should contain key French instructions."""
        prompt = QA_SYSTEM_PROMPTS["fr"]
        assert "contrats d'entreprise" in prompt.lower()
        assert "UNIQUEMENT" in prompt
        assert "CITEZ TOUJOURS" in prompt
        assert "[1]" in prompt

    def test_english_user_prompt_placeholders(self):
        """English user prompt should have context and question placeholders."""
        prompt = QA_USER_PROMPTS["en"]
        assert "{context}" in prompt
        assert "{question}" in prompt
        assert "DOCUMENT EXCERPTS" in prompt

    def test_french_user_prompt_placeholders(self):
        """French user prompt should have context and question placeholders."""
        prompt = QA_USER_PROMPTS["fr"]
        assert "{context}" in prompt
        assert "{question}" in prompt
        assert "EXTRAITS DE DOCUMENTS" in prompt

    def test_legacy_alias_matches_english(self):
        """Legacy QA_SYSTEM_PROMPT should match English version."""
        assert QA_SYSTEM_PROMPT == QA_SYSTEM_PROMPTS["en"]


class TestGetQaSystemPrompt:
    """Tests for get_qa_system_prompt function."""

    def test_returns_english_by_default(self):
        """get_qa_system_prompt should return English by default."""
        prompt = get_qa_system_prompt()
        assert prompt == QA_SYSTEM_PROMPTS["en"]

    def test_returns_english_when_specified(self):
        """get_qa_system_prompt('en') should return English."""
        prompt = get_qa_system_prompt("en")
        assert prompt == QA_SYSTEM_PROMPTS["en"]

    def test_returns_french_when_specified(self):
        """get_qa_system_prompt('fr') should return French."""
        prompt = get_qa_system_prompt("fr")
        assert prompt == QA_SYSTEM_PROMPTS["fr"]

    def test_fallback_to_english_for_unknown_language(self):
        """get_qa_system_prompt should fallback to English for unknown languages."""
        prompt = get_qa_system_prompt("de")  # German - not supported
        assert prompt == QA_SYSTEM_PROMPTS["en"]


class TestBuildQaPromptBilingual:
    """Tests for bilingual build_qa_prompt function."""

    def test_build_qa_prompt_english_default(self):
        """build_qa_prompt should use English template by default."""
        prompt = build_qa_prompt("What is X?", "Context here")
        assert "What is X?" in prompt
        assert "Context here" in prompt
        assert "DOCUMENT EXCERPTS" in prompt

    def test_build_qa_prompt_english_explicit(self):
        """build_qa_prompt with language='en' should use English."""
        prompt = build_qa_prompt("What is X?", "Context here", language="en")
        assert "DOCUMENT EXCERPTS" in prompt
        assert "QUESTION" in prompt

    def test_build_qa_prompt_french(self):
        """build_qa_prompt with language='fr' should use French."""
        prompt = build_qa_prompt("Quelle est la durée?", "Contexte ici", language="fr")
        assert "EXTRAITS DE DOCUMENTS" in prompt
        assert "Quelle est la durée?" in prompt
        assert "Contexte ici" in prompt

    def test_build_qa_prompt_fallback_for_unknown_language(self):
        """build_qa_prompt should fallback to English for unknown languages."""
        prompt = build_qa_prompt("Question?", "Context", language="de")
        assert "DOCUMENT EXCERPTS" in prompt  # English template


class TestDetectLanguageFromChunks:
    """Tests for detect_language_from_chunks function."""

    def test_empty_chunks_returns_english(self):
        """detect_language_from_chunks should return 'en' for empty list."""
        assert detect_language_from_chunks([]) == "en"

    def test_english_chunks_detected(self):
        """detect_language_from_chunks should detect English from chunks."""

        @dataclass
        class MockChunk:
            content: str

        chunks = [
            MockChunk(content="This is a contract agreement between parties."),
            MockChunk(content="The termination period shall be 30 days."),
            MockChunk(content="Payment is due within 15 business days."),
        ]
        assert detect_language_from_chunks(chunks) == "en"

    def test_french_chunks_detected(self):
        """detect_language_from_chunks should detect French from chunks."""

        @dataclass
        class MockChunk:
            content: str

        chunks = [
            MockChunk(content="Ceci est un contrat de service entre les parties."),
            MockChunk(content="La période de préavis est de 30 jours."),
            MockChunk(content="Le paiement est dû dans les 15 jours ouvrables."),
        ]
        assert detect_language_from_chunks(chunks) == "fr"

    def test_single_chunk_detection(self):
        """detect_language_from_chunks should work with single chunk."""

        @dataclass
        class MockChunk:
            content: str

        # French
        chunks_fr = [MockChunk(content="Le contrat prend fin après une période de 12 mois.")]
        assert detect_language_from_chunks(chunks_fr) == "fr"

        # English
        chunks_en = [MockChunk(content="The contract terminates after a period of 12 months.")]
        assert detect_language_from_chunks(chunks_en) == "en"

    def test_samples_first_three_chunks(self):
        """detect_language_from_chunks should sample from first 3 chunks."""

        @dataclass
        class MockChunk:
            content: str

        # First 3 are French, rest are English
        chunks = [
            MockChunk(content="Ceci est un contrat français."),
            MockChunk(content="Les conditions générales suivent."),
            MockChunk(content="Le paiement mensuel est requis."),
            MockChunk(content="This is an English section."),
            MockChunk(content="Payment terms are standard."),
        ]
        # Should detect French since it samples first 3
        assert detect_language_from_chunks(chunks) == "fr"
