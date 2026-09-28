"""Единый объект конфигурации провайдера (ТЗ §3.2).

LLMProviderConfig
    id / display_name / enabled / base_url / model /
    auth_type / credential_id /
    supports_model_listing / supports_streaming / supports_health_check
"""

from dataclasses import dataclass


@dataclass
class LLMProviderConfig:
    """Единая конфигурация AI-провайдера."""

    id: str = "ollama"                      # машинный id: ollama/groq/gemini/...
    display_name: str = "Ollama"            # человекочитаемое имя
    enabled: bool = True                    # включён в fallback-цепочку
    base_url: str = "http://localhost:11434"  # базовый URL API
    model: str = ""                         # модель по умолчанию
    auth_type: str = "none"                 # none | bearer | query_key
    credential_id: str = ""                 # account в CredentialService
    supports_model_listing: bool = True     # умеет list_models()
    supports_streaming: bool = False        # стриминг ответов
    supports_health_check: bool = True      # умеет check_connection()

    @classmethod
    def from_legacy(cls, name: str, entry: dict) -> "LLMProviderConfig":
        """Собрать из legacy-записи config.yaml (llm.providers[])."""
        name = (name or "").lower()
        defaults = {
            "ollama": ("Ollama", "http://localhost:11434", "none", "ollama"),
            "groq": ("Groq", "https://api.groq.com/openai/v1", "bearer", "groq"),
            "gemini": ("Gemini", "https://generativelanguage.googleapis.com/v1beta",
                       "query_key", "gemini"),
            "openai": ("OpenAI", "https://api.openai.com/v1", "bearer", "openai"),
            "anthropic": ("Anthropic", "https://api.anthropic.com/v1", "x-api-key",
                          "anthropic"),
            "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "bearer",
                           "openrouter"),
        }
        display, url, auth, cred = defaults.get(name, (name.title(), "", "bearer", name))
        return cls(
            id=name,
            display_name=display,
            enabled=bool(entry.get("enabled", False)),
            base_url=entry.get("url", entry.get("base_url", url)),
            model=entry.get("model", ""),
            auth_type=entry.get("auth_type", auth),
            credential_id=entry.get("credential_id", cred),
            supports_model_listing=name in ("ollama", "groq", "gemini", "openai",
                                            "openrouter"),
            supports_streaming=False,
            supports_health_check=True,
        )
