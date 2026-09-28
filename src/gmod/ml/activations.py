"""Функции активации и их производные (ТЗ §15).

Обязательные: ReLU, Sigmoid, Tanh, Linear.
Для классификации: Sigmoid, Softmax.
"""

import numpy as np


def relu(x: np.ndarray) -> np.ndarray:
    """ReLU."""
    return np.maximum(0.0, x)


def relu_derivative(x: np.ndarray) -> np.ndarray:
    """Производная ReLU."""
    return (x > 0).astype(float)


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoid (численно устойчивая)."""
    out = np.empty_like(x, dtype=float)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    out[~pos] = exp_x / (1.0 + exp_x)
    return out


def sigmoid_derivative(x: np.ndarray) -> np.ndarray:
    """Производная Sigmoid через значение функции."""
    s = sigmoid(x)
    return s * (1.0 - s)


def tanh(x: np.ndarray) -> np.ndarray:
    """Tanh."""
    return np.tanh(x)


def tanh_derivative(x: np.ndarray) -> np.ndarray:
    """Производная Tanh."""
    return 1.0 - np.tanh(x) ** 2


def linear(x: np.ndarray) -> np.ndarray:
    """Linear (тождественная)."""
    return x


def linear_derivative(x: np.ndarray) -> np.ndarray:
    """Производная Linear."""
    return np.ones_like(x, dtype=float)


def softmax(x: np.ndarray) -> np.ndarray:
    """Softmax по последней оси (численно устойчивый)."""
    shifted = x - np.max(x, axis=-1, keepdims=True)
    exp_x = np.exp(shifted)
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


ACTIVATIONS = {
    "relu": (relu, relu_derivative),
    "sigmoid": (sigmoid, sigmoid_derivative),
    "tanh": (tanh, tanh_derivative),
    "linear": (linear, linear_derivative),
    "softmax": (softmax, None),  # производная — через cross-entropy
}


def get_activation(name: str):
    """Пара (функция, производная) по имени (регистронезависимо)."""
    key = (name or "").strip().lower()
    if key not in ACTIVATIONS:
        raise ValueError(f"Unknown activation: {name}. Доступны: {sorted(ACTIVATIONS)}")
    return ACTIVATIONS[key]
