"""Константы приложения."""

import os
from pathlib import Path


def _get_appdata_dir() -> Path:
    """Получение директории %APPDATA%\\GMod."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "GMod"
    # Fallback для Linux/macOS или если APPDATA не задан
    return Path.home() / ".gmod"


# Пути (используют %APPDATA%\GMod)
DATA_DIR = _get_appdata_dir()
LOGS_DIR = DATA_DIR / "logs"
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

# Дефолтные модели — только реально предоставляемые провайдерами (09.2026):
# Groq production: llama-3.1-8b-instant, llama-3.3-70b-versatile,
#   openai/gpt-oss-120b, openai/gpt-oss-20b (старые llama3-*-8192 отключены)
# Gemini: gemini-2.5-flash / lite / pro, gemini-3.5-flash
#   (gemini-*-1.5, gemini-2.0-flash, gemini-flash/pro — отключены)
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Дефолтные API-ключи НЕ хранятся в коде (GitHub push-protection их блокирует).
# Задаются одним из способов (приоритет сверху вниз):
#   1. Настройки в приложении (сохраняются в %APPDATA%\GMod\config.yaml),
#   2. переменные окружения GROQ_API_KEY / GEMINI_API_KEY.
DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEFAULT_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Настройки логирования
DEFAULT_LOG_LEVEL = "INFO"
LOG_FILE = LOGS_DIR / "gmod.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
