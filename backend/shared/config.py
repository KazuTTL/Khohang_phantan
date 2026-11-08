# backend/shared/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedConfig(BaseSettings):
    """
    Cấu hình dùng chung cho các node phân tán (Base Configuration).
    """
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    EXCHANGE_NAME: str = "distributed_warehouse"
    DLQ_EXCHANGE_NAME: str = "distributed_warehouse.dlx"
    DLQ_QUEUE_NAME: str = "q.dlq"
    
    # Retry & Timeout
    MAX_OUTBOX_RETRIES: int = 5
    OUTBOX_POLL_INTERVAL_SECONDS: float = 2.0
    CONSUMER_RECONNECT_INTERVAL_SECONDS: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


shared_config = SharedConfig()
