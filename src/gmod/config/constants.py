"""Константы приложения."""

from pathlib import Path

# Пути
DATA_DIR = Path("data")
LOGS_DIR = Path("logs")
CONFIG_FILE = DATA_DIR / "config.yaml"
DATABASE_FILE = DATA_DIR / "gmod.db"

# Настройки БД
DB_VERSION = 1

# Настройки UI
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
DEFAULT_LEFT_DOCK_WIDTH = 250
DEFAULT_RIGHT_DOCK_WIDTH = 300

# Настройки LLM
DEFAULT_MESSAGE_LIMIT = 7
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000

# Настройки логирования
DEFAULT_LOG_LEVEL = "INFO"
LOG_FILE = LOGS_DIR / "gmod.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
