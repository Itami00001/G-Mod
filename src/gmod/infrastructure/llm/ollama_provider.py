"""Ollama провайдер для LLM."""

import logging
from typing import Optional, Dict, Any

try:
    import litellm
    LITELLM_AVAILABLE = True
except Exception as _litellm_import_error:  # noqa: BLE001 — в frozen-exe tiktoken падает с ValueError
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available, Ollama provider will not work: %s", _litellm_import_error)

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер Ollama для локальных LLM."""

    auth_type = "bearer"  # Ollama Cloud; для local ключ не шлём (см. _auth_headers)

    def _auth_headers(self) -> Dict[str, str]:
        """Единая авторизация (ТЗ §3.3): local — без ключа, cloud — Bearer.

        Применяется ко ВСЕМ запросам: /api/tags, /api/chat, /api/generate.
        """
        if getattr(self, "_local_mode", True):
            return {}
        return super()._auth_headers()
    
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
        self._local_mode = self.url.rstrip('/').lower() in {
            "http://localhost:11434", "http://127.0.0.1:11434",
        }
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

        По умолчанию — напрямую через нативный HTTP API (/api/chat),
        БЕЗ litellm: litellm пытается считать токены через tiktoken
        (кодировка cl100k_base) и падает с "Unknown encoding cl100k_base"
        ещё до сетевого запроса — чат при запущенной Ollama не работает.
        Нативный путь этот класс ошибок исключает полностью.
        litellm остаётся опцией: config {"use_litellm": True}.

        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры (temperature, max_tokens, etc.)

        Returns:
            Сгенерированный текст
        """
        use_litellm = bool(self.config.get("use_litellm", False)) if self.config else False
        if use_litellm:
            return self._generate_via_litellm(prompt, **kwargs)
        return self._generate_native(prompt, **kwargs)

    def _generate_native(self, prompt: str, **kwargs) -> str:
        """Генерация через нативный HTTP API Ollama (POST /api/chat)."""
        import requests

        extra = dict(kwargs)
        temperature = extra.pop("temperature", 0.7)
        max_tokens = extra.pop("max_tokens", 2000)
        headers = {}
        if self.api_key and not self._local_mode:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        logger.info(
            "Ollama: native generate model=%s url=%s prompt_len=%d",
            self.model, self.url, len(prompt),
        )
        try:
            response = requests.post(
                f"{self.url.rstrip('/')}/api/chat",
                json=payload,
                headers=headers,
                timeout=180,
            )
        except Exception as e:
            logger.error(f"Ollama native request failed: {e}")
            raise
        if response.status_code == 404:
            raise RuntimeError(
                f"Модель '{self.model}' не найдена на сервере {self.url}. "
                f"Установите её командой: ollama pull {self.model}"
            )
        response.raise_for_status()
        try:
            content = response.json().get("message", {}).get("content", "")
        except Exception as e:
            raise RuntimeError(f"Ollama вернул не-JSON ответ: {e}")
        if not content:
            raise RuntimeError("Ollama вернул пустой ответ")
        logger.info("Ollama: ответ получен (длина %d)", len(content))
        return content

    def _generate_via_litellm(self, prompt: str, **kwargs) -> str:
        """Генерация через litellm (опция use_litellm=True)."""
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
            if self.api_key and not self._local_mode:
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
        """Проверка доступности Ollama (сервер отвечает на /api/tags).

        litellm для проверки не нужен — используется прямой HTTP-запрос.
        """
        try:
            import requests
            headers = self._auth_headers()
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

    def check_connection(self):
        """Лёгкая проверка: сервер + модель (без generation prompt, ТЗ §6).

        Returns:
            ProviderStatus.
        """
        from gmod.infrastructure.llm.health import (
            MSG_OK, ProviderStatus, classify_exception,
        )

        use_litellm = bool(self.config.get("use_litellm", False)) if self.config else False
        if use_litellm and not LITELLM_AVAILABLE:
            from gmod.infrastructure.llm.health import MSG_NO_LIB
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        try:
            import requests
            resp = requests.get(f"{self.url}/api/tags", timeout=5,
                                headers=self._auth_headers())
            if resp.status_code == 200:
                # Сервер жив — проверяем, установлена ли нужная модель.
                try:
                    names = [m.get("name", "") for m in resp.json().get("models", [])]
                except Exception:
                    names = []
                if names and not self._model_installed(names):
                    from gmod.infrastructure.llm.health import MSG_MODEL_MISSING
                    hint = (MSG_MODEL_MISSING + f": '{self.model}'. "
                            f"Выполните: ollama pull {self.model}")
                    logger.warning("Ollama: %s (установлены: %s)", hint, names)
                    return ProviderStatus(False, hint, "model_missing", f"have={names}")
                logger.info("Ollama: проверка соединения — OK")
                return ProviderStatus(True, MSG_OK, "ok", f"HTTP 200, {self.url}")
            if resp.status_code in (401, 403):
                from gmod.infrastructure.llm.health import MSG_BAD_KEY
                logger.warning("Ollama: API ключ не валидный (HTTP %s)", resp.status_code)
                return ProviderStatus(False, MSG_BAD_KEY, "bad_key", f"HTTP {resp.status_code}")
            return ProviderStatus(
                False, f"⚠ Соединение отсутствует. HTTP {resp.status_code}",
                "no_connection", f"HTTP {resp.status_code}",
            )
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])

    def check_status(self):
        """Алиас check_connection для совместимости."""
        return self.check_connection()

    def validate_credentials(self):
        """Local — ключ не нужен; Cloud — ключ обязателен (ТЗ §3.3)."""
        from gmod.infrastructure.llm.health import (
            MSG_NO_KEY, MSG_OK, ProviderStatus,
        )
        if getattr(self, "_local_mode", True):
            return ProviderStatus(True, MSG_OK, "ok", "local, no key required")
        if not (self.api_key or "").strip():
            return ProviderStatus(False, MSG_NO_KEY, "no_key", "cloud needs key")
        return ProviderStatus(True, MSG_OK, "ok", "key present")

    def test_inference(self, prompt: str = "Ответь одним словом: тест.") -> str:
        """Явный тестовый inference (ТЗ §6: отдельная операция)."""
        logger.info("Ollama: тестовый inference (модель %s)", self.model)
        return self.generate(prompt, max_tokens=50, temperature=0.0)

    def _model_installed(self, server_models: list) -> bool:
        """Есть ли нужная модель на сервере (точное имя или базовое без тега)."""
        want = (self.model or "").strip()
        if not want:
            return True
        if want in server_models:
            return True
        base = want.split(":")[0]
        return any(m == base or m.split(":")[0] == base for m in server_models)

    def list_models(self) -> list:
        """Список моделей Ollama (GET /api/tags, с единой авторизацией, ТЗ §3.3)."""
        import requests
        resp = requests.get(f"{self.url}/api/tags", timeout=5,
                            headers=self._auth_headers())
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", []) if m.get("name")]

    def get_available_models(self) -> list:
        """Получение списка доступных моделей (алиас list_models)."""
        try:
            return self.list_models()
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return []
