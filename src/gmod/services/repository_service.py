"""RepositoryService — работа с репозиториями (ТЗ §30 + lifecycle ТЗ §4).

Состояния: NO_REPOSITORY / LOADING / ACTIVE / SWITCHING / ERROR.
Безопасный clone: сначала во временную директорию <target>.gmod-tmp-UUID,
verify -> register -> switch. current_repo_id не меняется до успеха.
"""

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Состояния lifecycle (ТЗ §4.1).
NO_REPOSITORY = "NO_REPOSITORY"
LOADING = "LOADING"
ACTIVE = "ACTIVE"
SWITCHING = "SWITCHING"
ERROR = "ERROR"


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

    # ---------------- lifecycle (ТЗ §4) ----------------

    @staticmethod
    def _is_git_dir(path: Path) -> bool:
        try:
            import git
            git.Repo(str(path))
            return True
        except Exception:
            return False

    @staticmethod
    def _dir_is_empty(path: Path) -> bool:
        try:
            return not any(path.iterdir())
        except Exception:
            return True

    def _remote_of(self, path: Path) -> str:
        try:
            import git
            return git.Repo(str(path)).remotes.origin.url
        except Exception:
            return ""

    def resolve_target(self, url_or_path: str, base_dir=None,
                       current_id: str = "") -> Dict[str, Any]:
        """Решение по цели открытия (ТЗ §4.3-4.4), БЕЗ сайд-эффектов.

        Returns:
            {"action": open_local|already_loaded|same_url_loaded|other_git|
                       nonempty_dir|clone_safe|empty_dir|invalid,
             "path": ..., "url": ..., "message": ...}
        """
        from gmod.config.constants import DATA_DIR
        text = (url_or_path or "").strip()
        if not text:
            return {"action": "invalid", "message": "Пустой путь/URL."}
        base = Path(base_dir) if base_dir else DATA_DIR / "repos"
        candidate = Path(text)

        def _saved_url(repo_id: str) -> str:
            try:
                return self.db.load_workspace_state(f"repo_{repo_id}_url") or ""
            except Exception:
                return ""

        # Локальный путь.
        if candidate.exists():
            if self._is_git_dir(candidate):
                remote = self._remote_of(candidate)
                if current_id and candidate.name == current_id:
                    return {"action": "already_loaded", "path": str(candidate),
                            "message": "Repository уже загружен."}
                if text and remote and text == remote:
                    return {"action": "open_local", "path": str(candidate),
                            "url": remote}
                if remote and remote != text and "://" in text:
                    return {"action": "other_git", "path": str(candidate),
                            "url": remote,
                            "message": "Папка содержит другой Git repository."}
                return {"action": "open_local", "path": str(candidate), "url": remote}
            if self._dir_is_empty(candidate):
                if "://" in text or text.endswith(".git"):
                    return {"action": "empty_dir", "path": str(candidate), "url": text}
                return {"action": "nonempty_dir", "path": str(candidate),
                        "message": "Папка не пуста и не является Git repository."}
            return {"action": "nonempty_dir", "path": str(candidate),
                    "message": "Папка не пуста и не является нужным Git repository."}

        # Похоже на URL → цель клонирования.
        name = text.rstrip("/").split("/")[-1].removesuffix(".git") or "repo"
        target = base / name
        if target.exists():
            # Уже есть в workspace? Не клонируем повторно (ТЗ §4.3).
            if _saved_url(name) in (text, "") or name == current_id:
                return {"action": "same_url_loaded", "path": str(target), "url": text,
                        "message": "Repository уже загружен."}
            if self._is_git_dir(target):
                existing_remote = self._remote_of(target)
                if existing_remote == text:
                    return {"action": "same_url_loaded", "path": str(target),
                            "url": text, "message": "Repository уже загружен."}
                return {"action": "other_git", "path": str(target), "url": existing_remote,
                        "message": "Папка содержит другой Git repository."}
            return {"action": "nonempty_dir", "path": str(target),
                    "message": "Целевая папка существует и не является Git repository."}
        return {"action": "clone_safe", "path": str(target), "url": text}

    def clone_safe(self, url: str, target: Path) -> Dict[str, Any]:
        """Безопасный clone: tmp -> verify -> move (ТЗ §4.5).

        current_repo_id НЕ меняется — это делает UI после успеха.
        """
        import git
        target = Path(target)
        tmp = target.parent / f"{target.name}.gmod-tmp-{uuid.uuid4().hex[:8]}"
        logger.info("clone_safe: %s -> %s (tmp %s)", url, target, tmp.name)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(url, str(tmp))
            # Verify: валидный репозиторий с коммитами.
            check = git.Repo(str(tmp))
            if not list(check.iter_commits(max_count=1)):
                raise RuntimeError("Клонирован пустой репозиторий без коммитов")
            if target.exists():
                raise RuntimeError(f"Целевая папка появилась во время clone: {target}")
            shutil.move(str(tmp), str(target))
            logger.info("clone_safe: готово %s", target)
            return {"status": "success", "path": str(target)}
        except Exception as e:
            logger.error("clone_safe failed: %s", e)
            try:
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass
            return {"status": "error", "message": str(e)}

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
