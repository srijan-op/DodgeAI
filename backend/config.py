"""Environment-driven settings. Loads parent `DodgeAI/.env` when present."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    # Logical database name inside the server (multi-DB support). Not the same as `neo4j_user`.
    neo4j_database: str = "neo4j"

    # Comma-separated origins, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Groq (chat agent). Set GROQ_API_KEY in .env. Leave keys empty to disable agent in /api/chat.
    # Optional GROQ_API_KEYS: comma-separated extra keys; on rate limit, the next key is used in order.
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    # Cypher execution caps (chat path)
    cypher_max_limit: int = 100
    cypher_statement_timeout_ms: int = 30_000

    # Chat memory (Redis optional; empty redis_url uses in-process dict per worker)
    redis_url: str = ""
    chat_history_max_turns: int = 10
    chat_history_ttl_seconds: int = 604_800  # 7 days

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def groq_api_key_list(self) -> list[str]:
        keys: list[str] = []
        main = (self.groq_api_key_1 or "").strip()
        if main:
            keys.append(main)
        bulk = (self.groq_api_key_2 or "").strip()
        if bulk:
            for part in bulk.split(","):
                k = part.strip()
                if k and k not in keys:
                    keys.append(k)
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
