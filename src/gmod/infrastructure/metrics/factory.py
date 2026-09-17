"""Фабрика метрик."""

import logging
from typing import Dict, Type, List, Optional

from gmod.domain.entities import CodeUnit, MetricResult
from gmod.domain.interfaces import IMetric
from gmod.infrastructure.metrics.base import BaseMetric

# Импорты всех метрик
from gmod.infrastructure.metrics.complexity import (
    CyclomaticComplexity, CognitiveComplexity, NPathComplexity,
    HalsteadVolume, HalsteadDifficulty, HalsteadEffort, HalsteadBugs,
    MaintainabilityIndex
)
from gmod.infrastructure.metrics.size import (
    LinesOfCode, FunctionLength, ParameterCount, ExitPointCount, NestingDepth
)
from gmod.infrastructure.metrics.coupling import (
    FanIn, FanOut, Coupling, Cohesion,
    AfferentCoupling, EfferentCoupling, Instability, Abstractness, DistanceFromMainSequence
)
from gmod.infrastructure.metrics.oop import (
    CouplingBetweenObjects, ResponseForClass, LackOfCohesionOfMethods,
    WeightedMethodsPerClass, DepthOfInheritanceTree, NumberOfChildren,
    ClassSize, PublicMethodCount, PrivateMethodCount
)
from gmod.infrastructure.metrics.comments import (
    CommentDensity, CommentToCodeRatio, DocumentationCoverage, CommentedOutCode
)
from gmod.infrastructure.metrics.code_smells import (
    LongMethod, LongParameterList, LargeClass, DuplicatedCode,
    FeatureEnvy, DataClumps, PrimitiveObsession, ShotgunSurgery, GodClass
)
from gmod.infrastructure.metrics.vcs import (
    ChurnMetric, ChangeFrequency, RecentChanges, AuthorsCount,
    CommitMessageQuality, BugFixFrequency
)

logger = logging.getLogger(__name__)


