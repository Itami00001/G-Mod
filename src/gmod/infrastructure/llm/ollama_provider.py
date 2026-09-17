"""Ollama провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Ollama provider will not work")

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер Ollama для локальных LLM."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация Ollama провайдера.
        
        Args:
            api_key: Не используется для Ollama, но требуется для интерфейса
            config: Конфигурация с url и model
        """
        super().__init__(api_key, config)
        self.url = config.get("url", "http://localhost:11434") if config else "http://localhost:11434"
        self.model = config.get("model", "llama3.2:3b") if config else "llama3.2:3b"
        self._validate_config()
    
    def _validate_config(self) -> bool:
        """Валидация конфигурации."""
        if not self.url:
            logger.warning("Ollama URL not configured, using default")
            self.url = "http://localhost:11434"
        return True
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа через Ollama.
        
        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры (temperature, max_tokens, etc.)
            
        Returns:
            Сгенерированный текст
        """
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available, cannot use Ollama provider")
        
        try:
            response = completion(
                model=f"ollama/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.url,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2000),
                **kwargs
            )
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Проверка доступности Ollama."""
        if not LITELLM_AVAILABLE:
            return False
        
        try:
            import requests
            response = requests.get(f"{self.url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available at {self.url}: {e}")
            return False
    
    def get_available_models(self) -> list:
        """Получение списка доступных моделей."""
        if not self.is_available():
            return []
        
        try:
            import requests
            response = requests.get(f"{self.url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model["name"] for model in models]
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
        
        return []
