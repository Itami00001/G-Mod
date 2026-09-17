"""Базовый интерфейс парсера языков."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from gmod.domain.entities import CodeUnit
from gmod.domain.interfaces import ILanguageParser


class BaseLanguageParser(ILanguageParser, ABC):
    """Базовый класс парсера языков."""
    
    def __init__(self, language: str):
        """Инициализация парсера.
        
        Args:
            language: Название языка (python, javascript, etc.)
        """
        self._language = language
    
    @abstractmethod
    def parse_file(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг файла на единицы кода."""
        pass
    
    @abstractmethod
    def get_dependencies(self, unit: CodeUnit) -> List[str]:
        """Получение зависимостей единицы кода."""
        pass
    
    def get_language(self) -> str:
        """Получение языка парсера."""
        return self._language