class MetricFactory:
    """Фабрика для создания метрик."""
    
    _metrics: Dict[str, Type[BaseMetric]] = {
        # Сложность
        "cyclomatic_complexity": CyclomaticComplexity,
        "cognitive_complexity": CognitiveComplexity,
        "npath_complexity": NPathComplexity,
        "halstead_volume": HalsteadVolume,
        "halstead_difficulty": HalsteadDifficulty,
        "halstead_effort": HalsteadEffort,
        "halstead_bugs": HalsteadBugs,
        "maintainability_index": MaintainabilityIndex,
        
        # Размер
        "lines_of_code": LinesOfCode,
        "function_length": FunctionLength,
        "parameter_count": ParameterCount,
        "exit_point_count": ExitPointCount,
        "nesting_depth": NestingDepth,
        
        # Связность
        "fan_in": FanIn,
        "fan_out": FanOut,
        "coupling": Coupling,
        "cohesion": Cohesion,
        "afferent_coupling": AfferentCoupling,
        "efferent_coupling": EfferentCoupling,
        "instability": Instability,
        "abstractness": Abstractness,
        "distance_from_main_sequence": DistanceFromMainSequence,
        
        # ООП
        "coupling_between_objects": CouplingBetweenObjects,
        "response_for_class": ResponseForClass,
        "lack_of_cohesion_of_methods": LackOfCohesionOfMethods,
        "weighted_methods_per_class": WeightedMethodsPerClass,
        "depth_of_inheritance_tree": DepthOfInheritanceTree,
        "number_of_children": NumberOfChildren,
        "class_size": ClassSize,
        "public_method_count": PublicMethodCount,
        "private_method_count": PrivateMethodCount,
        
        # Комментарии
        "comment_density": CommentDensity,
        "comment_to_code_ratio": CommentToCodeRatio,
        "documentation_coverage": DocumentationCoverage,
        "commented_out_code": CommentedOutCode,
        
        # Code smells
        "long_method": LongMethod,
        "long_parameter_list": LongParameterList,
        "large_class": LargeClass,
        "duplicated_code": DuplicatedCode,
        "feature_envy": FeatureEnvy,
        "data_clumps": DataClumps,
        "primitive_obsession": PrimitiveObsession,
        "shotgun_surgery": ShotgunSurgery,
        "god_class": GodClass,
        
        # VCS
        "churn": ChurnMetric,
        "change_frequency": ChangeFrequency,
        "recent_changes": RecentChanges,
        "authors_count": AuthorsCount,
        "commit_message_quality": CommitMessageQuality,
        "bug_fix_frequency": BugFixFrequency,
    }
    
    @classmethod
    def register_metric(cls, name: str, metric_class: Type[BaseMetric]) -> None:
        """Регистрация новой метрики.
        
        Args:
            name: Название метрики
            metric_class: Класс метрики
        """
        cls._metrics[name] = metric_class
        logger.info(f"Registered metric: {name}")
    
    @classmethod
    def get_metric(cls, name: str, **kwargs) -> Optional[IMetric]:
        """Получение метрики по названию.
        
        Args:
            name: Название метрики
            **kwargs: Дополнительные параметры для инициализации метрики
            
        Returns:
            Экземпляр метрики или None если метрика не найдена
        """
        metric_class = cls._metrics.get(name.lower())
        if metric_class:
            try:
                return metric_class(**kwargs)
            except Exception as e:
                logger.error(f"Error creating metric {name}: {e}")
                return None
        else:
            logger.warning(f"Metric not found: {name}")
            return None
    
    @classmethod
    def get_all_metrics(cls, **kwargs) -> List[IMetric]:
        """Получение всех доступных метрик.
        
        Args:
            **kwargs: Дополнительные параметры для инициализации метрик
            
        Returns:
            Список всех метрик
        """
        metrics = []
        for name, metric_class in cls._metrics.items():
            try:
                metric = metric_class(**kwargs)
                metrics.append(metric)
            except Exception as e:
                logger.error(f"Error creating metric {name}: {e}")
        
        return metrics
    
    @classmethod
    def get_supported_metrics(cls) -> List[str]:
        """Получение списка поддерживаемых метрик."""
        return list(cls._metrics.keys())
    
    @classmethod
    def compute_metric(cls, name: str, unit: CodeUnit, **kwargs) -> Optional[MetricResult]:
        """Вычисление одной метрики.
        
        Args:
            name: Название метрики
            unit: Единица кода
            **kwargs: Дополнительные параметры
            
        Returns:
            Результат вычисления метрики или None
        """
        metric = cls.get_metric(name, **kwargs)
        if metric:
            try:
                result = metric.compute(unit)
                return result
            except Exception as e:
                logger.error(f"Error computing metric {name}: {e}")
                return None
        return None
    
    @classmethod
    def compute_all_metrics(cls, unit: CodeUnit, **kwargs) -> List[MetricResult]:
        """Вычисление всех метрик для единицы кода.
        
        Args:
            unit: Единица кода
            **kwargs: Дополнительные параметры
            
        Returns:
            Список результатов вычисления метрик
        """
        results = []
        metrics = cls.get_all_metrics(**kwargs)
        
        for metric in metrics:
            try:
                result = metric.compute(unit)
                results.append(result)
            except Exception as e:
                logger.error(f"Error computing metric {metric.get_name()}: {e}")
        
        return results
    
    @classmethod
    def compute_metrics_by_category(cls, category: str, unit: CodeUnit, **kwargs) -> List[MetricResult]:
        """Вычисление метрик по категории.
        
        Args:
            category: Категория метрик (complexity, size, coupling, oop, comments, code_smells, vcs)
            unit: Единица кода
            **kwargs: Дополнительные параметры
            
        Returns:
            Список результатов вычисления метрик категории
        """
        # Определяем метрики по категории
        category_metrics = {
            "complexity": [
                "cyclomatic_complexity", "cognitive_complexity", "npath_complexity",
                "halstead_volume", "halstead_difficulty", "halstead_effort", "halstead_bugs",
                "maintainability_index"
            ],
            "size": [
                "lines_of_code", "function_length", "parameter_count", 
                "exit_point_count", "nesting_depth"
            ],
            "coupling": [
                "fan_in", "fan_out", "coupling", "cohesion",
                "afferent_coupling", "efferent_coupling", "instability", 
                "abstractness", "distance_from_main_sequence"
            ],
            "oop": [
                "coupling_between_objects", "response_for_class", 
                "lack_of_cohesion_of_methods", "weighted_methods_per_class",
                "depth_of_inheritance_tree", "number_of_children",
                "class_size", "public_method_count", "private_method_count"
            ],
            "comments": [
                "comment_density", "comment_to_code_ratio", 
                "documentation_coverage", "commented_out_code"
            ],
            "code_smells": [
                "long_method", "long_parameter_list", "large_class", 
                "duplicated_code", "feature_envy", "data_clumps",
                "primitive_obsession", "shotgun_surgery", "god_class"
            ],
            "vcs": [
                "churn", "change_frequency", "recent_changes", 
                "authors_count", "commit_message_quality", "bug_fix_frequency"
            ]
        }
        
        metric_names = category_metrics.get(category.lower(), [])
        results = []
        
        for name in metric_names:
            result = cls.compute_metric(name, unit, **kwargs)
            if result:
                results.append(result)
        
        return results
