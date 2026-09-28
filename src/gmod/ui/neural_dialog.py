"""Диалог «Настроить нейросеть» (ТЗ §11-12).

Вкладки: Данные / Архитектура / Обучение / Прогноз / Анализ / История.
Обучение — в QThread (▶/⏸/■/↻), графики — pyqtgraph (ТЗ §19).
Реальное обучение выполняет NeuralNetwork, не LLM (ТЗ §24).
"""

import logging

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class _TrainWorker(QThread):
    """Поток обучения: вызывает Trainer.fit, шлёт сигналы эпох."""

    epoch = Signal(dict)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, trainer, x_train, y_train, x_val, y_val, start_epoch=0):
        super().__init__()
        self.trainer = trainer
        self.x_train = x_train
        self.y_train = y_train
        self.x_val = x_val
        self.y_val = y_val
        self.start_epoch = start_epoch

    def run(self):
        try:
            result = self.trainer.fit(
                self.x_train, self.y_train, self.x_val, self.y_val,
                start_epoch=self.start_epoch)
            self.done.emit({
                "train_accuracy": result.train_accuracy,
                "val_accuracy": result.val_accuracy,
                "final_loss": result.final_loss,
                "stopped_early": result.stopped_early,
                "stop_reason": result.stop_reason,
                "epochs": len(result.history),
            })
        except Exception as e:
            logger.error("neural train failed: %s", e, exc_info=True)
            self.failed.emit(str(e))


class _TrainBridge(QObject):
    """Мост GUI-сигналов обучения (создаётся в GUI-потоке)."""

    progressed = Signal(dict)
    finished_ok = Signal(dict)
    failed = Signal(str)


