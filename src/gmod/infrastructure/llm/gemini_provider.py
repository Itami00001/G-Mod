"""Gemini провайдер для LLM (ТЗ §3, §6).

Проверка соединения — лёгкий GET v1beta/models БЕЗ generation prompt.
Тестовый inference — отдельная явная операция test_inference().
"""

import logging
from typing import Optional, Dict, Any, List

try:
    import litellm
    LITELLM_AVAILABLE = True
except Exception as _litellm_import_error:  # noqa: BLE001 — в frozen-exe tiktoken падает с ValueError
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Gemini provider will not work: %s", _litellm_import_error)

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Модели без текстовой генерации — скрываем из списков.
_NON_TEXT_MARKERS = ("embed", "tts", "image", "live", "audio", "translat", "veo",
                     "research")


class GeminiProvider(BaseLLMProvider):
    """Провайдер Google Gemini для LLM."""

    auth_type = "query_key"

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация Gemini провайдера.

        Args:
            api_key: API ключ для Google Gemini (AI Studio, формат AIza...)
            config: Конфигурация с model
        """
        super().__init__(api_key, config)
        from gmod.config.constants import DEFAULT_GEMINI_MODEL
        self.model = config.get("model", DEFAULT_GEMINI_MODEL) if config else DEFAULT_GEMINI_MODEL

        if not self.api_key:
            logger.warning("Gemini API key not provided")

    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа через Gemini.

        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры

        Returns:
            Сгенерированный текст
        """
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available, cannot use Gemini provider")

        if not self.api_key:
            raise ValueError("Gemini API key not provided")

        try:
            extra = dict(kwargs)
            temperature = extra.pop("temperature", 0.7)
            max_tokens = extra.pop("max_tokens", 2000)
            response = litellm.completion(
                model=f"gemini/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )

            content = response["choices"][0]["message"]["content"] or ""
            if not content:
                raise RuntimeError("Gemini вернул пустой ответ")
            return content

        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

    # ---------------- единый интерфейс (ТЗ §3.2, §6) ----------------

    def list_models(self) -> List[str]:
        """Список текстовых моделей Gemini (без генерации)."""
        import requests
        resp = requests.get(MODELS_URL, params=self._auth_params(), timeout=10)
        if resp.status_code in (400, 401, 403):
            raise RuntimeError("Нейросеть недоступна. API ключ не валидный "
                               "(нужен ключ AI Studio формата AIza...)")
        resp.raise_for_status()
        names = sorted(
            m.get("name", "").replace("models/", "")
            for m in resp.json().get("models", []) if m.get("name"))
        return [n for n in names if not any(b in n for b in _NON_TEXT_MARKERS)]

    def check_connection(self):
        """Лёгкая проверка: API + ключ + модель (без generation)."""
        from gmod.infrastructure.llm.health import (
            MSG_NO_LIB, ProviderStatus, classify_exception,
        )
        if not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        cred = self.validate_credentials()
        if not cred.ok:
            return cred
        try:
            names = self.list_models()
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])
        if names and self.model not in names:
            from gmod.infrastructure.llm.health import MSG_MODEL_MISSING
            hint = MSG_MODEL_MISSING + f": '{self.model}'. Обновите список моделей (🔄)."
            logger.warning("Gemini: %s", hint)
            return ProviderStatus(False, hint, "model_missing", f"have={len(names)}")
        from gmod.infrastructure.llm.health import MSG_OK
        logger.info("Gemini: проверка соединения — OK")
        return ProviderStatus(True, MSG_OK, "ok", f"model={self.model}")

    def validate_credentials(self):
        """Проверка ключа через /models (без генерации)."""
        from gmod.infrastructure.llm.health import (
            MSG_BAD_KEY, MSG_NO_KEY, MSG_OK, ProviderStatus, classify_exception,
        )
        key = (self.api_key or "").strip()
        if not key:
            return ProviderStatus(False, MSG_NO_KEY, "no_key", "empty key")
        if len(key) < 10:
            return ProviderStatus(False, MSG_BAD_KEY, "bad_key", "too short")
        try:
            self.list_models()
            return ProviderStatus(True, MSG_OK, "ok", "key accepted")
        except Exception as e:
            reason, msg = classify_exception(e)
            if reason == "bad_key":
                return ProviderStatus(False, MSG_BAD_KEY, "bad_key", str(e)[:200])
            logger.debug("Gemini validate via models failed (%s), key format ok", reason)
            return ProviderStatus(True, MSG_OK, "ok", "key format ok, server unreachable")

    def test_inference(self, prompt: str = "Ответь одним словом: тест.") -> str:
        """Явный тестовый inference (ТЗ §6: отдельная операция)."""
        logger.info("Gemini: тестовый inference (модель %s)", self.model)
        return self.generate(prompt, max_tokens=50, temperature=0.0)

    # ---------------- совместимость ----------------

    def validate_api_key(self) -> bool:
        """Быстрая форматная проверка ключа без сетевого запроса."""
        if not self.api_key:
            return False
        return len(self.api_key.strip()) >= 10

    def is_available(self) -> bool:
        """Проверка доступности (лёгкая, без генерации)."""
        try:
            return self.check_connection().ok
        except Exception:
            return False

    def check_status(self):
        """Алиас check_connection для совместимости."""
        return self.check_connection()
