"""Тесты сброса сессии и git-окружения (проблемы 2-3).

- gitenv: ensure_git, rmtree_safe с read-only, cleanup_stale_tmp по возрасту.
- clone_safe: retry после WinError-подобных ошибок (локальный клон, без сети).
- Reset: очистка виджетов, repo None, URL виден, только Чат, чат цел.
- Restore: снапшот roundtrip + возврат вида 1:1.
"""

import os
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    from gmod.infrastructure.db.database import Database
    return Database(tmp_path / "reset.db")


# ---------------- gitenv ----------------

def test_ensure_git_returns_path():
    from gmod.infrastructure.git.gitenv import ensure_git, find_git_exe
    path = ensure_git()
    assert path  # на машине разработчика системный git есть
    assert os.environ.get("GIT_PYTHON_GIT_EXECUTABLE") == path
    assert find_git_exe() == path


def test_rmtree_safe_readonly(tmp_path):
    """WinError 5-сценарий: read-only файлы удаляются со снятием флага."""
    from gmod.infrastructure.git.gitenv import rmtree_safe
    target = tmp_path / "pack"
    target.mkdir()
    locked = target / "a.idx"
    locked.write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)
    assert rmtree_safe(target) is True
    assert not target.exists()


def test_cleanup_stale_tmp_age(tmp_path):
    """Удаляются только *.gmod-tmp-* старше часа; свежие и чужие целы."""
    import time
    from gmod.infrastructure.git.gitenv import cleanup_stale_tmp
    old = tmp_path / "r.gmod-tmp-old"
    old.mkdir()
    os.utime(old, (0, 0))
    fresh = tmp_path / "r.gmod-tmp-new"
    fresh.mkdir()
    other = tmp_path / "keepme"
    other.mkdir()
    removed = cleanup_stale_tmp([str(tmp_path)], max_age_hours=1)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists() and other.exists()


def test_clone_safe_retries_then_succeeds(tmp_path, tmp_db, monkeypatch):
    """Две неудачи (WinError 5) -> третья попытка успешна, tmp убран."""
    import git
    from gmod.services.repository_service import RepositoryService

    src = tmp_path / "src"
    src.mkdir()
    repo = git.Repo.init(src)
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    repo.index.add(["a.py"])
    repo.index.commit("init")

    real_clone = git.Repo.clone_from
    calls = {"n": 0}

    def flaky(url, to_path, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(13, "Отказано в доступе", str(to_path))
        return real_clone(url, to_path, *args, **kwargs)

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(flaky))
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)

    svc = RepositoryService(db=tmp_db)
    target = tmp_path / "repos" / "src"
    result = svc.clone_safe(f"file:///{src.as_posix()}", target, retries=3)
    assert result["status"] == "success", result
    assert calls["n"] == 3
    assert target.is_dir()
    leftovers = [p for p in target.parent.iterdir() if ".gmod-tmp-" in p.name]
    assert leftovers == []


def test_clone_safe_no_git(monkeypatch, tmp_db):
    """Без git.exe — понятная ошибка, current_repo_id не тронут."""
    import gmod.infrastructure.git.gitenv as gitenv
    from gmod.services.repository_service import RepositoryService
    monkeypatch.setattr(gitenv, "ensure_git", lambda: "")
    tmp_db.save_workspace_state("current_repo_id", "keep-me")
    svc = RepositoryService(db=tmp_db)
    result = svc.clone_safe("https://example.com/x.git", Path("/tmp/nope"))
    assert result["status"] == "error"
    assert "git.exe" in result["message"]
    assert tmp_db.load_workspace_state("current_repo_id") == "keep-me"


# ---------------- snapshot roundtrip (без UI) ----------------

def test_session_snapshot_roundtrip(tmp_db, tmp_path, monkeypatch):
    """Снапшот сохраняется и читается 1:1, секретов нет."""
    # snapshot_path — staticmethod; патчим строкой (надёжно для staticmethod).
    monkeypatch.setattr("gmod.services.backup_service.BackupService.snapshot_path",
                        staticmethod(lambda: tmp_path / "session_snapshot.json"))
    from gmod.services.backup_service import BackupService
    svc = BackupService(db=tmp_db)
    payload = {"workspace": {"id": "default"}, "tabs": [{"tab_key": "Чат"}],
               "filters": {"metrics_search": "q"}, "chat_session_id": "s1",
               "repo_id": "r1"}
    path = svc.save_session_snapshot(payload)
    loaded = svc.load_session_snapshot()
    assert loaded["repo_id"] == "r1"
    assert loaded["chat_session_id"] == "s1"
    assert loaded["tabs"][0]["tab_key"] == "Чат"
    blob = Path(path).read_text(encoding="utf-8")
    assert "gsk_" not in blob and "sk-ant-" not in blob
    assert svc.load_session_snapshot() is not None
    # Нет файла — None, а не исключение.
    Path(path).unlink()
    assert svc.load_session_snapshot() is None


# ---------------- reset/restore в UI (offscreen) ----------------

