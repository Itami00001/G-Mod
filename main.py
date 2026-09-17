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
    # Создание необходимых директорий
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting GMod application")
    
    # Создание приложения Qt
    app = QApplication(sys.argv)
    app.setApplicationName("GMod")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("GMod Team")
    
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
