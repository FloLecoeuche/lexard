"""Performance benchmarking tools for Lexard."""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark run."""

    name: str
    iterations: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    target_ms: float | None = None
    errors: list[str] = field(default_factory=list)

    def passes_target(self) -> bool:
        """Check if P95 latency meets target."""
        if self.target_ms is None:
            return True
        return self.p95_ms <= self.target_ms

    @property
    def passed(self) -> bool:
        """Alias for passes_target."""
        return self.passes_target()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "target_ms": self.target_ms,
            "passed": self.passed,
            "errors": self.errors,
        }


@dataclass
class ConcurrencyResult:
    """Result of concurrent request benchmark."""

    name: str
    concurrency: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p95_ms: float
    requests_per_second: float
    target_ms: float | None = None

    def passes_target(self) -> bool:
        """Check if P95 latency meets target."""
        if self.target_ms is None:
            return True
        return self.p95_ms <= self.target_ms

    @property
    def passed(self) -> bool:
        """Alias for passes_target."""
        return self.passes_target()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "concurrency": self.concurrency,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "target_ms": self.target_ms,
            "passed": self.passed,
        }


class PerformanceBenchmark:
    """Performance benchmarking suite for Lexard API."""

    # Performance targets from PRD
    TARGETS = {
        "rag_query": 3000,  # ms
        "ingestion_10_pages": 15000,  # ms
        "embedding_per_chunk": 500,  # ms
        "concurrent_10_req": 5000,  # ms P95
    }

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.client = httpx.Client(timeout=60.0)
        self.async_client: httpx.AsyncClient | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
        if self.async_client:
            asyncio.get_event_loop().run_until_complete(
                self.async_client.aclose()
            )

    @staticmethod
    def _percentile(data: list[float], percentile: int) -> float:
        """Calculate percentile from a list of values."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    @staticmethod
    def _calculate_stats(times: list[float]) -> dict[str, float]:
        """Calculate statistics from timing data."""
        if not times:
            return {
                "min_ms": 0.0,
                "max_ms": 0.0,
                "mean_ms": 0.0,
                "median_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }
        return {
            "min_ms": min(times),
            "max_ms": max(times),
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "p95_ms": PerformanceBenchmark._percentile(times, 95),
            "p99_ms": PerformanceBenchmark._percentile(times, 99),
        }

    def benchmark_query(
        self,
        document_id: str | UUID,
        question: str = "What are the key terms?",
        iterations: int = 10,
    ) -> BenchmarkResult:
        """Benchmark RAG query latency."""
        times: list[float] = []
        errors: list[str] = []

        for i in range(iterations):
            try:
                start = time.perf_counter()
                response = self.client.post(
                    f"{self.api_url}/query",
                    json={
                        "document_id": str(document_id),
                        "question": question,
                    },
                )
                elapsed = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    times.append(elapsed)
                else:
                    errors.append(
                        f"Iteration {i + 1}: HTTP {response.status_code}"
                    )
            except Exception as e:
                errors.append(f"Iteration {i + 1}: {str(e)}")

        stats = self._calculate_stats(times)
        return BenchmarkResult(
            name="rag_query",
            iterations=iterations,
            target_ms=self.TARGETS["rag_query"],
            errors=errors,
            **stats,
        )

    def benchmark_upload(
        self,
        file_path: str | Path,
        iterations: int = 5,
    ) -> BenchmarkResult:
        """Benchmark document ingestion latency."""
        times: list[float] = []
        errors: list[str] = []
        file_path = Path(file_path)

        for i in range(iterations):
            try:
                with open(file_path, "rb") as f:
                    start = time.perf_counter()
                    response = self.client.post(
                        f"{self.api_url}/upload",
                        files={"file": (file_path.name, f)},
                    )
                    elapsed = (time.perf_counter() - start) * 1000

                if response.status_code in (200, 201):
                    times.append(elapsed)
                else:
                    errors.append(
                        f"Iteration {i + 1}: HTTP {response.status_code}"
                    )
            except Exception as e:
                errors.append(f"Iteration {i + 1}: {str(e)}")

        stats = self._calculate_stats(times)
        return BenchmarkResult(
            name="document_ingestion",
            iterations=iterations,
            target_ms=self.TARGETS["ingestion_10_pages"],
            errors=errors,
            **stats,
        )

    def benchmark_embeddings(
        self,
        texts: list[str] | None = None,
        iterations: int = 10,
    ) -> BenchmarkResult:
        """Benchmark embedding generation latency."""
        from src.rag.embeddings import EmbeddingsService

        if texts is None:
            texts = [
                "This is a sample contract text for testing embeddings."
            ]

        service = EmbeddingsService()
        times: list[float] = []
        errors: list[str] = []

        for i in range(iterations):
            try:
                for text in texts:
                    start = time.perf_counter()
                    service.embed(text)
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
            except Exception as e:
                errors.append(f"Iteration {i + 1}: {str(e)}")

        stats = self._calculate_stats(times)
        return BenchmarkResult(
            name="embedding_generation",
            iterations=iterations * len(texts or [1]),
            target_ms=self.TARGETS["embedding_per_chunk"],
            errors=errors,
            **stats,
        )

    async def _async_request(
        self,
        document_id: str,
        question: str,
    ) -> tuple[float, bool, str | None]:
        """Make a single async request and return timing."""
        if self.async_client is None:
            self.async_client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_connections=100),
            )

        try:
            start = time.perf_counter()
            response = await self.async_client.post(
                f"{self.api_url}/query",
                json={
                    "document_id": document_id,
                    "question": question,
                },
            )
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, response.status_code == 200, None
        except Exception as e:
            return 0.0, False, str(e)

    async def _run_concurrent_batch(
        self,
        document_id: str,
        question: str,
        concurrency: int,
    ) -> list[tuple[float, bool, str | None]]:
        """Run a batch of concurrent requests."""
        tasks = [
            self._async_request(document_id, question)
            for _ in range(concurrency)
        ]
        return await asyncio.gather(*tasks)

    def benchmark_concurrent(
        self,
        document_id: str | UUID,
        question: str = "What are the key terms?",
        concurrency: int = 10,
        batches: int = 3,
    ) -> ConcurrencyResult:
        """Benchmark concurrent request handling."""
        all_times: list[float] = []
        successful = 0
        failed = 0
        total_duration = 0.0

        for _ in range(batches):
            start = time.perf_counter()
            results = asyncio.get_event_loop().run_until_complete(
                self._run_concurrent_batch(
                    str(document_id),
                    question,
                    concurrency,
                )
            )
            batch_duration = time.perf_counter() - start
            total_duration += batch_duration

            for elapsed, success, _error in results:
                if success:
                    all_times.append(elapsed)
                    successful += 1
                else:
                    failed += 1

        total_requests = concurrency * batches
        rps = successful / total_duration if total_duration > 0 else 0

        stats = self._calculate_stats(all_times)
        return ConcurrencyResult(
            name="concurrent_requests",
            concurrency=concurrency,
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            min_ms=stats["min_ms"],
            max_ms=stats["max_ms"],
            mean_ms=stats["mean_ms"],
            p95_ms=stats["p95_ms"],
            requests_per_second=rps,
            target_ms=self.TARGETS["concurrent_10_req"],
        )

    def run_all_benchmarks(
        self,
        document_id: str | UUID,
        file_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Run all benchmarks and return results."""
        results = {}

        # RAG query benchmark
        results["rag_query"] = self.benchmark_query(document_id).to_dict()

        # Upload benchmark (if file provided)
        if file_path:
            results["upload"] = self.benchmark_upload(file_path).to_dict()

        # Embeddings benchmark
        results["embeddings"] = self.benchmark_embeddings().to_dict()

        # Concurrent requests benchmark
        results["concurrent"] = self.benchmark_concurrent(
            document_id
        ).to_dict()

        return results
