from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "bge-m3"
    LLM_MODEL: str = "qwen2.5:3b"  # Model chat mặc định nhẹ hơn để tăng tốc độ trên CPU
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 80
    TOP_K: int = 3
    SIMILARITY_THRESHOLD: float = 0.35
    MIN_SCORE_THRESHOLD: float = 0.6
    REQUIRED_CREDITS: int = 120
    OLLAMA_TIMEOUT_EMBED: int = 180
    OLLAMA_TIMEOUT_CHAT: int = 300
    OLLAMA_TIMEOUT_OCR: int = 180
    OLLAMA_KEEP_ALIVE: str = "30m"  # Giữ model trong RAM tránh load lại nhiều lần
    OLLAMA_NUM_CTX: int = 4096  # Context window phù hợp ngữ cảnh học vụ
    OLLAMA_NUM_PREDICT: int = 300  # Giới hạn độ dài token phản hồi
    MAX_CHUNK_CHARS: int = 600  # Cắt ngắn chunk quá dài khi đưa vào prompt LLM

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
