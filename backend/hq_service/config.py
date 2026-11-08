# backend/hq_service/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class HQSettings(BaseSettings):
    """Cấu hình riêng cho Node Trụ sở chính (HQ Node - 8000)"""
    SERVICE_NAME: str = "HQ_SERVICE"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Single Database Engine cho DB_HQ
    # Hỗ trợ cấu hình SQL Server vật lý (port 1433) hoặc sqlite fallback cho môi trường local
    DATABASE_URL: str = "sqlite+aiosqlite:///./db_hq.db"
    
    # RabbitMQ URL
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


hq_settings = HQSettings()
