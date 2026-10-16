"""Точка входа в приложение GMod."""

import sys
import logging
from pathlib import Path

# Добавляем src в PYTHONPATH
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gmod.config.logging_config import setup_logging
from gmod.config.constants import DATA_DIR, LOGS_DIR
from gmod.ui.main_window import MainWindow

# Настройка логирования
setup_logging()

logger = logging.getLogger(__name__)


def main():
    """Главная функция приложения."""
    # Создание необходимых директорий в %APPDATA%\GMod
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "repos").mkdir(parents=True, exist_ok=True)

    # Git: системный или встроенный portable-git. Чистка stale tmp.
    from gmod.infrastructure.git.gitenv import (
        cleanup_stale_tmp, ensure_git,
    )
    import tempfile
    _git_path = ensure_git()
    if not _git_path:
        logger.error("git.exe не найден: Git-операции будут недоступны")
    cleanup_stale_tmp([str(DATA_DIR / "repos"),
                       str(Path(tempfile.gettempdir()) / "GModClone")])

    # Санитайзер протухших путей репозиториев (dist\...\repos и т.п.).
    try:
        from gmod.services.repository_service import sanitize_repo_paths
        _san = sanitize_repo_paths()
        if _san.get("removed"):
            logger.warning("sanitize: невалидные привязки удалены: %s",
                           _san["removed"])
    except Exception as e:
        logger.warning("sanitize_repo_paths: %s", e)

    logger.info("Starting GMod application")
    
    # Создание приложения Qt
    app = QApplication(sys.argv)
    app.setApplicationName("GMod")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("GMod Team")

    # Единая дизайн-система (ТЗ §23): ThemeManager + gmod.qss.
    # Индивидуальная тема _set_theme() поверх QSS больше не применяется.
    from gmod.ui.theme import ThemeManager
    ThemeManager.apply(app)

    # Включение high-DPI scaling (современный подход)
    # В PySide6 high-DPI включен по умолчанию, но для совместимости оставим
    
    # Создание и показ главного окна
    window = MainWindow()
    window.show()
    
    logger.info("Main window shown")
    
    # Запуск event loop
    exit_code = app.exec()
    
    logger.info(f"Application exited with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
