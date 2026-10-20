import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "splitsmart-dev-secret-key-123")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT") or 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "splitsmart_db")
    DB_POOL_NAME = os.getenv("DB_POOL_NAME", "splitsmart_pool")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE") or 10)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

