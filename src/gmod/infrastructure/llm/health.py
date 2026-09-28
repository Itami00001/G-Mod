"""Единая проверка здоровья LLM-провайдеров с понятными статусами для UI.

Идея: вместо голого bool is_available() возвращаем структуру
ProviderStatus(ok, message, reason), где message уже готово для показа:
- "Нейросеть работает"
- "Нейросеть недоступна. API ключ не валидный"
- "Нейросеть недоступна. Нет соединения с ..."
- "Нейросеть недоступна. litellm не установлен"
"""

import logging
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger(__name__)

MSG_OK = "✓ Нейросеть работает"
MSG_NO_KEY = "⚠ Ключ отсутствует"
MSG_BAD_KEY = "⚠ Ключ недействителен"
MSG_NO_CONN = "⚠ Соединение отсутствует"
MSG_MODEL_MISSING = "⚠ Модель недоступна"
MSG_QUOTA = "⚠ Лимит/квота исчерпана"
MSG_NO_LIB = "✕ litellm не установлен"
MSG_DISABLED = "✕ Провайдер отключён"
MSG_UNKNOWN = "✕ Неизвестная ошибка"


@dataclass
class ProviderStatus:
    ok: bool
    message: str
    reason: str = ""  # ok|no_key|bad_key|no_connection|model_missing|quota|no_lib|disabled|unknown
    detail: str = ""  # технический detail для логов


def classify_exception(exc: Exception) -> Tuple[str, str]:
    """Классификация исключения litellm/requests в (reason, user_message) (ТЗ §6)."""
    text = f"{type(exc).__name__}: {exc}".lower()
    logger.debug("health: классифицируем исключение: %s", text[:300])

    auth_markers = (
        "401", "403", "unauthorized", "invalid api key", "incorrect api key",
        "invalid_api_key", "authentication", "bearer", "api key not valid",
        "permission denied", "access denied",
    )
    if any(m in text for m in auth_markers):
        logger.warning("health: причина — невалидный API ключ: %s", text[:200])
        return "bad_key", MSG_BAD_KEY

    quota_markers = (
        "429", "rate limit", "rate_limit", "quota", "insufficient",
        "too many requests", "billing", "credit balance", "low balance", "credits",
    )
    if any(m in text for m in quota_markers):
        logger.warning("health: причина — квота: %s", text[:200])
        return "quota", MSG_QUOTA

    conn_markers = (
        "connection", "connect", "refused", "timeout", "timed out",
        "max retries", "name resolution", "nodename", "temporary failure",
        "network is unreachable", "no route", "failed to establish",
    )
    if any(m in text for m in conn_markers):
        logger.warning("health: причина — нет соединения: %s", text[:200])
        return "no_connection", f"{MSG_NO_CONN} ({type(exc).__name__})"

    model_markers = ("model", "not found", "does not exist", "404")
    if any(m in text for m in model_markers):
        logger.warning("health: причина — модель/endpoint: %s", text[:200])
        return "model_missing", f"{MSG_MODEL_MISSING} ({type(exc).__name__})"

    logger.warning("health: неизвестная причина: %s", text[:200])
    return "unknown", f"{MSG_UNKNOWN}: {type(exc).__name__}".strip()[:200]
