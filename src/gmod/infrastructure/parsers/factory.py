"""Фабрика парсеров языков."""

import logging
from pathlib import Path
from typing import Dict, Type, Optional

from gmod.domain.entities import CodeUnit
from gmod.domain.interfaces import ILanguageParser
from gmod.infrastructure.parsers.base import BaseLanguageParser
from gmod.infrastructure.parsers.python_parser import PythonParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """Фабрика для создания парсеров языков."""
    
    _parsers: Dict[str, Type[BaseLanguageParser]] = {
        "python": PythonParser,
        # Другие парсеры могут быть добавлены здесь:
        # "javascript": JavaScriptParser,
        # "typescript": TypeScriptParser,
        # "java": JavaParser,
    }
    
    @classmethod
    def register_parser(cls, language: str, parser_class: Type[BaseLanguageParser]) -> None:
        """Регистрация нового парсера.
        
        Args:
            language: Название языка
            parser_class: Класс парсера
        """
        cls._parsers[language] = parser_class
        logger.info(f"Registered parser for language: {language}")
    
    @classmethod
    def get_parser(cls, language: str) -> Optional[ILanguageParser]:
        """Получение парсера для языка.
        
        Args:
            language: Название языка
            
        Returns:
            Экземпляр парсера или None если язык не поддерживается
        """
        parser_class = cls._parsers.get(language.lower())
        if parser_class:
            return parser_class()
        else:
            logger.warning(f"No parser available for language: {language}")
            return None
    
    @classmethod
    def get_supported_languages(cls) -> list:
        """Получение списка поддерживаемых языков."""
        return list(cls._parsers.keys())
    
    @classmethod
    def parse_file(cls, file_path: Path, content: str, language: str) -> list:
        """Парсинг файла с автоматическим выбором парсера.
        
        Args:
            file_path: Путь к файлу
            content: Содержимое файла
            language: Язык программирования
            
        Returns:
            Список единиц кода
        """
        parser = cls.get_parser(language)
        if parser:
            return parser.parse_file(file_path, content)
        else:
            logger.warning(f"Cannot parse {file_path}: no parser for {language}")
            return []
    
    @classmethod
    def detect_language(cls, file_path: Path) -> str:
        """Определение языка по расширению файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Название языка или "unknown"
        """
        extension = file_path.suffix.lower()
        
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
        }
        
        return language_map.get(extension, "unknown")
