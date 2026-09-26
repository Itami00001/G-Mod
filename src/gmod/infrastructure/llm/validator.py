"""Нейросеть-валидатор «с нуля» (без sklearn/torch — только stdlib).

Идея для диплома/методички:
- Маленький логистический классификатор (1 нейрон + sigmoid), обученный
  градиентным спуском на фидбеке пользователя.
- Вход: вектор признаков коммита/файла [risk_llm/10, сложность, churn, ...].
- Выход: вероятность того, что оценка LLM верна (1 = согласен).
- Пользователь управляет числом эпох и learning rate, видит точность
  (accuracy) на своих оценках 👍/👎 и динамику по эпохам.

Оптимизации:
- Чистый Python без тяжёлых зависимостей (работает везде, быстрый старт).
- Веса персистятся в %APPDATA%/GMod/validator.json — переживают перезапуск.
- Нормализация признаков min-max по обучающей выборке.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


@dataclass
class ValidatorRun:
    epochs: int
    lr: float
    accuracy: float
    n_samples: int
    loss_history: List[float] = field(default_factory=list)


class ZeroValidator:
    """Логистическая нейросеть с нуля: y = sigmoid(w·x + b)."""

    FEATURES = ["risk_norm", "complexity", "churn", "size", "coupling"]

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path
        self.weights: List[float] = [0.0] * len(self.FEATURES)
        self.bias: float = 0.0
        self.feature_min: List[float] = [0.0] * len(self.FEATURES)
        self.feature_max: List[float] = [1.0] * len(self.FEATURES)
        self.runs: List[ValidatorRun] = []
        if model_path and model_path.exists():
            self.load()

    # ---------------- признаки ----------------

    @classmethod
    def features_from_metrics(cls, risk_score: int, metrics: Dict[str, float]) -> List[float]:
        """Собрать вектор признаков из risk_score LLM + средних метрик.

        metrics: {"complexity": ..., "churn": ..., "size": ..., "coupling": ...}
        """
        def g(k: str) -> float:
            try:
                return float(metrics.get(k, 0.0))
            except (TypeError, ValueError):
                return 0.0

        return [
            max(0.0, min(1.0, risk_score / 10.0)),
            g("complexity"),
            g("churn"),
            g("size"),
            g("coupling"),
        ]

    def _normalize(self, X: List[List[float]]) -> List[List[float]]:
        if not X:
            return X
        n = len(self.FEATURES)
        self.feature_min = [min(row[i] for row in X) for i in range(n)]
        self.feature_max = [max(row[i] for row in X) for i in range(n)]
        out = []
        for row in X:
            norm = []
            for i in range(n):
                lo, hi = self.feature_min[i], self.feature_max[i]
                if hi - lo < 1e-9:
                    norm.append(0.0)
                else:
                    norm.append((row[i] - lo) / (hi - lo))
            out.append(norm)
        return out

    def _apply_norm(self, x: List[float]) -> List[float]:
        out = []
        for i in range(len(self.FEATURES)):
            lo, hi = self.feature_min[i], self.feature_max[i]
            if hi - lo < 1e-9:
                out.append(0.0)
            else:
                out.append((x[i] - lo) / (hi - lo))
        return out

    # ---------------- обучение ----------------

    def train(self, X: List[List[float]], y: List[int],
              epochs: int = 50, lr: float = 0.1) -> ValidatorRun:
        """Обучение градиентным спуском. Пользователь задаёт epochs.

        Returns:
            ValidatorRun с accuracy и loss_history для графика.
        """
        if not X or not y or len(X) != len(y):
            raise ValueError("Нужны непустые X и y одинаковой длины")
        epochs = max(1, min(int(epochs), 10000))
        lr = max(1e-4, min(float(lr), 5.0))
        logger.info("ZeroValidator: обучение на %d примерах, эпох=%d, lr=%s",
                    len(X), epochs, lr)

        Xn = self._normalize([list(r) for r in X])
        n = len(self.FEATURES)
        self.weights = [0.0] * n
        self.bias = 0.0
        loss_history: List[float] = []

        for epoch in range(epochs):
            total_loss = 0.0
            for xi, yi in zip(Xn, y):
                z = sum(w * v for w, v in zip(self.weights, xi)) + self.bias
                p = _sigmoid(z)
                eps = 1e-12
                total_loss += -(yi * math.log(p + eps) + (1 - yi) * math.log(1 - p + eps))
                err = p - yi
                for i in range(n):
                    self.weights[i] -= lr * err * xi[i]
                self.bias -= lr * err
            avg_loss = total_loss / len(Xn)
            # историю прореживаем, чтобы график не раздувался
            if epoch % max(1, epochs // 100) == 0 or epoch == epochs - 1:
                loss_history.append(round(avg_loss, 6))

        acc = self.accuracy(X, y)
        run = ValidatorRun(epochs=epochs, lr=lr, accuracy=acc,
                           n_samples=len(X), loss_history=loss_history)
        self.runs.append(run)
        logger.info("ZeroValidator: обучение завершено, accuracy=%.3f", acc)
        self.save()
        return run

    # ---------------- инференс ----------------

    def predict_proba(self, x: List[float]) -> float:
        xn = self._apply_norm(list(x))
        z = sum(w * v for w, v in zip(self.weights, xn)) + self.bias
        return _sigmoid(z)

    def predict(self, x: List[float], threshold: float = 0.5) -> int:
        return 1 if self.predict_proba(x) >= threshold else 0

    def accuracy(self, X: List[List[float]], y: List[int]) -> float:
        if not X:
            return 0.0
        ok = sum(1 for xi, yi in zip(X, y) if self.predict(xi) == yi)
        return ok / len(X)

    def verdict(self, risk_score: int, metrics: Dict[str, float]) -> Tuple[str, float]:
        """Человекочитаемый вердикт для UI: подтверждает ли валидатор оценку LLM."""
        x = self.features_from_metrics(risk_score, metrics)
        p = self.predict_proba(x)
        if not self.runs:
            return "Валидатор не обучен — соберите фидбек (👍/👎) и нажмите «Обучить»", p
        if p >= 0.7:
            return f"LLM-оценке можно доверять (уверенность валидатора {p:.0%})", p
        if p >= 0.4:
            return f"Спорный случай — проверьте вручную (уверенность {p:.0%})", p
        return f"LLM-оценка под вопросом (уверенность {p:.0%})", p

    # ---------------- персистентность ----------------

    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "bias": self.bias,
            "feature_min": self.feature_min,
            "feature_max": self.feature_max,
            "runs": [
                {"epochs": r.epochs, "lr": r.lr, "accuracy": r.accuracy,
                 "n_samples": r.n_samples, "loss_history": r.loss_history}
                for r in self.runs[-20:]
            ],
        }

    def save(self) -> None:
        if not self.model_path:
            return
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug("ZeroValidator: веса сохранены в %s", self.model_path)
        except Exception as e:
            logger.error("ZeroValidator: не удалось сохранить веса: %s", e)

    def load(self) -> None:
        try:
            assert self.model_path is not None
            with open(self.model_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.weights = list(data.get("weights", self.weights))
            self.bias = float(data.get("bias", 0.0))
            self.feature_min = list(data.get("feature_min", self.feature_min))
            self.feature_max = list(data.get("feature_max", self.feature_max))
            self.runs = [ValidatorRun(
                epochs=r.get("epochs", 0), lr=r.get("lr", 0.1),
                accuracy=r.get("accuracy", 0.0), n_samples=r.get("n_samples", 0),
                loss_history=list(r.get("loss_history", [])),
            ) for r in data.get("runs", [])]
            logger.info("ZeroValidator: загружены веса (%d прошлых запусков)", len(self.runs))
        except Exception as e:
            logger.error("ZeroValidator: не удалось загрузить веса: %s", e)


def default_model_path() -> Path:
    from gmod.config.constants import DATA_DIR
    return DATA_DIR / "validator.json"
