"""JavaScript/TypeScript парсер на регулярных выражениях.

Покрывает: function declarations, стрелочные функции, методы классов,
классы (включая export/export default). Границы блоков — по балансу
фигурных скобок. Качество — уровень regex-fallback Python-парсера:
быстро и достаточно для метрик.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from gmod.domain.entities import CodeUnit
from gmod.infrastructure.parsers.base import BaseLanguageParser

logger = logging.getLogger(__name__)


class JavaScriptParser(BaseLanguageParser):
    """Парсер JavaScript/TypeScript кода."""

    def __init__(self, language: str = "javascript"):
        """Инициализация JS парсера."""
        super().__init__(language)

    def parse_file(self, file_path: Path, content: str) -> List[CodeUnit]:
        """Парсинг JS/TS файла на единицы кода."""
        units: List[CodeUnit] = []
        lines = content.split("\n")

        # Классы: class Name ... {
        class_pattern = re.compile(r"^\s*(?:export\s+default\s+|export\s+)?class\s+(\w+)")
        # Функции: function name( / export [default] [async] function name(
        func_pattern = re.compile(
            r"^\s*(?:export\s+default\s+|export\s+)?(?:async\s+)?function\s*(\w*)\s*\(")
        # Стрелочные: const/let/var name = (....) => / = async (...) =>
        arrow_pattern = re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
        # Методы объекта: name(...) {  (осторожно: только с { в конце)
        method_pattern = re.compile(r"^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{\s*$")

        taken_ranges: List[tuple] = []  # занятые class-диапазоны (не дублировать методы)

        for i, line in enumerate(lines, 1):
            lineno = i
            match = class_pattern.match(line)
            if match:
                name = match.group(1)
                end_line = self._find_block_end(lines, lineno)
                taken_ranges.append((lineno, end_line))
                units.append(CodeUnit(
                    unit_type="class", name=name, file_path=str(file_path),
                    start_line=lineno, end_line=end_line,
                    content="\n".join(lines[lineno - 1:end_line]),
                    language=self._language))
                continue
            match = func_pattern.match(line)
            if match and "function" in line:
                name = match.group(1) or "anonymous"
                end_line = self._find_block_end(lines, lineno)
                units.append(CodeUnit(
                    unit_type="function", name=name, file_path=str(file_path),
                    start_line=lineno, end_line=end_line,
                    content="\n".join(lines[lineno - 1:end_line]),
                    language=self._language))
                continue
            match = arrow_pattern.match(line)
            if match:
                name = match.group(1)
                end_line = self._find_block_end(lines, lineno)
                units.append(CodeUnit(
                    unit_type="function", name=name, file_path=str(file_path),
                    start_line=lineno, end_line=end_line,
                    content="\n".join(lines[lineno - 1:end_line]),
                    language=self._language))
                continue

        # Методы верхнего уровня вида name() { вне классов (объектные литералы).
        for i, line in enumerate(lines, 1):
            match = method_pattern.match(line)
            if not match:
                continue
            name = match.group(1)
            if name in ("if", "for", "while", "switch", "catch", "function"):
                continue
            if any(start <= i <= end for start, end in taken_ranges):
                # Внутри класса — класс уже покрывает.
                continue
            end_line = self._find_block_end(lines, i)
            # Только нетривиальные блоки.
            if end_line - i < 1:
                continue
            units.append(CodeUnit(
                unit_type="function", name=name, file_path=str(file_path),
                start_line=i, end_line=end_line,
                content="\n".join(lines[i - 1:end_line]),
                language=self._language))

        logger.debug(f"Parsed {len(units)} code units from {file_path}")
        return units

    def _find_block_end(self, lines: List[str], start_line: int) -> int:
        """Конец блока по балансу {} начиная со строки определения."""
        depth = 0
        seen_open = False
        total = len(lines)
        for i in range(start_line - 1, total):
            stripped = self._strip_strings(lines[i])
            # Убираем однострочные комментарии для подсчёта скобок.
            code = stripped.split("//")[0]
            for ch in code:
                if ch == "{":
                    depth += 1
                    seen_open = True
                elif ch == "}":
                    depth -= 1
            if seen_open and depth <= 0:
                return i + 1
            # Защита: однострочное определение без блока.
            if i - (start_line - 1) > 2000:
                return i + 1
        return total

    @staticmethod
    def _strip_strings(line: str) -> str:
        """Грубо вырезать строковые литералы, чтобы скобки в них не считать."""
        result = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
        result = re.sub(r'"(?:[^"\\]|\\.)*"', '""', result)
        result = re.sub(r"`(?:[^`\\]|\\.)*`", "``", result)
        return result

    def get_dependencies(self, unit: CodeUnit) -> List[str]:
        """Зависимости: import ... from, import 'x', require('x')."""
        content = unit.content
        dependencies = []
        dependencies.extend(re.findall(r"from\s+['\"]([^'\"]+)['\"]", content))
        dependencies.extend(re.findall(r"import\s+['\"]([^'\"]+)['\"]", content))
        dependencies.extend(re.findall(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content))
        # Убираем дубликаты, сохраняя порядок.
        seen = set()
        unique = []
        for dep in dependencies:
            if dep not in seen:
                seen.add(dep)
                unique.append(dep)
        return unique


def _supports_extensions() -> dict:
    """Расширения JS-семейства."""
    return {".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
            ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript"}
