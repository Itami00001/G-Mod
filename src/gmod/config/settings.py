"""Загрузчик конфигурации из config.yaml с fallback на константы."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from gmod.config.constants import (
    CONFIG_FILE,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    DEFAULT_LEFT_DOCK_WIDTH, DEFAULT_RIGHT_DOCK_WIDTH,
    DEFAULT_MESSAGE_LIMIT, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS,
    DEFAULT_LOG_LEVEL,
)

logger = logging.getLogger(__name__)


class Settings:
    """Загрузчик и хранилище конфигурации приложения.

    Читает data/config.yaml при старте. Если файл недоступен или yaml не
    установлен — использует значения по умолчанию из constants.py.
    """

    _instance: Optional["Settings"] = None

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or CONFIG_FILE
        self._data: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def get(self, *keys: str, default: Any = None) -> Any:
        """Получить значение по цепочке ключей.

        Пример: settings.get("llm", "providers") → список провайдеров.
        """
        node = self._data
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key, default)
            if node is default:
                return default
        return node

    # ------------------------------------------------------------------
    # Удобные свойства для частых обращений
    # ------------------------------------------------------------------

    @property
    def llm_providers(self) -> list:
        """Список конфигураций провайдеров из config.yaml."""
        return self.get("llm", "providers", default=[])

    @property
    def ollama_url(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "ollama":
                return p.get("url", "http://localhost:11434")
        return "http://localhost:11434"

    @property
    def ollama_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "ollama":
                return p.get("model", "llama3.2:3b")
        return "llama3.2:3b"

    @property
    def ollama_api_key(self) -> str:
        """API ключ Ollama Cloud (для локального сервера — пустая строка)."""
        for p in self.llm_providers:
            if p.get("name") == "ollama":
                return p.get("api_key", "") or ""
        return ""

    @property
    def groq_api_key(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "groq":
                return p.get("api_key", "")
        return ""

    @property
    def groq_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "groq":
                return p.get("model", "llama3-8b-8192")
        return "llama3-8b-8192"

    @property
    def gemini_api_key(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "gemini":
                return p.get("api_key", "")
        return ""

    @property
    def gemini_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "gemini":
                return p.get("model", "gemini-flash")
        return "gemini-flash"

    @property
    def message_limit(self) -> int:
        return int(self.get("llm", "message_limit", default=DEFAULT_MESSAGE_LIMIT))

    @property
    def temperature(self) -> float:
        return float(self.get("llm", "temperature", default=DEFAULT_TEMPERATURE))

    @property
    def max_tokens(self) -> int:
        return int(self.get("llm", "max_tokens", default=DEFAULT_MAX_TOKENS))

    @property
    def analysis_depth(self) -> str:
        return self.get("analysis", "depth", default="full")

    @property
    def analysis_unit(self) -> str:
        return self.get("analysis", "unit", default="file")

    @property
    def theme(self) -> str:
        return self.get("app", "theme", default="dark")

    @property
    def log_level(self) -> str:
        return self.get("logging", "level", default=DEFAULT_LOG_LEVEL)

    # ---------- Валидатор (нейросеть с 0) и прогноз ----------
    @property
    def validator_epochs(self) -> int:
        return int(self.get("validator", "epochs", default=50))

    @property
    def validator_lr(self) -> float:
        return float(self.get("validator", "lr", default=0.1))

    @property
    def forecast_horizon(self) -> int:
        """Горизонт прогноза (коммитов вперёд) для UI ползунка."""
        return int(self.get("forecast", "horizon", default=5))

    def build_llm_config(self) -> Dict[str, Any]:
        """Собрать dict конфигурации для LLMProviderFactory из config.yaml."""
        providers = []
        for p in self.llm_providers:
            name = p.get("name", "").lower()
            enabled = p.get("enabled", False)
            entry: Dict[str, Any] = {"name": name, "enabled": enabled}

            if name == "ollama":
                entry["url"] = p.get("url", "http://localhost:11434")
                entry["model"] = p.get("model", "llama3.2:3b")
                entry["api_key"] = p.get("api_key", "") or ""
            elif name == "groq":
                entry["api_key"] = p.get("api_key", "")
                entry["model"] = p.get("model", "llama3-8b-8192")
            elif name == "gemini":
                entry["api_key"] = p.get("api_key", "")
                entry["model"] = p.get("model", "gemini-flash")

            providers.append(entry)

        return {
            "llm": {
                "providers": providers,
                "message_limit": self.message_limit,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            "analysis": {
                "depth": self.analysis_depth,
                "unit": self.analysis_unit,
            },
        }

    # ------------------------------------------------------------------
    # Загрузка
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Загрузка config.yaml. При ошибке — пустой dict (используются defaults)."""
        if not YAML_AVAILABLE:
            logger.warning("pyyaml not installed — using default settings")
            return

        if not self._config_path.exists():
            logger.warning(f"Config file not found: {self._config_path} — using defaults")
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._data = data
                    logger.info(f"Config loaded from {self._config_path}")
                else:
                    logger.warning("Config file is empty or invalid — using defaults")
        except Exception as e:
            logger.error(f"Error loading config: {e} — using defaults")

    def reload(self) -> None:
        """Перечитать конфиг с диска (например, после изменения через UI)."""
        self._data = {}
        self._load()


# ------------------------------------------------------------------
# Глобальный синглтон
# ------------------------------------------------------------------

_settings_instance: Optional[Settings] = None


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Получить глобальный экземпляр Settings (создаётся при первом вызове)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings(config_path)
    return _settings_instance


def reset_settings() -> None:
    """Сбросить синглтон (нужно для тестов)."""
    global _settings_instance
    _settings_instance = None
