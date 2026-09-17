"""Метрики сложности кода."""

import re
import logging
from typing import List

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class CyclomaticComplexity(BaseMetric):
    """Цикломатическая сложность (McCabe)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление цикломатической сложности."""
        content = unit.content
        complexity = 1  # Базовая сложность
        
        # Ключевые слова, увеличивающие сложность
        complexity_keywords = [
            r'\bif\b',
            r'\belif\b',
            r'\belse\b',
            r'\bfor\b',
            r'\bwhile\b',
            r'\btry\b',
            r'\bexcept\b',
            r'\bfinally\b',
            r'\bwith\b',
            r'\band\b',
            r'\bor\b',
            r'\?|:',  # Тернарный оператор
        ]
        
        for keyword in complexity_keywords:
            complexity += len(re.findall(keyword, content))
        
        # Учитываем case и lambda
        complexity += len(re.findall(r'\bcase\b', content))
        complexity += len(re.findall(r'\blambda\b', content))
        
        return float(complexity)


class CognitiveComplexity(BaseMetric):
    """Когнитивная сложность."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление когнитивной сложности."""
        content = unit.content
        complexity = 0
        nesting_level = 0
        
        lines = content.split('\n')
        
        for line in lines:
            stripped = line.strip()
            
            # Увеличиваем вложенность
            if any(keyword in stripped for keyword in ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'with']):
                if 'else' not in stripped or 'if' in stripped:  # else без if не увеличивает
                    nesting_level += 1
                    complexity += nesting_level
            
            # Уменьшаем вложенность
            if stripped in ['else:', 'except', 'finally:']:
                nesting_level -= 1
            
            # Логические операторы
            and_count = stripped.count(' and ')
            or_count = stripped.count(' or ')
            complexity += (and_count + or_count) * (nesting_level + 1)
        
        return float(complexity)


class NPathComplexity(BaseMetric):
    """NPath сложность."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление NPath сложности."""
        content = unit.content
        npath = 1
        
        # Каждое условие увеличивает количество путей
        if_count = len(re.findall(r'\bif\b', content))
        for_count = len(re.findall(r'\bfor\b', content))
        while_count = len(re.findall(r'\bwhile\b', content))
        case_count = len(re.findall(r'\bcase\b', content))
        
        # Каждое условие умножает количество путей на 2
        npath *= (2 ** (if_count + for_count + while_count + case_count))
        
        # Логические операторы увеличивают сложность
        and_count = content.count(' and ')
        or_count = content.count(' or ')
        npath *= (and_count + or_count + 1)
        
        return float(npath)


class HalsteadVolume(BaseMetric):
    """Объём Холстеда."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление объёма Холстеда."""
        content = unit.content
        
        # Операторы
        operators = set(re.findall(r'[+\-*/%=<>!&|^~?:;,.(){}\[\]]', content))
        operators.update(re.findall(r'\b(if|else|elif|for|while|try|except|finally|with|return|break|continue|pass|and|or|not|in|is|lambda|yield|await|async)\b', content))
        
        # Операнды
        operands = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', content))
        operands.update(re.findall(r'\b\d+\b', content))
        operands.update(re.findall(r'["\'][^"\']*["\']', content))
        
        # Общее количество операторов и операндов
        total_operators = len(re.findall(r'[+\-*/%=<>!&|^~?:;,.(){}\[\]]', content))
        total_operators += len(re.findall(r'\b(if|else|elif|for|while|try|except|finally|with|return|break|continue|pass|and|or|not|in|is|lambda|yield|await|async)\b', content))
        
        total_operands = len(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', content))
        total_operands += len(re.findall(r'\b\d+\b', content))
        total_operands += len(re.findall(r'["\'][^"\']*["\']', content))
        
        n1 = len(operators)  # Уникальные операторы
        n2 = len(operands)  # Уникальные операнды
        N1 = total_operators  # Общее количество операторов
        N2 = total_operands  # Общее количество операндов
        
        if n1 == 0 or n2 == 0:
            return 0.0
        
        # Длина программы
        program_length = N1 + N2
        
        # Словарный объём
        vocabulary = n1 + n2
        
        # Объём
        volume = program_length * (self._log2(vocabulary))
        
        return float(volume)
    
    def _log2(self, x: float) -> float:
        """Логарифм по основанию 2."""
        import math
        return math.log2(x) if x > 0 else 0


class HalsteadDifficulty(BaseMetric):
    """Сложность Холстеда."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление сложности Холстеда."""
        content = unit.content
        
        # Операторы
        operators = set(re.findall(r'[+\-*/%=<>!&|^~?:;,.(){}\[\]]', content))
        operators.update(re.findall(r'\b(if|else|elif|for|while|try|except|finally|with|return|break|continue|pass|and|or|not|in|is|lambda|yield|await|async)\b', content))
        
        # Операнды
        operands = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', content))
        
        n1 = len(operators)  # Уникальные операторы
        n2 = len(operands)  # Уникальные операнды
        
        if n1 == 0 or n2 == 0:
            return 0.0
        
        # Сложность
        difficulty = (n1 / 2) * (n2 / n2)  # Упрощённая формула
        
        return float(difficulty)


class HalsteadEffort(BaseMetric):
    """Усилие Холстеда."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление усилия Холстеда."""
        volume_metric = HalsteadVolume()
        difficulty_metric = HalsteadDifficulty()
        
        volume = volume_metric._compute_impl(unit)
        difficulty = difficulty_metric._compute_impl(unit)
        
        # Усилие = объём * сложность
        effort = volume * difficulty
        
        return float(effort)


class HalsteadBugs(BaseMetric):
    """Оценка количества багов по Холстеду."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление оценки количества багов."""
        volume_metric = HalsteadVolume()
        volume = volume_metric._compute_impl(unit)
        
        # Оценка багов = объём / 3000
        bugs = volume / 3000.0
        
        return float(bugs)


class MaintainabilityIndex(BaseMetric):
    """Индекс поддерживаемости."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индекса поддерживаемости."""
        # Используем упрощённую формулу MI
        # MI = 171 - 5.2 * ln(V) - 0.23 * CC - 16.2 * ln(LOC)
        
        volume_metric = HalsteadVolume()
        cc_metric = CyclomaticComplexity()
        
        volume = volume_metric._compute_impl(unit)
        cc = cc_metric._compute_impl(unit)
        loc = len(unit.content.split('\n'))
        
        import math
        
        if volume <= 0 or loc <= 0:
            return 50.0  # Среднее значение
        
        mi = 171 - 5.2 * math.log(volume) - 0.23 * cc - 16.2 * math.log(loc)
        
        # Нормализация в диапазон 0-100
        mi = max(0, min(100, mi))
        
        return float(mi)
