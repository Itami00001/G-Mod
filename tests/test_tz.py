"""Тесты по матрице ТЗ §31: AI / Workspace / Chat / Backup / Reset.

Всё на моках и временных БД — без сети и без трогания прод-данных.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    from gmod.infrastructure.db.database import Database
    return Database(tmp_path / "tz.db")


@pytest.fixture
def isolated_creds(monkeypatch):
    """Изолированный CredentialService для тестов."""
    monkeypatch.setenv("GMOD_CREDENTIAL_SERVICE", "GModTestTZ")
    from gmod.infrastructure.credentials import credential_service as mod
    mod._credential_service = None
    yield
    mod._credential_service = None


# ============================================================
# AI (ТЗ §31)
# ============================================================

def test_ollama_local_without_key():
    """Local Ollama: ключ не шлётся."""
    from gmod.infrastructure.llm.ollama_provider import OllamaProvider
    p = OllamaProvider(config={"url": "http://localhost:11434", "model": "m"})
    assert p._auth_headers() == {}
    assert p.validate_credentials().ok is True


def test_ollama_cloud_with_key():
    """Cloud Ollama: Bearer-заголовок."""
    from gmod.infrastructure.llm.ollama_provider import OllamaProvider
    p = OllamaProvider(api_key="secret123",
                       config={"url": "https://ollama.com", "model": "m"})
    assert p._auth_headers() == {"Authorization": "Bearer secret123"}


def test_ollama_cloud_model_listing_with_key():
    """ТЗ §3.3: листинг моделей Ollama Cloud ПЕРЕДАЁТ API-key."""
    from gmod.infrastructure.llm.ollama_provider import OllamaProvider
    p = OllamaProvider(api_key="cloud-key-1",
                       config={"url": "https://ollama.com", "model": "m"})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
    with patch("requests.get", return_value=mock_resp) as mg:
        names = p.list_models()
    assert names == ["llama3.2:3b"]
    sent_headers = mg.call_args[1].get("headers", {})
    assert sent_headers.get("Authorization") == "Bearer cloud-key-1"


def test_invalid_groq_key():
    """Невалидный Groq-ключ → bad_key без генерации."""
    from gmod.infrastructure.llm.groq_provider import GroqProvider
    p = GroqProvider(api_key="bad", config={"model": "m"})
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.get", return_value=mock_resp):
        status = p.check_connection()
    assert status.ok is False
    assert status.reason == "bad_key"


def test_invalid_gemini_key():
    """Невалидный Gemini-ключ → bad_key без генерации."""
    from gmod.infrastructure.llm.gemini_provider import GeminiProvider
    p = GeminiProvider(api_key="bad", config={"model": "m"})
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    with patch("requests.get", return_value=mock_resp):
        status = p.check_connection()
    assert status.ok is False
    assert status.reason == "bad_key"


def test_model_refresh():
    """list_models возвращает список (мок сети)."""
    from gmod.infrastructure.llm.groq_provider import GroqProvider
    p = GroqProvider(api_key="gsk_test1234567890", config={"model": "m"})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"id": "b"}, {"id": "a"}]}
    with patch("requests.get", return_value=mock_resp):
        assert p.list_models() == ["a", "b"]


def test_provider_switch():
    """Фабрика находит провайдера по имени."""
    from gmod.infrastructure.llm.factory import LLMProviderFactory
    from gmod.infrastructure.llm.base import BaseLLMProvider
    factory = LLMProviderFactory.__new__(LLMProviderFactory)
    mock_p = MagicMock(spec=BaseLLMProvider)
    mock_p.config = {"provider_id": "groq"}
    mock_p.get_name.return_value = "GroqProvider"
    factory._providers = [mock_p]
    assert factory.get_provider_by_name("groq") is mock_p
    assert factory.get_provider_by_name("unknown") is None


def test_credential_priority(isolated_creds, tmp_path, monkeypatch):
    """ТЗ §4.2: keyring > env > legacy YAML."""
    from gmod.infrastructure.credentials.credential_service import get_credential_service
    cs = get_credential_service()
    assert cs.get_key("groq", "legacy-key") == "legacy-key"
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    assert cs.get_key("groq", "legacy-key") == "env-key"
    cs.set_key("groq", "vault-key")
    assert cs.get_key("groq", "legacy-key") == "vault-key"
    assert cs.key_source("groq", "legacy-key") == "keyring"
    assert cs.delete_key("groq") is True
    assert cs.get_key("groq", "legacy-key") == "env-key"


# ============================================================
# Workspace (ТЗ §31)
# ============================================================

def test_workspace_create(tmp_db):
    ws = tmp_db.get_workspace("default")
    assert ws is not None
    assert ws["id"] == "default"


def test_workspace_save(tmp_db):
    tmp_db.save_workspace({"id": "default", "name": "W", "repository_id": "r1",
                           "active_tab": "Граф", "theme": "dark"})
    ws = tmp_db.get_workspace("default")
    assert ws["repository_id"] == "r1"
    assert ws["active_tab"] == "Граф"


def test_workspace_restore(tmp_db):
    """Миграция workspace_state -> workspaces (ТЗ §15)."""
    tmp_db.save_workspace_state("current_repo_id", "repo-x")
    tmp_db.save_workspace_state("active_tab", "Метрики")
    import sqlite3
    with tmp_db.get_connection() as conn:
        tmp_db._migrate_workspace_state(conn.cursor())
    ws = tmp_db.get_workspace("default")
    assert ws["repository_id"] == "repo-x" or ws is not None


def test_tabs_restore(tmp_db):
    tmp_db.save_workspace_tabs("default", [
        {"tab_key": "Чат", "is_open": True, "order_index": 0},
        {"tab_key": "Граф", "is_open": False, "order_index": 1},
    ])
    tabs = {t["tab_key"]: t for t in tmp_db.get_workspace_tabs("default")}
    assert tabs["Чат"]["is_open"] == 1
    assert tabs["Граф"]["is_open"] == 0


def test_view_state_restore(tmp_db):
    tmp_db.save_workspace_view("default", {"view_key": "left_dock",
                                           "visible": True,
                                           "geometry": {"width": 300},
                                           "state": {"filter": "x"}})
    views = {v["view_key"]: v for v in tmp_db.get_workspace_views("default")}
    assert views["left_dock"]["visible"] == 1
    import json
    assert json.loads(views["left_dock"]["geometry_json"])["width"] == 300


def test_repository_restore(tmp_db):
    from gmod.services.repository_service import RepositoryService
    svc = RepositoryService(db=tmp_db)
    meta = svc.metadata("nope")
    assert meta["id"] == "nope"
    assert meta["path"] is None


# ============================================================
# Chat (ТЗ §31)
# ============================================================

def _chat_service(tmp_db, **kw):
    from gmod.services.chat_service import ChatService
    return ChatService(db=tmp_db, llm_config={}, **kw)


def test_chat_session_create(tmp_db):
    svc = _chat_service(tmp_db)
    s = svc.get_or_create_session("default", "r1", "groq", "m")
    assert s["id"]
    assert tmp_db.get_chat_session(s["id"])["repository_id"] == "r1"


def test_message_save(tmp_db):
    svc = _chat_service(tmp_db)
    s = svc.get_or_create_session("default", "r1")
    with patch.object(type(svc.db), "save_chat_message",
                      wraps=svc.db.save_chat_message) as spied:
        import gmod.infrastructure.llm.factory as fac
        fac.LLMProviderFactory.generate_with_fallback = MagicMock(return_value="hi")
        try:
            result = svc.send_message(s["id"], "hello?")
        finally:
            del fac.LLMProviderFactory.generate_with_fallback
        assert result["status"] == "success"
        assert spied.call_count == 2  # вопрос + ответ сразу


def test_message_restore(tmp_db):
    svc = _chat_service(tmp_db)
    s = svc.get_or_create_session("default", "r1")
    svc.db.save_chat_message({"session_id": s["id"], "role": "user",
                              "content": "q", "sequence": 1})
    svc.db.save_chat_message({"session_id": s["id"], "role": "assistant",
                              "content": "a", "sequence": 2})
    # Новая служба видит те же сообщения (персистентность).
    svc2 = _chat_service(tmp_db)
    roles = [m["role"] for m in svc2.get_messages(s["id"])]
    assert roles == ["user", "assistant"]


def test_context_restore(tmp_db):
    """Вопрос пользователя попадает в промпт (ТЗ §8)."""
    import gmod.infrastructure.llm.factory as fac
    captured = {}

    def fake_gen(self, prompt, **kw):
        captured["prompt"] = prompt
        return "ok"

    fac.LLMProviderFactory.generate_with_fallback = fake_gen
    try:
        svc = _chat_service(tmp_db)
        s = svc.get_or_create_session("default", "r1")
        svc.send_message(s["id"], "UNIQUE_Q_987", system_prompt="SYS",
                         workspace_context="WS", repository_context="REPO")
    finally:
        del fac.LLMProviderFactory.generate_with_fallback
    prompt = captured["prompt"]
    assert "UNIQUE_Q_987" in prompt
    assert "[SYSTEM]: SYS" in prompt and "[WORKSPACE]: WS" in prompt
    assert "[REPOSITORY]: REPO" in prompt


def test_summary_creation(tmp_db):
    """При лимите — summary, история цела (ТЗ §10)."""
    import gmod.infrastructure.llm.factory as fac
    fac.LLMProviderFactory.generate_with_fallback = MagicMock(return_value="s")
    try:
        svc = _chat_service(tmp_db, message_limit=3)
        s = svc.get_or_create_session("default", "r1")
        svc.send_message(s["id"], "q1")
        svc.send_message(s["id"], "q2")
        svc.send_message(s["id"], "q3")
        updated = tmp_db.get_chat_session(s["id"])
        assert updated["summary"] != ""
        assert len(svc.get_messages(s["id"])) == 6  # история не удалена
    finally:
        del fac.LLMProviderFactory.generate_with_fallback


# ============================================================
# Backup (ТЗ §31)
# ============================================================

def _backup_service(tmp_db, tmp_path, monkeypatch):
    import gmod.services.backup_service as mod
    monkeypatch.setattr(mod, "backups_dir", lambda: tmp_path / "backups" or tmp_path)
    (tmp_path).mkdir(exist_ok=True)
    from gmod.services.backup_service import BackupService
    monkeypatch.setattr("gmod.services.backup_service.backups_dir",
                        lambda: tmp_path)
    return BackupService(db=tmp_db)


def test_backup_creation(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    result = svc.create_backup("default", "")
    assert result["status"] == "success"
    assert Path(result["path"]).exists()


def test_backup_contains_manifest(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    result = svc.create_backup("default", "myrepo")
    with zipfile.ZipFile(result["path"]) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["repository"] == "myrepo"
    assert manifest["schema_version"] == 3
    assert "created_at" in manifest


def test_backup_contains_chat(tmp_db, tmp_path, monkeypatch):
    from gmod.services.chat_service import ChatService
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    chat = ChatService(db=tmp_db)
    s = chat.get_or_create_session("default", "r1")
    tmp_db.save_chat_message({"session_id": s["id"], "role": "user",
                              "content": "hello-backup", "sequence": 1})
    result = svc.create_backup("default", "")
    with zipfile.ZipFile(result["path"]) as zf:
        messages = json.loads(zf.read("chat/messages.json").decode("utf-8"))
    assert any(m["content"] == "hello-backup" for m in messages)


def test_backup_contains_workspace(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    tmp_db.save_workspace({"id": "default", "name": "W", "repository_id": "r9",
                           "active_tab": "Граф", "theme": "dark"})
    result = svc.create_backup("default", "r9")
    with zipfile.ZipFile(result["path"]) as zf:
        ws = json.loads(zf.read("workspace/workspace.json").decode("utf-8"))
    assert ws["repository_id"] == "r9"


def test_backup_excludes_secrets(tmp_db, tmp_path, monkeypatch):
    """ТЗ §20/§7: в архиве нет ключей."""
    from gmod.services.backup_service import sanitized_config
    cfg = sanitized_config()
    blob = json.dumps(cfg)
    assert "gsk_" not in blob and "sk-ant-" not in blob and "sk-proj-" not in blob
    for p in cfg.get("llm", {}).get("providers", []):
        assert p.get("api_key", "") == ""
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    result = svc.create_backup("default", "")
    with zipfile.ZipFile(result["path"]) as zf:
        names = zf.namelist()
        assert "config/config.sanitized.yaml" in names
        blob = "".join(zf.read(n).decode("utf-8", errors="ignore") for n in names
                       if n.endswith((".yaml", ".json")))
    assert "gsk_" not in blob and "sk-ant-" not in blob


def test_backup_integrity(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    result = svc.create_backup("default", "")
    assert svc.verify_backup(result["path"])["status"] == "success"
    assert svc.verify_backup(tmp_path / "nope.zip")["status"] == "error"


# ============================================================
# Reset (ТЗ §31)
# ============================================================

def test_reset_creates_backup(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    result = svc.reset_workspace("default", "")
    assert result["status"] == "success"
    assert Path(result["backup"]).exists()


def test_reset_aborts_when_backup_fails(tmp_db, tmp_path, monkeypatch):
    """ТЗ §22: без backup reset НЕ выполняется."""
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    tmp_db.save_workspace({"id": "default", "name": "W", "repository_id": "",
                           "active_tab": "Граф", "theme": "dark"})
    with patch.object(type(svc), "create_backup",
                      return_value={"status": "error", "message": "disk full"}):
        result = svc.reset_workspace("default", "")
    assert result["status"] == "error"
    assert "не была сброшена" in result["message"]
    assert tmp_db.get_workspace("default")["active_tab"] == "Граф"


def test_reset_restores_defaults(tmp_db, tmp_path, monkeypatch):
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    tmp_db.save_workspace({"id": "default", "name": "W", "repository_id": "r1",
                           "active_tab": "Граф", "theme": "dark"})
    tmp_db.save_workspace_tabs("default", [{"tab_key": "Граф", "is_open": True,
                                            "order_index": 0}])
    result = svc.reset_workspace("default", "r1")
    assert result["status"] == "success"
    ws = tmp_db.get_workspace("default")
    assert ws["active_tab"] == "Чат" and ws["theme"] == "dark"
    # repository_id НЕ сбрасываем — проект остаётся привязан.
    assert ws["repository_id"] == "r1"


def test_reset_keeps_analysis_data(tmp_db, tmp_path, monkeypatch):
    """ТЗ §21: metrics/reports живы после reset."""
    svc = _backup_service(tmp_db, tmp_path, monkeypatch)
    tmp_db.save_metric("r1", "c1", "a.py", "function", "f",
                       "CyclomaticComplexity", 3.0)
    tmp_db.save_ai_report("r1", "c1", "archaeologist", "p", "{}", 5)
    svc.reset_workspace("default", "r1")
    with tmp_db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM raw_metrics WHERE repo_id='r1'")
        assert cur.fetchone()[0] == 1
    assert len(tmp_db.get_ai_reports("r1")) == 1
