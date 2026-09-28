"""RepositoryService — работа с репозиториями (ТЗ §30).

Цепочка: MainWindow -> RepositoryService -> GitParser -> git/Disk.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RepositoryService:
    """Фасад загрузки и инспекции репозиториев."""

    def __init__(self, db=None):
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        self.db = db
        from gmod.infrastructure.git.git_parser import GitParser
        self.parser = GitParser()

    def open_local(self, local_path) -> Dict[str, Any]:
        """Открыть локальный репозиторий и сохранить в workspace."""
        repo = self.parser.open_repository(Path(local_path))
        self.parser.save_repository_info(repo)
        self.db.save_workspace_state("current_repo_id", repo.id)
        logger.info("repository opened: %s", repo.id)
        return {"id": repo.id, "name": repo.name, "local_path": repo.local_path,
                "branch": repo.default_branch, "url": repo.url}

    def clone(self, url: str, base_dir=None) -> Dict[str, Any]:
        """Клонировать по URL (цель — %APPDATA%\\GMod\\repos)."""
        from gmod.config.constants import DATA_DIR
        base = Path(base_dir) if base_dir else DATA_DIR / "repos"
        base.mkdir(parents=True, exist_ok=True)
        name = url.rstrip("/").split("/")[-1].removesuffix(".git") or "repo"
        repo = self.parser.clone_repository(url, base / name)
        self.parser.save_repository_info(repo)
        self.db.save_workspace_state("current_repo_id", repo.id)
        logger.info("repository cloned: %s", repo.id)
        return {"id": repo.id, "name": repo.name, "local_path": repo.local_path,
                "branch": repo.default_branch, "url": repo.url}

    def commits(self, repo_id: str, repo_path: str = "", limit: int = 100) -> list:
        """Коммиты репозитория."""
        return self.parser.get_commits(repo_id, limit=limit, repo_path=repo_path or None)

    def branches(self, repo_id: str, repo_path: str = "") -> List[str]:
        """Ветки репозитория."""
        return self.parser.get_branches(repo_id, repo_path=repo_path or None)

    def metadata(self, repo_id: str) -> Dict[str, Optional[str]]:
        """Метаданные из workspace_state."""
        return {
            "id": repo_id,
            "path": self.db.load_workspace_state(f"repo_{repo_id}_path"),
            "url": self.db.load_workspace_state(f"repo_{repo_id}_url"),
            "branch": self.db.load_workspace_state(f"repo_{repo_id}_branch"),
        }

    def switch_branch(self, repo_path: str, branch: str) -> None:
        """Переключение ветки."""
        import git
        git.Repo(repo_path).git.checkout(branch)
        logger.info("branch switched: %s", branch)
