"""Тесты метрик."""

import pytest
from pathlib import Path

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.infrastructure.metrics.factory import MetricFactory
from gmod.infrastructure.metrics.complexity import CyclomaticComplexity, MaintainabilityIndex
from gmod.infrastructure.metrics.size import LinesOfCode, FunctionLength


@pytest.fixture
def sample_function_unit():
    """Фикстура для примера функции."""
    return CodeUnit(
        unit_type="function",
        name="test_function",
        file_path="test.py",
        start_line=1,
        end_line=10,
        content="""
def test_function(arg1, arg2):
    if arg1 > 0:
        if arg2 > 0:
            return arg1 + arg2
        else:
            return arg1 - arg2
    else:
        return 0
""",
        language="python"
    )


@pytest.fixture
def sample_class_unit():
    """Фикстура для примера класса."""
    return CodeUnit(
        unit_type="class",
        name="TestClass",
        file_path="test.py",
        start_line=1,
        end_line=20,
        content="""
class TestClass:
    def __init__(self):
        self.value = 0
    
    def method1(self):
        return self.value
    
    def method2(self, arg):
        if arg > 0:
            return arg
        return 0
""",
        language="python"
    )


def test_cyclomatic_complexity(sample_function_unit):
    """Тест цикломатической сложности."""
    metric = CyclomaticComplexity()
    result = metric.compute(sample_function_unit)
    
    assert result.metric_name == "CyclomaticComplexity"
    assert result.value > 1  # Должна быть больше базовой сложности
    assert result.unit_name == "test_function"


def test_maintainability_index(sample_function_unit):
    """Тест индекса поддерживаемости."""
    metric = MaintainabilityIndex()
    result = metric.compute(sample_function_unit)
    
    assert result.metric_name == "MaintainabilityIndex"
    assert 0 <= result.value <= 100  # Должен быть в диапазоне 0-100


def test_lines_of_code(sample_function_unit):
    """Тест количества строк кода."""
    metric = LinesOfCode()
    result = metric.compute(sample_function_unit)
    
    assert result.metric_name == "LinesOfCode"
    assert result.value > 0


def test_function_length(sample_function_unit):
    """Тест длины функции."""
    metric = FunctionLength()
    result = metric.compute(sample_function_unit)
    
    assert result.metric_name == "FunctionLength"
    assert result.value > 0


def test_metric_factory_get_metric():
    """Тест получения метрики из фабрики."""
    metric = MetricFactory.get_metric("cyclomatic_complexity")
    assert metric is not None
    assert metric.get_name() == "CyclomaticComplexity"


def test_metric_factory_get_all_metrics():
    """Тест получения всех метрик."""
    metrics = MetricFactory.get_all_metrics()
    assert len(metrics) > 0


def test_metric_factory_get_supported_metrics():
    """Тест получения списка поддерживаемых метрик."""
    supported = MetricFactory.get_supported_metrics()
    assert len(supported) > 0
    assert "cyclomatic_complexity" in supported
    assert "maintainability_index" in supported


def test_metric_factory_compute_metric(sample_function_unit):
    """Тест вычисления метрики через фабрику."""
    result = MetricFactory.compute_metric("cyclomatic_complexity", sample_function_unit)
    
    assert result is not None
    assert result.metric_name == "CyclomaticComplexity"
    assert result.value > 0


def test_metric_factory_compute_all_metrics(sample_function_unit):
    """Тест вычисления всех метрик через фабрику."""
    results = MetricFactory.compute_all_metrics(sample_function_unit)
    
    assert len(results) > 0
    from gmod.domain.entities import MetricResult
    assert all(isinstance(r, MetricResult) for r in results)


def test_metric_factory_compute_metrics_by_category(sample_function_unit):
    """Тест вычисления метрик по категории."""
    results = MetricFactory.compute_metrics_by_category("complexity", sample_function_unit)
    
    assert len(results) > 0
    assert all("complexity" in r.metric_name.lower() or "halstead" in r.metric_name.lower() or "maintainability" in r.metric_name.lower() for r in results)


def test_class_metrics(sample_class_unit):
    """Тест метрик для класса."""
    # OOP метрики
    from gmod.infrastructure.metrics.oop import WeightedMethodsPerClass
    
    wmc_metric = WeightedMethodsPerClass()
    result = wmc_metric.compute(sample_class_unit)
    
    assert result.metric_name == "WeightedMethodsPerClass"
    assert result.value > 0


def test_comment_metrics():
    """Тест метрик комментариев."""
    from gmod.infrastructure.metrics.comments import CommentDensity
    
    unit = CodeUnit(
        unit_type="function",
        name="commented_function",
        file_path="test.py",
        start_line=1,
        end_line=10,
        content="""
def commented_function():
    # This is a comment
    result = 0
    # Another comment
    return result
""",
        language="python"
    )
    
    metric = CommentDensity()
    result = metric.compute(unit)
    
    assert result.metric_name == "CommentDensity"
    assert result.value >= 0
