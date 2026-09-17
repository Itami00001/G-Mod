"""Gemini провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
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
            response = completion(
                model=f"gemini/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2000),
                **kwargs
            )
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Проверка доступности Gemini."""
        if not LITELLM_AVAILABLE:
            return False
        
        if not self.api_key:
            return False
        
        try:
            # Пробуем простой запрос для проверки доступности
            test_response = completion(
                model=f"gemini/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_key=self.api_key,
                max_tokens=10,
                timeout=10
            )
            return True
        except Exception as e:
            logger.warning(f"Gemini not available: {e}")
            return False
