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

MSG_OK = "Нейросеть работает"
MSG_BAD_KEY = "Нейросеть недоступна. API ключ не валидный"
MSG_NO_CONN = "Нейросеть недоступна. Нет соединения"
MSG_NO_LIB = "Нейросеть недоступна. litellm не установлен"
MSG_DISABLED = "Нейросеть недоступна. Провайдер отключён"


@dataclass
class ProviderStatus:
    ok: bool
    message: str
    reason: str = ""  # machine-readable: ok | bad_key | no_connection | no_lib | disabled | unknown
    detail: str = ""  # технический detail для логов


def classify_exception(exc: Exception) -> Tuple[str, str]:
    """Классификация исключения litellm/requests в (reason, user_message)."""
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
        return "unknown", f"Нейросеть недоступна. {type(exc).__name__}: {exc}".strip()[:200]

    logger.warning("health: неизвестная причина: %s", text[:200])
    return "unknown", f"Нейросеть недоступна. {type(exc).__name__}".strip()[:200]
