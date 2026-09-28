"""Predictor: прогноз с управляемым порогом (ТЗ §21)."""

from typing import Any, Dict, List

import numpy as np


class Predictor:
    """Инференс обученной сети."""

    def __init__(self, network, norm_params: dict = None,
                 feature_names: List[str] = None, units: List[dict] = None):
        self.network = network
        self.norm_params = norm_params or {}
        self.feature_names = feature_names or []
        self.units = units or []

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        if not self.norm_params:
            return np.asarray(x, dtype=float)
        from gmod.ml.datasets import apply_normalization
        return apply_normalization(x, self.norm_params)

    def predict_unit(self, values: Dict[str, float],
                     threshold: float = 0.5) -> Dict[str, Any]:
        """Прогноз для одного юнита {metric: value}.

        Returns:
            {probability, problematic, label}.
        """
        names = self.feature_names or list(values.keys())
        vec = np.array([[float(values.get(n, 0.0)) for n in names]])
        proba = float(self.network.predict_proba(self._normalize(vec))[0])
        problematic = proba >= threshold
        return {
            "probability": round(proba, 4),
            "problematic": bool(problematic),
            "label": f"Problematic = {proba:.1%}" if problematic
                     else f"OK = {(1.0 - proba):.1%}",
        }

    def predict_all(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Прогноз по всем юнитам датасета (для выбора объекта, ТЗ §21)."""
        out = []
        for i, unit in enumerate(self.units):
            values = unit.get("values", {})
            r = self.predict_unit(values, threshold)
            r.update({"file": unit.get("file", ""), "unit": unit.get("unit", ""),
                      "index": i})
            out.append(r)
        out.sort(key=lambda r: r["probability"], reverse=True)
        return out
