"""Configuration management for Lexard.

Loads settings from YAML file with environment variable overrides.
Environment variables use prefix LEXARD_ with double underscore for nesting.
Example: LEXARD_LLM__MODEL=llama3:8b
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


class AppConfig(BaseModel):
    """Application-level configuration."""

    name: str = "Lexard"
    environment: Literal["development", "production"] = "development"
    log_level: Literal["debug", "info", "warning", "error"] = "info"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "ollama"
    model: str = "mistral:7b-instruct"
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)
    timeout_seconds: int = Field(default=30, ge=1)


class EmbeddingsConfig(BaseModel):
    """Embeddings model configuration."""

    model: str = "all-mpnet-base-v2"
    batch_size: int = Field(default=32, ge=1)
    device: Literal["cpu", "cuda"] = "cpu"


class ChunkingConfig(BaseModel):
    """Document chunking configuration."""

    method: str = "fixed"
    size: int = Field(default=512, ge=1)
    overlap: int = Field(default=50, ge=0)


class QdrantConfig(BaseModel):
    """Qdrant vector database configuration."""

    host: str = "localhost"
    port: int = Field(default=6333, ge=1, le=65535)
    collection: str = "documents"


class RetrievalConfig(BaseModel):
    """RAG retrieval configuration."""

    top_k: int = Field(default=8, ge=1)
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    rerank: bool = False


class GuardrailsConfig(BaseModel):
    """Output guardrails configuration."""

    hallucination_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    enable_pii_filter: bool = True
    max_retries: int = Field(default=2, ge=0)


class StorageConfig(BaseModel):
    """File storage configuration."""

    upload_dir: str = "./data/uploads"
    max_file_size_mb: int = Field(default=50, ge=1)


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1)


class Settings(BaseModel):
    """Root settings container for all configuration."""

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


class ConfigurationError(Exception):
    """Raised when configuration loading fails."""

    pass


def _get_env_override(env_vars: dict, prefix: str, key: str) -> str | None:
    """Get environment variable override for a config key.

    Args:
        env_vars: Dictionary of environment variables
        prefix: Environment variable prefix (e.g., 'LEXARD_')
        key: Config key with double underscore nesting (e.g., 'LLM__MODEL')

    Returns:
        Environment variable value or None if not set
    """
    env_key = f"{prefix}{key}".upper()
    return env_vars.get(env_key)


def _apply_env_overrides(config_dict: dict, env_vars: dict, prefix: str = "LEXARD_") -> dict:
    """Apply environment variable overrides to config dictionary.

    Environment variables use the format: LEXARD_SECTION__KEY=value
    Example: LEXARD_LLM__MODEL=llama3:8b

    Args:
        config_dict: Configuration dictionary loaded from YAML
        env_vars: Dictionary of environment variables
        prefix: Environment variable prefix

    Returns:
        Updated configuration dictionary
    """
    result = config_dict.copy()

    for section_key, section_value in result.items():
        if isinstance(section_value, dict):
            updated_section = section_value.copy()
            for key, value in section_value.items():
                env_key = f"{prefix}{section_key}__{key}".upper()
                if env_key in env_vars:
                    env_value = env_vars[env_key]
                    # Convert string to appropriate type
                    if isinstance(value, bool):
                        updated_section[key] = env_value.lower() in ("true", "1", "yes")
                    elif isinstance(value, int):
                        updated_section[key] = int(env_value)
                    elif isinstance(value, float):
                        updated_section[key] = float(env_value)
                    else:
                        updated_section[key] = env_value
            result[section_key] = updated_section

    return result


def _find_config_file() -> Path:
    """Find the configuration file.

    Searches in order:
    1. CONFIG_PATH environment variable
    2. config/config.yaml (relative to cwd)
    3. config/config.yaml (relative to project root)

    Returns:
        Path to configuration file

    Raises:
        ConfigurationError: If no configuration file found
    """
    import os

    # Check CONFIG_PATH environment variable
    if config_path := os.environ.get("CONFIG_PATH"):
        path = Path(config_path)
        if path.exists():
            return path
        raise ConfigurationError(f"Configuration file not found at CONFIG_PATH: {config_path}")

    # Check relative to current working directory
    cwd_config = Path("config/config.yaml")
    if cwd_config.exists():
        return cwd_config

    # Check relative to this file's location (project root)
    project_root = Path(__file__).parent.parent
    project_config = project_root / "config" / "config.yaml"
    if project_config.exists():
        return project_config

    raise ConfigurationError(
        "Configuration file not found. "
        "Please create config/config.yaml or set CONFIG_PATH environment variable. "
        "See config/config.example.yaml for a template."
    )


def load_settings(config_path: Path | None = None, env_vars: dict | None = None) -> Settings:
    """Load settings from YAML file with environment variable overrides.

    Args:
        config_path: Optional path to config file. If None, searches default locations.
        env_vars: Optional dict of environment variables. If None, uses os.environ.

    Returns:
        Validated Settings instance

    Raises:
        ConfigurationError: If config file not found or invalid
    """
    import os

    if env_vars is None:
        env_vars = dict(os.environ)

    if config_path is None:
        config_path = _find_config_file()

    try:
        with open(config_path) as f:
            config_dict = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
    except OSError as e:
        raise ConfigurationError(f"Failed to read configuration file: {e}")

    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict, env_vars)

    try:
        return Settings(**config_dict)
    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    This function is cached to avoid re-reading the config file on every call.
    Use load_settings() directly if you need to reload configuration.

    Returns:
        Validated Settings instance

    Raises:
        ConfigurationError: If config file not found or invalid
    """
    return load_settings()