class NeuralDialog(QDialog):
    """Конструктор нейросети (ТЗ §11-12)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка нейросети")
        self.resize(900, 650)
        self.setModal(False)

        # Состояние.
        self.dataset = None          # (X, y, meta)
        self.split = None            # ((Xt, yt), (Xv, yv))
        self.network = None
        self.trainer = None
        self.worker = None
        self.history_records = []    # EpochRecord
        self.train_result = None
        self.val_report = None
        self.last_prediction = None
        self.threshold = 0.5

        # Мост сигналов обучения (GUI-поток).
        self._bridge = _TrainBridge()
        self._bridge.progressed.connect(self._update_live)
        self._bridge.finished_ok.connect(self._on_train_done)
        self._bridge.failed.connect(self._on_train_failed)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_data_tab(), "Данные")
        self.tabs.addTab(self._build_arch_tab(), "Архитектура")
        self.tabs.addTab(self._build_train_tab(), "Обучение")
        self.tabs.addTab(self._build_forecast_tab(), "Прогноз")
        self.tabs.addTab(self._build_analysis_tab(), "Анализ")
        self.tabs.addTab(self._build_history_tab(), "История")

        from gmod.ui.setting_defs import describe as _describe
        self._describe = _describe

    # ================= Данные (ТЗ §13) =================

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        form = QFormLayout()
        self.ds_source = QComboBox()
        self.ds_source.addItems(["Метрики проекта", "SQLite", "CSV", "JSON"])
        self.ds_source.setToolTip("Источник датасета. Основной для GMod — raw_metrics.")
        form.addRow("Dataset:", self.ds_source)
        path_row = QHBoxLayout()
        self.ds_path = QLineEdit()
        self.ds_path.setPlaceholderText("Путь к CSV/JSON (для файловых источников)")
        path_row.addWidget(self.ds_path, 1)
        browse_btn = QPushButton("…")
        browse_btn.setMaximumWidth(40)
        browse_btn.clicked.connect(self._on_browse_dataset)
        path_row.addWidget(browse_btn)
        form.addRow("Файл:", path_row)
        self.ds_label_col = QLineEdit("label")
        self.ds_label_col.setToolTip("Имя колонки-метки в CSV.")
        form.addRow("Колонка метки (CSV):", self.ds_label_col)
        self.ds_val_split = QDoubleSpinBox()
        self.ds_val_split.setRange(0.05, 0.5)
        self.ds_val_split.setSingleStep(0.05)
        self.ds_val_split.setValue(0.2)
        self.ds_val_split.setToolTip("Validation split: доля выборки под валидацию.")
        form.addRow("Validation split:", self.ds_val_split)
        self.ds_seed = QSpinBox()
        self.ds_seed.setRange(0, 99999)
        self.ds_seed.setValue(42)
        self.ds_seed.setToolTip("Random seed: фиксирует разбиение и инициализацию весов.")
        form.addRow("Random seed:", self.ds_seed)
        layout.addLayout(form)

        load_btn = QPushButton("Загрузить dataset")
        load_btn.clicked.connect(self._on_load_dataset)
        layout.addWidget(load_btn)

        self.ds_info = QLabel("Dataset не загружен.")
        self.ds_info.setWordWrap(True)
        layout.addWidget(self.ds_info)
        layout.addStretch()
        return tab

    def _on_browse_dataset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Dataset", "", "Data (*.csv *.json);;All (*)")
        if path:
            self.ds_path.setText(path)

    def _current_repo(self):
        try:
            parent = self.parent()
            repo_id = parent._get_current_repo_id() if parent else ""
            repo_path = parent._get_repo_path(repo_id) if (parent and repo_id) else ""
            return repo_id or "", repo_path or ""
        except Exception:
            return "", ""

    def _on_load_dataset(self) -> None:
        from gmod.ml.datasets import load_dataset, train_validation_split
        source_map = {"Метрики проекта": "metrics", "SQLite": "sqlite",
                      "CSV": "csv", "JSON": "json"}
        source = source_map.get(self.ds_source.currentText(), "metrics")
        repo_id, _repo_path = self._current_repo()
        try:
            X, y, meta = load_dataset(
                source, repo_id=repo_id, path=self.ds_path.text().strip(),
                label_column=self.ds_label_col.text().strip() or "label")
            split = train_validation_split(
                X, y, validation_split=float(self.ds_val_split.value()),
                seed=int(self.ds_seed.value()))
            self.dataset = (X, y, meta)
            self.split = split
            (Xt, yt), (Xv, yv) = split
            n_pos = int(y.sum())
            self.ds_info.setText(
                f"Загружено: {len(y)} примеров, признаков: {X.shape[1]}, "
                f"positive: {n_pos} ({n_pos / max(1, len(y)):.0%})\n"
                f"Train: {len(yt)}, validation: {len(yv)}\n"
                f"Признаки: {', '.join(meta.get('feature_names', []))}")
            logger.info("neural dataset: n=%d features=%d", len(y), X.shape[1])
            self._refresh_forecast_objects()
            self.status_message(f"Dataset загружен: {len(y)} примеров")
        except Exception as e:
            logger.error("dataset load: %s", e)
            QMessageBox.warning(self, "Dataset", f"Не удалось загрузить: {e}")

    def status_message(self, text: str) -> None:
        """Статус (лог + родительский статус-бар, если есть)."""
        logger.info("neural: %s", text)
        try:
            parent = self.parent()
            if parent and hasattr(parent, "status_bar"):
                parent.status_bar.showMessage(text)
        except Exception:
            pass

    # ================= Архитектура (ТЗ §14-15) =================

    def _build_arch_tab(self) -> QWidget:
        from gmod.ui.setting_defs import describe
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        form = QFormLayout()

        self.arch_input = QSpinBox()
        self.arch_input.setRange(1, 128)
        self.arch_input.setValue(8)
        describe(self.arch_input, "epochs")
        self.arch_input.setToolTip("Входных признаков: должно совпадать с dataset.")
        form.addRow("Входных признаков:", self.arch_input)

        self.arch_hidden = QLineEdit("16, 8")
        self.arch_hidden.setToolTip("Скрытые слои: нейронов через запятую. Пример: 16, 8.")
        form.addRow("Скрытые слои:", self.arch_hidden)

        self.arch_output = QSpinBox()
        self.arch_output.setRange(1, 32)
        self.arch_output.setValue(1)
        self.arch_output.setToolTip("Выходных нейронов: 1 для бинарной классификации.")
        form.addRow("Выходных нейронов:", self.arch_output)

        self.arch_activation = QComboBox()
        self.arch_activation.addItems(["ReLU", "Sigmoid", "Tanh", "Linear"])
        describe(self.arch_activation, "activation")
        form.addRow("Функция активации:", self.arch_activation)

        self.arch_out_activation = QComboBox()
        self.arch_out_activation.addItems(["Sigmoid", "Softmax", "Linear"])
        self.arch_out_activation.setToolTip(
            "Выходная активация: Sigmoid/Softmax для классификации.")
        form.addRow("Выходная активация:", self.arch_out_activation)

        self.arch_seed = QSpinBox()
        self.arch_seed.setRange(0, 99999)
        self.arch_seed.setValue(42)
        self.arch_seed.setToolTip("Random seed инициализации весов.")
        form.addRow("Random seed:", self.arch_seed)

        layout.addLayout(form)
        build_btn = QPushButton("Построить сеть")
        build_btn.clicked.connect(self._on_build_network)
        layout.addWidget(build_btn)
        self.arch_info = QLabel("Сеть не построена.")
        self.arch_info.setWordWrap(True)
        layout.addWidget(self.arch_info)
        layout.addStretch()
        return tab

    def _parse_hidden(self) -> list:
        parts = [p.strip() for p in self.arch_hidden.text().split(",") if p.strip()]
        layers = [int(p) for p in parts]
        if not layers or any(n < 1 or n > 1024 for n in layers):
            raise ValueError("Скрытые слои: числа 1–1024 через запятую.")
        return layers

    def _on_build_network(self) -> None:
        from gmod.ml.neural_network import NeuralNetwork
        from gmod.ml.schemas import ModelConfig
        try:
            cfg = ModelConfig(
                input_features=int(self.arch_input.value()),
                hidden_layers=self._parse_hidden(),
                output_neurons=int(self.arch_output.value()),
                activation=self.arch_activation.currentText(),
                output_activation=self.arch_out_activation.currentText(),
                seed=int(self.arch_seed.value()))
            if self.dataset is not None:
                n_features = self.dataset[0].shape[1]
                if n_features != cfg.input_features:
                    reply = QMessageBox.question(
                        self, "Архитектура",
                        f"Dataset имеет {n_features} признаков, "
                        f"а вход — {cfg.input_features}. Подставить {n_features}?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        cfg.input_features = n_features
                        self.arch_input.setValue(n_features)
            self.network = NeuralNetwork(cfg)
            self.network_config = cfg
            self.arch_info.setText(
                f"Построена: Input {cfg.input_features} → "
                f"{' → '.join(map(str, cfg.hidden_layers))} → {cfg.output_neurons} "
                f"({cfg.activation}/{cfg.output_activation})")
            self.status_message("Сеть построена")
        except Exception as e:
            logger.error("build network: %s", e)
            QMessageBox.warning(self, "Архитектура", f"Не удалось построить: {e}")

    # ================= Обучение (ТЗ §16-19) =================

    def _build_train_tab(self) -> QWidget:
        from gmod.ui.setting_defs import describe
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        form = QFormLayout()

        self.tr_epochs = QSpinBox()
        self.tr_epochs.setRange(1, 10000)
        self.tr_epochs.setValue(100)
        describe(self.tr_epochs, "epochs")
        form.addRow("Epochs:", self.tr_epochs)

        self.tr_lr = QDoubleSpinBox()
        self.tr_lr.setRange(0.0001, 1.0)
        self.tr_lr.setDecimals(4)
        self.tr_lr.setSingleStep(0.005)
        self.tr_lr.setValue(0.05)
        describe(self.tr_lr, "learning_rate")
        form.addRow("Learning rate:", self.tr_lr)

        self.tr_batch = QSpinBox()
        self.tr_batch.setRange(1, 1024)
        self.tr_batch.setValue(32)
        describe(self.tr_batch, "batch_size")
        form.addRow("Batch size:", self.tr_batch)

        self.tr_target = QDoubleSpinBox()
        self.tr_target.setRange(0.5, 1.0)
        self.tr_target.setSingleStep(0.01)
        self.tr_target.setDecimals(3)
        self.tr_target.setValue(0.9)
        describe(self.tr_target, "target_accuracy")
        form.addRow("Target accuracy:", self.tr_target)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.train_btn = QPushButton("▶ Обучить")
        self.train_btn.clicked.connect(self._on_train_start)
        btn_row.addWidget(self.train_btn)
        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_train_pause)
        btn_row.addWidget(self.pause_btn)
        self.stop_btn = QPushButton("■ Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_train_stop)
        btn_row.addWidget(self.stop_btn)
        self.resume_btn = QPushButton("↻ Продолжить")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_train_resume)
        btn_row.addWidget(self.resume_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Живые показатели (ТЗ §18).
        self.live_label = QLabel("Epoch: —  Loss: —  Accuracy: —  Validation: —")
        self.live_label.setWordWrap(True)
        layout.addWidget(self.live_label)

        # График (ТЗ §19): существующая библиотека проекта — pyqtgraph.
        try:
            import pyqtgraph as pg
            self.chart = pg.PlotWidget()
            self.chart.setMinimumHeight(220)
            self.chart.addLegend()
            self.chart.setLabel("left", "loss / accuracy")
            self.chart.setLabel("bottom", "epoch")
            self.loss_curve = self.chart.plot(pen=pg.mkPen("#B87979", width=2),
                                              name="Loss")
            self.acc_curve = self.chart.plot(pen=pg.mkPen("#8FAF8A", width=2),
                                             name="Accuracy")
            self.val_curve = self.chart.plot(pen=pg.mkPen("#8EA7C4", width=2),
                                             name="Validation")
            layout.addWidget(self.chart, 1)
            self._chart_ok = True
        except Exception as e:
            logger.warning("neural chart unavailable: %s", e)
            self._chart_ok = False
        return tab

    def _require_data_and_net(self):
        if self.dataset is None or self.split is None:
            raise RuntimeError("Сначала загрузите dataset (вкладка Данные).")
        if self.network is None:
            raise RuntimeError("Сначала постройте сеть (вкладка Архитектура).")
        (Xt, yt), (Xv, yv) = self.split
        if Xt.shape[1] != self.network.config.input_features:
            raise RuntimeError(
                f"Вход сети ({self.network.config.input_features}) не совпадает "
                f"с признаками ({Xt.shape[1]}). Перестройте сеть.")

    def _make_trainer(self):
        from gmod.ml.schemas import TrainConfig
        from gmod.ml.trainer import Trainer
        cfg = TrainConfig(
            epochs=int(self.tr_epochs.value()),
            learning_rate=float(self.tr_lr.value()),
            batch_size=int(self.tr_batch.value()),
            target_accuracy=float(self.tr_target.value()),
            validation_split=float(self.ds_val_split.value()),
            seed=int(self.ds_seed.value()))
        self.train_config = cfg
        # Колбэк эпох назначается в _on_train_start (мост в GUI-поток).
        self.trainer = Trainer(self.network, cfg)
        return self.trainer

    def _on_train_start(self) -> None:
        try:
            self._require_data_and_net()
        except Exception as e:
            QMessageBox.warning(self, "Обучение", str(e))
            return
        trainer = self._make_trainer()

        def _cb(record):
            self.history_records.append(
                {"epoch": record.epoch, "loss": record.loss,
                 "accuracy": record.accuracy, "val_accuracy": record.val_accuracy})
            try:
                self._bridge.progressed.emit(
                    {"epoch": record.epoch, "loss": record.loss,
                     "accuracy": record.accuracy,
                     "val_accuracy": record.val_accuracy})
            except Exception:
                pass

        trainer.on_epoch = _cb
        (Xt, yt), (Xv, yv) = self.split
        self.history_records = []
        if self._chart_ok:
            self.loss_curve.setData([], [])
            self.acc_curve.setData([], [])
            self.val_curve.setData([], [])
        self.worker = _TrainWorker(trainer, Xt, yt, Xv, yv, start_epoch=0)
        self.worker.done.connect(lambda r: self._bridge.finished_ok.emit(r))
        self.worker.failed.connect(lambda m: self._bridge.failed.emit(m))
        self.train_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.status_message("Обучение запущено")
        self.worker.start()

    def _update_live(self, info: dict) -> None:
        self.live_label.setText(
            f"Epoch: {info['epoch']} / {int(self.tr_epochs.value())}   "
            f"Loss: {info['loss']:.4f}   Accuracy: {info['accuracy']:.2%}   "
            f"Validation: {info['val_accuracy']:.2%}")
        if self._chart_ok and self.history_records:
            xs = [r["epoch"] for r in self.history_records]
            self.loss_curve.setData(xs, [r["loss"] for r in self.history_records])
            self.acc_curve.setData(xs, [r["accuracy"] for r in self.history_records])
            self.val_curve.setData(xs, [r["val_accuracy"] for r in self.history_records])

    def _train_buttons_idle(self) -> None:
        self.train_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)

    def _on_train_done(self, result: dict) -> None:
        self._train_buttons_idle()
        self.train_result = result
        status = (result.get("stop_reason") or
                  f"Готово: accuracy={result.get('train_accuracy', 0):.1%}, "
                  f"validation={result.get('val_accuracy', 0):.1%}")
        self.live_label.setText(status)
        self.status_message(status)
        logger.info("neural trained: %s", result)

    def _on_train_failed(self, message: str) -> None:
        self._train_buttons_idle()
        QMessageBox.warning(self, "Обучение", f"Ошибка: {message}")

    def _on_train_pause(self) -> None:
        if self.trainer is not None:
            self.trainer.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.status_message("Пауза")

    def _on_train_stop(self) -> None:
        if self.trainer is not None:
            self.trainer.stop()
            self.status_message("Остановка…")

    def _on_train_resume(self) -> None:
        if self.trainer is not None and self.worker is not None:
            self.trainer.resume()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.status_message("Продолжаем обучение")

    # ================= Прогноз (ТЗ §21) =================

    def _build_forecast_tab(self) -> QWidget:
        from gmod.ui.setting_defs import describe
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        form = QFormLayout()
        self.fc_object = QComboBox()
        self.fc_object.setMinimumWidth(300)
        self.fc_object.setToolTip("Объект прогноза: файл/функция из датасета.")
        form.addRow("Объект:", self.fc_object)
        self.fc_threshold = QSlider(Qt.Horizontal)
        self.fc_threshold.setRange(0, 100)
        self.fc_threshold.setValue(50)
        describe(self.fc_threshold, "prediction_threshold")
        self.fc_threshold.valueChanged.connect(self._on_threshold_changed)
        form.addRow("Prediction threshold:", self.fc_threshold)
        self.fc_threshold_label = QLabel("0.50")
        form.addRow("", self.fc_threshold_label)
        layout.addLayout(form)
        predict_btn = QPushButton("Сделать прогноз")
        predict_btn.clicked.connect(self._on_predict)
        layout.addWidget(predict_btn)
        self.fc_result = QLabel("Прогноз появится здесь.")
        self.fc_result.setWordWrap(True)
        self.fc_result.setFont(QFont("Consolas", 11))
        layout.addWidget(self.fc_result)
        layout.addStretch()
        return tab

    def _refresh_forecast_objects(self) -> None:
        try:
            self.fc_object.clear()
            if self.dataset is None:
                return
            _X, _y, meta = self.dataset
            for i, unit in enumerate(meta.get("units", [])[:500]):
                self.fc_object.addItem(f"{unit.get('file', '')} :: {unit.get('unit', '')}", i)
        except Exception as e:
            logger.debug("forecast objects: %s", e)

    def _on_threshold_changed(self, value: int) -> None:
        self.threshold = value / 100.0
        self.fc_threshold_label.setText(f"{self.threshold:.2f}")
        # Порог меняет результат без переобучения (ТЗ §21).
        if self.last_prediction is not None:
            self._show_prediction(self.last_prediction, from_threshold=True)

    def _on_predict(self) -> None:
        from gmod.ml.predictor import Predictor
        if self.network is None or self.dataset is None:
            QMessageBox.warning(self, "Прогноз", "Нужны dataset и обученная сеть.")
            return
        try:
            _X, _y, meta = self.dataset
            idx = self.fc_object.currentData()
            unit = meta.get("units", [])[idx if idx is not None else 0]
            predictor = Predictor(self.network, meta.get("norm_params", {}),
                                  meta.get("feature_names", []))
            result = predictor.predict_unit(unit.get("values", {}),
                                            threshold=self.threshold)
            result.update({"file": unit.get("file", ""), "unit": unit.get("unit", ""),
                           "threshold": self.threshold})
            self.last_prediction = result
            self._show_prediction(result)
        except Exception as e:
            logger.error("predict: %s", e)
            QMessageBox.warning(self, "Прогноз", f"Не удалось: {e}")

    def _show_prediction(self, result: dict, from_threshold: bool = False) -> None:
        proba = float(result.get("probability", 0.0))
        thr = float(result.get("threshold", self.threshold))
        problematic = proba >= thr
        label = (f"Problematic = {proba:.1%}" if problematic
                 else f"OK = {(1.0 - proba):.1%}")
        result["problematic"] = problematic
        result["label"] = label
        self.fc_result.setText(
            f"Prediction:\n{label}\n\nProbability:\n{proba:.3f}\n\n"
            f"Threshold: {thr:.2f}\n{result.get('file', '')} :: {result.get('unit', '')}")
        if not from_threshold:
            self.status_message(f"Прогноз: {label}")

    # ================= Анализ (ТЗ §20, §22-23) =================

    def _build_analysis_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        validate_btn = QPushButton("Валидировать")
        validate_btn.setToolTip("Посчитать метрики на validation-выборке (ТЗ §22).")
        validate_btn.clicked.connect(self._on_validate)
        btn_row.addWidget(validate_btn)
        analyze_btn = QPushButton("Проанализировать прогноз")
        analyze_btn.setToolTip("Сводка прогноза по всем объектам (ТЗ §22).")
        analyze_btn.clicked.connect(self._on_analyze_forecast)
        btn_row.addWidget(analyze_btn)
        explain_btn = QPushButton("Объяснить результат через AI")
        explain_btn.setToolTip("LLM объяснит прогноз по конфигурации и метрикам (ТЗ §23).")
        explain_btn.clicked.connect(self._on_explain_via_ai)
        btn_row.addWidget(explain_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.analysis_view = QTextEdit()
        self.analysis_view.setReadOnly(True)
        self.analysis_view.setFont(QFont("Consolas", 10))
        self.analysis_view.setPlaceholderText("Здесь появятся результаты валидации и explanation AI...")
        layout.addWidget(self.analysis_view, 1)
        save_btn = QPushButton("Сохранить модель")
        save_btn.setToolTip("Сохранить с автоверсией Model vN (ТЗ §25).")
        save_btn.clicked.connect(self._on_save_model)
        layout.addWidget(save_btn)
        return tab

    def _on_validate(self) -> None:
        from gmod.ml.evaluator import evaluate
        if self.network is None or self.split is None:
            QMessageBox.warning(self, "Валидация", "Нужны dataset и сеть.")
            return
        try:
            (_Xt, _yt), (Xv, yv) = self.split
            self.val_report = evaluate(self.network, Xv, yv, threshold=self.threshold)
            r = self.val_report
            lines = [
                "Validation Accuracy: {:.1%}".format(r.accuracy),
                "Precision: {:.3f}  Recall: {:.3f}  F1: {:.3f}".format(
                    r.precision, r.recall, r.f1),
                f"Confusion Matrix: TP={r.confusion.get('TP', 0)} "
                f"TN={r.confusion.get('TN', 0)} FP={r.confusion.get('FP', 0)} "
                f"FN={r.confusion.get('FN', 0)}",
                f"Samples: {r.n_samples}  Threshold: {self.threshold:.2f}",
            ]
            self.analysis_view.setText("\n".join(lines))
            self.status_message(f"Валидация: accuracy={r.accuracy:.1%}")
        except Exception as e:
            logger.error("validate: %s", e)
            QMessageBox.warning(self, "Валидация", f"Не удалось: {e}")

    def _on_analyze_forecast(self) -> None:
        """Сводка прогноза по всем объектам датасета (ТЗ §22)."""
        from gmod.ml.predictor import Predictor
        if self.network is None or self.dataset is None:
            QMessageBox.warning(self, "Анализ", "Нужны dataset и сеть.")
            return
        try:
            _X, _y, meta = self.dataset
            predictor = Predictor(self.network, meta.get("norm_params", {}),
                                  meta.get("feature_names", []),
                                  meta.get("units", []))
            results = predictor.predict_all(threshold=self.threshold)
            bad = [r for r in results if r["problematic"]]
            lines = [f"Всего объектов: {len(results)}, проблемных: {len(bad)} "
                     f"(порог {self.threshold:.2f})", "", "Топ проблемных:"]
            lines += [f"  {r['label']} — {r['file']} :: {r['unit']}" for r in bad[:15]]
            self.analysis_view.setText("\n".join(lines))
        except Exception as e:
            logger.error("analyze forecast: %s", e)
            QMessageBox.warning(self, "Анализ", f"Не удалось: {e}")

    def _on_explain_via_ai(self) -> None:
        """LLM объясняет результат нейросети (ТЗ §23, LLM не тренер — §24)."""
        if self.network is None:
            QMessageBox.warning(self, "AI", "Сначала постройте и обучите сеть.")
            return
        try:
            from gmod.services.llm_service import LLMService
            from gmod.config.settings import get_settings
            describe = self.network.describe()
            train = self.train_result or {}
            val = {"accuracy": getattr(self.val_report, "accuracy", 0),
                   "precision": getattr(self.val_report, "precision", 0),
                   "recall": getattr(self.val_report, "recall", 0),
                   "f1": getattr(self.val_report, "f1", 0)} if self.val_report else {}
            pred = self.last_prediction or {}
            _X, _y, meta = self.dataset if self.dataset else (None, None, {})
            top_units = ", ".join(
                f"{u.get('file', '')}::{u.get('unit', '')}"
                for u in (meta.get("units", []) if isinstance(meta, dict) else [])[:10])
            features = ", ".join(meta.get("feature_names", []) if isinstance(meta, dict) else [])
            prompt = (
                "Объясни пользователю результат нейросети (по-русски):\n"
                f"Конфигурация: {describe}\n"
                f"Обучение: {train}\nВалидация: {val}\nПрогноз: {pred}\n"
                f"Признаки: {features}\nОбъекты: {top_units}\n"
                "Ответь: почему такой прогноз? какие признаки повлияли? "
                "какие файлы проблемные? почему модель ошибается? "
                "что изменить в обучении?")
            settings = get_settings()
            answer = LLMService().generate(
                prompt, max_tokens=min(settings.max_tokens, 1500),
                temperature=0.5, timeout=settings.llm_timeout)
            self.analysis_view.setText("AI-объяснение:\n\n" + answer)
            self.status_message("AI-объяснение получено")
        except Exception as e:
            logger.error("explain via AI: %s", e)
            QMessageBox.warning(self, "AI", f"Не удалось: {e}")

    def _on_save_model(self) -> None:
        """Сохранение модели с версией (ТЗ §25)."""
        if self.network is None:
            QMessageBox.warning(self, "Модель", "Нет сети для сохранения.")
            return
        try:
            from gmod.ml.model_storage import ModelStorage
            repo_id, _p = self._current_repo()
            _X, _y, meta = self.dataset if self.dataset else (None, None, {})
            payload = {
                "workspace_id": "default",
                "dataset": {"source": self.ds_source.currentText(),
                            "repo_id": repo_id,
                            "feature_names": meta.get("feature_names", []) if isinstance(meta, dict) else [],
                            "norm_params": meta.get("norm_params", {}) if isinstance(meta, dict) else {}},
                "architecture": {"input_features": self.network.config.input_features,
                                 "hidden_layers": list(self.network.config.hidden_layers),
                                 "output_neurons": self.network.config.output_neurons,
                                 "activation": self.network.config.activation,
                                 "output_activation": self.network.config.output_activation},
                "activation": self.network.config.activation,
                "epochs": int(self.tr_epochs.value()),
                "learning_rate": float(self.tr_lr.value()),
                "target_accuracy": float(self.tr_target.value()),
                "seed": int(self.network.config.seed),
                "training_metrics": dict(self.train_result or {}),
                "validation_metrics": {
                    "accuracy": getattr(self.val_report, "accuracy", 0),
                    "precision": getattr(self.val_report, "precision", 0),
                    "recall": getattr(self.val_report, "recall", 0),
                    "f1": getattr(self.val_report, "f1", 0)},
                "weights": self.network.get_weights(),
            }
            model_id = ModelStorage().save("model", payload)
            self._refresh_history()
            QMessageBox.information(self, "Модель", f"Сохранено: {model_id}")
            self.status_message(f"Модель сохранена: {model_id}")
        except Exception as e:
            logger.error("save model: %s", e)
            QMessageBox.warning(self, "Модель", f"Не удалось сохранить: {e}")

    # ================= История (ТЗ §26) =================

    def _build_history_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list, 1)
        btn_row = QHBoxLayout()
        load_btn = QPushButton("Загрузить модель")
        load_btn.setToolTip("Открыть и повторно использовать модель.")
        load_btn.clicked.connect(self._on_load_model)
        btn_row.addWidget(load_btn)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._on_delete_model)
        btn_row.addWidget(del_btn)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._refresh_history)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._refresh_history()
        return tab

    def _refresh_history(self) -> None:
        from gmod.ml.model_storage import ModelStorage
        try:
            self.history_list.clear()
            self._history_data = ModelStorage().list_models()
            for m in self._history_data:
                acc = m.get("accuracy") or 0
                item = QListWidgetItem(
                    f"{m['model_id']} | Accuracy: {acc:.1%} | "
                    f"Epochs: {m.get('epochs', 0)} | "
                    f"Activation: {m.get('activation', '')} | "
                    f"Created: {str(m.get('created_at', ''))[:16]}")
                item.setData(Qt.UserRole, m.get("model_id", ""))
                self.history_list.addItem(item)
            if not self._history_data:
                self.history_list.addItem("Моделей пока нет — обучите и сохраните.")
        except Exception as e:
            logger.error("history refresh: %s", e)

    def _selected_history_id(self):
        current = self.history_list.currentItem()
        if current:
            return current.data(Qt.UserRole)
        return ""

    def _on_load_model(self) -> None:
        """Загрузить модель и повторно использовать (ТЗ §26)."""
        from gmod.ml.model_storage import ModelStorage
        from gmod.ml.neural_network import NeuralNetwork
        from gmod.ml.schemas import ModelConfig
        model_id = self._selected_history_id()
        if not model_id:
            QMessageBox.warning(self, "История", "Выберите модель.")
            return
        try:
            data = ModelStorage().load(model_id)
            arch = data.get("architecture", {})
            cfg = ModelConfig(
                input_features=int(arch.get("input_features", 8)),
                hidden_layers=list(arch.get("hidden_layers", [16, 8])),
                output_neurons=int(arch.get("output_neurons", 1)),
                activation=str(arch.get("activation", "relu")),
                output_activation=str(arch.get("output_activation", "sigmoid")),
                seed=int(data.get("seed", 42)))
            net = NeuralNetwork(cfg)
            net.set_weights(data.get("weights", {}))
            self.network = net
            self.network_config = cfg
            self.arch_input.setValue(cfg.input_features)
            self.arch_hidden.setText(", ".join(map(str, cfg.hidden_layers)))
            self.arch_output.setValue(cfg.output_neurons)
            self.arch_activation.setCurrentText(cfg.activation.capitalize()
                                                if cfg.activation.capitalize() in
                                                ["ReLU", "Sigmoid", "Tanh", "Linear"]
                                                else "ReLU")
            self.arch_info.setText(f"Загружена: {model_id}")
            val = data.get("validation_metrics", {})
            self.analysis_view.setText(
                f"Загружена {model_id}\nValidation accuracy: {val.get('accuracy', 0):.1%}\n"
                f"Epochs: {data.get('epochs', 0)}")
            self.status_message(f"Модель загружена: {model_id}")
        except Exception as e:
            logger.error("load model: %s", e)
            QMessageBox.warning(self, "История", f"Не удалось загрузить: {e}")

    def _on_delete_model(self) -> None:
        from gmod.ml.model_storage import ModelStorage
        model_id = self._selected_history_id()
        if not model_id:
            return
        reply = QMessageBox.question(self, "Удаление", f"Удалить {model_id}?",
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            ModelStorage().delete(model_id)
            self._refresh_history()
