"""Anthropic (Claude) провайдер для LLM (ТЗ §3.1, расширяемость).

Важно: у Anthropic API НЕТ endpoint списка моделей, поэтому
check_connection проверяет только формат ключа (без generation prompt),
а list_models возвращает курируемый статический список актуальных Claude.
Тестовый inference — отдельная явная операция test_inference().
"""

import logging
from typing import Optional, Dict, Any, List

try:
    import litellm
    LITELLM_AVAILABLE = True
except Exception as _litellm_import_error:  # noqa: BLE001
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Anthropic provider will not work: %s",
                    _litellm_import_error)

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Курируемый список (API списка моделей у Anthropic нет).
KNOWN_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-haiku-20241022",
]


class AnthropicProvider(BaseLLMProvider):
    """Провайдер Anthropic Claude."""

    auth_type = "x-api-key"

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, config)
        self.model = (config.get("model", "claude-sonnet-4-20250514")
                      if config else "claude-sonnet-4-20250514")
        if not self.api_key:
            logger.warning("Anthropic API key not provided")

    def generate(self, prompt: str, **kwargs) -> str:
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available, cannot use Anthropic provider")
        if not self.api_key:
            raise ValueError("Anthropic API key not provided")
        try:
            extra = dict(kwargs)
            temperature = extra.pop("temperature", 0.7)
            max_tokens = extra.pop("max_tokens", 2000)
            response = litellm.completion(
                model=f"anthropic/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
            content = response["choices"][0]["message"]["content"] or ""
            if not content:
                raise RuntimeError("Anthropic вернул пустой ответ")
            return content
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise

    def list_models(self) -> List[str]:
        """Статический курируемый список (у API Anthropic нет list endpoint)."""
        return list(KNOWN_MODELS)

    def check_connection(self):
        """Только формат ключа — без generation (ТЗ §6)."""
        from gmod.infrastructure.llm.health import (
            MSG_NO_LIB, ProviderStatus,
        )
        if not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        cred = self.validate_credentials()
        if not cred.ok:
            return cred
        from gmod.infrastructure.llm.health import MSG_OK
        logger.info("Anthropic: формат ключа OK (полная проверка — тестовым inference)")
        return ProviderStatus(True, MSG_OK, "ok", "key format ok; use test inference")

    def validate_credentials(self):
        """Формат ключа sk-ant-... (без сети — API списка моделей нет)."""
        from gmod.infrastructure.llm.health import (
            MSG_BAD_KEY, MSG_NO_KEY, MSG_OK, ProviderStatus,
        )
        key = (self.api_key or "").strip()
        if not key:
            return ProviderStatus(False, MSG_NO_KEY, "no_key", "empty key")
        if not (key.startswith("sk-ant-") and len(key) > 20):
            return ProviderStatus(False, MSG_BAD_KEY, "bad_key", "not sk-ant- format")
        return ProviderStatus(True, MSG_OK, "ok", "key format ok")

    def test_inference(self, prompt: str = "Ответь одним словом: тест.") -> str:
        """Явный тестовый inference (ТЗ §6: отдельная операция)."""
        logger.info("Anthropic: тестовый inference (модель %s)", self.model)
        return self.generate(prompt, max_tokens=50, temperature=0.0)

    def validate_api_key(self) -> bool:
        key = (self.api_key or "").strip()
        return key.startswith("sk-ant-") and len(key) > 20

    def is_available(self) -> bool:
        try:
            return self.check_connection().ok
        except Exception:
            return False

    def check_status(self):
        return self.check_connection()
