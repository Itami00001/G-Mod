"""Метрики размера кода."""

import re
import logging

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class LinesOfCode(BaseMetric):
    """Количество строк кода (LOC)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества строк кода."""
        lines = unit.content.split('\n')
        
        # Исключаем пустые строки и комментарии
        code_lines = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                code_lines += 1
        
        return float(code_lines)


class FunctionLength(BaseMetric):
    """Длина функции в строках."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление длины функции."""
        if unit.unit_type != "function":
            return 0.0
        
        lines = unit.content.split('\n')
        return float(len(lines))


class ParameterCount(BaseMetric):
    """Количество параметров функции."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества параметров."""
        if unit.unit_type != "function":
            return 0.0
        
        # Поиск определения функции
        content = unit.content
        first_line = content.split('\n')[0]
        
        # Извлечение параметров из скобок
        match = re.search(r'\((.*?)\)', first_line)
        if match:
            params = match.group(1)
            if params.strip() == "":
                return 0.0
            
            # Подсчёт параметров
            param_list = [p.strip() for p in params.split(',')]
            # Исключаем self и *args, **kwargs
            param_list = [p for p in param_list if p and p not in ['self', 'cls', '*args', '**kwargs']]
            return float(len(param_list))
        
        return 0.0


class ExitPointCount(BaseMetric):
    """Количество точек выхода (return, break, continue)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества точек выхода."""
        content = unit.content
        
        # Подсчёт return, break, continue
        return_count = len(re.findall(r'\breturn\b', content))
        break_count = len(re.findall(r'\bbreak\b', content))
        continue_count = len(re.findall(r'\bcontinue\b', content))
        
        return float(return_count + break_count + continue_count)


class NestingDepth(BaseMetric):
    """Максимальная глубина вложенности."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление максимальной глубины вложенности."""
        lines = unit.content.split('\n')
        max_depth = 0
        current_depth = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Увеличиваем глубину
            if any(keyword in stripped for keyword in ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'with', 'def', 'class']):
                if 'else' not in stripped or 'if' in stripped:
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)
            
            # Уменьшаем глубину
            if stripped in ['else:', 'except', 'finally:']:
                current_depth -= 1
        
        return float(max_depth)
