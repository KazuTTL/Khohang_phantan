# backend/branch_service/config.py
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BranchSettings(BaseSettings):
    """
    Cấu hình riêng cho Branch Service.
    Tuân thủ Nguyên tắc 6: Branch service là 1 codebase duy nhất,
    phân biệt các instance thông qua biến môi trường BRANCH_CODE.
    """
    BRANCH_CODE: Literal["HN", "HCM"] = Field(
        ...,
        description="Mã định danh chi nhánh (chỉ chấp nhận 'HN' hoặc 'HCM')",
        alias="BRANCH_CODE"
    )
    BRANCH_NAME: str = Field(default="", alias="BRANCH_NAME")
    PORT: int = Field(default=8001, alias="PORT")
    HOST: str = Field(default="0.0.0.0", alias="HOST")

    # URL kết nối cơ sở dữ liệu riêng của chi nhánh (CẤM cross-DB query)
    DB_URL: str = Field(default="", alias="DATABASE_URL")
    
    # URL RabbitMQ Broker
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    
    # URL HTTP tới Node Trụ sở chính (chỉ dùng cho health ping kiểm tra kết nối)
    HQ_API_URL: str = Field(default="http://localhost:8000", alias="HQ_API_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    @field_validator("BRANCH_CODE", mode="before")
    @classmethod
    def validate_branch_code(cls, v: str) -> str:
        if not v:
            raise ValueError("Biến môi trường BRANCH_CODE là bắt buộc ('HN' hoặc 'HCM')")
        v_upper = v.strip().upper()
        if v_upper not in ("HN", "HCM"):
            raise ValueError(f"BRANCH_CODE '{v}' không hợp lệ. Chỉ chấp nhận 'HN' hoặc 'HCM'")
        return v_upper

    def get_db_url(self) -> str:
        """Trả về connection string CSDL tương ứng với chi nhánh"""
        if self.DB_URL:
            return self.DB_URL
        code = self.BRANCH_CODE.lower()
        return f"sqlite+aiosqlite:///./db_branch_{code}.db"

    def get_branch_display_name(self) -> str:
        if self.BRANCH_NAME:
            return self.BRANCH_NAME
        return "Kho Chi Nhánh Hà Nội" if self.BRANCH_CODE == "HN" else "Kho Chi Nhánh TP.HCM"


# Khởi tạo singleton configuration
branch_settings = BranchSettings()
