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

    # Comma-separated allowed CORS origins
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
