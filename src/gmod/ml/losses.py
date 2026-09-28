"""Функции потерь и их производные (собственный код, ТЗ §10)."""

import numpy as np


def binary_cross_entropy(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """BCE для классификации."""
    eps = 1e-12
    p = np.clip(y_pred, eps, 1.0 - eps)
    y = y_true.reshape(p.shape)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def binary_cross_entropy_derivative(y_pred: np.ndarray,
                                    y_true: np.ndarray) -> np.ndarray:
    """d(mean BCE)/d(pred): нормировка на текущий батч (один раз)."""
    eps = 1e-12
    p = np.clip(y_pred, eps, 1.0 - eps)
    y = y_true.reshape(p.shape)
    n = max(1, p.shape[0])
    return (-(y / p) + (1.0 - y) / (1.0 - p)) / n


def mean_squared_error(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """MSE для регрессии."""
    y = y_true.reshape(y_pred.shape)
    return float(np.mean((y_pred - y) ** 2))


def mean_squared_error_derivative(y_pred: np.ndarray,
                                  y_true: np.ndarray) -> np.ndarray:
    """d(mean MSE)/d(pred): нормировка на текущий батч (один раз)."""
    y = y_true.reshape(y_pred.shape)
    n = max(1, y_pred.shape[0])
    return 2.0 * (y_pred - y) / n


LOSSES = {
    "bce": (binary_cross_entropy, binary_cross_entropy_derivative),
    "mse": (mean_squared_error, mean_squared_error_derivative),
}


def get_loss(name: str):
    """Пара (функция, производная) по имени."""
    key = (name or "").strip().lower()
    if key not in LOSSES:
        raise ValueError(f"Unknown loss: {name}. Доступны: {sorted(LOSSES)}")
    return LOSSES[key]
