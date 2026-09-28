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
    DEFAULT_OLLAMA_URL, DEFAULT_OLLAMA_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_GEMINI_MODEL,
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
        """API ключ Ollama Cloud: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("ollama")

    @property
    def groq_api_key(self) -> str:
        """API ключ Groq: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("groq")

    @property
    def gemini_api_key(self) -> str:
        """API ключ Gemini: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("gemini")

    @property
    def openai_api_key(self) -> str:
        """API ключ OpenAI: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("openai")

    @property
    def anthropic_api_key(self) -> str:
        """API ключ Anthropic: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("anthropic")

    def _resolve_key(self, account: str) -> str:
        """Приоритет ТЗ §4.2: OS Credential Store -> env -> legacy YAML."""
        yaml_key = ""
        for p in self.llm_providers:
            if p.get("name") == account:
                yaml_key = p.get("api_key", "") or ""
                break
        try:
            from gmod.infrastructure.credentials.credential_service import (
                get_credential_service,
            )
            return get_credential_service().get_key(account, yaml_key)
        except Exception:
            return yaml_key

    def key_source(self, account: str) -> str:
        """Где лежит ключ: keyring | env | legacy | none (для UI)."""
        yaml_key = ""
        for p in self.llm_providers:
            if p.get("name") == account:
                yaml_key = p.get("api_key", "") or ""
                break
        try:
            from gmod.infrastructure.credentials.credential_service import (
                get_credential_service,
            )
            return get_credential_service().key_source(account, yaml_key)
        except Exception:
            return "legacy" if yaml_key else "none"

    def legacy_keys(self) -> Dict[str, str]:
        """Непустые ключи из config.yaml — кандидаты на миграцию (ТЗ §4.2)."""
        found: Dict[str, str] = {}
        for p in self.llm_providers:
            name = (p.get("name") or "").lower()
            key = p.get("api_key", "") or ""
            if name and key:
                found[name] = key
        return found

    @property
    def groq_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "groq":
                return p.get("model", DEFAULT_GROQ_MODEL)
        return DEFAULT_GROQ_MODEL

    @property
    def openai_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "openai":
                return p.get("model", "gpt-4o-mini")
        return "gpt-4o-mini"

    @property
    def anthropic_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "anthropic":
                return p.get("model", "claude-sonnet-4-20250514")
        return "claude-sonnet-4-20250514"

    @property
    def gemini_api_key(self) -> str:
        """API ключ Gemini: keyring -> env -> legacy YAML (ТЗ §4.2)."""
        return self._resolve_key("gemini")

    @property
    def gemini_model(self) -> str:
        for p in self.llm_providers:
            if p.get("name") == "gemini":
                return p.get("model", DEFAULT_GEMINI_MODEL)
        return DEFAULT_GEMINI_MODEL

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

    # ---------- Чат-контекст (ТЗ v0.4 §1.3) и таймауты ----------
    @property
    def chat_context_mode(self) -> str:
        """Режим контекста: auto | brief | standard | full."""
        mode = str(self.get("chat", "context_mode", default="auto")).lower()
        return mode if mode in ("auto", "brief", "standard", "full") else "auto"

    @property
    def chat_context_depth(self) -> int:
        """Максимум релевантных файлов в контексте."""
        return int(self.get("chat", "context_depth", default=8))

    @property
    def llm_timeout(self) -> int:
        """Таймаут LLM-запросов, секунд (ТЗ: описание Timeout)."""
        return int(self.get("llm", "timeout", default=60))

    def build_llm_config(self) -> Dict[str, Any]:
        """Собрать dict конфигурации для LLMProviderFactory.

        Ключи резолвятся через CredentialService (ТЗ §4.2) — в YAML
        после миграции их нет. Недостающие провайдеры (openai/anthropic)
        добавляются автоматически; enabled = есть ключ.
        """
        from gmod.infrastructure.credentials.credential_service import (
            get_credential_service,
        )
        try:
            creds = get_credential_service()
        except Exception:
            creds = None

        def _key(account: str, yaml_key: str) -> str:
            if creds is not None:
                try:
                    return creds.get_key(account, yaml_key)
                except Exception:
                    pass
            return yaml_key

        providers = []
        seen = set()
        for p in self.llm_providers:
            name = p.get("name", "").lower()
            enabled = p.get("enabled", False)
            entry: Dict[str, Any] = {"name": name, "enabled": enabled}
            seen.add(name)

            if name == "ollama":
                entry["url"] = p.get("url", DEFAULT_OLLAMA_URL)
                entry["model"] = p.get("model", DEFAULT_OLLAMA_MODEL)
                entry["api_key"] = _key("ollama", p.get("api_key", "") or "")
            elif name == "groq":
                entry["api_key"] = _key("groq", p.get("api_key", "") or "")
                entry["model"] = p.get("model", DEFAULT_GROQ_MODEL)
            elif name == "gemini":
                entry["api_key"] = _key("gemini", p.get("api_key", "") or "")
                entry["model"] = p.get("model", DEFAULT_GEMINI_MODEL)
            elif name == "openai":
                entry["api_key"] = _key("openai", p.get("api_key", "") or "")
                entry["model"] = p.get("model", "gpt-4o-mini")
                entry["url"] = p.get("url", "https://api.openai.com/v1")
            elif name == "anthropic":
                entry["api_key"] = _key("anthropic", p.get("api_key", "") or "")
                entry["model"] = p.get("model", "claude-sonnet-4-20250514")
            elif name == "openrouter":
                entry["api_key"] = _key("openrouter", p.get("api_key", "") or "")
                entry["model"] = p.get("model", "openai/gpt-oss-20b")
                entry["url"] = p.get("url", "https://openrouter.ai/api/v1")

            providers.append(entry)

        # Новые провайдеры, которых нет в YAML: добавляем, enabled = есть ключ.
        for name, model, extra in (
            ("openai", "gpt-4o-mini", {"url": "https://api.openai.com/v1"}),
            ("anthropic", "claude-sonnet-4-20250514", {}),
        ):
            if name not in seen:
                key = _key(name, "")
                providers.append({"name": name, "enabled": bool(key),
                                  "model": model, "api_key": key, **extra})

        return {
            "llm": {
                "providers": providers,
                "message_limit": self.message_limit,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "timeout": self.llm_timeout,
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
