"""Базовый интерфейс метрик."""

from abc import ABC, abstractmethod
from typing import Optional

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.domain.interfaces import IMetric


class BaseMetric(IMetric, ABC):
    """Базовый класс метрики."""
    
    def __init__(self):
        """Инициализация метрики."""
        self._name = self.__class__.__name__
    
    def compute(self, unit: CodeUnit) -> MetricResult:
        """Вычисление метрики."""
        value = self._safe_compute(unit)
        if value is None:
            value = 0.0
        
        return MetricResult(
            metric_name=self.get_name(),
            value=value,
            unit_type=unit.unit_type,
            unit_name=unit.name,
            file_path=unit.file_path
        )
    
    @abstractmethod
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Реализация вычисления метрики."""
        pass
    
    def get_name(self) -> str:
        """Получение названия метрики."""
        return self._name
    
    def _safe_compute(self, unit: CodeUnit) -> Optional[float]:
        """Безопасное вычисление с обработкой ошибок."""
        try:
            return self._compute_impl(unit)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error computing {self.get_name()}: {e}")
            return None
