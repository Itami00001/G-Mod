"""Evaluator: метрики классификации и регрессии (ТЗ §20)."""

import numpy as np

from gmod.ml.schemas import ValidationReport


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """TP/TN/FP/FN."""
    y_true = np.asarray(y_true).reshape(-1).astype(int)
    y_pred = np.asarray(y_pred).reshape(-1).astype(int)
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return {"TP": tp, "TN": tn, "FP": fp, "FN": fn}


def classification_report(y_true: np.ndarray, y_pred: np.ndarray,
                          threshold: float = 0.5) -> ValidationReport:
    """Accuracy/Precision/Recall/F1 + confusion matrix."""
    c = confusion_counts(y_true, y_pred)
    tp, tn, fp, fn = c["TP"], c["TN"], c["FP"], c["FN"]
    n = tp + tn + fp + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return ValidationReport(task="classification",
                            accuracy=round(accuracy, 4),
                            precision=round(precision, 4),
                            recall=round(recall, 4), f1=round(f1, 4),
                            confusion=c, n_samples=n)


def regression_report(y_true: np.ndarray, y_pred: np.ndarray) -> ValidationReport:
    """MAE/MSE/RMSE/R²."""
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)
    n = len(y_true)
    if n == 0:
        return ValidationReport(task="regression", n_samples=0)
    err = y_pred - y_true
    mse = float(np.mean(err ** 2))
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(mse))
    var = float(np.mean((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - (mse / var) if var > 1e-12 else 0.0
    return ValidationReport(task="regression", mae=round(mae, 4),
                            mse=round(mse, 4), rmse=round(rmse, 4),
                            r2=round(r2, 4), n_samples=n)


def evaluate(network, x: np.ndarray, y: np.ndarray,
             threshold: float = 0.5) -> ValidationReport:
    """Валидация сети: классификация (порог) или регрессия."""
    if getattr(network.config, "output_neurons", 1) == 1:
        return classification_report(y, network.predict(x, threshold), threshold)
    return regression_report(y, network.forward(x).reshape(-1))
