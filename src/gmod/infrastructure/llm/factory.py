"""Фабрика LLM провайдеров с fallback-цепочкой."""

import logging
from typing import List, Optional, Dict, Any

from gmod.infrastructure.llm.base import BaseLLMProvider
from gmod.infrastructure.llm.ollama_provider import OllamaProvider
from gmod.infrastructure.llm.groq_provider import GroqProvider
from gmod.infrastructure.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Фабрика LLM провайдеров с fallback-цепочкой."""
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация фабрики.
        
        Args:
            config: Конфигурация провайдеров из настроек
        """
        self.config = config
        self._providers: List[BaseLLMProvider] = []
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Инициализация провайдеров в порядке fallback."""
        llm_config = self.config.get("llm", {})
        providers_config = llm_config.get("providers", [])
        
        # Инициализируем провайдеры в указанном порядке
        for provider_config in providers_config:
            provider_name = provider_config.get("name", "").lower()
            enabled = provider_config.get("enabled", False)
            
            if not enabled:
                logger.info(f"Provider {provider_name} is disabled, skipping")
                continue
            
            try:
                provider = self._create_provider(provider_name, provider_config)
                if provider and provider.is_available():
                    self._providers.append(provider)
                    logger.info(f"Provider {provider_name} initialized and available")
                else:
                    logger.warning(f"Provider {provider_name} not available, skipping")
            except Exception as e:
                logger.error(f"Error initializing provider {provider_name}: {e}")
        
        if not self._providers:
            logger.warning("No LLM providers available")
    
    def _create_provider(self, name: str, config: Dict[str, Any]) -> Optional[BaseLLMProvider]:
        """Создание провайдера по названию.
        
        Args:
            name: Название провайдера
            config: Конфигурация провайдера
            
        Returns:
            Экземпляр провайдера или None
        """
        provider_classes = {
            "ollama": OllamaProvider,
            "groq": GroqProvider,
            "gemini": GeminiProvider
        }
        
        provider_class = provider_classes.get(name.lower())
        if not provider_class:
            logger.warning(f"Unknown provider: {name}")
            return None
        
        api_key = config.get("api_key")
        provider_config = {k: v for k, v in config.items() if k != "api_key"}
        
        return provider_class(api_key=api_key, config=provider_config)
    
    def get_provider(self) -> Optional[BaseLLMProvider]:
        """Получение первого доступного провайдера.
        
        Returns:
            Первый доступный провайдер или None
        """
        for provider in self._providers:
            if provider.is_available():
                return provider
        return None
    
    def generate_with_fallback(self, prompt: str, **kwargs) -> str:
        """Генерация с fallback-цепочкой.
        
        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный текст
            
        Raises:
            RuntimeError: Если ни один провайдер недоступен
        """
        last_error = None
        
        for provider in self._providers:
            try:
                if provider.is_available():
                    logger.info(f"Using provider: {provider.get_name()}")
                    return provider.generate(prompt, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.get_name()} failed: {e}, trying next")
                continue
        
        # Если все провайдеры недоступны
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def get_available_providers(self) -> List[str]:
        """Получение списка доступных провайдеров.
        
        Returns:
            Список названий доступных провайдеров
        """
        return [provider.get_name() for provider in self._providers if provider.is_available()]
    
    def refresh_providers(self) -> None:
        """Обновление списка провайдеров (проверка доступности)."""
        logger.info("Refreshing LLM providers availability")
        self._providers = []
        self._initialize_providers()
