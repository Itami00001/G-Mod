"""Интерфейсы домена."""

from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path

from gmod.domain.entities import Repository, Commit, FileDiff, CodeUnit, MetricResult


class IGitParser(ABC):
    """Интерфейс парсера Git."""
    
    @abstractmethod
    def clone_repository(self, url: str, local_path: Path) -> Repository:
        """Клонирование репозитория."""
        pass
    
    @abstractmethod
    def open_repository(self, local_path: Path) -> Repository:
        """Открытие локального репозитория."""
        pass
    
    @abstractmethod
    def get_commits(self, repo_id: str, limit: int = 100) -> List[Commit]:
        """Получение списка коммитов."""
        pass
    
    @abstractmethod
    def get_file_diff(self, repo_id: str, commit_hash: str, file_path: str) -> Optional[FileDiff]:
        """Получение diff файла."""
        pass
    
    @abstractmethod
    def get_branches(self, repo_id: str) -> List[str]:
        """Получение списка веток."""
        pass


class ILanguageParser(ABC):
    """Интерфейс парсера языка."""
    
    @abstractmethod
    def parse_file(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг файла на единицы кода."""
        pass
    
    @abstractmethod
    def get_dependencies(self, unit: CodeUnit) -> List[str]:
        """Получение зависимостей единицы кода."""
        pass


class IMetric(ABC):
    """Интерфейс метрики."""
    
    @abstractmethod
    def compute(self, unit: CodeUnit) -> MetricResult:
        """Вычисление метрики."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Получение названия метрики."""
        pass


class ILLMProvider(ABC):
    """Интерфейс провайдера LLM."""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности."""
        pass
