"""Базовый интерфейс для LLM провайдеров."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from gmod.domain.interfaces import ILLMProvider


class BaseLLMProvider(ILLMProvider, ABC):
    """Базовый класс для LLM провайдеров."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация провайдера.
        
        Args:
            api_key: API ключ для доступа
            config: Дополнительная конфигурация
        """
        self.api_key = api_key
        self.config = config or {}
        self._name = self.__class__.__name__
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности провайдера."""
        pass
    
    def get_name(self) -> str:
        """Получение названия провайдера."""
        return self._name
    
    def _validate_config(self, required_keys: list) -> bool:
        """Валидация конфигурации.
        
        Args:
            required_keys: Список обязательных ключей
            
        Returns:
            True если конфигурация валидна
        """
        return all(key in self.config for key in required_keys)
