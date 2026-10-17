"""Vue Single-File-Component парсер.

`.vue` — это контейнер: <template> / <script> / <style>. Для метрик
интересен только блок <script> (логика). Извлекаем все <script> и
разбираем их тем же JS-парсером, что и обычные .js/.ts файлы.
Номера строк сдвигаем на позицию скрипта в исходном файле.
"""

import logging
import re
from pathlib import Path
from typing import List

from gmod.domain.entities import CodeUnit
from gmod.infrastructure.parsers.base import BaseLanguageParser
from gmod.infrastructure.parsers.javascript_parser import JavaScriptParser

logger = logging.getLogger(__name__)

_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script\s*>",
                        re.DOTALL | re.IGNORECASE)
_TS_LANG_RE = re.compile(r'\blang\s*=\s*["\']ts', re.IGNORECASE)


class VueParser(BaseLanguageParser):
    """Парсер Vue SFC: делегирует <script> обычному JS/TS-парсеру."""

    def __init__(self, language: str = "vue"):
        super().__init__(language)

    def parse_file(self, file_path: Path, content: str) -> List[CodeUnit]:
        units: List[CodeUnit] = []
        js = JavaScriptParser()
        for match in _SCRIPT_RE.finditer(content):
            script = match.group(1)
            if not script.strip():
                continue
            # Первая строка тела скрипта в координатах исходного файла.
            base_line = content.count("\n", 0, match.start(1))
            for unit in js.parse_file(file_path, script):
                unit.start_line += base_line
                unit.end_line += base_line
                unit.file_path = str(file_path)
                unit.language = self._language
                units.append(unit)
        logger.debug("Parsed %d code units from Vue SFC %s", len(units), file_path)
        return units

    def get_dependencies(self, unit: CodeUnit) -> List[str]:
        return JavaScriptParser().get_dependencies(unit)


def _supports_extensions() -> dict:
    """Расширения Vue-семейства."""
    return {".vue": "vue"}
