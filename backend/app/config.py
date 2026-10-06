from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "bge-m3"
    LLM_MODEL: str = "qwen2.5:7b"
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 80
    TOP_K: int = 4
    SIMILARITY_THRESHOLD: float = 0.35
    REQUIRED_CREDITS: int = 120
    OLLAMA_TIMEOUT_EMBED: int = 60
    OLLAMA_TIMEOUT_CHAT: int = 180

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
