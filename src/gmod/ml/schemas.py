"""Схемы ML-слоя: конфиги, метрики, отчёты (ТЗ §25)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ModelConfig:
    """Архитектура модели (ТЗ §14-15)."""

    input_features: int = 8
    hidden_layers: List[int] = field(default_factory=lambda: [16, 8])
    output_neurons: int = 1
    activation: str = "relu"
    output_activation: str = "sigmoid"
    seed: int = 42

    def layer_sizes(self) -> List[int]:
        """Полный список размеров: [in, *hidden, out]."""
        return [self.input_features] + list(self.hidden_layers) + [self.output_neurons]


@dataclass
class TrainConfig:
    """Параметры обучения (ТЗ §16)."""

    epochs: int = 100
    learning_rate: float = 0.01
    batch_size: int = 32
    target_accuracy: float = 0.9
    validation_split: float = 0.2
    seed: int = 42
    loss: str = "bce"


@dataclass
class EpochRecord:
    """Одна эпоха обучения."""

    epoch: int = 0
    loss: float = 0.0
    accuracy: float = 0.0
    val_loss: float = 0.0
    val_accuracy: float = 0.0


@dataclass
class TrainingResult:
    """Итог обучения."""

    history: List[EpochRecord] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str = ""
    train_accuracy: float = 0.0
    val_accuracy: float = 0.0
    final_loss: float = 0.0


@dataclass
class ValidationReport:
    """Отчёт валидации: классификация или регрессия (ТЗ §20)."""

    task: str = "classification"
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    confusion: Dict[str, int] = field(default_factory=dict)
    mae: float = 0.0
    mse: float = 0.0
    rmse: float = 0.0
    r2: float = 0.0
    n_samples: int = 0


@dataclass
class StoredModel:
    """Сохранённая модель с версией (ТЗ §25)."""

    model_id: str = ""
    workspace_id: str = "default"
    dataset: str = ""
    architecture: Dict[str, Any] = field(default_factory=dict)
    activation: str = "relu"
    epochs: int = 0
    learning_rate: float = 0.0
    target_accuracy: float = 0.0
    seed: int = 42
    training_metrics: Dict[str, Any] = field(default_factory=dict)
    validation_metrics: Dict[str, Any] = field(default_factory=dict)
    weights: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
