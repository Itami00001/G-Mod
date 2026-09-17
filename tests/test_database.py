"""Тесты базы данных."""

import pytest
import tempfile
from pathlib import Path

from gmod.infrastructure.db.database import Database


@pytest.fixture
def temp_db():
    """Фикстура для временной базы данных."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db = Database(db_path)
    yield db
    # Очистка
    if db_path.exists():
        db_path.unlink()


def test_database_initialization(temp_db):
    """Тест инициализации базы данных."""
    # Проверяем, что таблицы созданы
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем наличие таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert "workspace_state" in tables
        assert "raw_metrics" in tables
        assert "ai_reports" in tables
        assert "settings" in tables
        assert "schema_version" in tables
        assert "migrations" in tables


def test_workspace_state(temp_db):
    """Тест сохранения и загрузки состояния рабочей области."""
    # Сохранение
    temp_db.save_workspace_state("test_key", "test_value")
    
    # Загрузка
    value = temp_db.load_workspace_state("test_key")
    assert value == "test_value"
    
    # Обновление
    temp_db.save_workspace_state("test_key", "new_value")
    value = temp_db.load_workspace_state("test_key")
    assert value == "new_value"


def test_settings(temp_db):
    """Тест сохранения и загрузки настроек."""
    # Сохранение
    temp_db.save_setting("ui", "theme", "dark", "string")
    
    # Загрузка
    value, type_ = temp_db.load_setting("ui", "theme")
    assert value == "dark"
    assert type_ == "string"


def test_metrics(temp_db):
    """Тест сохранения и загрузки метрик."""
    # Сохранение метрики
    temp_db.save_metric(
        repo_id="test-repo",
        commit_hash="abc123",
        file_path="test.py",
        unit_type="function",
        unit_name="test_func",
        metric_name="cyclomatic_complexity",
        value=5.0
    )
    
    # Проверка кэширования
    cached_value = temp_db.get_cached_metric(
        repo_id="test-repo",
        commit_hash="abc123",
        file_path="test.py",
        unit_type="function",
        unit_name="test_func",
        metric_name="cyclomatic_complexity"
    )
    assert cached_value == 5.0


def test_ai_reports(temp_db):
    """Тест сохранения и загрузки AI-отчётов."""
    # Сохранение отчёта
    report_id = temp_db.save_ai_report(
        repo_id="test-repo",
        commit_hash="abc123",
        agent_type="archaeologist",
        prompt="Test prompt",
        response_json='{"risk": 5}',
        risk_score=5
    )
    
    assert report_id > 0
    
    # Загрузка отчётов
    reports = temp_db.get_ai_reports("test-repo")
    assert len(reports) == 1
    assert reports[0]["agent_type"] == "archaeologist"
    assert reports[0]["risk_score"] == 5
