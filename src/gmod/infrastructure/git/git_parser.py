"""Git парсер на основе gitpython."""

import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import git
from git import Repo, GitCommandError

from gmod.domain.entities import Repository, Commit, FileDiff
from gmod.domain.interfaces import IGitParser
from gmod.infrastructure.db.database import get_database

logger = logging.getLogger(__name__)


class GitParser(IGitParser):
    """Реализация парсера Git на gitpython."""
    
    def __init__(self, diff_only: bool = False):
        """Инициализация парсера.
        
        Args:
            diff_only: Если True, анализирует только diff, иначе файл целиком
        """
        self.diff_only = diff_only
        self.db = get_database()
    
    def clone_repository(self, url: str, local_path: Path) -> Repository:
        """Клонирование репозитория по URL."""
        try:
            logger.info(f"Cloning repository from {url} to {local_path}")
            
            # Создание директории если не существует
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Клонирование
            repo = Repo.clone_from(url, local_path)
            
            # Получение информации о репозитории
            repo_name = local_path.name
            default_branch = repo.active_branch.name
            
            # Создание сущности Repository
            repository = Repository(
                id=repo_name,
                url=url,
                local_path=str(local_path),
                name=repo_name,
                default_branch=default_branch
            )
            
            logger.info(f"Repository cloned successfully: {repo_name}")
            return repository
            
        except GitCommandError as e:
            logger.error(f"Git clone error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during cloning: {e}")
            raise
    
    def open_repository(self, local_path: Path) -> Repository:
        """Открытие локального репозитория."""
        try:
            logger.info(f"Opening repository at {local_path}")
            
            # Открытие репозитория
            repo = Repo(local_path)
            
            # Получение информации
            repo_name = local_path.name
            default_branch = repo.active_branch.name
            
            # Попытка получить URL (если это клон)
            try:
                url = repo.remotes.origin.url
            except Exception:
                url = str(local_path)
            
            # Создание сущности Repository
            repository = Repository(
                id=repo_name,
                url=url,
                local_path=str(local_path),
                name=repo_name,
                default_branch=default_branch
            )
            
            logger.info(f"Repository opened successfully: {repo_name}")
            return repository
            
        except GitCommandError as e:
            logger.error(f"Git open error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during opening: {e}")
            raise
    
    def get_commits(self, repo_id: str, limit: int = 100, repo_path: str = None) -> List[Commit]:
        """Получение списка коммитов."""
        try:
            # Сначала пробуем получить путь из БД
            if not repo_path:
                repo_path = self._get_repo_path(repo_id)
            
            if not repo_path:
                raise ValueError(f"Repository {repo_id} not found in database and no path provided")
            
            repo = Repo(repo_path)
            commits = []
            
            # Получение коммитов
            for commit in repo.iter_commits(max_count=limit):
                commit_entity = Commit(
                    hash=commit.hexsha,
                    message=commit.message.strip(),
                    author=commit.author.name,
                    date=datetime.fromtimestamp(commit.committed_date),
                    repo_id=repo_id
                )
                commits.append(commit_entity)
            
            logger.info(f"Retrieved {len(commits)} commits for {repo_id}")
            return commits
            
        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            raise
    
    def get_file_diff(self, repo_id: str, commit_hash: str, file_path: str) -> Optional[FileDiff]:
        """Получение diff файла."""
        try:
            # Загрузка пути репозитория из БД
            repo_path = self._get_repo_path(repo_id)
            if not repo_path:
                raise ValueError(f"Repository {repo_id} not found in database")
            
            repo = Repo(repo_path)
            commit = repo.commit(commit_hash)
            
            # Получение diff
            if commit.parents:
                # Diff с предыдущим коммитом
                parent = commit.parents[0]
                diffs = parent.diff(commit, paths=file_path, create_patch=True)
            else:
                # Первый коммит (без родителей)
                diffs = commit.diff(git.NULL_TREE, paths=file_path, create_patch=True)
            
            if not diffs:
                return None
            
            diff = diffs[0]
            
            # Определение типа изменения
            is_deleted = diff.deleted_file
            is_added = diff.new_file
            is_modified = not (is_deleted or is_added)
            
            # Получение содержимого
            old_content = None
            new_content = None
            
            if self.diff_only:
                # Анализ только diff
                if diff.a_blob:
                    old_content = diff.a_blob.data_stream.read().decode('utf-8', errors='ignore')
                if diff.b_blob:
                    new_content = diff.b_blob.data_stream.read().decode('utf-8', errors='ignore')
            else:
                # Анализ файла целиком
                if not is_deleted:
                    if diff.b_blob:
                        new_content = diff.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                if not is_added:
                    if diff.a_blob:
                        old_content = diff.a_blob.data_stream.read().decode('utf-8', errors='ignore')
            
            file_diff = FileDiff(
                file_path=file_path,
                old_content=old_content,
                new_content=new_content,
                commit_hash=commit_hash,
                repo_id=repo_id,
                is_added=is_added,
                is_deleted=is_deleted,
                is_modified=is_modified
            )
            
            return file_diff
            
        except Exception as e:
            logger.error(f"Error getting file diff: {e}")
            return None
    
    def get_branches(self, repo_id: str, repo_path: str = None) -> List[str]:
        """Получение списка веток."""
        try:
            # Сначала пробуем получить путь из БД
            if not repo_path:
                repo_path = self._get_repo_path(repo_id)
            
            if not repo_path:
                raise ValueError(f"Repository {repo_id} not found in database and no path provided")
            
            repo = Repo(repo_path)
            branches = [head.name for head in repo.heads]
            
            logger.info(f"Retrieved {len(branches)} branches for {repo_id}")
            return branches
            
        except Exception as e:
            logger.error(f"Error getting branches: {e}")
            raise
    
    def _get_repo_path(self, repo_id: str) -> Optional[str]:
        """Получение пути репозитория из БД по ID."""
        try:
            # Сохранение информации о репозитории при клонировании/открытии
            # В реальной реализации здесь будет запрос к БД
            # Пока возвращаем None для совместимости с существующим кодом
            return None
        except Exception as e:
            logger.error(f"Error getting repo path: {e}")
            return None
    
    def save_repository_info(self, repository: Repository) -> None:
        """Сохранение информации о репозитории в БД."""
        try:
            self.db.save_workspace_state(f"repo_{repository.id}_path", repository.local_path)
            self.db.save_workspace_state(f"repo_{repository.id}_url", repository.url)
            self.db.save_workspace_state(f"repo_{repository.id}_branch", repository.default_branch)
            logger.info(f"Repository info saved: {repository.id}")
        except Exception as e:
            logger.error(f"Error saving repository info: {e}")
