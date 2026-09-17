"""Тест цепочки коммит → AI-отчёт (шаг 9 prompt2).

Проверяет полную цепочку:
  1. Подготовка метрик для коммита в БД
  2. Запуск RunArchaeologistUseCase
  3. Генерация промпта
  4. LLM-ответ (через мок)
  5. Парсинг JSON-ответа в ArchaeologistResponse
  6. Сохранение AI-отчёта в БД
"""

import json
import tempfile
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gmod.domain.entities import Repository, Commit
from gmod.domain.schemas import ArchaeologistResponse
from gmod.infrastructure.db.database import Database


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path):
    """Временная БД для изоляции тестов."""
    db = Database(tmp_path / "test.db")
    return db


@pytest.fixture
def sample_repo():
    return Repository(
        id="test-repo-arch",
        url="https://github.com/example/repo",
        local_path="/tmp/test-repo",
        name="test-repo",
        default_branch="main",
    )


@pytest.fixture
def sample_commit():
    return Commit(
        hash="deadbeef1234567890ab",
        message="Refactor utils: extract helper functions",
        author="Alice Developer",
        date=datetime(2025, 1, 15, 10, 30, 0),
        repo_id="test-repo-arch",
    )


MOCK_LLM_RESPONSE = json.dumps({
    "risk_score": 6,
    "reason": "Extracted functions increase call overhead and may affect hot paths.",
    "recommendation": "Profile the refactored code under load before merging.",
    "affected_units": ["utils.py::process_data", "utils.py::validate_input"],
    "confidence": 0.85,
    "performance_impact": "среднее",
    "complexity_change": "decreased",
    "suggested_actions": [
        "Run benchmarks on process_data",
        "Check call frequency of validate_input"
    ],
})


# ---------------------------------------------------------------------------
# Тест 1: парсинг JSON-ответа LLM → ArchaeologistResponse
# ---------------------------------------------------------------------------

def test_parse_archaeologist_response():
    """Ответ LLM корректно парсится в ArchaeologistResponse."""
    data = json.loads(MOCK_LLM_RESPONSE)
    response = ArchaeologistResponse(**data)

    assert response.risk_score == 6
    assert response.confidence == pytest.approx(0.85)
    assert response.performance_impact == "среднее"
    assert len(response.affected_units) == 2
    assert len(response.suggested_actions) == 2


# ---------------------------------------------------------------------------
# Тест 2: сохранение и чтение AI-отчёта в БД
# ---------------------------------------------------------------------------

def test_ai_report_saved_to_db(temp_db, sample_repo, sample_commit):
    """После анализа отчёт сохраняется в БД и читается обратно."""
    report_id = temp_db.save_ai_report(
        repo_id=sample_repo.id,
        commit_hash=sample_commit.hash,
        agent_type="archaeologist",
        prompt="[SYSTEM]: You are Archaeologist...\n[USER]: Analyse commit deadbeef...",
        response_json=MOCK_LLM_RESPONSE,
        risk_score=6,
    )

    assert report_id > 0

    reports = temp_db.get_ai_reports(sample_repo.id)
    assert len(reports) == 1

    report = reports[0]
    assert report["commit_hash"] == sample_commit.hash
    assert report["agent_type"] == "archaeologist"
    assert report["risk_score"] == 6


# ---------------------------------------------------------------------------
# Тест 3: полная цепочка через RunArchaeologistUseCase (с мокингом LLM)
# ---------------------------------------------------------------------------

