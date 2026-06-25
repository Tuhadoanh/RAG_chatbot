# backend/app/core/config.py
from pydantic_settings import BaseSettings
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    GOOGLE_API_KEY: str

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str

    MONGODB_URI: str
    MONGODB_DATABASE: str

    RETRIEVER_SCORE_THRESHOLD: float = 0.5
    RETRIEVER_K: int = 5
    BM25_WEIGHT: float = 0.3
    FAISS_WEIGHT: float = 0.7
    EMBEDDING_BATCH_SIZE: int = 1400

    DB_FAISS_PATH: str = "faiss_db"
    BM25_INDEX_PATH: str = "bm25_index/bm25.pkl"
    NEW_SOURCES_PATH: str = "./New_Sources"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Export sang os.environ để các thư viện bên thứ 3 (Google SDK, LangChain)
# tự tìm được biến môi trường bằng os.getenv()
os.environ.setdefault("GOOGLE_API_KEY", settings.GOOGLE_API_KEY)