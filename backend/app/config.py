from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Models cấu hình (7b <-> 14b linh hoạt)
    LLM_MODEL: str = "qwen2.5:7b"
    VLM_MODEL: str = "qwen2.5vl:7b"
    REWRITE_MODEL: str = "qwen2.5:7b"
    EMBED_MODEL: str = "bge-m3"
    EMBEDDING_MODEL: str = "bge-m3"
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:7b"
    
    # RAG & Chunking
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 80
    TOP_K: int = 4
    SIMILARITY_THRESHOLD: float = 0.35
    MIN_SCORE_THRESHOLD: float = 0.6
    RAG_TOP_CANDIDATES: int = 15
    RAG_FINAL_TOP_K: int = 4
    MAX_CHUNK_CHARS: int = 600

    # Quy định tốt nghiệp & Giới hạn học kỳ (chuyển từ hard-code sang config)
    # TODO (Quy chế học vụ cần kiểm chứng nguồn chính thức):
    # 1. Công thức GPA tích lũy khi chưa học lại: Chưa có trích dẫn văn bản chính thức xác nhận
    #    tính toàn bộ môn F hay chỉ tính môn đạt. Cần kiểm chứng từ Quyết định đào tạo gốc của LHU.
    # 2. Quy định học lại lấy điểm: VB1 quy định lấy điểm lần học cuối (QĐ 22 Điều 11 Khoản 5đ),
    #    trong khi VB2 ghi nhận lấy điểm cao nhất các lần học (chưa kiểm chứng).
    # 3. Tuyệt đối KHÔNG viết các quy định chưa kiểm chứng vào câu trả lời của bot như sự thật
    #    nếu chưa có trích dẫn chính xác từ văn bản quy định RAG.
    REQUIRED_CREDITS: int = 150
    MIN_GRADUATION_GPA: float = 5.0  # Nguồn: QĐ 1013/QĐ-ĐHLH Mục A.1.2 (GPA toàn khóa >= 5.0 thang 10)
    SUGGESTED_CREDITS_PER_SEMESTER: int = 20  # Gợi ý tiến độ học kỳ chính; mức này là giả định của hệ thống, hãy xác nhận với Phòng Đào tạo
    SUGGESTED_CREDITS_SUMMER: int = 8  # Gợi ý tiến độ học kỳ hè; mức này là giả định của hệ thống, hãy xác nhận với Phòng Đào tạo
    MAX_CREDITS_PER_SEMESTER: int = 20  # Alias tương thích ngược (trỏ tới SUGGESTED_CREDITS_PER_SEMESTER)
    MAX_CREDITS_SUMMER: int = 8  # Alias tương thích ngược (trỏ tới SUGGESTED_CREDITS_SUMMER)
    MAX_STANDARD_SEMESTERS: int = 8  # Nguồn: Niên giám 2023 Mục 7.1 (CTĐT 8 học kỳ)
    MAX_EXTENDED_SEMESTERS: int = 12  # Nguồn: QĐ 22 Điều 3 Khoản 1 (tối đa 6 năm / 12 học kỳ chính)
    
    # Thời gian chờ (Timeout)
    OCR_TIMEOUT_SECONDS: int = 300
    OLLAMA_TIMEOUT_EMBED: int = 180
    OLLAMA_TIMEOUT_CHAT: int = 300
    OLLAMA_TIMEOUT_OCR: int = 300
    
    # Tối ưu bộ nhớ máy 4GB VRAM, 16GB RAM
    KEEP_ALIVE: str = "15m"
    OLLAMA_KEEP_ALIVE: str = "15m"
    VLM_KEEP_ALIVE: str = "0s"  # Giải phóng VRAM ngay sau khi VLM đọc xong
    NUM_CTX: int = 4096
    OLLAMA_NUM_CTX: int = 4096
    OLLAMA_NUM_PREDICT: int = 1000
    MAX_IMAGE_DIM: int = 1280  # Cạnh dài ảnh tối đa <= 1280px

    # Cổng trường LHU (DKMH)
    LHU_PORTAL_URL: str = "https://tapi.lhu.edu.vn"
    LHU_SESSION_TTL_SECONDS: int = 1800  # 30 phút
    LHU_LOCKOUT_ATTEMPTS: int = 5
    LHU_LOCKOUT_SECONDS: int = 900  # 15 phút
    DAO_TAO_OFFICE: str = "B101, Cơ sở 1"
    DKMH_URL: str = "https://dkmh.lhu.edu.vn"
    GPA4_ROUND_1DP: bool = False  # Làm tròn 1 chữ số thập phân (half-up) cho GPA thang 4 (mặc định False)
    
    # Tư vấn học vụ & Tùy chọn LLM
    ADVISORY_USE_LLM: bool = True  # True: Dùng LLM format lại 4 phần; False: Dùng bản dựng sẵn từ code (cho máy yếu)
    ADVISORY_TEMPERATURE: float = 0.2
    REWRITE_TEMPERATURE: float = 0.0

    # Debug & Logging
    DEBUG_MODE: bool = True
    
    OLLAMA_NUM_THREAD: Optional[int] = None
    OLLAMA_NUM_BATCH: Optional[int] = None

    @model_validator(mode="after")
    def sync_aliases(self):
        # Đồng bộ alias model và context giữa các biến cũ và mới
        if self.VLM_MODEL and not self.OLLAMA_VISION_MODEL:
            self.OLLAMA_VISION_MODEL = self.VLM_MODEL
        elif self.OLLAMA_VISION_MODEL and not self.VLM_MODEL:
            self.VLM_MODEL = self.OLLAMA_VISION_MODEL
            
        if self.EMBED_MODEL and not self.EMBEDDING_MODEL:
            self.EMBEDDING_MODEL = self.EMBED_MODEL
        elif self.EMBEDDING_MODEL and not self.EMBED_MODEL:
            self.EMBED_MODEL = self.EMBEDDING_MODEL
            
        if self.NUM_CTX:
            self.OLLAMA_NUM_CTX = self.NUM_CTX
            
        if self.KEEP_ALIVE:
            self.OLLAMA_KEEP_ALIVE = self.KEEP_ALIVE
            
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
