from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""

    embedding_backend: str = "local"  # local | openai

    chroma_data_dir: str = "../chroma_data"
    upload_dir: str = "../uploads"
    sqlite_url: str = "sqlite:///../chatpdf.db"


settings = Settings()
