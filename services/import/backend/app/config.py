"""Environment-backed configuration for the Import Service."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings required by the locked Import Service SRS."""

    mongodb_uri: str = "mongodb://mongodb:27017/aunqa_ps"
    chromadb_host: str = "chromadb"
    chromadb_port: int = 8000
    project_data_root: Path = Path("/app/project-data")

    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    chunk_size: int = 500
    chunk_overlap: int = 100

    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    connection_timeout_ms: int = 5_000

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("embedding_model")
    @classmethod
    def embedding_model_is_locked(cls, value: str) -> str:
        if value != "BAAI/bge-m3":
            raise ValueError("EMBEDDING_MODEL is locked to BAAI/bge-m3 by the SRS")
        return value

    @field_validator("embedding_dimension")
    @classmethod
    def embedding_dimension_is_locked(cls, value: int) -> int:
        if value != 1024:
            raise ValueError("EMBEDDING_DIMENSION is locked to 1024 by the SRS")
        return value

    @field_validator("chunk_size")
    @classmethod
    def chunk_size_is_locked(cls, value: int) -> int:
        if value != 500:
            raise ValueError("CHUNK_SIZE is locked to 500 by the SRS")
        return value

    @field_validator("chunk_overlap")
    @classmethod
    def chunk_overlap_is_locked(cls, value: int) -> int:
        if value != 100:
            raise ValueError("CHUNK_OVERLAP is locked to 100 by the SRS")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()
