"""Метрики комментариев."""

import re
import logging

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class CommentDensity(BaseMetric):
    """Плотность комментариев."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление плотности комментариев."""
        content = unit.content
        lines = content.split('\n')
        
        comment_lines = 0
        code_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            if stripped.startswith('#'):
                comment_lines += 1
            else:
                code_lines += 1
        
        if code_lines == 0:
            return 0.0
        
        density = (comment_lines / code_lines) * 100
        
        return float(density)


class CommentToCodeRatio(BaseMetric):
    """Соотношение комментариев к коду."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление соотношения комментариев к коду."""
        content = unit.content
        
        # Подсчёт символов в комментариях
        comment_chars = 0
        code_chars = 0
        
        lines = content.split('\n')
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            # Проверка на многострочные комментарии
            if '"""' in line or "'''" in line:
                if not in_multiline_comment:
                    in_multiline_comment = True
                else:
                    in_multiline_comment = False
                    comment_chars += len(line)
                    continue
            
            if in_multiline_comment:
                comment_chars += len(line)
                continue
            
            if stripped.startswith('#'):
                comment_chars += len(line)
            else:
                code_chars += len(line)
        
        if code_chars == 0:
            return 0.0
        
        ratio = comment_chars / code_chars
        
        return float(ratio)


class DocumentationCoverage(BaseMetric):
    """Покрытие документацией."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление покрытия документацией."""
        if unit.unit_type not in ["function", "class"]:
            return 0.0
        
        content = unit.content
        
        # Проверяем наличие docstring
        has_docstring = ('"""' in content or "'''" in content)
        
        # Для функций также проверяем комментарии перед определением
        lines = content.split('\n')
        first_line = lines[0].strip()
        
        has_comment = False
        if first_line.startswith('#'):
            has_comment = True
        
        # Возвращаем 1.0 если есть документация, 0.0 если нет
        return float(1.0 if (has_docstring or has_comment) else 0.0)


class CommentedOutCode(BaseMetric):
    """Количество закомментированного кода."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества закомментированного кода."""
        content = unit.content
        lines = content.split('\n')
        
        commented_code_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                # Проверяем, похож ли это на код
                code_indicators = ['=', '(', ')', '[', ']', '{', '}', ':', '.', '+', '-', '*', '/']
                if any(indicator in stripped for indicator in code_indicators):
                    commented_code_lines += 1
        
        return float(commented_code_lines)
