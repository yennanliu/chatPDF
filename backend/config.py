from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    google_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    @property
    def resolved_google_api_key(self) -> str:
        return self.google_api_key or self.gemini_api_key

    embedding_backend: str = "local"  # local | openai

    chroma_data_dir: str = "../chroma_data"
    upload_dir: str = "../uploads"
    sqlite_url: str = "sqlite:///../chatpdf.db"
    eval_gold_path: str = "../eval/gold.json"  # persisted RAG-eval gold set

    # ── Langfuse observability (optional) ─────────────────────────────────────
    # When both keys are set, every LLM call (chat / eval answer / judge / query
    # expansion) is traced and eval metrics are pushed as scores. Unset → no-op.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"  # or https://us.cloud.langfuse.com / self-host URL

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    # Comma-separated allowed CORS origins
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Resource bounds (DoS / cost / context-bloat guards) ───────────────────
    max_upload_mb: int = 50           # reject PDFs larger than this
    max_query_chars: int = 8000       # reject oversized chat queries
    max_docs_per_session: int = 50    # cap fan-out across collections
    max_history_messages: int = 20    # window chat history (≈10 turns) into context
    llm_max_retries: int = 2          # provider-SDK retries for transient errors
    warm_reranker_on_startup: bool = False  # preload cross-encoder at boot (slow start)
    chat_response_scoring: bool = True  # judge each chat answer after streaming (extra LLM call/turn)


settings = Settings()
