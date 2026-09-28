"""Trainer: эпохи, early stopping, пауза/стоп/продолжить (ТЗ §16-18)."""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np

from gmod.ml.neural_network import NeuralNetwork
from gmod.ml.schemas import EpochRecord, TrainConfig, TrainingResult

logger = logging.getLogger(__name__)


class Trainer:
    """Обучение сети с колбэками и управлением (ТЗ §18)."""

    def __init__(self, network: NeuralNetwork, config: TrainConfig,
                 on_epoch: Optional[Callable[[EpochRecord], None]] = None):
        self.network = network
        self.config = config
        self.on_epoch = on_epoch
        self._pause = threading.Event()   # установлен = пауза
        self._stop = threading.Event()    # установлен = стоп
        self._pause.clear()
        self._stop.clear()
        self.current_epoch = 0

    # ---------------- управление (ТЗ §18) ----------------

    def pause(self) -> None:
        """⏸ Пауза."""
        self._pause.set()
        logger.info("trainer: пауза")

    def resume(self) -> None:
        """↻ Продолжить."""
        self._pause.clear()
        logger.info("trainer: продолжено")

    def stop(self) -> None:
        """■ Остановить."""
        self._stop.set()
        self._pause.clear()
        logger.info("trainer: остановка")

    @property
    def paused(self) -> bool:
        """На паузе ли."""
        return self._pause.is_set()

    # ---------------- обучение ----------------

    def fit(self, x_train: np.ndarray, y_train: np.ndarray,
            x_val: Optional[np.ndarray] = None,
            y_val: Optional[np.ndarray] = None,
            start_epoch: int = 0) -> TrainingResult:
        """Цикл обучения. Возвращает TrainingResult.

        Args:
            start_epoch: с какой эпохи продолжить (для ↻ Продолжить).
        """
        cfg = self.config
        n = len(x_train)
        batch = max(1, min(cfg.batch_size, n))
        rng = np.random.default_rng(cfg.seed + start_epoch)
        history = []
        stopped_early = False
        stop_reason = ""
        self._stop.clear()

        for epoch in range(start_epoch + 1, cfg.epochs + 1):
            if self._stop.is_set():
                stop_reason = "Остановлено пользователем."
                break
            while self._pause.is_set() and not self._stop.is_set():
                time.sleep(0.1)
            if self._stop.is_set():
                stop_reason = "Остановлено пользователем."
                break

            # Mini-batch SGD.
            perm = rng.permutation(n)
            for start in range(0, n, batch):
                idx = perm[start:start + batch]
                self.network.train_step(x_train[idx], y_train[idx],
                                        cfg.learning_rate)

            loss = self.network.compute_loss(x_train, y_train)
            acc = self.network.accuracy(x_train, y_train)
            if x_val is not None and len(x_val):
                val_loss = self.network.compute_loss(x_val, y_val)
                val_acc = self.network.accuracy(x_val, y_val)
            else:
                val_loss, val_acc = loss, acc
            self.current_epoch = epoch
            record = EpochRecord(epoch=epoch, loss=round(loss, 6),
                                 accuracy=round(acc, 6),
                                 val_loss=round(val_loss, 6),
                                 val_accuracy=round(val_acc, 6))
            history.append(record)
            if self.on_epoch is not None:
                try:
                    self.on_epoch(record)
                except Exception as e:
                    logger.warning("trainer callback: %s", e)

            # Early stopping по целевой точности (ТЗ §17).
            if val_acc >= cfg.target_accuracy:
                stopped_early = True
                stop_reason = (f"Target accuracy reached ({val_acc:.1%} >= "
                               f"{cfg.target_accuracy:.0%}). Training stopped.")
                logger.info("trainer: %s", stop_reason)
                break

        if history:
            last = history[-1]
            train_acc, final_loss = last.accuracy, last.loss
            val_acc = last.val_accuracy
        else:
            train_acc = val_acc = final_loss = 0.0
        return TrainingResult(history=history, stopped_early=stopped_early,
                              stop_reason=stop_reason,
                              train_accuracy=train_acc,
                              val_accuracy=val_acc, final_loss=final_loss)
