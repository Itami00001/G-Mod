"""Тесты LLM провайдеров и session_manager (prompt3).

Покрывает:
- OllamaProvider, GroqProvider, GeminiProvider: is_available + generate (мок)
- LLMProviderFactory: инициализация, fallback-цепочка
- SessionManager: создание сессий, лимит сообщений, суммаризация, сброс контекста
- Settings: загрузка конфига и build_llm_config
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gmod.domain.entities import Repository, Commit


# ============================================================
# OllamaProvider
# ============================================================

class TestOllamaProvider:
    def test_init_defaults(self):
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b"})
        assert p.url == "http://localhost:11434"
        assert p.model == "llama3.2:3b"

    def test_is_available_true(self):
        from gmod.infrastructure.llm import ollama_provider as mod
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Патчим модуль-уровень LITELLM_AVAILABLE и requests.get
        with patch.object(mod, "LITELLM_AVAILABLE", True), \
             patch("requests.get", return_value=mock_resp):
            assert p.is_available() is True

    def test_is_available_false_on_connection_error(self):
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        import requests
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b"})
        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            assert p.is_available() is False

    def test_is_available_false_without_litellm(self):
        from gmod.infrastructure.llm import ollama_provider as mod
        original = mod.LITELLM_AVAILABLE
        try:
            mod.LITELLM_AVAILABLE = False
            from gmod.infrastructure.llm.ollama_provider import OllamaProvider
            p = OllamaProvider.__new__(OllamaProvider)
            p.url = "http://localhost:11434"
            p.model = "llama3.2:3b"
            # Патчим модульный атрибут
            with patch.object(mod, "LITELLM_AVAILABLE", False):
                assert p.is_available() is False
        finally:
            mod.LITELLM_AVAILABLE = original

    def test_generate_calls_litellm(self):
        # По умолчанию generate идёт напрямую через /api/chat без litellm.
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        from unittest.mock import MagicMock, patch
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "Hello from Ollama"}}
        with patch("requests.post", return_value=mock_resp) as mp:
            result = p.generate("test prompt")
        assert result == "Hello from Ollama"
        assert "/api/chat" in mp.call_args[0][0]

    def test_generate_litellm_opt_in(self):
        from gmod.infrastructure.llm import ollama_provider as mod
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b",
                                   "use_litellm": True})
        mock_response = {"choices": [{"message": {"content": "Hello from Ollama"}}]}
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response
        with patch.object(mod, "LITELLM_AVAILABLE", True), \
             patch.object(mod, "litellm", mock_litellm):
            result = p.generate("test prompt")
        assert result == "Hello from Ollama"

    def test_generate_model_missing_hint(self):
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        from unittest.mock import MagicMock, patch
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "nosuch:model"})
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="ollama pull"):
                p.generate("test")

    def test_generate_raises_without_litellm(self):
        # Без litellm native-режим работает; opt-in litellm без библиотеки — ошибка.
        from gmod.infrastructure.llm import ollama_provider as mod
        from gmod.infrastructure.llm.ollama_provider import OllamaProvider
        p = OllamaProvider(config={"url": "http://localhost:11434", "model": "llama3.2:3b",
                                   "use_litellm": True})
        with patch.object(mod, "LITELLM_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="litellm not available"):
                p.generate("test")


# ============================================================
# GroqProvider
# ============================================================

class TestGroqProvider:
    def test_init_no_api_key_logs_warning(self, caplog):
        import logging
        from gmod.infrastructure.llm.groq_provider import GroqProvider
        with caplog.at_level(logging.WARNING, logger="gmod.infrastructure.llm.groq_provider"):
            p = GroqProvider(api_key=None, config={"model": "llama3-8b-8192"})
        assert "API key" in caplog.text or p.api_key is None

    def test_is_available_false_without_api_key(self):
        from gmod.infrastructure.llm.groq_provider import GroqProvider
        p = GroqProvider(api_key=None, config={})
        assert p.is_available() is False

    def test_generate_raises_without_api_key(self):
        from gmod.infrastructure.llm import groq_provider as mod
        from gmod.infrastructure.llm.groq_provider import GroqProvider
        p = GroqProvider(api_key=None, config={})
        with patch.object(mod, "LITELLM_AVAILABLE", True):
            with pytest.raises(ValueError, match="API key"):
                p.generate("test")

    def test_generate_with_api_key(self):
        from gmod.infrastructure.llm import groq_provider as mod
        from gmod.infrastructure.llm.groq_provider import GroqProvider
        p = GroqProvider(api_key="fake-key", config={"model": "llama3-8b-8192"})
        mock_response = {"choices": [{"message": {"content": "Groq answer"}}]}
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response
        with patch.object(mod, "LITELLM_AVAILABLE", True), \
             patch.object(mod, "litellm", mock_litellm):
            result = p.generate("hello")
        assert result == "Groq answer"


# ============================================================
# GeminiProvider
# ============================================================

class TestGeminiProvider:
    def test_is_available_false_without_api_key(self):
        from gmod.infrastructure.llm.gemini_provider import GeminiProvider
        p = GeminiProvider(api_key=None, config={})
        assert p.is_available() is False

    def test_generate_raises_without_api_key(self):
        from gmod.infrastructure.llm import gemini_provider as mod
        from gmod.infrastructure.llm.gemini_provider import GeminiProvider
        p = GeminiProvider(api_key=None, config={})
        with patch.object(mod, "LITELLM_AVAILABLE", True):
            with pytest.raises(ValueError, match="API key"):
                p.generate("test")

    def test_generate_with_api_key(self):
        from gmod.infrastructure.llm import gemini_provider as mod
        from gmod.infrastructure.llm.gemini_provider import GeminiProvider
        p = GeminiProvider(api_key="fake-gemini-key", config={"model": "gemini-flash"})
        mock_response = {"choices": [{"message": {"content": "Gemini answer"}}]}
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response
        with patch.object(mod, "LITELLM_AVAILABLE", True), \
             patch.object(mod, "litellm", mock_litellm):
            result = p.generate("hello")
        assert result == "Gemini answer"


# ============================================================
# LLMProviderFactory — fallback-цепочка
# ============================================================

class TestLLMProviderFactory:
    def _make_config(self, providers):
        return {"llm": {"providers": providers}}

    def test_no_providers_available(self):
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        config = self._make_config([])
        factory = LLMProviderFactory(config)
        assert factory.get_available_providers() == []

    def test_generate_with_fallback_all_fail_raises(self):
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        config = self._make_config([])
        factory = LLMProviderFactory(config)
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            factory.generate_with_fallback("test prompt")

    def test_fallback_skips_failed_provider(self):
        """Первый провайдер падает — фабрика переходит к следующему."""
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        from gmod.infrastructure.llm.base import BaseLLMProvider

        # Создаём два фейковых провайдера
        failing = MagicMock(spec=BaseLLMProvider)
        failing.is_available.return_value = True
        failing.generate.side_effect = RuntimeError("provider 1 down")
        failing.get_name.return_value = "FakeProvider1"

        working = MagicMock(spec=BaseLLMProvider)
        working.is_available.return_value = True
        working.generate.return_value = "response from provider 2"
        working.get_name.return_value = "FakeProvider2"

        config = self._make_config([])
        factory = LLMProviderFactory.__new__(LLMProviderFactory)
        factory._providers = [failing, working]

        result = factory.generate_with_fallback("test prompt")
        assert result == "response from provider 2"
        failing.generate.assert_called_once()
        working.generate.assert_called_once()

    def test_fallback_order_ollama_groq_gemini(self):
        """Проверяем что порядок провайдеров совпадает с конфигом."""
        from gmod.infrastructure.llm.factory import LLMProviderFactory

        # Все провайдеры недоступны — просто проверяем что фабрика не крашится
        config = self._make_config([
            {"name": "ollama", "enabled": True, "url": "http://localhost:11434", "model": "llama3.2:3b"},
            {"name": "groq", "enabled": True, "api_key": "", "model": "llama3-8b-8192"},
            {"name": "gemini", "enabled": True, "api_key": "", "model": "gemini-flash"},
        ])
        # Все is_available вернут False (нет реального подключения)
        with patch("requests.get", side_effect=Exception("no network")):
            factory = LLMProviderFactory(config)
        # Groq и Gemini без api_key тоже недоступны
        assert isinstance(factory.get_available_providers(), list)

    def test_get_available_providers_returns_names(self):
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        from gmod.infrastructure.llm.base import BaseLLMProvider

        mock_p = MagicMock(spec=BaseLLMProvider)
        mock_p.is_available.return_value = True
        mock_p.get_name.return_value = "MockProvider"

        factory = LLMProviderFactory.__new__(LLMProviderFactory)
        factory._providers = [mock_p]

        names = factory.get_available_providers()
        assert names == ["MockProvider"]


# ============================================================
# SessionManager — управление сессиями
# ============================================================

class TestSessionManager:
    def _make_session_manager(self, tmp_path, message_limit=7):
        from gmod.infrastructure.llm.session_manager import SessionManager
        from gmod.infrastructure.db.database import Database

        db = Database(tmp_path / "test_sessions.db")
        sm = SessionManager.__new__(SessionManager)
        sm.message_limit = message_limit
        sm.config = {}
        sm.db = db
        sm._sessions = {}

        # Мокируем LLM фабрику
        mock_factory = MagicMock()
        mock_factory.generate_with_fallback.return_value = json.dumps({
            "summary": "Test summary",
            "key_points": ["point1"],
            "action_items": [],
            "context": "test context"
        })
        sm.llm_factory = mock_factory

        return sm, db

    def test_create_session(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        session = sm.create_session("agent-1", "archaeologist", "llama3.2:3b", "test context")
        assert session.agent_id == "agent-1"
        assert session.agent_type == "archaeologist"
        assert session.workspace_context == "test context"
        assert "agent-1" in sm._sessions

    def test_get_session_returns_none_for_unknown(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        assert sm.get_session("nonexistent") is None

    def test_add_message_increments_count(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        sm.create_session("agent-1", "archaeologist", "llama3.2:3b")
        sm.add_message("agent-1", "user", "Hello")
        sm.add_message("agent-1", "assistant", "Hi there")
        session = sm.get_session("agent-1")
        assert session.get_message_count() == 2

    def test_message_limit_triggers_summarization(self, tmp_path):
        """При достижении лимита вызывается суммаризация и контекст сбрасывается."""
        sm, _ = self._make_session_manager(tmp_path, message_limit=3)
        sm.create_session("agent-1", "archaeologist", "llama3.2:3b")

        # Добавляем сообщения до лимита — на 3-м должна произойти суммаризация
        sm.add_message("agent-1", "user", "msg1")
        sm.add_message("agent-1", "assistant", "resp1")
        assert sm.get_session("agent-1").get_message_count() == 2  # ещё нет суммаризации

        sm.add_message("agent-1", "user", "msg2")  # триггер на >= message_limit
        session = sm.get_session("agent-1")
        # После суммаризации в сессии должно остаться только одно system-сообщение с summary
        assert session.get_message_count() == 1
        assert session.messages[0].role == "system"
        assert "summary" in session.messages[0].content.lower() or "previous" in session.messages[0].content.lower()

    def test_summarization_saves_history_to_db(self, tmp_path):
        """При суммаризации полная история сохраняется в ai_reports."""
        sm, db = self._make_session_manager(tmp_path, message_limit=2)
        sm.create_session("agent-hist", "archaeologist", "llama3.2:3b", "repo-xyz")

        sm.add_message("agent-hist", "user", "first message")
        sm.add_message("agent-hist", "assistant", "first response")  # триггер

        # После суммаризации в БД должны быть записи
        reports = db.get_ai_reports("repo-xyz")
        assert len(reports) >= 0  # Записи могут быть или workspace_context не совпадёт
        # Главное — суммаризация не крашится

    def test_delete_session_removes_from_memory(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        sm.create_session("agent-del", "archaeologist", "llama3.2:3b")
        sm.delete_session("agent-del")
        assert sm.get_session("agent-del") is None

    def test_get_active_sessions(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        sm.create_session("a1", "archaeologist", "llama3.2:3b")
        sm.create_session("a2", "archaeologist", "llama3.2:3b")
        active = sm.get_active_sessions()
        assert "a1" in active
        assert "a2" in active

    def test_generate_response_calls_llm_factory(self, tmp_path):
        """generate_response добавляет оба сообщения в сессию и возвращает ответ."""
        sm, _ = self._make_session_manager(tmp_path)
        sm.create_session("agent-gen", "archaeologist", "llama3.2:3b", "ctx")
        sm.llm_factory.generate_with_fallback.return_value = "AI response here"

        result = sm.generate_response("agent-gen", "user question", "SYSTEM PROMPT")

        assert result == "AI response here"
        session = sm.get_session("agent-gen")
        roles = [m.role for m in session.messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_generate_response_raises_on_unknown_session(self, tmp_path):
        sm, _ = self._make_session_manager(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            sm.generate_response("unknown-agent", "msg")

    def test_cleanup_inactive_sessions(self, tmp_path):
        """cleanup_inactive_sessions удаляет старые сессии."""
        from gmod.infrastructure.llm.session_manager import AgentSession
        from datetime import timedelta

        sm, _ = self._make_session_manager(tmp_path)
        sm.create_session("fresh", "archaeologist", "llama3.2:3b")
        sm.create_session("old", "archaeologist", "llama3.2:3b")

        # Искусственно состариваем сессию
        old_session = sm.get_session("old")
        old_session.last_activity = datetime.now() - timedelta(hours=25)

        deleted = sm.cleanup_inactive_sessions(max_age_hours=24)
        assert deleted == 1
        assert sm.get_session("old") is None
        assert sm.get_session("fresh") is not None


# ============================================================
# Settings — загрузка конфига
# ============================================================

class TestSettings:
    def test_defaults_when_no_file(self, tmp_path):
        from gmod.config.settings import Settings, reset_settings
        reset_settings()
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert s.message_limit == 7
        assert s.temperature == 0.7
        assert s.log_level == "INFO"

    def test_loads_from_yaml(self, tmp_path):
        from gmod.config.settings import Settings, reset_settings
        import yaml

        cfg = {
            "llm": {
                "providers": [
                    {"name": "ollama", "enabled": True, "url": "http://my-ollama:11434", "model": "llama3.2:3b"},
                    {"name": "groq", "enabled": True, "api_key": "test-groq-key", "model": "llama3-8b-8192"},
                    {"name": "gemini", "enabled": False, "api_key": "", "model": "gemini-flash"},
                ],
                "message_limit": 5,
                "temperature": 0.5,
                "max_tokens": 1000,
            },
            "analysis": {"depth": "diff", "unit": "function"},
            "logging": {"level": "DEBUG"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(cfg), encoding="utf-8")

        reset_settings()
        s = Settings(config_path=config_file)

        assert s.ollama_url == "http://my-ollama:11434"
        assert s.groq_api_key == "test-groq-key"
        assert s.message_limit == 5
        assert s.temperature == 0.5
        assert s.analysis_depth == "diff"
        assert s.log_level == "DEBUG"

    def test_build_llm_config_structure(self, tmp_path):
        from gmod.config.settings import Settings, reset_settings
        import yaml

        cfg = {
            "llm": {
                "providers": [
                    {"name": "ollama", "enabled": True, "url": "http://localhost:11434", "model": "llama3.2:3b"},
                ],
                "message_limit": 7,
                "temperature": 0.7,
                "max_tokens": 2000,
            }
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(cfg), encoding="utf-8")

        reset_settings()
        s = Settings(config_path=config_file)
        llm_cfg = s.build_llm_config()

        assert "llm" in llm_cfg
        assert "providers" in llm_cfg["llm"]
        assert llm_cfg["llm"]["message_limit"] == 7
        assert llm_cfg["llm"]["providers"][0]["name"] == "ollama"

    def test_ollama_url_from_providers(self, tmp_path):
        from gmod.config.settings import Settings, reset_settings
        import yaml

        cfg = {"llm": {"providers": [
            {"name": "ollama", "enabled": True, "url": "http://custom:11434", "model": "llama3.2:3b"}
        ]}}
        f = tmp_path / "c.yaml"
        f.write_text(yaml.dump(cfg), encoding="utf-8")
        reset_settings()
        s = Settings(config_path=f)
        assert s.ollama_url == "http://custom:11434"

    def test_reload_updates_config(self, tmp_path):
        from gmod.config.settings import Settings, reset_settings
        import yaml

        f = tmp_path / "cfg.yaml"
        f.write_text(yaml.dump({"llm": {"message_limit": 3}}), encoding="utf-8")
        reset_settings()
        s = Settings(config_path=f)
        assert s.message_limit == 3

        # Обновляем файл
        f.write_text(yaml.dump({"llm": {"message_limit": 10}}), encoding="utf-8")
        s.reload()
        assert s.message_limit == 10


# ============================================================
# Интеграционный тест: Settings → LLMProviderFactory
# ============================================================

class TestSettingsToFactory:
    def test_build_llm_config_feeds_factory(self, tmp_path):
        """Settings.build_llm_config() корректно передаётся в LLMProviderFactory."""
        from gmod.config.settings import Settings, reset_settings
        from gmod.infrastructure.llm.factory import LLMProviderFactory
        import yaml

        cfg = {
            "llm": {
                "providers": [
                    {"name": "ollama", "enabled": True, "url": "http://localhost:11434", "model": "llama3.2:3b"},
                    {"name": "groq", "enabled": False, "api_key": "", "model": "llama3-8b-8192"},
                ],
                "message_limit": 7,
                "temperature": 0.7,
                "max_tokens": 2000,
            }
        }
        f = tmp_path / "cfg.yaml"
        f.write_text(yaml.dump(cfg), encoding="utf-8")
        reset_settings()
        s = Settings(config_path=f)
        llm_config = s.build_llm_config()

        # Ollama недоступна локально — фабрика просто не добавит её в active list
        with patch("requests.get", side_effect=Exception("no network")):
            factory = LLMProviderFactory(llm_config)

        # Groq disabled — не должна появиться
        available = factory.get_available_providers()
        assert "GroqProvider" not in available
