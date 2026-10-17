"""Ollama провайдеры: Local (без ключа) и Cloud (OpenAI-совместимый, ключ обязателен).

Разделение по требованию: ключ работает только для Cloud; локальный
режим ключ игнорирует (предупреждение в лог).
"""

import logging
from typing import Optional, Dict, Any, List

try:
    import litellm
    LITELLM_AVAILABLE = True
except Exception as _litellm_import_error:  # noqa: BLE001 — в frozen-exe tiktoken падает с ValueError
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logging.warning("litellm not available: %s", _litellm_import_error)

from gmod.infrastructure.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

LOCAL_URLS = {"http://localhost:11434", "http://127.0.0.1:11434"}


def _map_http_status(status_code: int, what: str = ""):
    """Статус HTTP-кода через единую таблицу (401/403/429/404)."""
    from gmod.infrastructure.llm.health import (
        HTTP_STATUS_TABLE, ProviderStatus,
    )
    if status_code in HTTP_STATUS_TABLE:
        reason, msg = HTTP_STATUS_TABLE[status_code]
        if status_code == 404 and what:
            msg = f"{msg}: '{what}'"
        return ProviderStatus(False, msg, reason, f"HTTP {status_code}")
    return ProviderStatus(
        False, f"⚠ Соединение отсутствует. HTTP {status_code}",
        "no_connection", f"HTTP {status_code}",
    )


