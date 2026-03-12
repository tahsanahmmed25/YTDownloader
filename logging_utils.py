import logging
from logging.handlers import RotatingFileHandler
import os

from app_config import LOG_DIR, ensure_dir

_LOGGER = None


def setup_logging():
    global _LOGGER
    if _LOGGER:
        return _LOGGER

    ensure_dir(LOG_DIR)
    log_path = os.path.join(LOG_DIR, "app.log")

    logger = logging.getLogger("ytdownloader")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _LOGGER = logger
    return logger


def get_logger():
    return setup_logging()
