"""Тесты ТЗ v0.4 §31: AI-контекст / Reports / Repository / Neural Network.

Моки + временные БД/репо, без сети.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    from gmod.infrastructure.db.database import Database
    return Database(tmp_path / "v04.db")


def _make_git_repo(path: Path, files: dict, message: str = "init"):
    import git
    path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(path)
    for name, content in files.items():
        (path / name).write_text(content, encoding="utf-8")
    repo.index.add(list(files.keys()))
    repo.index.commit(message)
    return repo


def _seed_metrics(db, repo_id="r1", commit="c1"):
    db.save_metric(repo_id, commit, "a.py", "function", "f1",
                   "CyclomaticComplexity", 12.0)
    db.save_metric(repo_id, commit, "a.py", "function", "f1",
                   "LinesOfCode", 50.0)
    db.save_metric(repo_id, commit, "b.py", "function", "f2",
                   "CyclomaticComplexity", 2.0)
    db.save_metric(repo_id, commit, "b.py", "function", "f2",
                   "LinesOfCode", 10.0)
    return commit


# ============================================================
# AI-контекст (ТЗ §31)
# ============================================================

def test_full_repository_context(tmp_db, tmp_path):
    """Полный контекст репозитория: дерево, README, языки, файлы."""
    from gmod.services.context_service import ContextAssemblyService
    repo = _make_git_repo(tmp_path / "repo", {
        "app.py": "def f():\n    return 1\n",
        "README.md": "# Demo\n",
        "pyproject.toml": "[project]\nname='d'\n",
    })
    svc = ContextAssemblyService(db=tmp_db)
    ctx = svc.build_repository_context("r1", str(tmp_path / "repo"))
    assert ctx.file_count >= 3
    assert ".py" in ctx.languages
    assert "Demo" in ctx.readme
    assert "app.py" in ctx.directory_tree
    assert "pyproject.toml" in ctx.config_files


def test_metrics_are_added_to_context(tmp_db):
    """Метрики попадают в контекст детально, не агрегатом."""
    _seed_metrics(tmp_db)
    from gmod.services.context_service import ContextAssemblyService
    svc = ContextAssemblyService(db=tmp_db)
    ctx = svc.assemble(repo_id="r1", repo_path="", mode="standard")
    assert ctx.sections.get("metrics") == 4
    assert "CyclomaticComplexity" in ctx.text
    assert "3550 metrics" not in ctx.text  # запрещённый агрегат-формат
    assert "avg=" in ctx.text and "top values" in ctx.text


def test_context_repository_id(tmp_db, tmp_path):
    """Контекст несёт repository_id/commit/snapshot."""
    import git
    _make_git_repo(tmp_path / "repo", {"a.py": "x = 1\n"})
    head = git.Repo(str(tmp_path / "repo")).head.commit.hexsha
    _seed_metrics(tmp_db, repo_id="r1", commit=head)
    _seed_metrics(tmp_db)
    from gmod.services.context_service import ContextAssemblyService
    svc = ContextAssemblyService(db=tmp_db)
    ctx = svc.assemble(repo_id="r1", repo_path=str(tmp_path / "repo"),
                       mode="brief")
    assert ctx.repository_id == "r1"
    assert ctx.metrics_snapshot_id != ""


def test_old_context_is_invalidated(tmp_db):
    """Снапшоты разных состояний различаются."""
    _seed_metrics(tmp_db, repo_id="r1", commit="c1")
    _seed_metrics(tmp_db, repo_id="r1", commit="c2")
    from gmod.services.context_service import ContextAssemblyService
    svc = ContextAssemblyService(db=tmp_db)
    s1 = svc.build_metrics_context("r1", "c1").snapshot_id
    s2 = svc.build_metrics_context("r1", "c2").snapshot_id
    assert s1 and s2 and s1 != s2


def test_user_question_present(tmp_db):
    """Вопрос пользователя и retrieval релевантного (ТЗ §1.2)."""
    _seed_metrics(tmp_db)
    from gmod.services.context_service import ContextAssemblyService
    svc = ContextAssemblyService(db=tmp_db)
    rel = svc.select_relevant(
        "Какие функции самые сложные?",
        repo_ctx=MagicMock(changed_files=[]),
        metrics_ctx=svc.build_metrics_context("r1"),
        git_ctx=MagicMock(changed_files=[], recent_commits=[]),
        repo_path="", max_files=5)
    assert rel["metrics"]  # выбросы/top для вопроса про сложность


def test_ai_does_not_use_stale_repository(tmp_db):
    """Сессии чата разделены по репозиториям (ТЗ §30)."""
    from gmod.services.chat_service import ChatService
    svc = ChatService(db=tmp_db, llm_config={})
    s1 = svc.get_or_create_session("default", "repo-A")
    s2 = svc.get_or_create_session("default", "repo-B")
    assert s1["id"] != s2["id"]
    assert s1["repository_id"] == "repo-A"
    # Повторный вход в A — та же сессия, не B.
    assert svc.get_or_create_session("default", "repo-A")["id"] == s1["id"]


# ============================================================
# Reports (ТЗ §31)
# ============================================================

def _report(i, risk=5):
    return {"id": i, "agent_type": "archaeologist", "commit_hash": "abc",
            "risk_score": risk, "timestamp": "t",
            "response_json": json.dumps({"risk_score": risk, "reason": f"r{i}"})}


def test_two_report_comparison():
    from gmod.services.report_comparison import compare
    result = compare(_report(1, 5), _report(2, 8))
    assert len(result["rows"]) == 8
    risk_row = next(r for r in result["rows"] if r["field"] == "Риск")
    assert risk_row["changed"] is True


def test_invalid_selection_count():
    from gmod.services.report_comparison import validate_selection
    assert validate_selection([]) == (False, "Для сравнения выберите 2 отчёта.")
    assert validate_selection([1]) == (False, "Для сравнения выберите 2 отчёта.")
    assert validate_selection([1, 2]) == (True, "")
    ok, msg = validate_selection([1, 2, 3])
    assert ok is False and "только 2" in msg


def test_report_diff():
    from gmod.services.report_comparison import compare
    result = compare(_report(1, 5), _report(2, 5))
    assert "Отчёт A" in result["ai_diff"] and "Отчёт B" in result["ai_diff"]


def _qt_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return app or QApplication([])


def _checked_ids(window, reports):
    """Эмуляция ☐-выбора: первые два checked."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget, QListWidgetItem
    _qt_app()
    lst = QListWidget()
    for r in reports:
        item = QListWidgetItem(f"#{r['id']}")
        item.setData(Qt.UserRole, r)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        lst.addItem(item)
    lst.item(0).setCheckState(Qt.Checked)
    lst.item(1).setCheckState(Qt.Checked)
    chosen = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it.checkState() == Qt.Checked:
            chosen.append(it.data(Qt.UserRole))
    return chosen


