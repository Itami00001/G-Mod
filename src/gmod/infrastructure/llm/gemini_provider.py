"""Gemini провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Gemini provider will not work")

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Провайдер Google Gemini для LLM."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация Gemini провайдера.
        
        Args:
            api_key: API ключ для Google Gemini
            config: Конфигурация с model
        """
        super().__init__(api_key, config)
        self.model = config.get("model", "gemini-flash") if config else "gemini-flash"
        
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
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise
    
    def validate_api_key(self) -> bool:
        """Быстрая форматная проверка ключа без сетевого запроса."""
        if not self.api_key:
            return False
        key = self.api_key.strip()
        if len(key) < 10:
            logger.warning("Gemini: API ключ слишком короткий (%d символов)", len(key))
            return False
        return True

    def is_available(self) -> bool:
        """Проверка доступности Gemini."""
        from gmod.infrastructure.llm.health import MSG_BAD_KEY, MSG_NO_LIB

        if not LITELLM_AVAILABLE:
            logger.warning("Gemini: %s", MSG_NO_LIB)
            return False

        if not self.validate_api_key():
            logger.warning("Gemini: %s (ключ пуст или слишком короткий)", MSG_BAD_KEY)
            return False

        try:
            # Пробуем простой запрос для проверки доступности
            test_response = litellm.completion(
                model=f"gemini/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_key=self.api_key,
                max_tokens=10,
                timeout=10
            )
            logger.info("Gemini: доступна (модель %s)", self.model)
            return True
        except Exception as e:
            from gmod.infrastructure.llm.health import classify_exception
            reason, msg = classify_exception(e)
            logger.warning(f"Gemini not available ({reason}): {e}")
            return False

    def check_status(self):
        """Расширенная проверка с понятным сообщением для UI."""
        from gmod.infrastructure.llm.health import (
            MSG_BAD_KEY, MSG_NO_LIB, MSG_OK, ProviderStatus, classify_exception,
        )

        if not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        if not self.validate_api_key():
            return ProviderStatus(False, MSG_BAD_KEY, "bad_key", "empty/short key")
        try:
            litellm.completion(
                model=f"gemini/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_key=self.api_key,
                max_tokens=10,
                timeout=10,
            )
            logger.info("Gemini: проверка соединения — OK")
            return ProviderStatus(True, MSG_OK, "ok", f"model={self.model}")
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])
