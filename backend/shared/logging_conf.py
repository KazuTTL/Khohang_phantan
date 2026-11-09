# backend/shared/logging_conf.py
import logging
import sys


def setup_logging(service_name: str, branch_code: str | None = None) -> logging.Logger:
    """
    Cấu hình Structured Logging chuẩn cho các node dịch vụ phân tán.
    """
    name = f"{service_name}_{branch_code}" if branch_code else service_name
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger
