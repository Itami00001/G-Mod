"""Конфигурация логирования."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from gmod.config.constants import LOG_BACKUP_COUNT, LOG_FILE, LOG_MAX_BYTES


def setup_logging(level: str = "INFO") -> None:
    """Настройка логирования."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
