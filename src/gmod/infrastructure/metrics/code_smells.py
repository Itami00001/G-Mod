"""Метрики code smells."""

import re
import logging

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class LongMethod(BaseMetric):
    """Обнаружение длинных методов."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора длинного метода."""
        if unit.unit_type != "function":
            return 0.0
        
        # Порог - 50 строк
        lines = unit.content.split('\n')
        length = len(lines)
        
        # Возвращаем 1.0 если метод длинный, 0.0 если нет
        return float(1.0 if length > 50 else 0.0)


class LongParameterList(BaseMetric):
    """Обнаружение длинных списков параметров."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора длинного списка параметров."""
        if unit.unit_type != "function":
            return 0.0
        
        # Порог - 7 параметров
        first_line = unit.content.split('\n')[0]
        match = re.search(r'\((.*?)\)', first_line)
        
        if match:
            params = match.group(1)
            if params.strip():
                param_list = [p.strip() for p in params.split(',')]
                param_list = [p for p in param_list if p and p not in ['self', 'cls', '*args', '**kwargs']]
                return float(1.0 if len(param_list) > 7 else 0.0)
        
        return 0.0


class LargeClass(BaseMetric):
    """Обнаружение больших классов."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора большого класса."""
        if unit.unit_type != "class":
            return 0.0
        
        # Порог - 300 строк или 20 методов
        lines = unit.content.split('\n')
        line_count = len(lines)
        method_count = len(re.findall(r'def\s+\w+', unit.content))
        
        is_large = line_count > 300 or method_count > 20
        
        return float(1.0 if is_large else 0.0)


class DuplicatedCode(BaseMetric):
    """Обнаружение дублированного кода."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора дублированного кода."""
        # Упрощённая версия: проверяем повторяющиеся строки
        lines = unit.content.split('\n')
        line_counts = {}
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                line_counts[stripped] = line_counts.get(stripped, 0) + 1
        
        # Количество повторяющихся строк
        duplicated_lines = sum(1 for count in line_counts.values() if count > 1)
        
        # Возвращаем процент дублированных строк
        total_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        
        if total_lines == 0:
            return 0.0
        
        duplication_ratio = (duplicated_lines / total_lines) * 100
        
        return float(duplication_ratio)


class FeatureEnvy(BaseMetric):
    """Обнаружение Feature Envy."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора Feature Envy."""
        if unit.unit_type != "function":
            return 0.0
        
        content = unit.content
        
        # Подсчитываем обращения к другим объектам
        other_object_calls = len(re.findall(r'(\w+)\.\w+\s*\(', content))
        self_calls = len(re.findall(r'self\.\w+\s*\(', content))
        
        if self_calls == 0:
            return 0.0
        
        # Если обращений к другим объектам больше, чем к self
        envy_ratio = other_object_calls / self_calls
        
        # Порог - 2.0
        return float(1.0 if envy_ratio > 2.0 else 0.0)


class DataClumps(BaseMetric):
    """Обнаружение Data Clumps."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора Data Clumps."""
        content = unit.content
        
        # Ищем часто встречающиеся группы параметров
        # Упрощённая версия: ищем повторяющиеся пары параметров
        
        # Извлекаем все параметры из функций
        param_patterns = re.findall(r'def\s+\w+\s*\(([^)]*)\)', content)
        
        param_pairs = []
        for params in param_patterns:
            param_list = [p.strip() for p in params.split(',') if p.strip()]
            # Создаём пары соседних параметров
            for i in range(len(param_list) - 1):
                pair = (param_list[i], param_list[i + 1])
                param_pairs.append(pair)
        
        # Подсчитываем повторяющиеся пары
        pair_counts = {}
        for pair in param_pairs:
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        
        # Количество повторяющихся пар
        duplicated_pairs = sum(1 for count in pair_counts.values() if count > 1)
        
        return float(duplicated_pairs)


class PrimitiveObsession(BaseMetric):
    """Обнаружение Primitive Obsession."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора Primitive Obsession."""
        content = unit.content
        
        # Подсчитываем использование примитивных типов
        primitive_types = ['int', 'float', 'str', 'bool', 'list', 'dict']
        primitive_usage = 0
        
        for ptype in primitive_types:
            primitive_usage += content.count(f': {ptype}')
            primitive_usage += content.count(f': {ptype.upper()}')
        
        # Общее количество аннотаций типов
        total_annotations = len(re.findall(r':\s*\w+', content))
        
        if total_annotations == 0:
            return 0.0
        
        # Процент примитивных типов
        primitive_ratio = (primitive_usage / total_annotations) * 100
        
        # Порог - 80%
        return float(1.0 if primitive_ratio > 80 else 0.0)


class ShotgunSurgery(BaseMetric):
    """Обнаружение Shotgun Surgery."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора Shotgun Surgery."""
        # Это требует анализа всего проекта
        # Упрощённая версия: возвращаем 0 для отдельной единицы кода
        return 0.0


class GodClass(BaseMetric):
    """Обнаружение God Class."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление индикатора God Class."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Признаки God Class:
        # 1. Много методов (> 20)
        # 2. Много атрибутов (> 10)
        # 3. Высокая связность с другими классами
        # 4. Много ответственности
        
        method_count = len(re.findall(r'def\s+\w+', content))
        attribute_count = len(re.findall(r'self\.(\w+)\s*=', content))
        
        # Проверяем доступ к внешним модулям
        external_access = len(re.findall(r'(\w+)\.\w+', content))
        
        # Проверяем разнообразие ответственности
        responsibility_keywords = ['database', 'file', 'network', 'ui', 'config', 'log', 'cache']
        responsibility_count = sum(1 for keyword in responsibility_keywords if keyword in content.lower())
        
        # God Class если выполняется несколько условий
        conditions = [
            method_count > 20,
            attribute_count > 10,
            external_access > 15,
            responsibility_count > 2
        ]
        
        is_god_class = sum(conditions) >= 2
        
        return float(1.0 if is_god_class else 0.0)
