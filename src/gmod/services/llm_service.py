"""LLMService — фасад над фабрикой провайдеров (ТЗ §30).

Цепочка: UI/ChatService -> LLMService -> LLMProviderFactory -> провайдеры.
"""

import logging
from typing Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """Единая точка генерации и проверок провайдеров."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            from gmod.config.settings import get_settings
            config = get_settings().build_llm_config()
        self.config = config

    def _factory(self):
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        return LLMProviderFactory(self.config)

    def generate(self, prompt: str, provider: str = "", model: str = "",
                 **kwargs) -> str:
        """Генерация с приоритетом выбранного провайдера."""
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        factory = LLMProviderFactory(self.config)
        if provider:
            ordered = sorted(factory._providers,
                             key=lambda p: 0 if (p.config.get("provider_id", "")
                                                 == provider.lower()) else 1)
            factory._providers = ordered
            for p in factory._providers:
                if p.config.get("provider_id", "") == provider.lower() and model:
                    p.model = model
        return factory.generate_with_fallback(prompt, **kwargs)

    def check_all(self) -> Dict[str, Any]:
        """Статусы всех провайдеров (ТЗ §6)."""
        return self._factory().check_all_statuses()

    def check(self, provider_id: str):
        """Статус одного провайдера."""
        from gmod.infrastructure.llm.factory import (
            build_provider, provider_entry_from_settings,
        )
        provider = build_provider(provider_id,
                                  provider_entry_from_settings(provider_id))
        if provider is None:
            from gmod.infrastructure.llm.health import ProviderStatus, MSG_DISABLED
            return ProviderStatus(False, MSG_DISABLED, "disabled", "unknown provider")
        return provider.check_connection()

    def list_models(self, provider_id: str) -> List[str]:
        """Модели провайдера (авторизация внутри, ТЗ §3.2)."""
        from gmod.infrastructure.llm.factory import (
            build_provider, provider_entry_from_settings,
        )
        provider = build_provider(provider_id,
                                  provider_entry_from_settings(provider_id))
        if provider is None:
            return []
        try:
            return provider.list_models()
        except Exception as e:
            logger.warning("list_models %s: %s", provider_id, e)
            return []

    def test_inference(self, provider_id: str, prompt: str = "") -> str:
        """Явный тестовый inference (ТЗ §6)."""
        from gmod.infrastructure.llm.factory import (
            build_provider, provider_entry_from_settings,
        )
        provider = build_provider(provider_id,
                                  provider_entry_from_settings(provider_id))
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_id}")
        fn = getattr(provider, "test_inference", None)
        if fn is None:
            return provider.generate(prompt or "Ответь одним словом: тест.",
                                     max_tokens=50, temperature=0.0)
        return fn(prompt or "Ответь одним словом: тест.")
