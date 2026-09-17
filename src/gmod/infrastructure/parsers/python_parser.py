"""Python парсер на основе tree-sitter."""

import logging
from pathlib import Path
from typing import List
import re

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logging.warning("tree-sitter-python not available, using regex-based parsing")

from gmod.domain.entities import CodeUnit
from gmod.infrastructure.parsers.base import BaseLanguageParser

logger = logging.getLogger(__name__)


class PythonParser(BaseLanguageParser):
    """Парсер Python кода."""
    
    def __init__(self):
        """Инициализация Python парсера."""
        super().__init__("python")
        self.parser = None
        self.language = None
        
        if TREE_SITTER_AVAILABLE:
            try:
                # Попытка загрузить tree-sitter язык
                PY_LANGUAGE = Language(tspython.language())
                self.parser = Parser()
                self.parser.set_language(PY_LANGUAGE)
                self.language = PY_LANGUAGE
                logger.info("Tree-sitter Python parser initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize tree-sitter: {e}, using regex-based parsing")
    
    def parse_file(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг Python файла на единицы кода."""
        units = []
        
        if self.parser and self.language:
            # Используем tree-sitter если доступен
            units = self._parse_with_tree_sitter(file_path, content)
        else:
            # Падбэк на regex-парсинг
            units = self._parse_with_regex(file_path, content)
        
        logger.debug(f"Parsed {len(units)} code units from {file_path}")
        return units
    
    def _parse_with_tree_sitter(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг с помощью tree-sitter."""
        units = []
        
        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node
            
            # Рекурсивный обход дерева
            self._traverse_tree(root_node, file_path, content, units)
            
        except Exception as e:
            logger.error(f"Tree-sitter parsing error: {e}")
            # Падбэк на regex
            return self._parse_with_regex(file_path, content)
        
        return units
    
    def _traverse_tree(self, node, file_path: Path, content: str, units: List[CodeUnit]) -> None:
        """Рекурсивный обход tree-sitter дерева."""
        # Проверяем тип узла
        node_type = node.type
        
        if node_type in ["function_definition", "async_function_definition"]:
            # Извлечение функции
            self._extract_function(node, file_path, content, units)
        elif node_type == "class_definition":
            # Извлечение класса
            self._extract_class(node, file_path, content, units)
        
        # Рекурсивный обход детей
        for child in node.children:
            self._traverse_tree(child, file_path, content, units)
    
    def _extract_function(self, node, file_path: Path, content: str, units: List[CodeUnit]) -> None:
        """Извлечение информации о функции."""
        try:
            # Получение имени функции
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "anonymous"
            
            # Получение границ
            start_line = node.start_point[0] + 1  # tree-sitter использует 0-based индексы
            end_line = node.end_point[0] + 1
            
            # Получение содержимого
            lines = content.split("\n")
            function_content = "\n".join(lines[start_line-1:end_line])
            
            # Создание единицы кода
            unit = CodeUnit(
                unit_type="function",
                name=name,
                file_path=str(file_path),
                start_line=start_line,
                end_line=end_line,
                content=function_content,
                language="python"
            )
            
            units.append(unit)
            
        except Exception as e:
            logger.error(f"Error extracting function: {e}")
    
    def _extract_class(self, node, file_path: Path, content: str, units: List[CodeUnit]) -> None:
        """Извлечение информации о классе."""
        try:
            # Получение имени класса
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "anonymous"
            
            # Получение границ
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            # Получение содержимого
            lines = content.split("\n")
            class_content = "\n".join(lines[start_line-1:end_line])
            
            # Создание единицы кода
            unit = CodeUnit(
                unit_type="class",
                name=name,
                file_path=str(file_path),
                start_line=start_line,
                end_line=end_line,
                content=class_content,
                language="python"
            )
            
            units.append(unit)
            
        except Exception as e:
            logger.error(f"Error extracting class: {e}")
    
    def _parse_with_regex(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг с помощью regex (падбэк)."""
        units = []
        lines = content.split("\n")
        
        # Парсинг функций
        function_pattern = r'^def\s+(\w+)\s*\('
        for i, line in enumerate(lines, 1):
            match = re.match(function_pattern, line.strip())
            if match:
                func_name = match.group(1)
                # Находим конец функции (упрощенно - до следующей функции или класса)
                end_line = self._find_end_function(lines, i)
                function_content = "\n".join(lines[i-1:end_line])
                
                unit = CodeUnit(
                    unit_type="function",
                    name=func_name,
                    file_path=str(file_path),
                    start_line=i,
                    end_line=end_line,
                    content=function_content,
                    language="python"
                )
                units.append(unit)
        
        # Парсинг классов
        class_pattern = r'^class\s+(\w+)\s*:'
        for i, line in enumerate(lines, 1):
            match = re.match(class_pattern, line.strip())
            if match:
                class_name = match.group(1)
                # Находим конец класса (упрощенно - по отступам)
                end_line = self._find_end_class(lines, i)
                class_content = "\n".join(lines[i-1:end_line])
                
                unit = CodeUnit(
                    unit_type="class",
                    name=class_name,
                    file_path=str(file_path),
                    start_line=i,
                    end_line=end_line,
                    content=class_content,
                    language="python"
                )
                units.append(unit)
        
        return units
    
    def _find_end_function(self, lines: List[str], start_line: int) -> int:
        """Поиск конца функции (упрощенно)."""
        for i in range(start_line, len(lines)):
            line = lines[i].strip()
            # Если встречаем новую функцию или класс на том же уровне отступа
            if line.startswith("def ") or line.startswith("class "):
                return i
        return len(lines)
    
    def _find_end_class(self, lines: List[str], start_line: int) -> int:
        """Поиск конца класса (упрощенно)."""
        base_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
        
        for i in range(start_line, len(lines)):
            if i >= len(lines):
                break
            line = lines[i]
            if line.strip() == "":
                continue
            current_indent = len(line) - len(line.lstrip())
            # Если отступ меньше или равен базовому - конец класса
            if current_indent <= base_indent and not line.strip().startswith("#"):
                return i
        return len(lines)
    
    def get_dependencies(self, unit: CodeUnit) -> List[str]:
        """Получение зависимостей единицы кода."""
        dependencies = []
        content = unit.content
        
        # Поиск import statements
        import_patterns = [
            r'import\s+(\w+)',
            r'from\s+(\w+)\s+import',
            r'from\s+\.(\w+)\s+import'
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            dependencies.extend(matches)
        
        # Удаление дубликатов
        dependencies = list(set(dependencies))
        
        return dependencies
