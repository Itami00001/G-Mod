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
        """Инициализация провайдеров в порядке fallback.

        ВАЖНО (фикс «нейросети не работают»): раньше недоступный на старте
        провайдер молча выбрасывался из списка навсегда. Теперь все включённые
        провайдеры сохраняются, а доступность проверяется лениво — в момент
        generate_with_fallback() / check_all_statuses(). Так Ollama, поднятая
        позже, подхватится без перезапуска.
        """
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
                if provider is None:
                    continue
                self._providers.append(provider)
                # Лёгкая проверка только для лога, не для фильтрации
                try:
                    available = provider.is_available()
                except Exception as e:
                    available = False
                    logger.warning(f"Provider {provider_name} availability check raised: {e}")
                if available:
                    logger.info(f"Provider {provider_name} initialized and available")
                else:
                    logger.warning(
                        f"Provider {provider_name} initialized but currently unavailable "
                        "(kept in chain, will retry on generate)"
                    )
            except Exception as e:
                logger.error(f"Error initializing provider {provider_name}: {e}", exc_info=True)
        
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
        provider_config = {k: v for k, v in config.items() if k not in ("api_key", "enabled", "order")}
        # Ollama тоже может нести api_key внутри config (для Ollama Cloud) —
        # провайдер сам разрулит приоритет.
        if name.lower() == "ollama" and api_key:
            provider_config.setdefault("api_key", api_key)

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
                    try:
                        return provider.generate(prompt, **kwargs)
                    except Exception as generate_error:
                        # litellm падает на подсчёте токенов для некоторых
                        # Ollama-моделей (нет токенизатора cl100k_base) —
                        # обходим через нативный HTTP API Ollama.
                        if isinstance(provider, OllamaProvider) and "cl100k_base" in str(generate_error):
                            logger.warning(
                                "litellm не смог вызвать Ollama (%s), "
                                "пробую прямой HTTP-запрос к /api/generate",
                                generate_error,
                            )
                            return self._direct_ollama_generate(provider, prompt, **kwargs)
                        raise
            except Exception as e:
                last_error = e
                try:
                    from gmod.infrastructure.llm.health import classify_exception
                    reason, _msg = classify_exception(e)
                except Exception:
                    reason = "unknown"
                logger.warning(f"Provider {provider.get_name()} failed ({reason}): {e}, trying next")
                continue
        
        # Если все провайдеры недоступны
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    @staticmethod
    def _direct_ollama_generate(provider: OllamaProvider, prompt: str, **kwargs) -> str:
        """Прямой запрос к нативному HTTP API Ollama (без litellm).
        
        Запасной путь, когда litellm не умеет посчитать токены для модели
        (ошибка вида "cl100k_base").
        
        Args:
            provider: Экземпляр OllamaProvider
            prompt: Промпт для генерации
            **kwargs: temperature / max_tokens
            
        Returns:
            Сгенерированный текст
        """
        import requests

        headers = {}
        api_key = getattr(provider, "api_key", None)
        local_mode = getattr(provider, "_local_mode", True)
        if api_key and not local_mode:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": provider.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 2000),
            },
        }
        response = requests.post(
            f"{provider.url.rstrip('/')}/api/generate",
            json=payload,
            headers=headers,
            timeout=180,
        )
        response.raise_for_status()
        content = response.json().get("response", "")
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return content
    
    def get_available_providers(self) -> List[str]:
        """Получение списка доступных провайдеров.

        Returns:
            Список названий доступных провайдеров
        """
        return [provider.get_name() for provider in self._providers if provider.is_available()]

    def get_all_providers(self) -> List[BaseLLMProvider]:
        """Все включённые провайдеры (даже недоступные сейчас)."""
        return list(self._providers)

    def check_all_statuses(self) -> Dict[str, Any]:
        """Проверка всех провайдеров с понятными сообщениями для UI.

        Returns:
            {provider_display_name: {"ok": bool, "message": str, "reason": str}}
        """
        from gmod.infrastructure.llm.health import MSG_DISABLED

        result: Dict[str, Any] = {}
        for provider in self._providers:
            name = provider.get_name()
            try:
                if hasattr(provider, "check_status"):
                    status = provider.check_status()  # type: ignore[attr-defined]
                    result[name] = {
                        "ok": status.ok,
                        "message": status.message,
                        "reason": status.reason,
                        "detail": status.detail,
                    }
                    logger.info("health: %s -> %s (%s)", name, status.message, status.reason)
                else:
                    ok = provider.is_available()
                    result[name] = {
                        "ok": ok,
                        "message": "Нейросеть работает" if ok else "Нейросеть недоступна",
                        "reason": "ok" if ok else "unknown",
                        "detail": "",
                    }
            except Exception as e:
                logger.error("health: %s check raised: %s", name, e, exc_info=True)
                result[name] = {
                    "ok": False,
                    "message": f"Нейросеть недоступна. {type(e).__name__}",
                    "reason": "unknown",
                    "detail": str(e)[:300],
                }
        if not result:
            result["none"] = {
                "ok": False, "message": MSG_DISABLED,
                "reason": "disabled", "detail": "no enabled providers",
            }
        return result
    
    def refresh_providers(self) -> None:
        """Обновление списка провайдеров (проверка доступности)."""
        logger.info("Refreshing LLM providers availability")
        self._providers = []
        self._initialize_providers()