def _make_window(tmp_db, monkeypatch):
    """MainWindow на временной БД, модалки автозакрыты."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.Ok))
    import gmod.infrastructure.db.database as dbm
    old_singleton = dbm._db_instance
    dbm._db_instance = tmp_db
    from gmod.config import settings as settings_mod
    settings_mod.reset_settings()
    from gmod.ui.main_window import MainWindow
    w = MainWindow()
    w.show()  # offscreen: нужно для корректного isVisible() виджетов
    return app, w, old_singleton, dbm


def _make_repo(path: Path):
    import git
    path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(path)
    (path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    repo.index.add(["a.py"])
    repo.index.commit("init")
    return repo


def test_reset_clears_ui_keeps_db_and_chat(tmp_path, tmp_db, monkeypatch):
    import gmod.services.backup_service as mod
    monkeypatch.setattr(mod, "backups_dir", lambda: tmp_path / "backups")
    (tmp_path / "backups").mkdir(exist_ok=True)

    app, w, old_singleton, dbm = _make_window(tmp_db, monkeypatch)
    try:
        from PySide6.QtCore import Qt
        repo_dir = tmp_path / "proj"
        _make_repo(repo_dir)
        w._switch_to_repo({"path": str(repo_dir), "url": ""})
        app.processEvents()
        assert w._get_current_repo_id() == "proj"
        assert w.metrics_model.rowCount() > 0

        # Грязним состояние: отчёт, чекбокс, пути, прогноз.
        w.db.save_ai_report("proj", "c1", "archaeologist", "p",
                            '{"risk_score": 5}', 5)
        w._refresh_reports()
        assert w.reports_list.count() >= 1
        w.reports_list.item(0).setCheckState(Qt.Checked)
        w.func_paths_list.addItem("a.py")
        chat_cards_before = w.chat_cards_layout.count()

        w._on_reset_workspace()
        app.processEvents()

        # Экран как при первом запуске...
        assert w.metrics_model.rowCount() == 0
        assert w.reports_list.count() == 0
        assert w.files_tree.model().rowCount() == 0
        assert w._get_current_repo_id() in ("", None)
        assert w.repo_url_widget.isVisible()
        tabs = [w.central_tabs.tabText(i) for i in range(w.central_tabs.count())]
        assert tabs == ["Чат"]
        # ...чат цел, БД цела.
        assert w.chat_cards_layout.count() == chat_cards_before
        with tmp_db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM raw_metrics WHERE repo_id='proj'")
            assert cur.fetchone()[0] > 0
            cur.execute("SELECT COUNT(*) FROM ai_reports WHERE repo_id='proj'")
            assert cur.fetchone()[0] >= 1
        # Снапшот сохранён до сброса.
        from gmod.services.backup_service import BackupService
        snap = BackupService(db=tmp_db).load_session_snapshot()
        assert snap and snap["repo_id"] == "proj"
        w.close()
    finally:
        dbm._db_instance = old_singleton


def test_restore_session_roundtrip(tmp_path, tmp_db, monkeypatch):
    import gmod.services.backup_service as mod
    monkeypatch.setattr(mod, "backups_dir", lambda: tmp_path / "backups")
    (tmp_path / "backups").mkdir(exist_ok=True)

    app, w, old_singleton, dbm = _make_window(tmp_db, monkeypatch)
    try:
        repo_dir = tmp_path / "proj2"
        _make_repo(repo_dir)
        w._switch_to_repo({"path": str(repo_dir), "url": ""})
        app.processEvents()
        assert w._get_current_repo_id() == "proj2"
        session_before = w._chat_session_id

        w._on_reset_workspace()
        app.processEvents()
        assert w._get_current_repo_id() in ("", None)

        w._on_restore_session()
        app.processEvents()
        assert w._get_current_repo_id() == "proj2"
        assert w._chat_session_id == session_before
        assert w.metrics_model.rowCount() > 0
        w.close()
    finally:
        dbm._db_instance = old_singleton


def _make_repo_with(path: Path, files: dict):
    """Git-репозиторий с произвольным набором файлов {rel: content}."""
    import git
    path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(path)
    rels = []
    for rel, content in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        rels.append(rel)
    repo.index.add(rels)
    repo.index.commit("init")
    return repo


def test_switch_python_to_js_recomputes_metrics(tmp_path, tmp_db, monkeypatch):
    """Регрессия: после смены репозитория метрики считаются для нового
    (в т.ч. JS-репозитория), а не остаются пустыми."""
    app, w, old_singleton, dbm = _make_window(tmp_db, monkeypatch)
    try:
        py = tmp_path / "pylib"
        js = tmp_path / "jslib"
        _make_repo_with(py, {"a.py": "def fa():\n    if True:\n        return 1\n"})
        _make_repo_with(js, {"a.js": "export function fb(x) {\n"
                                    "  if (x) return 1;\n"
                                    "  return 0;\n}\n"})

        w._switch_to_repo({"path": str(py), "url": ""})
        app.processEvents()
        assert w._get_current_repo_id() == "pylib"
        assert w.metrics_model.rowCount() > 0

        w._switch_to_repo({"path": str(js), "url": ""})
        app.processEvents()
        assert w._get_current_repo_id() == "jslib"
        assert w.metrics_model.rowCount() > 0, w.metrics_status.text()
        w.close()
    finally:
        dbm._db_instance = old_singleton


def test_switch_unsupported_repo_reports_reason(tmp_path, tmp_db, monkeypatch):
    """Если в репозитории нет поддерживаемых языков, статус объясняет
    причину, а не показывает молчаливое «0 метрик»."""
    app, w, old_singleton, dbm = _make_window(tmp_db, monkeypatch)
    try:
        odd = tmp_path / "odd"
        _make_repo_with(odd, {"data.bin": "x", "notes.custom": "y"})
        w._switch_to_repo({"path": str(odd), "url": ""})
        app.processEvents()
        assert w._get_current_repo_id() == "odd"
        assert w.metrics_model.rowCount() == 0
        assert "рассчитать" in w.metrics_status.text()
        w.close()
    finally:
        dbm._db_instance = old_singleton