class OllamaProvider(BaseLLMProvider):
    """Ollama Local: только localhost, БЕЗ ключа.

    Переданный ключ игнорируется (warning в лог) — для облака
    используйте OllamaCloudProvider.
    """

    auth_type = "none"

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация локального провайдера.

        Args:
            api_key: Игнорируется (локальный режим без ключа)
            config: Конфигурация с url и model
        """
        super().__init__(None, config)
        self.url = config.get("url", "http://localhost:11434") if config else "http://localhost:11434"
        self.model = config.get("model", "llama3.2:3b") if config else "llama3.2:3b"
        if api_key or (config and config.get("api_key")):
            logger.warning("Ollama Local: API-ключ игнорируется (localhost без ключа)")
        if self.url.rstrip("/").lower() not in LOCAL_URLS:
            logger.warning("Ollama Local: не-localhost URL %s — для облака нужен OllamaCloud",
                           self.url)
        self._validate_config()

    def _validate_config(self, required_keys: list = None) -> bool:
        """Валидация конфигурации (совместима с BaseLLMProvider)."""
        if not self.url:
            logger.warning("Ollama URL not configured, using default")
            self.url = "http://localhost:11434"
        if required_keys:
            return super()._validate_config(required_keys)
        return True

    def _auth_headers(self) -> Dict[str, str]:
        """Локальный режим: заголовков авторизации нет."""
        return {}

    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация через нативный HTTP API (POST /api/chat), БЕЗ litellm.

        Args:
            prompt: Промпт для генерации
            **kwargs: temperature, max_tokens, timeout

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
        timeout = extra.pop("timeout", 180)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        logger.info(
            "Ollama Local: generate model=%s url=%s prompt_len=%d",
            self.model, self.url, len(prompt),
        )
        try:
            response = requests.post(
                f"{self.url.rstrip('/')}/api/chat",
                json=payload,
                headers={},
                timeout=timeout,
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
        """Сервер отвечает на /api/tags (без litellm)."""
        try:
            import requests
            response = requests.get(f"{self.url}/api/tags", timeout=5)
            ok = response.status_code == 200
            if ok:
                logger.info("Ollama Local: доступна (%s, модель %s)", self.url, self.model)
            else:
                logger.warning("Ollama Local: недоступна, HTTP %s", response.status_code)
            return ok
        except Exception as e:
            logger.warning(f"Ollama not available at {self.url}: {e}")
            return False

    def check_connection(self):
        """Лёгкая проверка: сервер + модель (без generation, с таблицей кодов)."""
        from gmod.infrastructure.llm.health import (
            MSG_NO_LIB, MSG_OK, ProviderStatus, classify_exception,
        )

        use_litellm = bool(self.config.get("use_litellm", False)) if self.config else False
        if use_litellm and not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        try:
            import requests
            resp = requests.get(f"{self.url}/api/tags", timeout=5)
            if resp.status_code == 200:
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
                logger.info("Ollama Local: проверка соединения — OK")
                return ProviderStatus(True, MSG_OK, "ok", f"HTTP 200, {self.url}")
            return _map_http_status(resp.status_code)
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])

    def check_status(self):
        """Алиас check_connection для совместимости."""
        return self.check_connection()

    def validate_credentials(self):
        """Local: ключ не нужен и игнорируется."""
        from gmod.infrastructure.llm.health import MSG_OK, ProviderStatus
        return ProviderStatus(True, MSG_OK, "ok", "local, no key required")

    def test_inference(self, prompt: str = "Ответь одним словом: тест.") -> str:
        """Явный тестовый inference (отдельная операция)."""
        logger.info("Ollama Local: тестовый inference (модель %s)", self.model)
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
        """Список моделей (GET /api/tags)."""
        import requests
        resp = requests.get(f"{self.url}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", []) if m.get("name")]

    def get_available_models(self) -> list:
        """Алиас list_models."""
        try:
            return self.list_models()
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return []


class OllamaCloudProvider(BaseLLMProvider):
    """Ollama Cloud: ключ ОБЯЗАТЕЛЕН.

    Транспорт выбирается по URL (нормализация):
    - URL заканчивается на /api → нативный Ollama API
      (POST {url}/chat, GET {url}/tags, Bearer);
    - иначе → OpenAI-совместимый режим через litellm
      (base https://ollama.com/v1).
    Дефолт: https://ollama.com/v1.
    """

    auth_type = "bearer"

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Инициализация облачного провайдера.

        Args:
            api_key: Bearer-ключ Ollama Cloud (обязателен; SSH-ключ не подойдёт)
            config: url (base endpoint), model
        """
        super().__init__(api_key, config)
        from gmod.config.constants import DEFAULT_OLLAMA_CLOUD_URL
        raw_url = (config.get("url") or DEFAULT_OLLAMA_CLOUD_URL) if config else DEFAULT_OLLAMA_CLOUD_URL
        self.url = self.normalize_url(raw_url)
        self.model = (config.get("model") or "llama3.2:3b") if config else "llama3.2:3b"
        if config and config.get("api_key") and not self.api_key:
            self.api_key = config.get("api_key")
        if not self.api_key:
            logger.warning("Ollama Cloud: API-ключ обязателен, но не задан")

    @staticmethod
    def normalize_url(url: str) -> str:
        """Нормализовать base URL облака.

        - Пусто -> https://ollama.com/v1
        - .../api или .../api/ -> как есть (нативный транспорт)
        - .../v1 -> как есть (OpenAI транспорт)
        - голый хост -> + /v1 (OpenAI транспорт)
        """
        from gmod.config.constants import DEFAULT_OLLAMA_CLOUD_URL
        text = (url or "").strip().rstrip("/")
        if not text:
            return DEFAULT_OLLAMA_CLOUD_URL
        lowered = text.lower()
        if lowered.endswith("/api") or lowered.endswith("/v1"):
            return text
        return text + "/v1"

    def _transport(self) -> str:
        """'native' для .../api, иначе 'openai'."""
        return "native" if self.url.rstrip("/").lower().endswith("/api") else "openai"

    def _native_base(self) -> str:
        """Хост для нативных /api/tags и /api/chat."""
        base = self.url.rstrip("/")
        lowered = base.lower()
        if lowered.endswith("/v1"):
            base = base[: -len("/v1")]
        if not lowered.endswith("/api"):
            base = base + "/api"
        return base

    def _models_url(self) -> str:
        """URL списка моделей под текущий транспорт."""
        if self._transport() == "native":
            return f"{self._native_base()}/tags"
        return f"{self.url.rstrip('/')}/models"

    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация: нативный /api/chat или OpenAI-режим (по URL)."""
        if not (self.api_key or "").strip():
            raise ValueError("Ollama Cloud: API-ключ обязателен")
        if self._transport() == "native":
            return self._generate_native(prompt, **kwargs)
        return self._generate_openai(prompt, **kwargs)

    def _generate_native(self, prompt: str, **kwargs) -> str:
        """Нативный POST {base}/api/chat с Bearer."""
        import requests
        extra = dict(kwargs)
        temperature = extra.pop("temperature", 0.7)
        max_tokens = extra.pop("max_tokens", 2000)
        timeout = extra.pop("timeout", 60)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        resp = requests.post(f"{self._native_base()}/chat", json=payload,
                             headers=self._auth_headers(), timeout=timeout)
        if resp.status_code in (401, 403, 404, 429):
            raise RuntimeError(_map_http_status(resp.status_code, self.model).message)
        resp.raise_for_status()
        try:
            content = resp.json().get("message", {}).get("content", "")
        except Exception as e:
            raise RuntimeError(f"Ollama Cloud вернул не-JSON ответ: {e}")
        if not content:
            raise RuntimeError("Ollama Cloud вернул пустой ответ")
        logger.info("Ollama Cloud (native): ответ получен (длина %d)", len(content))
        return content

    def _generate_openai(self, prompt: str, **kwargs) -> str:
        """Генерация через OpenAI-совместимый endpoint (litellm)."""
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available, cannot use Ollama Cloud")
        if not (self.api_key or "").strip():
            raise ValueError("Ollama Cloud: API-ключ обязателен")
        try:
            extra = dict(kwargs)
            temperature = extra.pop("temperature", 0.7)
            max_tokens = extra.pop("max_tokens", 2000)
            timeout = extra.pop("timeout", 60)
            response = litellm.completion(
                model=f"openai/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.url,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **extra,
            )
            content = response["choices"][0]["message"]["content"] or ""
            if not content:
                raise RuntimeError("Ollama Cloud вернул пустой ответ")
            logger.info("Ollama Cloud: ответ получен (длина %d)", len(content))
            return content
        except Exception as e:
            logger.error(f"Ollama Cloud generation error: {e}")
            raise

    def list_models(self) -> List[str]:
        """Список моделей (GET /models с Bearer, ТЗ §3.3)."""
        import requests
        resp = requests.get(self._models_url(), headers=self._auth_headers(), timeout=10)
        if resp.status_code in (401, 403, 429):
            raise RuntimeError(_map_http_status(resp.status_code).message)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", data.get("models", []))
        return sorted(m.get("id", m.get("name", "")) for m in items if m.get("id") or m.get("name"))

    def check_connection(self):
        """Сервер + ключ + модель (без generation)."""
        from gmod.infrastructure.llm.health import (
            MSG_NO_LIB, ProviderStatus, classify_exception,
        )
        if not LITELLM_AVAILABLE:
            return ProviderStatus(False, MSG_NO_LIB, "no_lib", "litellm not installed")
        cred = self.validate_credentials()
        if not cred.ok:
            return cred
        try:
            names = self.list_models()
        except Exception as e:
            reason, msg = classify_exception(e)
            return ProviderStatus(False, msg, reason, str(e)[:300])
        from gmod.infrastructure.llm.health import MSG_OK
        short = self.model.split("/")[-1]
        if names and self.model not in names and short not in names:
            from gmod.infrastructure.llm.health import MSG_MODEL_MISSING
            return ProviderStatus(False, f"{MSG_MODEL_MISSING}: '{self.model}'",
                                  "model_missing", f"have={len(names)}")
        logger.info("Ollama Cloud: проверка соединения — OK")
        return ProviderStatus(True, MSG_OK, "ok", f"model={self.model}")

    def check_status(self):
        """Алиас check_connection для совместимости."""
        return self.check_connection()

    def validate_credentials(self):
        """Ключ обязателен; SSH-ключ сразу помечаем предупреждением."""
        from gmod.infrastructure.llm.health import (
            MSG_BAD_KEY, MSG_NO_KEY, MSG_OK, ProviderStatus,
        )
        key = (self.api_key or "").strip()
        if not key:
            return ProviderStatus(False, MSG_NO_KEY, "no_key", "cloud needs key")
        if key.startswith("ssh-"):
            return ProviderStatus(
                False,
                MSG_BAD_KEY + ": похоже на SSH-ключ, а нужен Bearer API-ключ "
                "Ollama Cloud (создаётся в настройках ключей на сайте).",
                "bad_key", "ssh-like key")
        return ProviderStatus(True, MSG_OK, "ok", "key present")

    def test_inference(self, prompt: str = "Ответь одним словом: тест.") -> str:
        """Явный тестовый inference (отдельная операция)."""
        logger.info("Ollama Cloud: тестовый inference (модель %s)", self.model)
        # 200 токенов: reasoning-моделям (gpt-oss) мало 50 — вернут пустоту.
        return self.generate(prompt, max_tokens=200, temperature=0.0)

    def is_available(self) -> bool:
        try:
            return self.check_connection().ok
        except Exception:
            return False
