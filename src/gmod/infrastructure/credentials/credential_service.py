"""CredentialService — безопасное хранение API-ключей (ТЗ §4).

Приоритет поиска ключа:
    1. OS Credential Store (keyring, service=GMod)
    2. Environment Variable (GROQ_API_KEY / GEMINI_API_KEY / ...)
    3. Legacy config.yaml (только чтение; после миграции удаляется)

Никаких секретов в коде, SQLite, JSON или backup ZIP.
"""

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "GMod"

# account -> env var
ENV_VARS: Dict[str, str] = {
    "ollama": "OLLAMA_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

KNOWN_ACCOUNTS = tuple(ENV_VARS.keys())


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False


class CredentialService:
    """Сервис доступа к секретам (ТЗ §4)."""

    def __init__(self, service: str = SERVICE_NAME):
        self.service = service

    # ---------------- чтение ----------------

    def get_key(self, account: str, legacy_yaml_key: str = "") -> str:
        """Получить ключ по приоритету: keyring -> env -> legacy YAML."""
        account = account.lower()
        # 1. OS Credential Store
        if _keyring_available():
            try:
                import keyring
                value = keyring.get_password(self.service, account)
                if value:
                    logger.debug("credential: %s из OS Credential Store", account)
                    return value
            except Exception as e:
                logger.warning("credential: keyring read failed for %s: %s", account, e)
        # 2. Environment Variable
        env_name = ENV_VARS.get(account, "")
        if env_name and os.environ.get(env_name):
            logger.debug("credential: %s из env %s", account, env_name)
            return os.environ[env_name]
        # 3. Legacy config.yaml
        if legacy_yaml_key:
            logger.debug("credential: %s из legacy config.yaml", account)
            return legacy_yaml_key
        return ""

    def has_key(self, account: str, legacy_yaml_key: str = "") -> bool:
        """Есть ли ключ хоть в одном источнике."""
        return bool(self.get_key(account, legacy_yaml_key))

    def key_source(self, account: str, legacy_yaml_key: str = "") -> str:
        """Где лежит ключ: keyring | env | legacy | none (для UI/диагностики)."""
        account = account.lower()
        if _keyring_available():
            try:
                import keyring
                if keyring.get_password(self.service, account):
                    return "keyring"
            except Exception:
                pass
        env_name = ENV_VARS.get(account, "")
        if env_name and os.environ.get(env_name):
            return "env"
        if legacy_yaml_key:
            return "legacy"
        return "none"

    # ---------------- запись/удаление ----------------

    def set_key(self, account: str, value: str) -> None:
        """Сохранить ключ в OS Credential Store."""
        if not _keyring_available():
            raise RuntimeError("keyring недоступен — ключ не сохранён")
        import keyring
        keyring.set_password(self.service, account.lower(), value or "")
        logger.info("credential: %s сохранён в OS Credential Store", account)

    def delete_key(self, account: str) -> bool:
        """Удалить ключ из OS Credential Store. Returns True если был."""
        if not _keyring_available():
            return False
        import keyring
        try:
            existing = keyring.get_password(self.service, account.lower())
        except Exception:
            existing = None
        try:
            keyring.delete_password(self.service, account.lower())
        except Exception:
            pass
        logger.info("credential: %s удалён из OS Credential Store", account)
        return bool(existing)

    # ---------------- миграция ----------------

    def migrate_from_legacy(self, legacy: Dict[str, str]) -> Dict[str, str]:
        """Перенести ключи из legacy config.yaml в keyring.

        Args:
            legacy: {account: key} из YAML.

        Returns:
            {account: 'migrated' | 'skipped-empty' | 'failed: ...'}.
        """
        result: Dict[str, str] = {}
        for account, key in legacy.items():
            account = account.lower()
            if not key:
                result[account] = "skipped-empty"
                continue
            try:
                self.set_key(account, key)
                result[account] = "migrated"
            except Exception as e:
                result[account] = f"failed: {e}"
        return result

    @staticmethod
    def mask_key(value: str, visible: int = 4) -> str:
        """Маскированное отображение: ••••••abcd."""
        if not value:
            return "(не задан)"
        if len(value) <= visible:
            return "•" * len(value)
        return "•" * max(4, len(value) - visible) + value[-visible:]


# Глобальный экземпляр
_credential_service: Optional[CredentialService] = None


def get_credential_service() -> CredentialService:
    """Глобальный CredentialService.

    Через env GMOD_CREDENTIAL_SERVICE можно задать другое имя сервиса
    (используется в тестах для изоляции от реального хранилища).
    """
    global _credential_service
    service = os.environ.get("GMOD_CREDENTIAL_SERVICE", SERVICE_NAME)
    if _credential_service is None or _credential_service.service != service:
        _credential_service = CredentialService(service=service)
    return _credential_service
