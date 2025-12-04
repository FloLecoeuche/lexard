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
    build_qa_prompt,
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
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client.generate("Test")

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://localhost:11434/api/chat"


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

            mock_client.get.assert_called_once_with(
                "http://localhost:11434/api/tags"
            )


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