def test_archaeologist_chain_with_mocked_llm(tmp_path, sample_repo, sample_commit):
    """Полная цепочка: метрики → промпт → LLM-мок → JSON → БД."""
    db = Database(tmp_path / "chain_test.db")

    # Заранее кладём метрики в БД (имитируем Шаг 2 — AnalyzeRepository)
    db.save_metric(
        repo_id=sample_repo.id,
        commit_hash=sample_commit.hash,
        file_path="utils.py",
        unit_type="function",
        unit_name="process_data",
        metric_name="cyclomatic_complexity",
        value=8.0,
    )
    db.save_metric(
        repo_id=sample_repo.id,
        commit_hash=sample_commit.hash,
        file_path="utils.py",
        unit_type="function",
        unit_name="validate_input",
        metric_name="lines_of_code",
        value=45.0,
    )

    # Мокируем RunArchaeologistUseCase: подменяем git_parser, llm и саму БД
    from gmod.usecases.run_archaeologist import RunArchaeologistUseCase
    from gmod.domain.entities import FileDiff

    config = {
        "llm": {"providers": [], "message_limit": 7},
        "analysis": {"depth": "full"},
    }

    usecase = RunArchaeologistUseCase.__new__(RunArchaeologistUseCase)
    usecase.config = config
    usecase.db = db

    # Мок git_parser
    mock_git = MagicMock()
    mock_git.get_commits.return_value = [sample_commit]
    mock_git.get_file_diff.return_value = FileDiff(
        file_path="utils.py",
        old_content="def process_data(x):\n    return x * 2\n",
        new_content="def process_data(x):\n    x = validate_input(x)\n    return x * 2\n",
        commit_hash=sample_commit.hash,
        repo_id=sample_repo.id,
        is_modified=True,
    )
    usecase.git_parser = mock_git

    # Мок analyze_usecase
    mock_analyze = MagicMock()
    mock_analyze.get_analysis_results.return_value = [
        {
            "unit_type": "function",
            "unit_name": "process_data",
            "metric_name": "cyclomatic_complexity",
            "value": 8.0,
            "file_path": "utils.py",
        },
        {
            "unit_type": "function",
            "unit_name": "validate_input",
            "metric_name": "lines_of_code",
            "value": 45.0,
            "file_path": "utils.py",
        },
    ]
    mock_analyze._get_changed_files.return_value = ["utils.py"]
    usecase.analyze_usecase = mock_analyze

    # Мок session_manager — генерирует наш фейковый JSON
    mock_session = MagicMock()
    mock_session.generate_response.return_value = MOCK_LLM_RESPONSE
    usecase.session_manager = mock_session

    # Запуск цепочки
    result = usecase.execute(
        repository=sample_repo,
        commit_hash=sample_commit.hash,
        agent_id="test-archaeologist-session",
    )

    # Проверяем результат
    assert result["status"] == "success", f"Expected success, got: {result}"
    assert result["commit_hash"] == sample_commit.hash
    assert result["agent_id"] == "test-archaeologist-session"
    assert "report_id" in result
    assert result["analysis"]["risk_score"] == 6
    assert result["analysis"]["performance_impact"] == "среднее"

    # Проверяем что отчёт записан в БД
    reports = db.get_ai_reports(sample_repo.id)
    assert len(reports) == 1
    assert reports[0]["risk_score"] == 6


# ---------------------------------------------------------------------------
# Тест 4: fallback при ошибке LLM
# ---------------------------------------------------------------------------

def test_archaeologist_chain_llm_error(tmp_path, sample_repo, sample_commit):
    """При ошибке LLM возвращается корректный error-ответ."""
    db = Database(tmp_path / "error_test.db")
    db.save_metric(
        repo_id=sample_repo.id,
        commit_hash=sample_commit.hash,
        file_path="utils.py",
        unit_type="file",
        unit_name="utils.py",
        metric_name="lines_of_code",
        value=120.0,
    )

    from gmod.usecases.run_archaeologist import RunArchaeologistUseCase
    from gmod.domain.entities import FileDiff

    config = {"llm": {"providers": [], "message_limit": 7}, "analysis": {"depth": "full"}}

    usecase = RunArchaeologistUseCase.__new__(RunArchaeologistUseCase)
    usecase.config = config
    usecase.db = db

    mock_git = MagicMock()
    mock_git.get_commits.return_value = [sample_commit]
    mock_git.get_file_diff.return_value = FileDiff(
        file_path="utils.py",
        old_content="old",
        new_content="new",
        commit_hash=sample_commit.hash,
        repo_id=sample_repo.id,
        is_modified=True,
    )
    usecase.git_parser = mock_git

    mock_analyze = MagicMock()
    mock_analyze.get_analysis_results.return_value = [
        {"unit_type": "file", "unit_name": "utils.py", "metric_name": "lines_of_code", "value": 120.0, "file_path": "utils.py"}
    ]
    mock_analyze._get_changed_files.return_value = ["utils.py"]
    usecase.analyze_usecase = mock_analyze

    # LLM бросает исключение (все провайдеры упали)
    mock_session = MagicMock()
    mock_session.generate_response.side_effect = RuntimeError("All LLM providers failed")
    usecase.session_manager = mock_session

    result = usecase.execute(
        repository=sample_repo,
        commit_hash=sample_commit.hash,
    )

    assert result["status"] == "error"
    assert "LLM generation failed" in result["message"]


# ---------------------------------------------------------------------------
# Тест 5: нет метрик → ранний выход
# ---------------------------------------------------------------------------

def test_archaeologist_no_metrics_returns_error(tmp_path, sample_repo, sample_commit):
    """Если метрик нет, возвращается понятная ошибка без краша."""
    db = Database(tmp_path / "no_metrics.db")

    from gmod.usecases.run_archaeologist import RunArchaeologistUseCase

    config = {"llm": {"providers": [], "message_limit": 7}, "analysis": {"depth": "full"}}

    usecase = RunArchaeologistUseCase.__new__(RunArchaeologistUseCase)
    usecase.config = config
    usecase.db = db

    mock_git = MagicMock()
    mock_git.get_commits.return_value = [sample_commit]
    usecase.git_parser = mock_git

    mock_analyze = MagicMock()
    mock_analyze.get_analysis_results.return_value = []  # нет метрик
    usecase.analyze_usecase = mock_analyze

    mock_session = MagicMock()
    usecase.session_manager = mock_session

    result = usecase.execute(
        repository=sample_repo,
        commit_hash=sample_commit.hash,
    )

    assert result["status"] == "error"
    assert "No metrics" in result["message"]
