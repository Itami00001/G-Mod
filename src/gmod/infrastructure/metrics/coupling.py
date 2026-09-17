"""Метрики связности и сцепления."""

import re
import logging
from typing import List, Set

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class FanIn(BaseMetric):
    """Fan-in: количество модулей, которые зависят от данного."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление fan-in."""
        # Это требует анализа всего проекта, упрощённая версия
        # Подсчитываем количество вызовов других функций
        content = unit.content
        
        # Поиск вызовов функций
        function_calls = re.findall(r'(\w+)\s*\(', content)
        
        # Исключаем встроенные функции и ключевые слова
        builtins = {'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'range', 'enumerate', 'zip', 'map', 'filter'}
        external_calls = [call for call in function_calls if call not in builtins]
        
        return float(len(set(external_calls)))


class FanOut(BaseMetric):
    """Fan-out: количество модулей, от которых зависит данный."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление fan-out."""
        # Подсчитываем импорты и вызовы внешних модулей
        content = unit.content
        
        # Импорты
        imports = re.findall(r'import\s+(\w+)', content)
        from_imports = re.findall(r'from\s+(\w+)\s+import', content)
        
        # Вызовы внешних модулей
        module_calls = re.findall(r'(\w+)\.\w+\s*\(', content)
        
        total_external = len(set(imports + from_imports + module_calls))
        
        return float(total_external)


class Coupling(BaseMetric):
    """Общая связность (coupling)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление общей связности."""
        fan_in_metric = FanIn()
        fan_out_metric = FanOut()
        
        fan_in = fan_in_metric._compute_impl(unit)
        fan_out = fan_out_metric._compute_impl(unit)
        
        # Связность = fan-in + fan-out
        coupling = fan_in + fan_out
        
        return float(coupling)


class Cohesion(BaseMetric):
    """Сцепление (cohesion) - насколько элементы модуля связаны между собой."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление сцепления."""
        # Упрощённая версия: на основе общих переменных
        content = unit.content
        
        # Извлечение имён переменных
        variables = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=', content))
        
        # Извлечение имён функций/методов
        functions = set(re.findall(r'def\s+(\w+)', content))
        
        # Извлечение имён классов
        classes = set(re.findall(r'class\s+(\w+)', content))
        
        # Сцепление основано на использовании общих элементов
        total_elements = len(variables) + len(functions) + len(classes)
        
        if total_elements == 0:
            return 0.0
        
        # Чем больше общих элементов, тем выше сцепление
        # Нормализуем относительно размера кода
        loc = len(content.split('\n'))
        cohesion = (total_elements / loc) * 100 if loc > 0 else 0.0
        
        return float(min(100.0, cohesion))


class AfferentCoupling(BaseMetric):
    """Afferent Coupling (Ca) - количество классов, зависящих от данного."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление afferent coupling."""
        # Это требует анализа всего проекта
        # Упрощённая версия: количество импортов данного модуля в других файлах
        # Возвращаем 0 для отдельной единицы кода
        return 0.0


class EfferentCoupling(BaseMetric):
    """Efferent Coupling (Ce) - количество классов, от которых зависит данный."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление efferent coupling."""
        # Количество импортированных модулей
        content = unit.content
        
        imports = re.findall(r'import\s+(\w+)', content)
        from_imports = re.findall(r'from\s+(\w+)\s+import', content)
        
        total_imports = len(set(imports + from_imports))
        
        return float(total_imports)


class Instability(BaseMetric):
    """Нестабильность = Ce / (Ca + Ce)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление нестабильности."""
        ca_metric = AfferentCoupling()
        ce_metric = EfferentCoupling()
        
        ca = ca_metric._compute_impl(unit)
        ce = ce_metric._compute_impl(unit)
        
        if ca + ce == 0:
            return 0.0
        
        instability = ce / (ca + ce)
        
        return float(instability)


class Abstractness(BaseMetric):
    """Абстрактность = количество абстрактных классов / общее количество классов."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление абстрактности."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Проверяем, является ли класс абстрактным
        is_abstract = 'ABC' in content or 'abstractmethod' in content or 'pass' in content
        
        # В контексте одного класса это либо 0 либо 1
        return float(1.0 if is_abstract else 0.0)


class DistanceFromMainSequence(BaseMetric):
    """Расстояние от главной последовательности D = |A + I - 1|."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление расстояния от главной последовательности."""
        abstractness_metric = Abstractness()
        instability_metric = Instability()
        
        a = abstractness_metric._compute_impl(unit)
        i = instability_metric._compute_impl(unit)
        
        distance = abs(a + i - 1)
        
        return float(distance)
