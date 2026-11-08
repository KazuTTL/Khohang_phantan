# backend/shared/logging_conf.py
import logging
import sys


def setup_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Khởi tạo và cấu hình Logger chuẩn hóa cho toàn bộ các node dịch vụ phân tán.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Disable propagating to root if handled
    logger.propagate = False
    return logger
