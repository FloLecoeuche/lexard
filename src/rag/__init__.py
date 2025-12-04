"""RAG layer - Retrieval, embeddings, chunking, and LLM integration."""

from src.rag.chunking import Chunk, Chunker
from src.rag.embeddings import EmbeddingService
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
from src.rag.retriever import RetrievedChunk, Retriever

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
