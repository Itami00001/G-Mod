"""Главное окно приложения."""

import logging
from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QDockWidget,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QPushButton,
    QLabel, QFrame, QVBoxLayout, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPalette, QColor
# import qdarktheme  # Temporarily disabled - requires Python 3.11+

from gmod.config.logging_config import setup_logging
from gmod.config.constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    DEFAULT_LEFT_DOCK_WIDTH, DEFAULT_RIGHT_DOCK_WIDTH
)
from gmod.infrastructure.db.database import get_database

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Главное окно приложения GMod."""
    
    def __init__(self):
        """Инициализация главного окна."""
        super().__init__()
        self.db = get_database()
        self._restore_workspace_state()
        self._setup_ui()
        self._apply_theme()
    
    def _restore_workspace_state(self) -> None:
        """Восстановление состояния рабочей области."""
        # Восстановление размеров окна
        width = self.db.load_workspace_state("window_width")
        height = self.db.load_workspace_state("window_height")
        
        if width and height:
            self.resize(int(width), int(height))
        else:
            self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        # Восстановление позиции окна
        x = self.db.load_workspace_state("window_x")
        y = self.db.load_workspace_state("window_y")
        
        if x and y:
            self.move(int(x), int(y))
    
    def _setup_ui(self) -> None:
        """Настройка UI."""
        self.setWindowTitle("GMod - Git Archaeologist")
        self.setMinimumSize(800, 600)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Центральная область с вкладками
        self.central_tabs = QTabWidget()
        self.central_tabs.setTabsClosable(True)
        self.central_tabs.setMovable(True)
        main_layout.addWidget(self.central_tabs, 1)
        
        # Создание шторок
        self._create_left_dock()
        self._create_right_dock()
        
        # Создание меню
        self._create_menu()
        
        # Статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
        
        # Создание вкладок
        self._create_central_tabs()
    
    def _create_left_dock(self) -> None:
        """Создание левой шторки."""
        self.left_dock = QDockWidget("Навигация", self)
        self.left_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.left_dock.setFeatures(
            QDockWidget.DockWidgetClosable | 
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        
        # Восстановление ширины
        width = self.db.load_workspace_state("left_dock_width")
        if width:
            self.left_dock.setMinimumWidth(int(width))
        else:
            self.left_dock.setMinimumWidth(DEFAULT_LEFT_DOCK_WIDTH)
        
        # Контент шторки
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Секция "Анализ"
        analysis_section = self._create_collapsible_section("Анализ")
        analysis_layout = analysis_section.findChild(QVBoxLayout, "section_layout")
        
        metrics_btn = QPushButton("Метрики")
        metrics_btn.clicked.connect(lambda: self._switch_to_tab("Метрики"))
        analysis_layout.addWidget(metrics_btn)
        
        modes_btn = QPushButton("Режимы работы")
        modes_btn.clicked.connect(lambda: self._switch_to_tab("Анализ"))
        analysis_layout.addWidget(modes_btn)
        
        left_layout.addWidget(analysis_section)
        
        # Секция "Данные"
        data_section = self._create_collapsible_section("Данные")
        data_layout = data_section.findChild(QVBoxLayout, "section_layout")
        
        reports_btn = QPushButton("Отчёты")
        reports_btn.clicked.connect(lambda: self._switch_to_tab("Отчёты"))
        data_layout.addWidget(reports_btn)
        
        history_btn = QPushButton("История анализов")
        history_btn.clicked.connect(lambda: self._switch_to_tab("История"))
        data_layout.addWidget(history_btn)
        
        left_layout.addWidget(data_section)
        
        # Секция "Проект"
        project_section = self._create_collapsible_section("Проект")
        project_layout = project_section.findChild(QVBoxLayout, "section_layout")
        
        overview_btn = QPushButton("Обзор проекта")
        overview_btn.clicked.connect(lambda: self._switch_to_tab("Обзор"))
        project_layout.addWidget(overview_btn)
        
        left_layout.addWidget(project_section)
        
        # Секция "Система"
        system_section = self._create_collapsible_section("Система")
        system_layout = system_section.findChild(QVBoxLayout, "section_layout")
        
        settings_btn = QPushButton("Быстрые настройки")
        settings_btn.clicked.connect(lambda: self._switch_to_tab("Настройки"))
        system_layout.addWidget(settings_btn)
        
        gmod_btn = QPushButton("Использовать GMod")
        gmod_btn.clicked.connect(self._on_gmod_button)
        system_layout.addWidget(gmod_btn)
        
        left_layout.addWidget(system_section)
        
        left_layout.addStretch()
        
        self.left_dock.setWidget(left_content)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)
    
    def _create_right_dock(self) -> None:
        """Создание правой шторки."""
        self.right_dock = QDockWidget("Репозиторий", self)
        self.right_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.right_dock.setFeatures(
            QDockWidget.DockWidgetClosable | 
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        
        # Восстановление ширины
        width = self.db.load_workspace_state("right_dock_width")
        if width:
            self.right_dock.setMinimumWidth(int(width))
        else:
            self.right_dock.setMinimumWidth(DEFAULT_RIGHT_DOCK_WIDTH)
        
        # Контент шторки
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Поле Git URL
        url_layout = QHBoxLayout()
        url_label = QLabel("Git URL:")
        self.url_input = QPushButton("Загрузить репозиторий")
        self.url_input.clicked.connect(self._on_load_repository)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        right_layout.addLayout(url_layout)
        
        # Вкладки репозитория
        self.repo_tabs = QTabWidget()
        
        # Заглушки для вкладок
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        files_layout.addWidget(QLabel("Файлы (заглушка)"))
        self.repo_tabs.addTab(files_tab, "Файлы")
        
        stack_tab = QWidget()
        stack_layout = QVBoxLayout(stack_tab)
        stack_layout.addWidget(QLabel("Стек (заглушка)"))
        self.repo_tabs.addTab(stack_tab, "Стек")
        
        readme_tab = QWidget()
        readme_layout = QVBoxLayout(readme_tab)
        readme_layout.addWidget(QLabel("README (заглушка)"))
        self.repo_tabs.addTab(readme_tab, "README")
        
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        info_layout.addWidget(QLabel("Инфо (заглушка)"))
        self.repo_tabs.addTab(info_tab, "Инфо")
        
        right_layout.addWidget(self.repo_tabs)
        
        self.right_dock.setWidget(right_content)
        self.addDockWidget(Qt.RightDockWidgetArea, self.right_dock)
    
    def _create_collapsible_section(self, title: str) -> QFrame:
        """Создание сворачиваемой секции."""
        section = QFrame()
        section.setFrameStyle(QFrame.StyledPanel)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок секции
        header = QPushButton(title)
        header.setCheckable(True)
        header.setChecked(True)
        header.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                font-weight: bold;
                border: none;
                background: #f0f0f0;
            }
            QPushButton:checked {
                background: #e0e0e0;
            }
        """)
        header.clicked.connect(lambda checked: self._toggle_section(section, checked))
        layout.addWidget(header)
        
        # Контент секции
        content_layout = QVBoxLayout()
        content_layout.setObjectName("section_layout")
        content_layout.setContentsMargins(5, 5, 5, 5)
        layout.addLayout(content_layout)
        
        return section
    
    def _toggle_section(self, section: QFrame, checked: bool) -> None:
        """Переключение видимости секции."""
        content_layout = section.findChild(QVBoxLayout, "section_layout")
        if content_layout:
            for i in range(content_layout.count()):
                widget = content_layout.itemAt(i).widget()
                if widget:
                    widget.setVisible(checked)
    
    def _create_central_tabs(self) -> None:
        """Создание центральных вкладок."""
        # Вкладка "Чат"
        chat_tab = self._create_chat_tab()
        self.central_tabs.addTab(chat_tab, "Чат")
        
        # Вкладка "Метрики"
        metrics_tab = QWidget()
        metrics_layout = QVBoxLayout(metrics_tab)
        metrics_layout.addWidget(QLabel("Метрики (заглушка)"))
        self.central_tabs.addTab(metrics_tab, "Метрики")
        
        # Вкладка "Граф"
        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)
        graph_layout.addWidget(QLabel("Граф (заглушка)"))
        self.central_tabs.addTab(graph_tab, "Граф")
        
        # Вкладка "Отчёты"
        reports_tab = QWidget()
        reports_layout = QVBoxLayout(reports_tab)
        reports_layout.addWidget(QLabel("Отчёты (заглушка)"))
        self.central_tabs.addTab(reports_tab, "Отчёты")
        
        # Вкладка "Анализ"
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.addWidget(QLabel("Анализ (заглушка)"))
        self.central_tabs.addTab(analysis_tab, "Анализ")
    
    def _create_chat_tab(self) -> QWidget:
        """Создание вкладки чата."""
        chat_tab = QWidget()
        chat_layout = QVBoxLayout(chat_tab)
        
        # Область истории диалога
        chat_history = QLabel("AI: Привет! Загрузи репозиторий, чтобы начать.")
        chat_history.setWordWrap(True)
        chat_history.setStyleSheet("padding: 10px; background: #f5f5f5; border-radius: 5px;")
        chat_layout.addWidget(chat_history, 1)
        
        # Область ввода
        input_layout = QHBoxLayout()
        
        # Выбор провайдера
        provider_label = QLabel("Провайдер:")
        input_layout.addWidget(provider_label)
        
        # Выбор модели
        model_label = QLabel("Модель:")
        input_layout.addWidget(model_label)
        
        # Кнопка отправки
        send_button = QPushButton("Отправить")
        send_button.clicked.connect(self._on_send_message)
        input_layout.addWidget(send_button)
        
        chat_layout.addLayout(input_layout)
        
        return chat_tab
    
    def _create_menu(self) -> None:
        """Создание меню."""
        menubar = self.menuBar()
        
        # Меню шестерёнки
        gear_menu = menubar.addMenu("⚙ Меню")
        
        # Открыть настройки
        settings_action = QAction("Открыть настройки", self)
        settings_action.triggered.connect(lambda: self._switch_to_tab("Настройки"))
        gear_menu.addAction(settings_action)
        
        # Выбрать тему
        theme_menu = gear_menu.addMenu("Выбрать тему")
        
        dark_theme_action = QAction("Тёмная", self)
        dark_theme_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_menu.addAction(dark_theme_action)
        
        light_theme_action = QAction("Светлая", self)
        light_theme_action.triggered.connect(lambda: self._set_theme("light"))
        theme_menu.addAction(light_theme_action)
        
        system_theme_action = QAction("Системная", self)
        system_theme_action.triggered.connect(lambda: self._set_theme("system"))
        theme_menu.addAction(system_theme_action)
        
        gear_menu.addSeparator()
        
        # Сбросить рабочую область
        reset_action = QAction("Сбросить рабочую область", self)
        reset_action.triggered.connect(self._on_reset_workspace)
        gear_menu.addAction(reset_action)
        
        gear_menu.addSeparator()
        
        # О программе
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._on_about)
        gear_menu.addAction(about_action)
        
        # Закрыть программу
        exit_action = QAction("Закрыть программу", self)
        exit_action.triggered.connect(self.close)
        gear_menu.addAction(exit_action)
    
    def _apply_theme(self) -> None:
        """Применение темы."""
        theme = self.db.load_workspace_state("theme") or "dark"
        self._set_theme(theme)
    
    def _set_theme(self, theme: str) -> None:
        """Установка темы."""
        self.db.save_workspace_state("theme", theme)
        
        # Базовая темная тема (временно заменили qdarktheme)
        if theme == "dark":
            app = QApplication.instance()
            palette = app.palette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
        elif theme == "light":
            app = QApplication.instance()
            app.setPalette(QApplication.style().standardPalette())
        else:  # system
            app = QApplication.instance()
            app.setPalette(QApplication.style().standardPalette())
    
    def _switch_to_tab(self, tab_name: str) -> None:
        """Переключение на вкладку."""
        for i in range(self.central_tabs.count()):
            if self.central_tabs.tabText(i) == tab_name:
                self.central_tabs.setCurrentIndex(i)
                break
    
    def _on_load_repository(self) -> None:
        """Обработка загрузки репозитория."""
        self.status_bar.showMessage("Загрузка репозитория (заглушка)")
        logger.info("Load repository button clicked (stub)")
    
    def _on_send_message(self) -> None:
        """Обработка отправки сообщения."""
        self.status_bar.showMessage("Отправка сообщения (заглушка)")
        logger.info("Send message button clicked (stub)")
    
    def _on_gmod_button(self) -> None:
        """Обработка кнопки GMod - вызов зарезервированного серверного endpoint."""
        try:
            # Зарезервированный endpoint для GMod сервера
            gmod_endpoint = "https://api.gmod.example.com/v1/analyze"
            
            self.status_bar.showMessage("Подключение к GMod серверу...")
            logger.info("Attempting to connect to GMod server endpoint")
            
            # Формируем запрос
            payload = {
                "action": "analyze",
                "workspace_state": {
                    "window_width": self.width(),
                    "window_height": self.height(),
                    "active_tab": self.central_tabs.tabText(self.central_tabs.currentIndex())
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Заглушка для демонстрации - в реальности будет работать
            self.status_bar.showMessage("GMod сервер: endpoint зарезервирован (demo mode)")
            logger.info(f"GMod server endpoint called: {gmod_endpoint} (demo mode)")
            
            # Показываем уведомление пользователю
            QMessageBox.information(
                self,
                "GMod Сервер",
                "GMod серверный endpoint зарезервирован.\n"
                "В полноценной версии здесь будет осуществляться\n"
                "интеграция с облачным сервисом GMod."
            )
            
        except Exception as e:
            self.status_bar.showMessage(f"GMod: ошибка - {str(e)}")
            logger.error(f"GMod endpoint error: {e}")
    
    def _on_reset_workspace(self) -> None:
        """Обработка сброса рабочей области."""
        self.status_bar.showMessage("Сброс рабочей области (заглушка)")
        logger.info("Reset workspace button clicked (stub)")
    
    def _on_about(self) -> None:
        """Обработка 'О программе'."""
        self.status_bar.showMessage("GMod v0.1.0 - Git Archaeologist")
    
    def closeEvent(self, event) -> None:
        """Обработка закрытия окна."""
        # Сохранение состояния
        self.db.save_workspace_state("window_width", str(self.width()))
        self.db.save_workspace_state("window_height", str(self.height()))
        self.db.save_workspace_state("window_x", str(self.x()))
        self.db.save_workspace_state("window_y", str(self.y()))
        self.db.save_workspace_state("left_dock_width", str(self.left_dock.width()))
        self.db.save_workspace_state("right_dock_width", str(self.right_dock.width()))
        
        logger.info("Application closing, workspace state saved")
        event.accept()
