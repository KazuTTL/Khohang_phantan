# backend/shared/config.py
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HQSettings(BaseSettings):
    """Cấu hình cho Trụ sở chính (HQ Node - 8000)"""
    DB_URL: str = Field(default="sqlite+aiosqlite:///./db_hq.db", alias="DATABASE_URL")
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")
    PORT: int = Field(default=8000, alias="PORT")
    HOST: str = Field(default="0.0.0.0", alias="HOST")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )


class BranchSettings(BaseSettings):
    """Cấu hình cho Branch Service (HN - 8001 | HCM - 8002)"""
    BRANCH_CODE: Literal["HN", "HCM"] = Field(
        ...,
        description="Mã định danh chi nhánh (chỉ chấp nhận 'HN' hoặc 'HCM')",
        alias="BRANCH_CODE"
    )
    BRANCH_NAME: str = Field(default="", alias="BRANCH_NAME")
    PORT: int = Field(default=8001, alias="PORT")
    HOST: str = Field(default="0.0.0.0", alias="HOST")
    DB_URL: str = Field(default="", alias="DATABASE_URL")
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    HQ_API_URL: str = Field(default="http://localhost:8000", alias="HQ_API_URL")
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    def get_db_url(self) -> str:
        if self.DB_URL:
            return self.DB_URL
        code = self.BRANCH_CODE.lower()
        return f"sqlite+aiosqlite:///./db_branch_{code}.db"


@lru_cache()
def get_hq_settings() -> HQSettings:
    return HQSettings()


@lru_cache()
def get_branch_settings() -> BranchSettings:
    return BranchSettings()
