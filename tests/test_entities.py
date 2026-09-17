"""Тесты доменных сущностей."""

import pytest
from datetime import datetime

from gmod.domain.entities import Repository, Commit, FileDiff, CodeUnit, MetricResult, AIReport


def test_repository_creation():
    """Тест создания сущности Repository."""
    repo = Repository(
        id="test-repo",
        url="https://github.com/test/repo",
        local_path="/tmp/test",
        name="test-repo"
    )
    assert repo.id == "test-repo"
    assert repo.url == "https://github.com/test/repo"
    assert repo.default_branch == "main"
    assert repo.created_at is not None


def test_commit_creation():
    """Тест создания сущности Commit."""
    commit = Commit(
        hash="abc123",
        message="Test commit",
        author="Test Author",
        date=datetime.now(),
        repo_id="test-repo"
    )
    assert commit.hash == "abc123"
    assert commit.message == "Test commit"
    assert commit.repo_id == "test-repo"


def test_code_unit_creation():
    """Тест создания сущности CodeUnit."""
    unit = CodeUnit(
        unit_type="function",
        name="test_function",
        file_path="test.py",
        start_line=1,
        end_line=10,
        content="def test_function(): pass",
        language="python"
    )
    assert unit.unit_type == "function"
    assert unit.name == "test_function"
    assert unit.dependencies == []


def test_metric_result_creation():
    """Тест создания сущности MetricResult."""
    result = MetricResult(
        metric_name="cyclomatic_complexity",
        value=5.0,
        unit_type="function",
        unit_name="test_function",
        file_path="test.py"
    )
    assert result.metric_name == "cyclomatic_complexity"
    assert result.value == 5.0
    assert result.timestamp is not None


def test_ai_report_creation():
    """Тест создания сущности AIReport."""
    report = AIReport(
        id=1,
        repo_id="test-repo",
        commit_hash="abc123",
        agent_type="archaeologist",
        prompt="Test prompt",
        response_json='{"risk": 5}',
        risk_score=5
    )
    assert report.id == 1
    assert report.agent_type == "archaeologist"
    assert report.risk_score == 5