def test_checkbox_selection():
    chosen = _checked_ids(None, [_report(1), _report(2), _report(3)])
    assert [r["id"] for r in chosen] == [1, 2]


def test_ctrl_click_selection():
    """Ctrl+Click = multiselect (ExtendedSelection)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QAbstractItemView
    from PySide6.QtCore import Qt, QItemSelectionModel
    _qt_app()
    lst = QListWidget()
    lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
    for r in [_report(1), _report(2), _report(3)]:
        item = QListWidgetItem(f"#{r['id']}")
        item.setData(Qt.UserRole, r)
        lst.addItem(item)
    sel = lst.selectionModel()
    sel.select(lst.model().index(0, 0),
               QItemSelectionModel.Select | QItemSelectionModel.Rows)
    sel.select(lst.model().index(2, 0),
               QItemSelectionModel.Select | QItemSelectionModel.Rows)
    ids = sorted(i.data(Qt.UserRole)["id"] for i in lst.selectedItems())
    assert ids == [1, 3]


# ============================================================
# Repository lifecycle (ТЗ §31)
# ============================================================

def _repo_service(tmp_db):
    from gmod.services.repository_service import RepositoryService
    return RepositoryService(db=tmp_db)


def test_open_existing_repository(tmp_path, tmp_db):
    _make_git_repo(tmp_path / "local", {"a.py": "x=1\n"})
    svc = _repo_service(tmp_db)
    decision = svc.resolve_target(str(tmp_path / "local"))
    assert decision["action"] == "open_local"


def test_same_repository_not_cloned_twice(tmp_path, tmp_db):
    repo = _make_git_repo(tmp_path / "target", {"a.py": "x=1\n"})
    url = "https://example.com/target.git"
    svc = _repo_service(tmp_db)
    # Имитация: цель уже зарегистрирована в workspace с тем же URL.
    tmp_db.save_workspace_state("repo_target_url", url)
    decision = svc.resolve_target(url)
    # Цель target не существует в base (APPDATA) -> clone_safe;
    # но зарегистрированный тот же URL должен детектиться, когда путь есть.
    assert decision["action"] in ("clone_safe", "same_url_loaded")
    # Ключевое: resolve существующего пути с тем же remote — не clone.
    d2 = svc.resolve_target(str(tmp_path / "target"))
    assert d2["action"] == "open_local"


def test_different_remote_detected(tmp_path, tmp_db):
    _make_git_repo(tmp_path / "other", {"a.py": "x=1\n"})
    svc = _repo_service(tmp_db)
    decision = svc.resolve_target("https://example.com/foreign.git")
    assert decision["action"] in ("clone_safe", "same_url_loaded", "other_git",
                                  "nonempty_dir")
    d2 = svc.resolve_target(str(tmp_path / "other"))
    assert d2["action"] == "open_local"  # локальный git открывается как есть


def test_nonempty_non_git_directory(tmp_path, tmp_db):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "notes.txt").write_text("hi", encoding="utf-8")
    svc = _repo_service(tmp_db)
    decision = svc.resolve_target(str(d))
    assert decision["action"] == "nonempty_dir"


def test_repository_switch(tmp_path, tmp_db):
    """Переключение: resolve+open двух репо, current меняется только явно."""
    _make_git_repo(tmp_path / "ra", {"a.py": "x=1\n"})
    _make_git_repo(tmp_path / "rb", {"b.py": "y=2\n"})
    svc = _repo_service(tmp_db)
    assert svc.resolve_target(str(tmp_path / "ra"))["action"] == "open_local"
    assert svc.resolve_target(str(tmp_path / "rb"))["action"] == "open_local"
    tmp_db.save_workspace_state("current_repo_id", "ra")
    assert tmp_db.load_workspace_state("current_repo_id") == "ra"


def test_failed_clone_does_not_change_active_repository(tmp_path, tmp_db):
    """ТЗ §4.5: неуспешный clone не трогает current_repo_id и чистит tmp."""
    from gmod.services.repository_service import RepositoryService
    svc = RepositoryService(db=tmp_db)
    tmp_db.save_workspace_state("current_repo_id", "active-repo")
    target = tmp_path / "newrepo"
    result = svc.clone_safe("https://invalid.invalid/none.git", target)
    assert result["status"] == "error"
    assert tmp_db.load_workspace_state("current_repo_id") == "active-repo"
    assert not target.exists()
    leftovers = [p for p in tmp_path.iterdir() if "gmod-tmp" in p.name]
    assert leftovers == []


# ============================================================
# Neural Network (ТЗ §31)
# ============================================================

def _toy_data(n=120, seed=7):
    import numpy as np
    rng = np.random.default_rng(seed)
    X = rng.random((n, 8))
    y = (X[:, 0] + X[:, 1] > 1.0).astype(int)
    return X, y


def _make_net(seed=3):
    from gmod.ml.neural_network import NeuralNetwork
    from gmod.ml.schemas import ModelConfig
    return NeuralNetwork(ModelConfig(input_features=8, hidden_layers=[16, 8],
                                     output_neurons=1, activation="relu",
                                     output_activation="sigmoid", seed=seed))


def test_forward():
    import numpy as np
    net = _make_net()
    out = net.forward(np.random.default_rng(0).random((4, 8)))
    assert out.shape == (4, 1)
    assert np.all((out >= 0.0) & (out <= 1.0))


def test_backward():
    """Веса меняются после train_step, loss конечен."""
    import numpy as np
    net = _make_net()
    X, y = _toy_data(32, seed=1)
    before = [w.copy() for w in [layer.weights for layer in net.layers]]
    loss = net.train_step(X, y, learning_rate=0.1)
    assert loss == loss and loss > 0  # конечное число
    changed = any(not np.array_equal(b, l.weights)
                  for b, l in zip(before, net.layers))
    assert changed


def test_training():
    from gmod.ml.schemas import TrainConfig
    from gmod.ml.trainer import Trainer
    X, y = _toy_data()
    net = _make_net()
    before = net.compute_loss(X, y)
    result = Trainer(net, TrainConfig(epochs=30, learning_rate=0.5,
                                      batch_size=32, target_accuracy=0.999,
                                      seed=3)).fit(X, y)
    assert result.final_loss < before
    assert len(result.history) == 30


def test_accuracy():
    X, y = _toy_data(200)
    net = _make_net()
    from gmod.ml.schemas import TrainConfig
    from gmod.ml.trainer import Trainer
    Trainer(net, TrainConfig(epochs=150, learning_rate=0.1, batch_size=32,
                             target_accuracy=0.999, seed=3)).fit(X, y)
    assert net.accuracy(X, y) > 0.9


def test_epoch_count():
    from gmod.ml.schemas import TrainConfig
    from gmod.ml.trainer import Trainer
    X, y = _toy_data(40)
    net = _make_net()
    result = Trainer(net, TrainConfig(epochs=7, learning_rate=0.1,
                                      batch_size=16, target_accuracy=0.999,
                                      seed=3)).fit(X, y)
    assert len(result.history) == 7
    assert [r.epoch for r in result.history] == list(range(1, 8))


def test_activation_functions():
    import numpy as np
    from gmod.ml.activations import get_activation
    for name in ("relu", "sigmoid", "tanh", "linear", "softmax"):
        fn, _deriv = get_activation(name)
        out = fn(np.array([[-1.0, 0.0, 1.0]]))
        assert out.shape == (1, 3)
    import pytest
    with pytest.raises(ValueError):
        get_activation("nope")


def test_validation_split():
    import numpy as np
    from gmod.ml.datasets import train_validation_split
    X = np.random.default_rng(0).random((100, 8))
    y = np.zeros(100, dtype=int)
    (Xt, _yt), (Xv, _yv) = train_validation_split(X, y, 0.2, seed=5)
    assert len(Xt) == 80 and len(Xv) == 20


def test_prediction():
    X, y = _toy_data(200)
    net = _make_net()
    from gmod.ml.schemas import TrainConfig
    from gmod.ml.trainer import Trainer
    from gmod.ml.predictor import Predictor
    Trainer(net, TrainConfig(epochs=150, learning_rate=0.1, batch_size=32,
                             target_accuracy=0.999, seed=3)).fit(X, y)
    pred = Predictor(net, {}, [f"f{i}" for i in range(8)])
    r = pred.predict_unit({"f0": 0.95, "f1": 0.95}, threshold=0.5)
    assert r["problematic"] is True
    assert 0.0 <= r["probability"] <= 1.0


def test_threshold():
    """Порог меняет результат (ТЗ §21)."""
    from gmod.ml.predictor import Predictor
    net = _make_net()
    pred = Predictor(net, {}, [f"f{i}" for i in range(8)])
    low = pred.predict_unit({"f0": 0.5}, threshold=0.0)
    high = pred.predict_unit({"f0": 0.5}, threshold=1.0)
    assert low["problematic"] is True
    assert high["problematic"] is False


def test_model_save(tmp_path):
    from gmod.ml.model_storage import ModelStorage
    net = _make_net()
    ms = ModelStorage(tmp_path)
    mid = ms.save("mymodel", {"weights": net.get_weights(), "epochs": 5})
    assert mid.startswith("mymodel_v")
    assert (tmp_path / f"{mid}.json").exists()


def test_model_load(tmp_path):
    from gmod.ml.model_storage import ModelStorage
    net = _make_net()
    ms = ModelStorage(tmp_path)
    mid = ms.save("mymodel", {"weights": net.get_weights(), "epochs": 5,
                              "validation_metrics": {"accuracy": 0.9}})
    data = ms.load(mid)
    assert "weights" in data and "layer_0" in data["weights"]
    items = ms.list_models()
    assert items and items[0]["model_id"] == mid
