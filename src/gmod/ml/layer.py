"""Полносвязный слой: forward + backward (собственный код, ТЗ §10)."""

import numpy as np

from gmod.ml.activations import get_activation


class DenseLayer:
    """Слой y = act(X @ W + b)."""

    def __init__(self, input_dim: int, output_dim: int,
                 activation: str = "relu", rng=None):
        if input_dim < 1 or output_dim < 1:
            raise ValueError("Размеры слоя должны быть >= 1")
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.activation_name = (activation or "relu").lower()
        self.activation, self.activation_derivative = get_activation(activation)
        rng = rng or np.random.default_rng()
        # He-инициализация для ReLU, Xavier для остальных.
        scale = np.sqrt(2.0 / input_dim) if self.activation_name == "relu" else np.sqrt(
            1.0 / input_dim)
        self.weights = rng.normal(0.0, scale, size=(input_dim, output_dim))
        self.bias = np.zeros(output_dim)
        # Кэш forward для backward.
        self._last_input = None
        self._last_z = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Прямой проход."""
        self._last_input = x
        self._last_z = x @ self.weights + self.bias
        return self.activation(self._last_z)

    def backward(self, grad_output: np.ndarray, learning_rate: float,
                 max_grad_norm: float = 5.0) -> np.ndarray:
        """Обратный проход с SGD-обновлением. Возвращает градиент на вход.

        Градиенты клиппируются по глобальной норме — защита от
        расходимости при большом learning rate.
        """
        if self.activation_derivative is not None:
            grad_z = grad_output * self.activation_derivative(self._last_z)
        else:
            # Softmax + cross-entropy: градиент уже готов.
            grad_z = grad_output
        # grad_z уже нормирован на батч в loss (single normalization).
        grad_w = self._last_input.T @ grad_z
        grad_b = np.mean(grad_z, axis=0)
        norm = float(np.sqrt(np.sum(grad_w ** 2) + np.sum(grad_b ** 2)))
        if norm > max_grad_norm:
            scale = max_grad_norm / norm
            grad_w = grad_w * scale
            grad_b = grad_b * scale
        grad_input = grad_z @ self.weights.T
        # SGD-обновление весов (собственный код, ТЗ §10).
        self.weights -= learning_rate * grad_w
        self.bias -= learning_rate * grad_b
        return grad_input

    def get_params(self) -> dict:
        """Веса для сохранения."""
        return {"weights": self.weights.tolist(), "bias": self.bias.tolist(),
                "activation": self.activation_name}

    def set_params(self, params: dict) -> None:
        """Восстановление весов."""
        self.weights = np.array(params["weights"], dtype=float)
        self.bias = np.array(params["bias"], dtype=float)
