"""Ollama провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Ollama provider will not work")

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер Ollama для локальных LLM."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация Ollama провайдера.

        Args:
            api_key: API ключ для Ollama Cloud (для локального сервера не нужен,
                можно оставить пустым). Хранится в config.yaml: llm.providers[].api_key
            config: Конфигурация с url и model
        """
        super().__init__(api_key, config)
        self.url = config.get("url", "http://localhost:11434") if config else "http://localhost:11434"
        self.model = config.get("model", "llama3.2:3b") if config else "llama3.2:3b"
        # api_key может прийти как в config, так и отдельным параметром
        if config and config.get("api_key") and not self.api_key:
            self.api_key = config.get("api_key")
        if self.api_key:
            logger.info("Ollama: API ключ задан (длина %d), будет передан как Bearer", len(self.api_key))
        else:
            logger.debug("Ollama: API ключ не задан (локальный режим без ключа)")
        self._validate_config()
    
    def _validate_config(self, required_keys: list = None) -> bool:
        """Валидация конфигурации (совместима с BaseLLMProvider)."""
        if not self.url:
            logger.warning("Ollama URL not configured, using default")
            self.url = "http://localhost:11434"
        if required_keys:
            return super()._validate_config(required_keys)
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
            # Извлекаем известные параметры, остальные пробрасываем как есть.
            # (Прямой **kwargs после явных temperature/max_tokens давал бы
            # TypeError при дублировании ключей.)
            extra = dict(kwargs)
            temperature = extra.pop("temperature", 0.7)
            max_tokens = extra.pop("max_tokens", 2000)
            completion_kwargs: Dict[str, Any] = dict(
                model=f"ollama/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.url,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            # Ollama Cloud требует Bearer-ключ; локальному серверу он не мешает.
            if self.api_key:
                completion_kwargs["api_key"] = self.api_key
            logger.info(
                "Ollama: generate model=%s url=%s prompt_len=%d",
                self.model, self.url, len(prompt),
            )
            response = litellm.completion(**completion_kwargs, **extra)

            content = response["choices"][0]["message"]["content"]
            logger.info("Ollama: ответ получен (длина %d)", len(content or ""))
            return content
            
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Проверка доступности Ollama."""
        from gmod.infrastructure.llm.health import MSG_NO_LIB

        if not LITELLM_AVAILABLE:
            logger.warning("Ollama: %s", MSG_NO_LIB)
            return False

        try:
            import requests
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = requests.get(f"{self.url}/api/tags", timeout=5, headers=headers)
            ok = response.status_code == 200
            if ok:
                logger.info("Ollama: доступна (%s, модель %s)", self.url, self.model)
            else:
                logger.warning("Ollama: недоступна, HTTP %s", response.status_code)
            return ok
        except Exception as e:
            logger.warning(f"Ollama not available at {self.url}: {e}")
            return False

    def check_status(self):
        """Расширенная проверка с понятным сообщением для UI.

        Returns:
            ProviderStatus с message вида "Нейросеть работает" /
            "Нейросеть недоступна. ...".
        """
        from gmod.infrastructure.llm.health import (
            MSG_NO_LIB, MSG_OK, ProviderStatus, classify_exception,
        )

        if not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        try:
            import requests
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = requests.get(f"{self.url}/api/tags", timeout=5, headers=headers)
            if resp.status_code == 200:
                logger.info("Ollama: проверка соединения — OK")
                return ProviderStatus(True, MSG_OK, "ok", f"HTTP 200, {self.url}")
            if resp.status_code in (401, 403):
                from gmod.infrastructure.llm.health import MSG_BAD_KEY
                logger.warning("Ollama: API ключ не валидный (HTTP %s)", resp.status_code)
                return ProviderStatus(False, MSG_BAD_KEY, "bad_key", f"HTTP {resp.status_code}")
            return ProviderStatus(
                False, f"Нейросеть недоступна. HTTP {resp.status_code}",
                "unknown", f"HTTP {resp.status_code}",
            )
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])
    def get_available_models(self) -> list:
        """Получение списка доступных моделей."""
        if not self.is_available():
            return []
        
        try:
            import requests
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = requests.get(f"{self.url}/api/tags", timeout=5, headers=headers)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model["name"] for model in models]
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
        
        return []
