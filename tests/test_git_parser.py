"""Тесты Git парсера."""

import pytest
import tempfile
from pathlib import Path

from gmod.infrastructure.git.git_parser import GitParser
from gmod.domain.entities import Repository


@pytest.fixture
def temp_repo():
    """Фикстура для временного репозитория."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        yield repo_path


def test_git_parser_initialization():
    """Тест инициализации Git парсера."""
    parser = GitParser(diff_only=False)
    assert parser.diff_only is False
    
    parser_diff = GitParser(diff_only=True)
    assert parser_diff.diff_only is True


def test_git_parser_open_local_repository(temp_repo):
    """Тест открытия локального репозитория."""
    # Создаём простой локальный репозиторий
    temp_repo.mkdir(parents=True, exist_ok=True)
    (temp_repo / "test.txt").write_text("test content")
    
    import subprocess
    subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo, check=True, capture_output=True)
    
    # Открываем репозиторий
    parser = GitParser()
    repository = parser.open_repository(temp_repo)
    
    assert repository is not None
    assert repository.name == temp_repo.name
    assert repository.local_path == str(temp_repo)
    assert repository.default_branch == "master" or repository.default_branch == "main"


def test_git_parser_get_commits(temp_repo):
    """Тест получения коммитов."""
    # Создаём репозиторий с несколькими коммитами
    temp_repo.mkdir(parents=True, exist_ok=True)
    
    import subprocess
    subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_repo, check=True, capture_output=True)
    
    # Первый коммит
    (temp_repo / "file1.txt").write_text("content1")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "First commit"], cwd=temp_repo, check=True, capture_output=True)
    
    # Второй коммит
    (temp_repo / "file2.txt").write_text("content2")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=temp_repo, check=True, capture_output=True)
    
    # Открываем и получаем коммиты
    parser = GitParser()
    repository = parser.open_repository(temp_repo)
    commits = parser.get_commits(repository.id, limit=10, repo_path=str(temp_repo))
    
    assert len(commits) == 2
    assert commits[0].message == "Second commit"
    assert commits[1].message == "First commit"


def test_git_parser_get_branches(temp_repo):
    """Тест получения веток."""
    # Создаём репозиторий с ветками
    temp_repo.mkdir(parents=True, exist_ok=True)
    
    import subprocess
    subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_repo, check=True, capture_output=True)
    
    # Создаём файл и коммит
    (temp_repo / "test.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo, check=True, capture_output=True)
    
    # Создаём новую ветку
    subprocess.run(["git", "branch", "feature"], cwd=temp_repo, check=True, capture_output=True)
    
    # Получаем ветки
    parser = GitParser()
    repository = parser.open_repository(temp_repo)
    branches = parser.get_branches(repository.id, repo_path=str(temp_repo))
    
    assert len(branches) >= 1
    assert "master" in branches or "main" in branches
