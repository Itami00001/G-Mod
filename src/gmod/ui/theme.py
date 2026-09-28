"""ThemeManager — единая дизайн-система (ТЗ §23-24).

QSS: resources/styles/gmod.qss. Локальные setStyleSheet в MainWindow
постепенно выводятся; новые виджеты стилизуются только через QSS
(objectName + селекторы).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

THEME_RELATIVE = Path("resources") / "styles" / "gmod.qss"


def _candidate_paths():
    """Все места, где может лежать gmod.qss (dev + frozen exe)."""
    here = Path(__file__).resolve()
    yield here.parent.parent.parent / THEME_RELATIVE  # dev: src/../..
    try:
        import sys
        base = getattr(sys, "_MEIPASS", None)
        if base:
            yield Path(base) / THEME_RELATIVE
            yield Path(base) / "_internal" / THEME_RELATIVE
    except Exception:
        pass


class ThemeManager:
    """Применение единой темы приложения."""

    _cached_qss: str = ""

    @classmethod
    def qss_path(cls) -> Path | None:
        """Первый существующий путь к QSS."""
        for candidate in _candidate_paths():
            try:
                if candidate.is_file():
                    return candidate
            except Exception:
                pass
        return None

    @classmethod
    def qss(cls) -> str:
        """Текст QSS (кэшируется)."""
        if not cls._cached_qss:
            path = cls.qss_path()
            if path is None:
                logger.error("ThemeManager: gmod.qss не найден")
                return ""
            try:
                cls._cached_qss = path.read_text(encoding="utf-8")
                logger.info("ThemeManager: QSS загружен (%s)", path)
            except Exception as e:
                logger.error("ThemeManager: нет QSS %s: %s", path, e)
                cls._cached_qss = ""
        return cls._cached_qss

    @classmethod
    def apply(cls, app) -> None:
        """Применить тему ко всему приложению."""
        qss = cls.qss()
        if qss:
            app.setStyleSheet(qss)
            logger.info("ThemeManager: тема применена")

    @classmethod
    def reload(cls, app) -> None:
        """Перечитать QSS с диска и применить (для разработки)."""
        cls._cached_qss = ""
        cls.apply(app)
