"""RAG layer - Retrieval, embeddings, chunking, and LLM integration.

Note: Direct imports from submodules are preferred to avoid circular imports.
"""

__all__ = [
    "Chunk",
    "Chunker",
    "EmbeddingService",
    "LLMConnectionError",
    "LLMError",
    "LLMGenerationError",
    "LLMResponse",
    "LLMTimeoutError",
    "OllamaClient",
    "QA_SYSTEM_PROMPT",
    "RetrievedChunk",
    "Retriever",
    "build_qa_prompt",
]


def __getattr__(name: str):
    """Lazy import to avoid circular imports."""
    if name in ("Chunk", "Chunker"):
        from src.rag.chunking import Chunk, Chunker

        return Chunk if name == "Chunk" else Chunker

    if name == "EmbeddingService":
        from src.rag.embeddings import EmbeddingService

        return EmbeddingService

    if name in (
        "LLMConnectionError",
        "LLMError",
        "LLMGenerationError",
        "LLMResponse",
        "LLMTimeoutError",
        "OllamaClient",
        "QA_SYSTEM_PROMPT",
        "build_qa_prompt",
    ):
        from src.rag.llm import (
            LLMConnectionError,
            LLMError,
            LLMGenerationError,
            LLMResponse,
            LLMTimeoutError,
            OllamaClient,
            QA_SYSTEM_PROMPT,
            build_qa_prompt,
        )

        return {
            "LLMConnectionError": LLMConnectionError,
            "LLMError": LLMError,
            "LLMGenerationError": LLMGenerationError,
            "LLMResponse": LLMResponse,
            "LLMTimeoutError": LLMTimeoutError,
            "OllamaClient": OllamaClient,
            "QA_SYSTEM_PROMPT": QA_SYSTEM_PROMPT,
            "build_qa_prompt": build_qa_prompt,
        }[name]

    if name in ("RetrievedChunk", "Retriever"):
        from src.rag.retriever import RetrievedChunk, Retriever

        return RetrievedChunk if name == "RetrievedChunk" else Retriever

    raise AttributeError(f"module 'src.rag' has no attribute '{name}'")
