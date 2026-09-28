"""MLP с нуля: forward, loss, backprop, обновление весов (ТЗ §10)."""

import numpy as np

from gmod.ml.activations import get_activation
from gmod.ml.layer import DenseLayer
from gmod.ml.losses import get_loss
from gmod.ml.schemas import ModelConfig


class NeuralNetwork:
    """Многослойный перцептрон из Dense-слоёв."""

    def __init__(self, config: ModelConfig):
        sizes = config.layer_sizes()
        if len(sizes) < 2:
            raise ValueError("Нужен хотя бы вход и выход")
        get_activation(config.activation)
        get_activation(config.output_activation)
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.layers = []
        for i in range(len(sizes) - 1):
            is_last = i == len(sizes) - 2
            act = config.output_activation if is_last else config.activation
            self.layers.append(DenseLayer(sizes[i], sizes[i + 1],
                                          activation=act, rng=self.rng))
        self.loss_name = "bce" if config.output_neurons == 1 else "mse"
        self.loss_fn, self.loss_derivative = get_loss(self.loss_name)

    # ---------------- инференс ----------------

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Прямой проход (ТЗ §10: forward propagation)."""
        out = np.asarray(x, dtype=float)
        for layer in self.layers:
            out = layer.forward(out)
        return out

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Вероятности (0..1)."""
        out = self.forward(x)
        return np.clip(out.reshape(-1), 0.0, 1.0)

    def predict(self, x: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Классы с порогом (порог меняет результат, ТЗ §21)."""
        return (self.predict_proba(x) >= threshold).astype(int)

    # ---------------- обучение ----------------

    def train_step(self, x_batch: np.ndarray, y_batch: np.ndarray,
                   learning_rate: float) -> float:
        """Один SGD-шаг: forward + loss + backward + update. Возвращает loss."""
        y_pred = self.forward(x_batch)
        loss = self.loss_fn(y_pred, y_batch)
        grad = self.loss_derivative(y_pred, y_batch)
        for layer in reversed(self.layers):
            grad = layer.backward(grad, learning_rate)
        return float(loss)

    def compute_loss(self, x: np.ndarray, y: np.ndarray) -> float:
        """Loss без обновления весов."""
        return float(self.loss_fn(self.forward(x), y))

    def accuracy(self, x: np.ndarray, y: np.ndarray,
                 threshold: float = 0.5) -> float:
        """Доля верных классов."""
        if len(x) == 0:
            return 0.0
        pred = self.predict(x, threshold)
        return float(np.mean(pred == np.asarray(y).reshape(-1)))

    # ---------------- персистентность ----------------

    def get_weights(self) -> dict:
        """Все веса сети."""
        return {f"layer_{i}": layer.get_params()
                for i, layer in enumerate(self.layers)}

    def set_weights(self, weights: dict) -> None:
        """Восстановление весов (количество слоёв должно совпадать)."""
        for i, layer in enumerate(self.layers):
            key = f"layer_{i}"
            if key not in weights:
                raise ValueError(f"Нет весов для {key}")
            layer.set_params(weights[key])

    def describe(self) -> dict:
        """Конфигурация для AI-объяснения (ТЗ §23)."""
        return {
            "input_features": self.config.input_features,
            "hidden_layers": list(self.config.hidden_layers),
            "output_neurons": self.config.output_neurons,
            "activation": self.config.activation,
            "output_activation": self.config.output_activation,
            "loss": self.loss_name,
            "seed": self.config.seed,
        }
