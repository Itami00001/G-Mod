"""Groq провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Groq provider will not work")

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Провайдер Groq для быстрых LLM."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация Groq провайдера.
        
        Args:
            api_key: API ключ для Groq
            config: Конфигурация с model
        """
        super().__init__(api_key, config)
        self.model = config.get("model", "llama3.2:3b") if config else "llama3.2:3b"
        
        if not self.api_key:
            logger.warning("Groq API key not provided")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа через Groq.
        
        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный текст
        """
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available, cannot use Groq provider")
        
        if not self.api_key:
            raise ValueError("Groq API key not provided")
        
        try:
            extra = dict(kwargs)
            temperature = extra.pop("temperature", 0.7)
            max_tokens = extra.pop("max_tokens", 2000)
            response = litellm.completion(
                model=f"groq/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Groq generation error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Проверка доступности Groq."""
        if not LITELLM_AVAILABLE:
            return False
        
        if not self.api_key:
            return False
        
        try:
            # Пробуем простой запрос для проверки доступности
            test_response = litellm.completion(
                model=f"groq/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_key=self.api_key,
                max_tokens=10,
                timeout=10
            )
            return True
        except Exception as e:
            logger.warning(f"Groq not available: {e}")
            return False
