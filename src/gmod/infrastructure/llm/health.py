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
MSG_FORBIDDEN = "⚠ Доступ запрещён"
MSG_NO_CONN = "⚠ Соединение отсутствует"
MSG_TIMEOUT = "⚠ Сервер не отвечает (timeout)"
MSG_REFUSED = "✕ Сервер выключен или недоступен (connection refused)"
MSG_MODEL_MISSING = "⚠ Модель недоступна"
MSG_QUOTA = "⚠ Лимит/квота исчерпана"
MSG_NO_LIB = "✕ litellm не установлен"
MSG_DISABLED = "✕ Провайдер отключён"
MSG_UNKNOWN = "✕ Неизвестная ошибка"

# Таблица HTTP-кодов → (reason, сообщение). Приоритет выше, чем
# ключевые слова в тексте ошибки: код точнее текста.
HTTP_STATUS_TABLE = {
    401: ("bad_key", MSG_BAD_KEY + " (401): невалидный API-ключ"),
    403: ("forbidden", MSG_FORBIDDEN + " (403): доступ запрещён"),
    429: ("quota", MSG_QUOTA + " (429): превышен лимит запросов"),
    404: ("model_missing", MSG_MODEL_MISSING + " (404): модель не найдена"),
}

# Цвета индикаторов для UI (зелёный/жёлтый/красный).
REASON_COLORS = {
    "ok": "green",
    "no_key": "orange",
    "bad_key": "red",
    "forbidden": "red",
    "no_connection": "red",
    "model_missing": "orange",
    "quota": "orange",
    "no_lib": "red",
    "disabled": "gray",
    "unknown": "red",
}


def status_code_of(exc: Exception):
    """Достать HTTP-код из исключения (litellm/requests/httpx).

    Returns:
        int код или None.
    """
    for attr in ("status_code", "status"):
        code = getattr(exc, attr, None)
        if isinstance(code, int):
            return code
        if isinstance(code, str) and code.isdigit():
            return int(code)
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


@dataclass
class ProviderStatus:
    ok: bool
    message: str
    reason: str = ""  # ok|no_key|bad_key|no_connection|model_missing|quota|no_lib|disabled|unknown
    detail: str = ""  # технический detail для логов


def classify_exception(exc: Exception) -> Tuple[str, str]:
    """Классификация исключения в (reason, user_message) (ТЗ §6).

    Сначала — точный HTTP-код (таблица выше), затем маркеры:
    timeout → «сервер не отвечает», refused → «сервер выключен».
    """
    code = status_code_of(exc)
    if code in HTTP_STATUS_TABLE:
        reason, msg = HTTP_STATUS_TABLE[code]
        logger.warning("health: HTTP %s -> %s", code, reason)
        return reason, msg

    text = f"{type(exc).__name__}: {exc}".lower()
    logger.debug("health: классифицируем исключение: %s", text[:300])

    # Текстовые коды без атрибута status_code (litellm пишет код в текст).
    import re as _re
    if _re.search(r"\b401\b", text):
        return "bad_key", HTTP_STATUS_TABLE[401][1]
    if _re.search(r"\b403\b", text):
        return "forbidden", HTTP_STATUS_TABLE[403][1]

    auth_markers = (
        "unauthorized", "invalid api key", "incorrect api key",
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
        if "refused" in text:
            logger.warning("health: сервер выключен: %s", text[:200])
            return "no_connection", MSG_REFUSED
        logger.warning("health: нет соединения: %s", text[:200])
        return "no_connection", MSG_TIMEOUT if "timeout" in text or "timed out" in text \
            else f"{MSG_NO_CONN} ({type(exc).__name__})"

    model_markers = ("model", "not found", "does not exist", "404")
    if any(m in text for m in model_markers):
        logger.warning("health: причина — модель/endpoint: %s", text[:200])
        return "model_missing", f"{MSG_MODEL_MISSING} ({type(exc).__name__})"

    logger.warning("health: неизвестная причина: %s", text[:200])
    return "unknown", f"{MSG_UNKNOWN}: {type(exc).__name__}".strip()[:200]
