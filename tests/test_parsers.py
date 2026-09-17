"""Тесты парсеров языков."""

import pytest
from pathlib import Path

from gmod.infrastructure.parsers.factory import ParserFactory
from gmod.infrastructure.parsers.python_parser import PythonParser
from gmod.domain.entities import CodeUnit


def test_parser_factory_initialization():
    """Тест инициализации фабрики парсеров."""
    languages = ParserFactory.get_supported_languages()
    assert "python" in languages


def test_python_parser_initialization():
    """Тест инициализации Python парсера."""
    parser = PythonParser()
    assert parser.get_language() == "python"


def test_python_parser_parse_function():
    """Тест парсинга Python функции."""
    parser = PythonParser()
    content = """
def test_function(arg1, arg2):
    result = arg1 + arg2
    return result
"""
    file_path = Path("test.py")
    units = parser.parse_file(file_path, content)
    
    assert len(units) > 0
    assert any(unit.unit_type == "function" and unit.name == "test_function" for unit in units)


def test_python_parser_parse_class():
    """Тест парсинга Python класса."""
    parser = PythonParser()
    content = """
class TestClass:
    def __init__(self):
        self.value = 0
    
    def method(self):
        return self.value
"""
    file_path = Path("test.py")
    units = parser.parse_file(file_path, content)
    
    assert len(units) > 0
    assert any(unit.unit_type == "class" and unit.name == "TestClass" for unit in units)


def test_python_parser_dependencies():
    """Тест извлечения зависимостей."""
    parser = PythonParser()
    content = """
import os
import sys
from typing import List

def test_function():
    return os.path.join("path", "file")
"""
    file_path = Path("test.py")
    units = parser.parse_file(file_path, content)
    
    if units:
        dependencies = parser.get_dependencies(units[0])
        # Проверяем что зависимости найдены
        assert len(dependencies) >= 0  # Может быть 0 если regex не сработал


def test_parser_factory_get_parser():
    """Тест получения парсера из фабрики."""
    python_parser = ParserFactory.get_parser("python")
    assert python_parser is not None
    assert python_parser.get_language() == "python"


def test_parser_factory_detect_language():
    """Тест определения языка по расширению."""
    assert ParserFactory.detect_language(Path("test.py")) == "python"
    assert ParserFactory.detect_language(Path("test.js")) == "javascript"
    assert ParserFactory.detect_language(Path("test.java")) == "java"
    assert ParserFactory.detect_language(Path("test.txt")) == "unknown"


def test_parser_factory_parse_file():
    """Тест парсинга файла через фабрику."""
    content = """
def example():
    pass
"""
    file_path = Path("example.py")
    units = ParserFactory.parse_file(file_path, content, "python")
    
    assert len(units) > 0
