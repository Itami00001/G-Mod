"""ООП метрики (CBO, RFC, LCOM, WMC, DIT, NOC)."""

import re
import logging
from typing import List, Set

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class CouplingBetweenObjects(BaseMetric):
    """CBO - Coupling Between Objects."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление CBO."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Количество классов, от которых зависит данный класс
        # Импорты других классов
        imports = re.findall(r'from\s+(\w+)\s+import', content)
        
        # Наследование
        inheritance = re.findall(r'class\s+\w+\s*\(([^)]+)\)', content)
        
        # Использование типов из других классов
        type_annotations = re.findall(r':\s*(\w+)', content)
        
        # Убираем встроенные типы
        builtin_types = {'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'None', 'Any', 'Optional'}
        external_types = [t for t in type_annotations if t not in builtin_types]
        
        total_coupling = len(set(imports + inheritance + external_types))
        
        return float(total_coupling)


class ResponseForClass(BaseMetric):
    """RFC - Response For Class."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление RFC."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Количество методов класса
        methods = re.findall(r'def\s+(\w+)', content)
        
        # Количество вызываемых методов
        method_calls = re.findall(r'self\.(\w+)\s*\(', content)
        
        rfc = len(set(methods + method_calls))
        
        return float(rfc)


class LackOfCohesionOfMethods(BaseMetric):
    """LCOM - Lack of Cohesion of Methods."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление LCOM."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Извлекаем методы
        method_pattern = r'def\s+(\w+)\s*\([^)]*\):'
        methods = re.findall(method_pattern, content)
        
        if len(methods) < 2:
            return 0.0
        
        # Извлекаем атрибуты, используемые в каждом методе
        method_attributes = {}
        method_blocks = re.split(r'def\s+\w+\s*\([^)]*\):', content)
        
        for i, method_name in enumerate(methods):
            if i + 1 < len(method_blocks):
                method_content = method_blocks[i + 1]
                # Поиск использования self.attribute
                attributes = set(re.findall(r'self\.(\w+)', method_content))
                method_attributes[method_name] = attributes
        
        # Вычисляем LCOM
        # LCOM = |P| - |Q|, где P - пары методов без общих атрибутов, Q - пары с общими атрибутами
        method_names = list(method_attributes.keys())
        p = 0  # пары без общих атрибутов
        q = 0  # пары с общими атрибутами
        
        for i in range(len(method_names)):
            for j in range(i + 1, len(method_names)):
                attrs_i = method_attributes[method_names[i]]
                attrs_j = method_attributes[method_names[j]]
                
                if attrs_i.intersection(attrs_j):
                    q += 1
                else:
                    p += 1
        
        lcom = max(0, p - q)
        
        return float(lcom)


class WeightedMethodsPerClass(BaseMetric):
    """WMC - Weighted Methods Per Class."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление WMC."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Извлекаем методы
        method_pattern = r'def\s+(\w+)\s*\([^)]*\):'
        methods = re.findall(method_pattern, content)
        
        # Для каждого метода вычисляем цикломатическую сложность
        total_complexity = 0
        method_blocks = re.split(r'def\s+\w+\s*\([^)]*\):', content)
        
        for i, method_name in enumerate(methods):
            if i + 1 < len(method_blocks):
                method_content = method_blocks[i + 1]
                # Упрощённая сложность: количество условий
                complexity = 1
                complexity += method_content.count('if')
                complexity += method_content.count('elif')
                complexity += method_content.count('for')
                complexity += method_content.count('while')
                complexity += method_content.count('except')
                total_complexity += complexity
        
        return float(total_complexity)


class DepthOfInheritanceTree(BaseMetric):
    """DIT - Depth of Inheritance Tree."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление DIT."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Проверяем наследование
        inheritance_match = re.search(r'class\s+\w+\s*\(([^)]+)\)', content)
        if not inheritance_match:
            return 0.0  # Базовый класс
        
        # В реальном анализе здесь нужно рекурсивно вычислять глубину
        # Упрощённая версия: считаем уровни наследования в текущем определении
        parents = inheritance_match.group(1)
        inheritance_levels = parents.count(',')
        
        return float(inheritance_levels + 1)


class NumberOfChildren(BaseMetric):
    """NOC - Number of Children."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление NOC."""
        # Это требует анализа всего проекта
        # Упрощённая версия: возвращаем 0 для отдельной единицы кода
        return 0.0


class ClassSize(BaseMetric):
    """Размер класса (количество методов и атрибутов)."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление размера класса."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Количество методов
        methods = len(re.findall(r'def\s+(\w+)', content))
        
        # Количество атрибутов
        attributes = len(re.findall(r'self\.(\w+)\s*=', content))
        
        return float(methods + attributes)


class PublicMethodCount(BaseMetric):
    """Количество публичных методов."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества публичных методов."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Публичные методы (не начинающиеся с _)
        public_methods = re.findall(r'def\s+([a-zA-Z]\w+)\s*\(', content)
        
        return float(len(public_methods))


class PrivateMethodCount(BaseMetric):
    """Количество приватных методов."""
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества приватных методов."""
        if unit.unit_type != "class":
            return 0.0
        
        content = unit.content
        
        # Приватные методы (начинающиеся с _)
        private_methods = re.findall(r'def\s+(_\w+)\s*\(', content)
        
        return float(len(private_methods))
