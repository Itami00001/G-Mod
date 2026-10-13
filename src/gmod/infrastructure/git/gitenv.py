"""Поиск и подключение git.exe: системный или встроенный portable-git.

GitPython — только обёртка, ей нужен бинарь git. На чистой машине его
может не быть: тогда используем vendor/portable-git (dev) или
{app}/portable-git (установленная версия).
"""

import logging
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BUNDLED_GIT: Optional[str] = None


def _candidate_paths() -> list:
    """Возможные места встроенного git.exe (не системный PATH)."""
    out = []
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            out.append(Path(base) / "portable-git" / "cmd" / "git.exe")
            out.append(Path(base) / "_internal" / "portable-git" / "cmd" / "git.exe")
        # Рядом с exe (onedir) и рядом с проектом (dev).
        out.append(Path(sys.executable).parent / "portable-git" / "cmd" / "git.exe")
        here = Path(__file__).resolve()
        out.append(here.parent.parent.parent.parent / "vendor" / "portable-git" / "cmd" / "git.exe")
    except Exception:
        pass
    return out


def find_git_exe() -> str:
    """Путь к git.exe: системный PATH, иначе встроенный. '' если нет."""
    system_git = shutil.which("git")
    if system_git:
        return system_git
    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                return str(candidate)
        except Exception:
            continue
    return ""


def ensure_git() -> str:
    """Гарантировать git для GitPython. Возвращает путь или ''.

    Устанавливает GIT_PYTHON_GIT_EXECUTABLE, чтобы GitPython брал
    именно этот бинарь.
    """
    global _BUNDLED_GIT
    path = find_git_exe()
    if path:
        try:
            import git as _git
            _git.Git.GIT_PYTHON_GIT_EXECUTABLE = path
        except Exception:
            pass
        os.environ.setdefault("GIT_PYTHON_GIT_EXECUTABLE", path)
        if _BUNDLED_GIT != path:
            logger.info("git: используется %s", path)
            _BUNDLED_GIT = path
    else:
        logger.error("git: git.exe не найден (ни системный, ни встроенный)")
    return path


def clear_readonly(path: str) -> None:
    """Снять read-only (pack-файлы git) — против WinError 5 при удалении."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass


def rmtree_safe(path, retries: int = 3) -> bool:
    """Удаление дерева с повторениями и снятием read-only (WinError 5)."""
    import shutil as _shutil

    target = Path(path)

    def _onerror(func, p, _exc):
        clear_readonly(p)
        try:
            func(p)
        except Exception:
            pass

    for attempt in range(1, retries + 1):
        try:
            if not target.exists() and not target.is_symlink():
                return True
            _shutil.rmtree(target, onerror=_onerror)
            return not target.exists()
        except Exception as e:
            logger.warning("rmtree %s попытка %d: %s", target, attempt, e)
            time.sleep(0.5 * attempt)
    return not target.exists()


def cleanup_stale_tmp(directories, max_age_hours: int = 1) -> int:
    """Удаление *.gmod-tmp-* старше N часов (при старте приложения)."""
    removed = 0
    now = time.time()
    for directory in directories:
        try:
            base = Path(directory)
            if not base.is_dir():
                continue
            for child in base.iterdir():
                try:
                    if ".gmod-tmp-" not in child.name:
                        continue
                    age_hours = (now - child.stat().st_mtime) / 3600
                    if age_hours >= max_age_hours and rmtree_safe(child):
                        removed += 1
                        logger.info("tmp cleanup: удалён %s", child)
                except Exception:
                    continue
        except Exception:
            continue
    return removed
