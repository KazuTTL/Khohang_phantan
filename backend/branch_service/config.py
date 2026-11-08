# backend/branch_service/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class BranchSettings(BaseSettings):
    """
    NGUYÊN TẮC 6: Branch service là 1 codebase duy nhất,
    phân biệt các instance thông qua biến môi trường BRANCH_CODE.
    """
    BRANCH_CODE: str = "HN"
    BRANCH_NAME: str = "Kho Chi Nhánh Hà Nội"
    PORT: int = 8001
    HOST: str = "0.0.0.0"

    # Single Database Engine cho DB của chi nhánh tương ứng
    # Hỗ trợ SQL Server vật lý (1434 cho HN, 1435 cho HCM) hoặc sqlite fallback
    DATABASE_URL: str = ""

    # RabbitMQ URL
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        code = self.BRANCH_CODE.strip().lower()
        return f"sqlite+aiosqlite:///./db_branch_{code}.db"


branch_settings = BranchSettings()
