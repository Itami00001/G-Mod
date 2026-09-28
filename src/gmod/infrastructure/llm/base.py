"""Базовый интерфейс для LLM провайдеров (ТЗ §3.2).

Единый интерфейс:
    check_connection()      — жив ли endpoint (без generation prompt)
    validate_credentials()  — валиден ли ключ
    list_models()           — список моделей провайдера
    generate()              — генерация ответа

HTTP-авторизация централизована в _auth_headers() — дублирование
авторизационной логики в UI-функциях запрещено.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from gmod.domain.interfaces import ILLMProvider

logger = logging.getLogger(__name__)


class BaseLLMProvider(ILLMProvider, ABC):
    """Базовый класс для LLM провайдеров."""

    #: тип авторизации: none | bearer | query_key | x-api-key
    auth_type: str = "bearer"

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация провайдера.

        Args:
            api_key: API ключ для доступа
            config: Дополнительная конфигурация
        """
        self.api_key = api_key
        self.config = config or {}
        self._name = self.__class__.__name__

    # ---------------- единый интерфейс (ТЗ §3.2) ----------------

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа."""
        pass

    def check_connection(self):
        """Проверка соединения БЕЗ generation prompt (ТЗ §6).

        Returns:
            ProviderStatus.
        """
        from gmod.infrastructure.llm.health import ProviderStatus
        try:
            ok = self.is_available()
        except Exception as e:
            from gmod.infrastructure.llm.health import classify_exception
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])
        from gmod.infrastructure.llm.health import MSG_OK
        if ok:
            return ProviderStatus(True, MSG_OK, "ok", "")
        return ProviderStatus(False, "Нейросеть недоступна. Нет соединения",
                              "no_connection", "")

    def validate_credentials(self):
        """Проверка ключа БЕЗ generation prompt (ТЗ §6).

        Returns:
            ProviderStatus.
        """
        from gmod.infrastructure.llm.health import MSG_BAD_KEY, MSG_OK, ProviderStatus
        if self.auth_type == "none":
            return ProviderStatus(True, MSG_OK, "ok", "no key required")
        if not (self.api_key or "").strip():
            return ProviderStatus(False, "Нейросеть недоступна. Ключ отсутствует",
                                  "no_key", "empty key")
        return ProviderStatus(True, MSG_OK, "ok", "key present")

    def list_models(self) -> List[str]:
        """Список моделей провайдера. Переопределяется в наследниках."""
        return []

    # ---------------- совместимость ----------------

    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности провайдера (legacy, держит check_connection)."""
        pass

    def get_name(self) -> str:
        """Получение названия провайдера."""
        return self._name

    # ---------------- единая авторизация (ТЗ §3.2/§3.3) ----------------

    def _auth_headers(self) -> Dict[str, str]:
        """Единые HTTP-заголовки авторизации для ВСЕХ запросов провайдера.

        Использовать в /api/tags, /api/chat, /api/generate и list_models —
        строить Authorization вручную в UI запрещено.
        """
        key = (self.api_key or "").strip()
        if not key:
            return {}
        if self.auth_type == "bearer":
            return {"Authorization": f"Bearer {key}"}
        if self.auth_type == "x-api-key":
            return {"x-api-key": key}
        return {}

    def _auth_params(self) -> Dict[str, str]:
        """Query-параметры авторизации (auth_type == 'query_key', напр. Gemini)."""
        key = (self.api_key or "").strip()
        if self.auth_type == "query_key" and key:
            return {"key": key}
        return {}

    def _validate_config(self, required_keys: list) -> bool:
        """Валидация конфигурации.

        Args:
            required_keys: Список обязательных ключей

        Returns:
            True если конфигурация валидна
        """
        return all(key in self.config for key in required_keys)
