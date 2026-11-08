"""Настройка логирования: формат, уровень, ротация файлов."""

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import get_settings

LOG_FORMAT = "%(levelname)s %(asctime)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
LOG_FILE = "actions.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3


def setup_logging():
    """Настраивает ротируемый файл логов и возвращает корневой логгер."""
    settings = get_settings()
    logger = logging.getLogger("valutatrade")
    if logger.handlers:
        return logger

    level_name = str(settings.get("log_level", "INFO")).upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.propagate = False

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.log_dir / LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(logging.CRITICAL)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(console)
    return logger


def get_logger(name):
    """Возвращает настроенный логгер с указанным именем."""
    setup_logging()
    return logging.getLogger(f"valutatrade.{name}")


def set_console_level(level_name):
    """Меняет уровень вывода в консоль (INFO для update-rates)."""
    logger = setup_logging()
    level = getattr(logging, str(level_name).upper(), logging.CRITICAL)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(level)
