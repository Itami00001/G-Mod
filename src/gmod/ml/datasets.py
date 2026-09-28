"""Датасеты: метрики проекта / SQLite / CSV / JSON (ТЗ §13).

Основной источник GMod — raw_metrics. Признаки (8 по умолчанию):
cyclomatic, cognitive, maintainability(inv), loc, fan_in, fan_out,
churn, comment_density. Метка problematic: сложность/churn/поддерживаемость
за порогами (настраивается).
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Имена метрик в БД — имена классов (см. BaseMetric.get_name).
FEATURES = [
    "CyclomaticComplexity",
    "CognitiveComplexity",
    "MaintainabilityIndex",
    "LinesOfCode",
    "FanIn",
    "FanOut",
    "ChurnMetric",
    "CommentDensity",
]

# MaintainabilityIndex и CommentDensity — «чем больше, тем лучше».
_INVERTED = {"MaintainabilityIndex", "CommentDensity"}


def label_rule(values: Dict[str, float],
               complexity_threshold: float = 10.0,
               churn_threshold: float = 5.0,
               maintainability_threshold: float = 50.0) -> int:
    """Метка problematic (1/0) по порогам."""
    if values.get("CyclomaticComplexity", 0.0) > complexity_threshold:
        return 1
    if values.get("ChurnMetric", 0.0) > churn_threshold:
        return 1
    mi = values.get("MaintainabilityIndex", None)
    if mi is not None and mi < maintainability_threshold:
        return 1
    return 0


def _normalize_matrix(x: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Min-max нормализация + параметры для инференса."""
    lo = x.min(axis=0)
    hi = x.max(axis=0)
    span = np.where(hi - lo < 1e-9, 1.0, hi - lo)
    return (x - lo) / span, {"min": lo.tolist(), "max": hi.tolist()}


def apply_normalization(x: np.ndarray, params: dict) -> np.ndarray:
    """Применение сохранённой нормализации."""
    lo = np.array(params["min"], dtype=float)
    hi = np.array(params["max"], dtype=float)
    span = np.where(hi - lo < 1e-9, 1.0, hi - lo)
    return (np.asarray(x, dtype=float) - lo) / span


def train_validation_split(x: np.ndarray, y: np.ndarray,
                           validation_split: float = 0.2,
                           seed: int = 42):
    """Стратифицированно-приближённый split с перемешиванием."""
    n = len(x)
    if n == 0:
        raise ValueError("Пустой датасет")
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_val = max(1, int(round(n * validation_split))) if n > 1 else 0
    val_idx, train_idx = idx[:n_val], idx[n_val:]
    if len(train_idx) == 0:
        train_idx, val_idx = idx, idx[:0]
    return (x[train_idx], y[train_idx]), (x[val_idx], y[val_idx])


def from_metric_rows(rows: List[Dict[str, Any]],
                     complexity_threshold: float = 10.0,
                     churn_threshold: float = 5.0,
                     maintainability_threshold: float = 50.0):
    """Датасет из строк raw_metrics.

    Returns:
        (X_norm, y, meta) где meta = {units, norm_params, feature_names}.
    """
    from collections import defaultdict
    units: Dict[Tuple[str, str, str], Dict[str, float]] = defaultdict(dict)
    for r in rows:
        key = (str(r.get("file_path", "")), str(r.get("unit_type", "")),
               str(r.get("unit_name", "")))
        try:
            units[key][str(r.get("metric_name", ""))] = float(r.get("value", 0.0))
        except (TypeError, ValueError):
            continue
    X, y, meta_units = [], [], []
    for (fp, utype, uname), values in sorted(units.items()):
        if utype not in ("function", "class", "method"):
            continue
        vec = [float(values.get(f, 0.0)) for f in FEATURES]
        # Инверсия «чем больше, тем лучше» через max-нормализацию позже;
        # здесь сырые значения.
        X.append(vec)
        y.append(label_rule(values, complexity_threshold, churn_threshold,
                            maintainability_threshold))
        meta_units.append({"file": fp, "unit": f"{utype}:{uname}",
                           "values": {f: vec[i] for i, f in enumerate(FEATURES)}})
    if not X:
        raise ValueError("Нет функций/классов с метриками для датасета")
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)
    Xn, norm_params = _normalize_matrix(X)
    logger.info("dataset: units=%d positive=%d", len(y), int(y.sum()))
    return Xn, y, {"units": meta_units, "norm_params": norm_params,
                   "feature_names": list(FEATURES)}


def from_raw_metrics(db, repo_id: str, commit_hash: str = "", **kwargs):
    """Датасет из БД проекта (основной источник, ТЗ §13)."""
    with db.get_connection() as conn:
        cur = conn.cursor()
        if commit_hash:
            cur.execute("""
                SELECT file_path, unit_type, unit_name, metric_name, value
                FROM raw_metrics WHERE repo_id = ? AND commit_hash = ?
            """, (repo_id, commit_hash))
        else:
            cur.execute("""
                SELECT file_path, unit_type, unit_name, metric_name, value
                FROM raw_metrics WHERE repo_id = ?
            """, (repo_id,))
        rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        raise ValueError(f"В raw_metrics нет данных (repo={repo_id})")
    return from_metric_rows(rows, **kwargs)


def from_csv(path: str, label_column: str = "label"):
    """Датасет из CSV: все колонки кроме label — признаки (только stdlib)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or label_column not in rows[0]:
        raise ValueError(f"В CSV нет колонки '{label_column}'")
    feature_names = [c for c in rows[0].keys() if c != label_column]
    X = np.array([[float(r[c]) for c in feature_names] for r in rows])
    y = np.array([int(float(r[label_column])) for r in rows])
    Xn, norm = _normalize_matrix(X)
    return Xn, y, {"units": [], "norm_params": norm, "feature_names": feature_names}


def from_json(path: str):
    """Датасет из JSON: {"features": [[...]], "labels": [...]}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    X = np.array(data["features"], dtype=float)
    y = np.array(data["labels"], dtype=int)
    Xn, norm = _normalize_matrix(X)
    names = data.get("feature_names", [f"f{i}" for i in range(X.shape[1])])
    return Xn, y, {"units": [], "norm_params": norm, "feature_names": names}


def load_dataset(source: str, db=None, repo_id: str = "",
                 path: str = "", label_column: str = "label", **kwargs):
    """Единая точка загрузки (ТЗ §13: метрики/SQLite/CSV/JSON)."""
    source = (source or "metrics").lower()
    if source in ("metrics", "sqlite"):
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        return from_raw_metrics(db, repo_id, **kwargs)
    if source == "csv":
        # pandas не обязателен — from_csv работает на csv-модуле.
        return from_csv(path, label_column)
    if source == "json":
        return from_json(path)
    raise ValueError(f"Неизвестный источник датасета: {source}")
