"""Главное окно приложения."""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QDockWidget,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QPushButton,
    QLabel, QFrame, QVBoxLayout, QApplication, QMessageBox,
    QComboBox, QTextEdit, QLineEdit, QSplitter, QTableView,
    QHeaderView, QAbstractItemView, QFileDialog, QProgressBar,
    QCheckBox, QSpinBox, QDoubleSpinBox, QScrollArea, QGroupBox,
    QFormLayout, QTabBar, QStyle, QTreeView, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QAction, QIcon, QPalette, QColor, QStandardItemModel, QStandardItem, QFont, QDesktopServices
from PySide6.QtCore import QUrl
# import qdarktheme  # Temporarily disabled - requires Python 3.11+

from gmod.config.logging_config import setup_logging
from gmod.config.constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    DEFAULT_LEFT_DOCK_WIDTH, DEFAULT_RIGHT_DOCK_WIDTH
)
from gmod.infrastructure.db.database import get_database
from gmod.config.settings import get_settings

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Главное окно приложения GMod."""
    
    def __init__(self):
        """Инициализация главного окна."""
        super().__init__()
        self.db = get_database()
        self._restore_window_geometry()
        self._setup_ui()
        self._apply_theme()
        self._restore_last_repository()
        self._restore_tabs_state()
        # Восстанавливаем состояние шторок после инициализации UI
        QTimer.singleShot(0, self._restore_dock_state)
    
    def _restore_last_repository(self) -> None:
        """Восстановление последнего проекта при старте (prompt4 п.10)."""
        try:
            from pathlib import Path

            from gmod.domain.entities import Repository

            repo_id = self.db.load_workspace_state("current_repo_id")
            if not repo_id:
                return
            repo_path = self.db.load_workspace_state(f"repo_{repo_id}_path")
            if not repo_path or not Path(repo_path).exists():
                return
            repo = Repository(
                id=repo_id,
                url=self.db.load_workspace_state(f"repo_{repo_id}_url") or "",
                local_path=repo_path,
                name=Path(repo_path).name,
                default_branch=(
                    self.db.load_workspace_state(f"repo_{repo_id}_branch") or "main"
                ),
            )
            self._populate_repo_dock(repo)
            self.status_bar.showMessage(f"Восстановлен проект: {repo_id}")
        except Exception as e:
            logger.error(f"Error restoring last repository: {e}")

    def _restore_window_geometry(self) -> None:
        """Восстановление геометрии окна."""
        width = self.db.load_workspace_state("window_width")
        height = self.db.load_workspace_state("window_height")
        
        if width and height:
            self.resize(int(width), int(height))
        else:
            self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        x = self.db.load_workspace_state("window_x")
        y = self.db.load_workspace_state("window_y")
        
        if x and y:
            self.move(int(x), int(y))

    def _restore_dock_state(self) -> None:
        """Восстановление видимости и ширины шторок."""
        left_vis = self.db.load_workspace_state("left_dock_visible")
        right_vis = self.db.load_workspace_state("right_dock_visible")
        left_width = self.db.load_workspace_state("left_dock_width")
        right_width = self.db.load_workspace_state("right_dock_width")
        
        if left_width:
            self.left_dock.setMinimumWidth(int(left_width))
        else:
            self.left_dock.setMinimumWidth(DEFAULT_LEFT_DOCK_WIDTH)
        
        if right_width:
            self.right_dock.setMinimumWidth(int(right_width))
        else:
            self.right_dock.setMinimumWidth(DEFAULT_RIGHT_DOCK_WIDTH)
        
        # По умолчанию обе шторки развёрнуты, если состояние не сохранено
        # Пустая строка или None = не сохранено -> True
        left_visible = True if not left_vis else bool(int(left_vis))
        right_visible = True if not right_vis else bool(int(right_vis))
        self.left_dock.setVisible(left_visible)
        self.right_dock.setVisible(right_visible)
        
        # Восстановление видимости и ширины шторок
        left_vis = self.db.load_workspace_state("left_dock_visible")
        right_vis = self.db.load_workspace_state("right_dock_visible")
        left_width = self.db.load_workspace_state("left_dock_width")
        right_width = self.db.load_workspace_state("right_dock_width")
        
        if left_width:
            self.left_dock.setMinimumWidth(int(left_width))
        else:
            self.left_dock.setMinimumWidth(DEFAULT_LEFT_DOCK_WIDTH)
        
        if right_width:
            self.right_dock.setMinimumWidth(int(right_width))
        else:
            self.right_dock.setMinimumWidth(DEFAULT_RIGHT_DOCK_WIDTH)
        
        # По умолчанию обе шторки развёрнуты, если состояние не сохранено
        left_visible = True if left_vis is None else bool(int(left_vis))
        right_visible = True if right_vis is None else bool(int(right_vis))
        self.left_dock.setVisible(left_visible)
        self.right_dock.setVisible(right_visible)
    
    def _setup_ui(self) -> None:
        """Настройка UI."""
        self.setWindowTitle("GMod - Git Archaeologist")
        self.setMinimumSize(800, 600)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Верхняя панель с тулбарами и кнопками переключения шторок
        self._create_top_bar(main_layout)
        
        # Область контента (левая шторка, центральная область, правая шторка)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Создание шторок
        self._create_left_dock()
        self._create_right_dock()
        
        # Центральная область с вкладками
        self.central_tabs = QTabWidget()
        self.central_tabs.setTabsClosable(True)
        self.central_tabs.setMovable(True)
        content_layout.addWidget(self.central_tabs, 1)
        
        main_layout.addLayout(content_layout, 1)
        
        # Создание меню
        self._create_menu()
        
        # Статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
        
        # Создание вкладок
        self._create_central_tabs()
    
    def _create_top_bar(self, parent_layout: QVBoxLayout) -> None:
        """Создание верхней панели с кнопками переключения шторок."""
        top_bar = QWidget()
        top_bar.setFixedHeight(36)
        top_bar.setStyleSheet("""
            QWidget {
                background: #2b2b2b;
                border-bottom: 1px solid #3c3c3c;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #cccccc;
                font-size: 16px;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #3c3c3c;
            }
            QPushButton:pressed {
                background: #4c4c4c;
            }
        """)
        
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 0, 8, 0)
        top_layout.setSpacing(4)
        
        # Кнопка переключения левой шторки
        self.toggle_left_btn = QPushButton("◧")
        self.toggle_left_btn.setFixedSize(28, 28)
        self.toggle_left_btn.setToolTip("Показать/скрыть левую панель")
        self.toggle_left_btn.clicked.connect(self._toggle_left_dock)
        top_layout.addWidget(self.toggle_left_btn)
        
        # Кнопка переключения правой шторки
        self.toggle_right_btn = QPushButton("◨")
        self.toggle_right_btn.setFixedSize(28, 28)
        self.toggle_right_btn.setToolTip("Показать/скрыть правую панель")
        self.toggle_right_btn.clicked.connect(self._toggle_right_dock)
        top_layout.addWidget(self.toggle_right_btn)
        
        top_layout.addStretch()
        
        # Заголовок приложения
        title_label = QLabel("GMod — Git Archaeologist")
        title_label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 13px;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        parent_layout.addWidget(top_bar)
    
    def _toggle_left_dock(self) -> None:
        """Переключение видимости левой шторки."""
        self.left_dock.setVisible(not self.left_dock.isVisible())
    
    def _toggle_right_dock(self) -> None:
        """Переключение видимости правой шторки."""
        self.right_dock.setVisible(not self.right_dock.isVisible())

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
        analysis_layout = self._get_section_layout(analysis_section)
        
        metrics_btn = QPushButton("Метрики")
        metrics_btn.clicked.connect(lambda: self._switch_to_tab("Метрики"))
        analysis_layout.addWidget(metrics_btn)

        graph_btn = QPushButton("Граф")
        graph_btn.clicked.connect(lambda: self._switch_to_tab("Граф"))
        analysis_layout.addWidget(graph_btn)
        
        modes_btn = QPushButton("Режимы работы")
        modes_btn.clicked.connect(lambda: self._switch_to_tab("Анализ"))
        analysis_layout.addWidget(modes_btn)
        
        left_layout.addWidget(analysis_section)
        
        # Секция "Данные"
        data_section = self._create_collapsible_section("Данные")
        data_layout = self._get_section_layout(data_section)
        
        reports_btn = QPushButton("Отчёты")
        reports_btn.clicked.connect(lambda: self._switch_to_tab("Отчёты"))
        data_layout.addWidget(reports_btn)
        
        history_btn = QPushButton("История анализов")
        history_btn.clicked.connect(lambda: self._switch_to_tab("История"))
        data_layout.addWidget(history_btn)
        
        left_layout.addWidget(data_section)
        
        # Секция "Проект"
        project_section = self._create_collapsible_section("Проект")
        project_layout = self._get_section_layout(project_section)
        
        overview_btn = QPushButton("Обзор проекта")
        overview_btn.clicked.connect(lambda: self._switch_to_tab("Обзор"))
        project_layout.addWidget(overview_btn)
        
        left_layout.addWidget(project_section)
        
        # Секция "Система"
        system_section = self._create_collapsible_section("Система")
        system_layout = self._get_section_layout(system_section)
        
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
        """Создание правой шторки (prompt4 п.7)."""
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
        
        # Поле Git URL (пока репозиторий не загружен)
        self.repo_url_widget = QWidget()
        url_layout = QHBoxLayout(self.repo_url_widget)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_label = QLabel("Git URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://github.com/user/repo или путь к папке")
        self.url_load_btn = QPushButton("Загрузить")
        self.url_load_btn.clicked.connect(self._on_load_repository)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input, 1)
        url_layout.addWidget(self.url_load_btn)
        right_layout.addWidget(self.repo_url_widget)
        
        # Вкладки репозитория (показываются после загрузки)
        self.repo_tabs = QTabWidget()
        self.repo_tabs.hide()
        
        # 0: Файлы — QTreeView с файловой моделью
        self.files_tree = QTreeView()
        self.files_tree.setHeaderHidden(True)
        self.repo_tabs.addTab(self.files_tree, "Файлы")
        
        # 1: Стек
        stack_tab = QWidget()
        stack_layout = QVBoxLayout(stack_tab)
        self.stack_view = QTextEdit()
        self.stack_view.setReadOnly(True)
        stack_layout.addWidget(self.stack_view)
        self.repo_tabs.addTab(stack_tab, "Стек")
        
        # 2: README
        readme_tab = QWidget()
        readme_layout = QVBoxLayout(readme_tab)
        self.readme_view = QTextEdit()
        self.readme_view.setReadOnly(True)
        readme_layout.addWidget(self.readme_view)
        self.repo_tabs.addTab(readme_tab, "README")
        
        # 3: Инфо
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        self.info_view = QTextEdit()
        self.info_view.setReadOnly(True)
        info_layout.addWidget(self.info_view)
        self.repo_tabs.addTab(info_tab, "Инфо")
        
        # 4: Ветки
        self.branches_combo = QComboBox()
        self.branches_combo.currentTextChanged.connect(self._on_branch_changed)
        branches_widget = QWidget()
        branches_layout = QVBoxLayout(branches_widget)
        branches_layout.addWidget(QLabel("Ветка:"))
        branches_layout.addWidget(self.branches_combo)
        branches_layout.addStretch()
        self.repo_tabs.addTab(branches_widget, "Ветки")
        
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
        
        # Контент-виджет секции (хранит кнопки)
        content_widget = QWidget()
        content_widget.setProperty("section_content", True)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setObjectName("section_layout")
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        header.clicked.connect(lambda checked: content_widget.setVisible(checked))
        
        layout.addWidget(header)
        layout.addWidget(content_widget)
        
        return section
    
    def _get_section_layout(self, section: QFrame) -> Optional["QVBoxLayout"]:
        """Получение layout секции."""
        content_widget = section.findChild(QWidget, "", Qt.FindDirectChildrenOnly)
        # Ищем виджет с нужным свойством
        for child in section.findChildren(QWidget):
            if child.property("section_content"):
                return child.layout()
        return None
    
    # Канонический порядок вкладок (для восстановления рабочей области 1:1)
    TAB_ORDER = ["Чат", "Метрики", "Граф", "Отчёты", "Анализ", "История", "Обзор"]

    def _tab_factories(self) -> Dict[str, Any]:
        """Маппинг названия вкладки → конструктор (для переоткрытия)."""
        return {
            "Чат": self._create_chat_tab,
            "Метрики": self._create_metrics_tab,
            "Граф": self._create_graph_tab,
            "Отчёты": self._create_reports_tab,
            "Анализ": self._create_analysis_tab,
            "История": self._create_history_tab,
            "Обзор": self._create_overview_tab,
        }

    def _create_central_tabs(self) -> None:
        """Создание центральных вкладок."""
        for name in self.TAB_ORDER:
            factory = self._tab_factories().get(name)
            if factory:
                self.central_tabs.addTab(factory(), name)

        # Закрытие вкладок (крестики) + сохранение состояния при переключении
        try:
            self.central_tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        except Exception:
            pass
        try:
            self.central_tabs.currentChanged.connect(lambda _i: self._save_tabs_state())
        except Exception:
            pass

    def _ensure_tab(self, tab_name: str) -> int:
        """Найти вкладку или пересоздать её (для навигации из шторки).

        Returns:
            Индекс вкладки или -1, если такой вкладки нет в фабрике.
        """
        for i in range(self.central_tabs.count()):
            if self.central_tabs.tabText(i) == tab_name:
                return i
        factory = self._tab_factories().get(tab_name)
        if factory is None:
            return -1
        # Вставляем в канонической позиции относительно соседей
        want = self.TAB_ORDER.index(tab_name) if tab_name in self.TAB_ORDER else 999
        insert_at = self.central_tabs.count()
        for i in range(self.central_tabs.count()):
            try:
                other = self.TAB_ORDER.index(self.central_tabs.tabText(i))
            except ValueError:
                continue
            if other > want:
                insert_at = i
                break
        self.central_tabs.insertTab(insert_at, factory(), tab_name)
        self._save_tabs_state()
        return insert_at

    def _on_tab_close_requested(self, index: int) -> None:
        """Закрытие вкладки по крестику (Чат закрыть нельзя)."""
        name = self.central_tabs.tabText(index)
        if name == "Чат":
            self.status_bar.showMessage("Вкладку «Чат» нельзя закрыть")
            return
        self.central_tabs.removeTab(index)
        self._save_tabs_state()
        self.status_bar.showMessage(f"Вкладка «{name}» закрыта (откройте снова из левой шторки)")

    def _open_tab_names(self) -> list:
        """Имена открытых вкладок (без служебной «Настройки»)."""
        return [
            self.central_tabs.tabText(i)
            for i in range(self.central_tabs.count())
            if self.central_tabs.tabText(i) != "Настройки"
        ]

    def _save_tabs_state(self) -> None:
        """Сохранение набора и активной вкладки (workspace 1:1)."""
        try:
            import json

            self.db.save_workspace_state("open_tabs", json.dumps(self._open_tab_names()))
            self.db.save_workspace_state(
                "active_tab", self.central_tabs.tabText(self.central_tabs.currentIndex())
            )
        except Exception as e:
            logger.error(f"Error saving tabs state: {e}")

    def _restore_tabs_state(self) -> None:
        """Восстановление набора и активной вкладки при старте."""
        try:
            import json

            raw = self.db.load_workspace_state("open_tabs")
            active = self.db.load_workspace_state("active_tab")
            settings_open = False
            if raw:
                try:
                    wanted = json.loads(raw)
                except (ValueError, TypeError):
                    wanted = []
                # Закрываем лишнее (кроме Чата)
                for i in range(self.central_tabs.count() - 1, -1, -1):
                    name = self.central_tabs.tabText(i)
                    if name not in wanted and name != "Чат" and name != "Настройки":
                        self.central_tabs.removeTab(i)
                # Открываем недостающее в каноническом порядке
                for name in self.TAB_ORDER:
                    if name in wanted and name != "Чат":
                        self._ensure_tab(name)
                if "Настройки" in (wanted or []):
                    settings_open = True
            if settings_open:
                self._create_settings_tab()
            if active:
                for i in range(self.central_tabs.count()):
                    if self.central_tabs.tabText(i) == active:
                        self.central_tabs.setCurrentIndex(i)
                        break
            # Видимость шторок
            try:
                left_vis = self.db.load_workspace_state("left_dock_visible")
                right_vis = self.db.load_workspace_state("right_dock_visible")
                if left_vis is not None:
                    self.left_dock.setVisible(bool(int(left_vis)))
                if right_vis is not None:
                    self.right_dock.setVisible(bool(int(right_vis)))
            except (ValueError, TypeError):
                pass
            # Выбор провайдера/модели в чате
            try:
                saved_provider = self.db.load_workspace_state("chat_provider")
                saved_model = self.db.load_workspace_state("chat_model")
                if saved_provider:
                    for i in range(self.provider_combo.count()):
                        if self.provider_combo.itemText(i) == saved_provider:
                            self.provider_combo.setCurrentIndex(i)
                            break
                if saved_model:
                    for i in range(self.model_combo.count()):
                        if self.model_combo.itemText(i) == saved_model:
                            self.model_combo.setCurrentIndex(i)
                            break
                    else:
                        self.model_combo.addItem(saved_model)
                        self.model_combo.setCurrentText(saved_model)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error restoring tabs state: {e}")
    
    def _create_metrics_tab(self) -> QWidget:
        """Создание вкладки метрик с таблицей, фильтрами и экспортом."""
        from PySide6.QtWidgets import (
            QTableView, QHeaderView, QAbstractItemView, QFileDialog,
            QComboBox, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
            QLabel, QWidget, QSplitter, QGroupBox, QFormLayout
        )
        from PySide6.QtCore import QSortFilterProxyModel, Qt
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        import csv
        import json
        
        metrics_tab = QWidget()
        layout = QVBoxLayout(metrics_tab)
        
        # Панель фильтров
        filter_group = QGroupBox("Фильтры")
        filter_layout = QHBoxLayout(filter_group)
        
        # Фильтр по файлу
        filter_layout.addWidget(QLabel("Файл:"))
        self.metrics_file_filter = QComboBox()
        self.metrics_file_filter.addItem("Все файлы")
        self.metrics_file_filter.currentTextChanged.connect(self._apply_metrics_filters)
        filter_layout.addWidget(self.metrics_file_filter)
        
        # Фильтр по типу единицы
        filter_layout.addWidget(QLabel("Тип:"))
        self.metrics_type_filter = QComboBox()
        self.metrics_type_filter.addItems(["Все", "file", "function", "class", "module"])
        self.metrics_type_filter.currentTextChanged.connect(self._apply_metrics_filters)
        filter_layout.addWidget(self.metrics_type_filter)
        
        # Фильтр по имени метрики
        filter_layout.addWidget(QLabel("Метрика:"))
        self.metrics_name_filter = QComboBox()
        self.metrics_name_filter.addItem("Все метрики")
        self.metrics_name_filter.currentTextChanged.connect(self._apply_metrics_filters)
        filter_layout.addWidget(self.metrics_name_filter)
        
        # Поиск по имени единицы
        filter_layout.addWidget(QLabel("Поиск:"))
        self.metrics_search = QLineEdit()
        self.metrics_search.setPlaceholderText("Имя функции/класса...")
        self.metrics_search.textChanged.connect(self._apply_metrics_filters)
        filter_layout.addWidget(self.metrics_search)
        
        filter_layout.addStretch()
        
        # Кнопки экспорта
        export_csv_btn = QPushButton("Экспорт CSV")
        export_csv_btn.clicked.connect(self._export_metrics_csv)
        filter_layout.addWidget(export_csv_btn)
        
        export_json_btn = QPushButton("Экспорт JSON")
        export_json_btn.clicked.connect(self._export_metrics_json)
        filter_layout.addWidget(export_json_btn)
        
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._run_analysis_and_refresh_metrics)
        filter_layout.addWidget(refresh_btn)
        
        layout.addWidget(filter_group)
        
        # Таблица метрик
        self.metrics_table = QTableView()
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.metrics_table.setSortingEnabled(True)
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # Модель данных
        self.metrics_model = QStandardItemModel()
        self.metrics_model.setHorizontalHeaderLabels([
            "Файл", "Тип", "Имя", "Метрика", "Значение", "Время"
        ])
        
        # Прокси-модель для фильтрации
        self.metrics_proxy = QSortFilterProxyModel()
        self.metrics_proxy.setSourceModel(self.metrics_model)
        self.metrics_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.metrics_proxy.setFilterKeyColumn(-1)  # Фильтр по всем колонкам
        
        self.metrics_table.setModel(self.metrics_proxy)
        
        layout.addWidget(self.metrics_table)
        
        # Статус бар метрик
        self.metrics_status = QLabel("Метрики не загружены. Выполните анализ репозитория.")
        layout.addWidget(self.metrics_status)
        
        # Загружаем данные если есть
        self._refresh_metrics()
        
        return metrics_tab
    
    def _refresh_metrics(self) -> None:
        """Обновление таблицы метрик из БД."""
        try:
            from gmod.infrastructure.db.database import get_database
            
            db = get_database()
            repo_id = self._get_current_repo_id()
            
            if not repo_id:
                self.metrics_status.setText("Репозиторий не выбран. Загрузите репозиторий в правой шторке.")
                self.metrics_model.removeRows(0, self.metrics_model.rowCount())
                return
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT file_path, unit_type, unit_name, metric_name, value, timestamp
                    FROM raw_metrics
                    WHERE repo_id = ?
                    ORDER BY file_path, unit_type, unit_name, metric_name
                """, (repo_id,))
                
                rows = cursor.fetchall()
                
                # Очищаем модель
                self.metrics_model.removeRows(0, self.metrics_model.rowCount())
                
                # Заполняем данными
                files_set = set()
                metrics_set = set()
                
                for row in rows:
                    file_path, unit_type, unit_name, metric_name, value, timestamp = row
                    files_set.add(file_path)
                    metrics_set.add(metric_name)
                    
                    items = [
                        QStandardItem(file_path),
                        QStandardItem(unit_type),
                        QStandardItem(unit_name),
                        QStandardItem(metric_name),
                        QStandardItem(f"{value:.4f}"),
                        QStandardItem(str(timestamp))
                    ]
                    # Делаем элементы нередактируемыми
                    for item in items:
                        item.setEditable(False)
                    self.metrics_model.appendRow(items)
                
                # Обновляем фильтры
                current_file = self.metrics_file_filter.currentText()
                self.metrics_file_filter.blockSignals(True)
                self.metrics_file_filter.clear()
                self.metrics_file_filter.addItem("Все файлы")
                self.metrics_file_filter.addItems(sorted(files_set))
                if current_file in files_set:
                    self.metrics_file_filter.setCurrentText(current_file)
                self.metrics_file_filter.blockSignals(False)
                
                current_metric = self.metrics_name_filter.currentText()
                self.metrics_name_filter.blockSignals(True)
                self.metrics_name_filter.clear()
                self.metrics_name_filter.addItem("Все метрики")
                self.metrics_name_filter.addItems(sorted(metrics_set))
                if current_metric in metrics_set:
                    self.metrics_name_filter.setCurrentText(current_metric)
                self.metrics_name_filter.blockSignals(False)
                
                self.metrics_status.setText(f"Загружено метрик: {len(rows)}")
            
        except Exception as e:
            logger.error(f"Error refreshing metrics: {e}")
            self.metrics_status.setText(f"Ошибка загрузки: {e}")

    def _run_analysis_and_refresh_metrics(self) -> None:
        """Запуск анализа репозитория и обновление метрик (prompt4 fix)."""
        repo_id = self._get_current_repo_id()
        if not repo_id:
            self.metrics_status.setText("Репозиторий не выбран. Загрузите репозиторий в правой шторке.")
            return

        repo_path = self._get_repo_path(repo_id)
        if not repo_path:
            self.metrics_status.setText("Метрики не получилось рассчитать: путь к репозиторию не найден.")
            return

        # Получаем последний коммит
        from gmod.infrastructure.git.git_parser import GitParser
        git_parser = GitParser()
        try:
            commits = git_parser.get_commits(repo_id, limit=1, repo_path=repo_path)
        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            self.metrics_status.setText(f"Метрики не получилось рассчитать: {e}")
            return
        if not commits:
            self.metrics_status.setText("Метрики не получилось рассчитать: коммиты не найдены.")
            return

        commit_hash = commits[0].hash

        self.metrics_status.setText("Метрики в обработке...")
        self.status_bar.showMessage("Метрики в обработке...")
        QApplication.processEvents()

        try:
            from gmod.domain.entities import Repository
            from gmod.usecases.analyze_repository import AnalyzeRepositoryUseCase

            repo = Repository(
                id=repo_id,
                url="",
                local_path=repo_path,
                name=repo_id
            )

            # Используем diff_only настройку из конфига
            from gmod.config.settings import get_settings
            settings = get_settings()
            diff_only = settings.analysis_depth == "diff"

            usecase = AnalyzeRepositoryUseCase(diff_only=diff_only)
            result = usecase.execute(repo, commit_hash)

            # В последнем коммите может не быть поддерживаемых файлов
            # (только .md/.txt и т.п.) — тогда сканируем весь репозиторий,
            # чтобы вкладка не оставалась пустой.
            if result.get("status") != "success" or result.get("metrics_computed", 0) == 0:
                logger.info("Метрики: diff-анализ пуст (%s), запускаю полное сканирование",
                            result.get("message", "нет данных"))
                self.metrics_status.setText("Метрики в обработке (полное сканирование)...")
                QApplication.processEvents()
                result = usecase.analyze_paths(repo, commit_hash, ["."])

            if result.get('status') == 'success' and result.get('metrics_computed', 0) > 0:
                msg = ('Метрики рассчитаны: {0} файлов, {1} единиц, {2} метрик'.format(
                    result['files_analyzed'], result['units_analyzed'], result['metrics_computed']))
                self.metrics_status.setText(msg)
                self.status_bar.showMessage(msg)
                logger.info("Метрики: %s", msg)
            else:
                err = result.get('message', 'нет данных')
                if result.get('errors'):
                    err = "; ".join(str(x) for x in result['errors'][:3])
                self.metrics_status.setText(f'Метрики не получилось рассчитать: {err}')
                self.status_bar.showMessage("Метрики не получилось рассчитать")
                logger.warning("Метрики не рассчитаны: %s", err)

            # Обновляем таблицу метрик
            self._refresh_metrics()

        except Exception as e:
            logger.error(f"Error running analysis: {e}", exc_info=True)
            self.metrics_status.setText(f"Метрики не получилось рассчитать: {e}")
            self.status_bar.showMessage("Метрики не получилось рассчитать")

    def _get_current_repo_id(self) -> Optional[str]:
        """Получение ID текущего репозитория."""
        try:
            # Пытаемся получить из состояния рабочей области
            repo_id = self.db.load_workspace_state("current_repo_id")
            if repo_id:
                return repo_id
            
            # Пытаемся получить первый доступный репозиторий
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT repo_id FROM raw_metrics LIMIT 1")
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            logger.error(f"Error getting repo id: {e}")
        return None
    
    def _apply_metrics_filters(self) -> None:
        """Применение фильтров к таблице метрик."""
        # Фильтр по файлу
        file_filter = self.metrics_file_filter.currentText()
        type_filter = self.metrics_type_filter.currentText()
        metric_filter = self.metrics_name_filter.currentText()
        search_text = self.metrics_search.text().lower()

        # Сбрасываем фильтр прокси-модели
        self.metrics_proxy.setFilterFixedString("")

        # Применяем комбинированный фильтр через перебор строк.
        # Важно: скрываем строки представления (proxy), а данные берём
        # через маппинг proxy -> source, иначе ломается при сортировке.
        for proxy_row in range(self.metrics_proxy.rowCount()):
            file_item = None
            type_item = None
            name_item = None
            metric_item = None
            for col, holder in (
                (0, "file_item"), (1, "type_item"), (2, "name_item"), (3, "metric_item")
            ):
                proxy_index = self.metrics_proxy.index(proxy_row, col)
                source_index = self.metrics_proxy.mapToSource(proxy_index)
                item = self.metrics_model.item(source_index.row(), col)
                if holder == "file_item":
                    file_item = item
                elif holder == "type_item":
                    type_item = item
                elif holder == "name_item":
                    name_item = item
                else:
                    metric_item = item
            
            show = True
            
            if file_filter != "Все файлы" and file_item and file_item.text() != file_filter:
                show = False
            if type_filter != "Все" and type_item and type_item.text() != type_filter:
                show = False
            if metric_filter != "Все метрики" and metric_item and metric_item.text() != metric_filter:
                show = False
            if search_text:
                if name_item and search_text not in name_item.text().lower():
                    show = False
            
            # Скрываем/показываем строку представления
            self.metrics_table.setRowHidden(proxy_row, not show)
    
    def _export_metrics_csv(self) -> None:
        """Экспорт метрик в CSV."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Экспорт метрик в CSV", "metrics.csv", "CSV Files (*.csv)"
            )
            if not file_path:
                return
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Заголовки
                headers = ["Файл", "Тип", "Имя", "Метрика", "Значение", "Время"]
                writer.writerow(headers)
                
                # Данные (только видимые строки)
                for row in range(self.metrics_model.rowCount()):
                    if not self.metrics_table.isRowHidden(row):
                        row_data = []
                        for col in range(self.metrics_model.columnCount()):
                            item = self.metrics_model.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
            
            self.status_bar.showMessage(f"Экспортировано в CSV: {file_path}")
            logger.info(f"Metrics exported to CSV: {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать CSV: {e}")
    
    def _export_metrics_json(self) -> None:
        """Экспорт метрик в JSON."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Экспорт метрик в JSON", "metrics.json", "JSON Files (*.json)"
            )
            if not file_path:
                return
            
            data = []
            for row in range(self.metrics_model.rowCount()):
                if not self.metrics_table.isRowHidden(row):
                    row_data = {}
                    for col in range(self.metrics_model.columnCount()):
                        header = self.metrics_model.horizontalHeaderItem(col)
                        item = self.metrics_model.item(row, col)
                        if header and item:
                            row_data[header.text()] = item.text()
                    data.append(row_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.status_bar.showMessage(f"Экспортировано в JSON: {file_path}")
            logger.info(f"Metrics exported to JSON: {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting JSON: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать JSON: {e}")
    
    def _create_chat_tab(self) -> QWidget:
        """Создание вкладки чата."""
        from PySide6.QtWidgets import QTextEdit, QComboBox, QScrollArea
        
        chat_tab = QWidget()
        chat_layout = QVBoxLayout(chat_tab)
        
        # Область истории диалога (скроллируемая)
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("История диалога появится здесь...")
        self.chat_history.append("AI: Привет! Загрузи репозиторий, чтобы начать.")
        chat_layout.addWidget(self.chat_history, 1)
        
        # Поле ввода сообщения
        self.chat_input = QTextEdit()
        self.chat_input.setMaximumHeight(80)
        self.chat_input.setPlaceholderText("Введите сообщение...")
        chat_layout.addWidget(self.chat_input)
        
        # Нижняя панель: провайдер + модель + отправить
        input_controls = QHBoxLayout()
        
        provider_label = QLabel("🤖 Провайдер:")
        input_controls.addWidget(provider_label)
        
        self.provider_combo = QComboBox()
        input_controls.addWidget(self.provider_combo)
        
        model_label = QLabel("🧠 Модель:")
        input_controls.addWidget(model_label)
        
        self.model_combo = QComboBox()
        input_controls.addWidget(self.model_combo)
        
        input_controls.addStretch()
        
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self._on_send_message)
        input_controls.addWidget(self.send_button)

        chat_layout.addLayout(input_controls)

        # Статус нейросети: «Нейросеть работает» / «Нейросеть недоступна...»
        status_row = QHBoxLayout()
        self.llm_status_dot = QLabel("●")
        self.llm_status_dot.setStyleSheet("color: gray; font-size: 16px;")
        self.llm_status_label = QLabel("Нейросеть: статус неизвестен")
        self.llm_status_label.setStyleSheet("color: gray; font-size: 11px;")
        self.llm_check_btn = QPushButton("Проверить")
        self.llm_check_btn.setMaximumWidth(110)
        self.llm_check_btn.clicked.connect(self._on_check_llm_status)
        status_row.addWidget(self.llm_status_dot)
        status_row.addWidget(self.llm_status_label, 1)
        status_row.addWidget(self.llm_check_btn)
        chat_layout.addLayout(status_row)
        
        # Загружаем провайдеры и модели из настроек
        self._load_llm_settings()
        # Тихая проверка статуса после создания вкладки (не блокирует UI)
        QTimer.singleShot(500, self._on_check_llm_status)
        
        return chat_tab
    
    def _load_llm_settings(self) -> None:
        """Загрузка настроек LLM из конфигурации."""
        try:
            settings = get_settings()
            llm_config = settings.build_llm_config()
            
            # Заполняем провайдеров
            self.provider_combo.clear()
            self.provider_model_map = {}
            
            for provider_config in llm_config.get("llm", {}).get("providers", []):
                if provider_config.get("enabled", False):
                    name = provider_config.get("name", "").capitalize()
                    self.provider_combo.addItem(name, provider_config)
                    
                    # Сохраняем модель для провайдера
                    model = provider_config.get("model", "")
                    if model:
                        self.provider_model_map[name] = model
            
            # Если нет включенных провайдеров, добавляем все как заглушку
            if self.provider_combo.count() == 0:
                self.provider_combo.addItems(["Ollama", "Groq", "Gemini"])
                self.provider_model_map = {
                    "Ollama": "llama3.2:3b",
                    "Groq": "openai/gpt-oss-20b",
                    "Gemini": "gemini-2.5-flash"
                }
            
            # Подключаем сигнал смены провайдера
            self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
            
            # Инициализируем модели для текущего провайдера
            self._on_provider_changed(self.provider_combo.currentText())
            
        except Exception as e:
            logger.error(f"Error loading LLM settings: {e}")
            self.provider_combo.addItems(["Ollama", "Groq", "Gemini"])
            self.provider_model_map = {
                "Ollama": "llama3.2:3b",
                "Groq": "openai/gpt-oss-20b",
                "Gemini": "gemini-2.5-flash"
            }
    
    def _on_provider_changed(self, provider_name: str) -> None:
        """Обработка смены провайдера: для Ollama — обновляем модели с сервера."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        seen = set()
        base_model = self.provider_model_map.get(provider_name, "")
        candidates = []
        if base_model:
            candidates.append(base_model)
        # Только реально предоставляемые провайдерами модели.
        # Groq проверен живым API 27.09.2026 (ключ пользователя):
        #   openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b.
        # Gemini: gemini-2.5-flash / lite / pro, gemini-3.5-flash.
        # Ollama: точный список подтягивается с сервера (кнопка 🔄 / автовыбор).
        if provider_name == "Ollama":
            candidates += ["llama3.2:3b", "llama3.1:8b", "codellama:7b", "mistral:7b"]
            # Асинхронно подгружаем реальные модели с сервера
            QTimer.singleShot(0, self._fetch_ollama_models_for_chat)
        elif provider_name == "Groq":
            candidates += ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
            QTimer.singleShot(0, self._fetch_groq_models_for_chat)
        elif provider_name == "Gemini":
            candidates += ["gemini-2.5-flash", "gemini-2.5-flash-lite",
                           "gemini-2.5-pro", "gemini-3.5-flash"]
            QTimer.singleShot(0, self._fetch_gemini_models_for_chat)
        for m in candidates:
            if m and m not in seen:
                self.model_combo.addItem(m)
                seen.add(m)
        self.model_combo.blockSignals(False)
        # Сохраняем выбор и обновляем статус
        try:
            self.db.save_workspace_state("chat_provider", provider_name)
            self.db.save_workspace_state("chat_model", self.model_combo.currentText())
        except Exception:
            pass
        if hasattr(self, "llm_status_label"):
            QTimer.singleShot(0, self._on_check_llm_status)

    def _fetch_groq_models_for_chat(self) -> None:
        """Подтянуть список моделей Groq (GET /openai/v1/models по API-ключу)."""
        try:
            from gmod.config.settings import get_settings
            settings = get_settings()
            key = settings.groq_api_key.strip()
            if not key:
                return
            import requests
            resp = requests.get("https://api.groq.com/openai/v1/models",
                                headers={"Authorization": f"Bearer {key}"}, timeout=10)
            if resp.status_code != 200:
                logger.warning("Groq models fetch: HTTP %s", resp.status_code)
                return
            names = sorted(m.get("id", "") for m in resp.json().get("data", []) if m.get("id"))
            if not names:
                return
            try:
                if self.provider_combo.currentText() != "Groq":
                    return
            except Exception:
                return
            current = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(names)
            if current in names:
                self.model_combo.setCurrentText(current)
            self.model_combo.blockSignals(False)
            logger.info("Groq: загружено %d моделей для чата", len(names))
        except Exception as e:
            logger.debug("Groq models fetch failed: %s", e)

    def _fetch_gemini_models_for_chat(self) -> None:
        """Подтянуть список моделей Gemini (v1beta/models по API-ключу)."""
        try:
            from gmod.config.settings import get_settings
            settings = get_settings()
            key = settings.gemini_api_key.strip()
            if not key:
                return
            import requests
            resp = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                                params={"key": key}, timeout=10)
            if resp.status_code != 200:
                logger.warning("Gemini models fetch: HTTP %s", resp.status_code)
                return
            names = sorted(
                m.get("name", "").replace("models/", "")
                for m in resp.json().get("models", []) if m.get("name"))
            # Только текстовые генеративные модели, без embedding/tts/image/live.
            bad = ("embed", "tts", "image", "live", "audio", "translat", "veo", "research")
            names = [n for n in names if not any(b in n for b in bad)]
            if not names:
                return
            try:
                if self.provider_combo.currentText() != "Gemini":
                    return
            except Exception:
                return
            current = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(names)
            if current in names:
                self.model_combo.setCurrentText(current)
            self.model_combo.blockSignals(False)
            logger.info("Gemini: загружено %d моделей для чата", len(names))
        except Exception as e:
            logger.debug("Gemini models fetch failed: %s", e)

    def _fetch_ollama_models_for_chat(self) -> None:
        """Получить модели с Ollama для комбобокса чата."""
        try:
            from gmod.config.settings import get_settings
            settings = get_settings()
            url = settings.ollama_url.rstrip("/") + "/api/tags"
            import requests
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models if m.get("name")]
                if model_names:
                    current = self.model_combo.currentText()
                    self.model_combo.blockSignals(True)
                    self.model_combo.clear()
                    self.model_combo.addItems(model_names)
                    if current in model_names:
                        self.model_combo.setCurrentText(current)
                    else:
                        self.model_combo.setCurrentIndex(0)
                    self.model_combo.blockSignals(False)
                    logger.info("Ollama: загружено %d моделей для чата", len(model_names))
        except Exception as e:
            logger.debug("Ollama models fetch failed: %s", e)

    def _build_llm_config_for_selection(self) -> dict:
        """Конфиг с выбранным в чате провайдером первым в fallback-цепочке.

        Фикс «чат игнорирует выбор провайдера»: переупорядочиваем providers
        так, чтобы выбранный шёл первым, и подменяем его model на выбранную.
        """
        settings = get_settings()
        cfg = settings.build_llm_config()
        try:
            selected = self.provider_combo.currentText().lower()
            sel_model = self.model_combo.currentText().strip()
        except Exception:
            return cfg
        providers = cfg.get("llm", {}).get("providers", [])
        for p in providers:
            if p.get("name", "").lower() == selected and sel_model:
                p["model"] = sel_model
        providers.sort(key=lambda p: 0 if p.get("name", "").lower() == selected else 1)
        logger.info("LLM: выбран провайдер '%s' модель '%s'", selected, sel_model)
        return cfg

    def _on_check_llm_status(self) -> None:
        """Проверка доступности нейросети с показом статуса и логами."""
        if not hasattr(self, "llm_status_label"):
            return
        self.llm_status_label.setText("Нейросеть: проверка...")
        self.llm_status_dot.setStyleSheet("color: orange; font-size: 16px;")
        QApplication.processEvents()
        try:
            from gmod.infrastructure.llm.factory import LLMProviderFactory

            cfg = self._build_llm_config_for_selection()
            factory = LLMProviderFactory(cfg)
            statuses = factory.check_all_statuses()
            try:
                selected = self.provider_combo.currentText()
            except Exception:
                selected = ""
            # Ищем статус выбранного провайдера
            shown = None
            for prov_name, st in statuses.items():
                if selected and selected.lower() in prov_name.lower():
                    shown = st
                    break
            if shown is None:
                ok_all = [s for s in statuses.values() if s.get("ok")]
                shown = ok_all[0] if ok_all else next(iter(statuses.values()))
            msg = shown.get("message", "")
            ok = shown.get("ok", False)
            self.llm_status_label.setText(f"Нейросеть: {msg}")
            color = "green" if ok else "red"
            self.llm_status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            self.status_bar.showMessage(msg)
            logger.info("LLM статус: %s (ok=%s)", msg, ok)
        except Exception as e:
            logger.error("LLM статус: ошибка проверки: %s", e, exc_info=True)
            self.llm_status_label.setText(f"Нейросеть недоступна. {e}")
            self.llm_status_dot.setStyleSheet("color: red; font-size: 16px;")
    
    def _create_graph_tab(self) -> QWidget:
        """Создание вкладки графа с pyqtgraph + networkx."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
            QLabel, QGroupBox, QSplitter, QTextEdit, QCheckBox
        )
        from PySide6.QtCore import Qt
        
        graph_tab = QWidget()
        layout = QVBoxLayout(graph_tab)
        
        # Панель управления графом
        control_group = QGroupBox("Управление графом")
        control_layout = QHBoxLayout(control_group)
        
        control_layout.addWidget(QLabel("Режим:"))
        self.graph_mode_combo = QComboBox()
        self.graph_mode_combo.addItems(["Зависимости файлов", "Эволюция изменений", "Связность модулей"])
        self.graph_mode_combo.currentTextChanged.connect(self._on_graph_mode_changed)
        control_layout.addWidget(self.graph_mode_combo)
        
        control_layout.addWidget(QLabel("Метрика для цвета:"))
        self.graph_metric_combo = QComboBox()
        self.graph_metric_combo.addItems(["Цикломатическая сложность", "LOC", "Fan-out", "Churn", "Maintainability Index"])
        self.graph_metric_combo.currentTextChanged.connect(self._on_graph_metric_changed)
        control_layout.addWidget(self.graph_metric_combo)
        
        self.graph_show_labels = QCheckBox("Показывать подписи")
        self.graph_show_labels.setChecked(True)
        self.graph_show_labels.toggled.connect(self._refresh_graph)
        control_layout.addWidget(self.graph_show_labels)
        
        self.graph_layout_btn = QPushButton("Пересчитать layout")
        self.graph_layout_btn.clicked.connect(self._refresh_graph)
        control_layout.addWidget(self.graph_layout_btn)
        
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        # Область графа (pyqtgraph)
        import pyqtgraph as pg
        from pyqtgraph import GraphicsLayoutWidget
        
        self.graph_widget = GraphicsLayoutWidget()
        self.graph_plot = self.graph_widget.addPlot()
        self.graph_plot.setAspectLocked(True)
        self.graph_plot.hideAxis('bottom')
        self.graph_plot.hideAxis('left')
        self.graph_plot.setMenuEnabled(False)
        self.graph_plot.setMouseEnabled(x=True, y=True)
        
        # Включаем зум и панорамирование
        self.graph_plot.vb.setMouseMode(pg.ViewBox.PanMode)
        
        layout.addWidget(self.graph_widget, 1)
        
        # Панель информации о выбранном узле
        info_group = QGroupBox("Информация об узле")
        info_layout = QVBoxLayout(info_group)
        
        self.graph_node_info = QTextEdit()
        self.graph_node_info.setReadOnly(True)
        self.graph_node_info.setMaximumHeight(120)
        self.graph_node_info.setPlaceholderText("Кликните на узел для просмотра метрик...")
        info_layout.addWidget(self.graph_node_info)
        
        layout.addWidget(info_group)
        
        # Инициализируем граф
        self._graph_data = None
        self._graph_pos = None
        self._graph_nodes = []
        self._graph_scatter = None
        self._graph_text_items = []
        
        # Подключаем клик
        if hasattr(self, 'graph_plot'):
            self.graph_plot.scene().sigMouseClicked.connect(self._on_graph_click)
        
        # Загружаем начальный граф
        QTimer.singleShot(100, self._refresh_graph)
        
        return graph_tab
    
    def _on_graph_mode_changed(self, mode: str) -> None:
        """Обработка смены режима графа."""
        self._refresh_graph()
    
    def _on_graph_metric_changed(self, metric: str) -> None:
        """Обработка смены метрики для цвета."""
        self._refresh_graph()
    
    def _refresh_graph(self) -> None:
        """Перестроение графа."""
        if not hasattr(self, 'graph_plot'):
            return
            
        try:
            import networkx as nx
            import pyqtgraph as pg
            import numpy as np
            
            # Очищаем текущий график
            self.graph_plot.clear()
            self._graph_text_items = []
            
            repo_id = self._get_current_repo_id()
            if not repo_id:
                return
            
            mode = self.graph_mode_combo.currentText()
            
            if mode == "Зависимости файлов":
                self._build_dependency_graph(repo_id)
            elif mode == "Эволюция изменений":
                self._build_evolution_graph(repo_id)
            elif mode == "Связность модулей":
                self._build_coupling_graph(repo_id)
            
            if self._graph_data is None:
                return
            
            G = self._graph_data
            pos = self._graph_pos
            
            # Создаем scatter plot для узлов
            node_sizes = []
            node_colors = []
            node_positions = []
            
            metric_name = self.graph_metric_combo.currentText()
            metric_values = {}
            
            # Получаем значения метрик для узлов
            metric_values = self._get_node_metrics(repo_id, metric_name)
            
            max_metric = max(metric_values.values()) if metric_values else 1
            min_metric = min(metric_values.values()) if metric_values else 0
            
            for node in G.nodes():
                if node in pos:
                    x, y = pos[node]
                    node_positions.append([x, y])
                    
                    # Размер узла пропорционален степени
                    degree = G.degree(node)
                    node_sizes.append(max(10, min(50, degree * 5 + 10)))
                    
                    # Цвет по метрике
                    if node in metric_values and max_metric > min_metric:
                        norm = (metric_values[node] - min_metric) / (max_metric - min_metric)
                        # Цветовая схема: синий -> красный
                        r = int(255 * norm)
                        g = int(255 * (1 - norm))
                        b = 50
                    else:
                        r, g, b = 100, 100, 200
                    node_colors.append(pg.mkColor(r, g, b, 200))
            
            if not node_positions:
                return
            
            # Создаем scatter plot
            self._graph_scatter = pg.ScatterPlotItem(
                pos=np.array(node_positions),
                size=node_sizes,
                brush=node_colors,
                pen=pg.mkPen('w', width=1),
                hoverable=True
            )
            self.graph_plot.addItem(self._graph_scatter)
            
            # Рисуем ребра
            for edge in G.edges():
                if edge[0] in pos and edge[1] in pos:
                    x1, y1 = pos[edge[0]]
                    x2, y2 = pos[edge[1]]
                    line = pg.PlotDataItem(
                        [x1, x2], [y1, y2],
                        pen=pg.mkPen((100, 100, 100, 100), width=1)
                    )
                    self.graph_plot.addItem(line)
            
            # Добавляем подписи узлов
            if self.graph_show_labels.isChecked():
                for i, node in enumerate(G.nodes()):
                    if node in pos:
                        x, y = pos[node]
                        text = pg.TextItem(node, color='w', anchor=(0.5, 0.5))
                        text.setPos(x, y)
                        self.graph_plot.addItem(text)
                        self._graph_text_items.append(text)
            
            # Сохраняем узлы для клика
            self._graph_nodes = list(G.nodes())
            
        except Exception as e:
            logger.error(f"Error refreshing graph: {e}")
            import traceback
            traceback.print_exc()
    
    def _build_dependency_graph(self, repo_id: str) -> None:
        """Построение графа зависимостей файлов."""
        import networkx as nx
        from gmod.infrastructure.db.database import get_database
        
        G = nx.DiGraph()
        db = get_database()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Получаем все файлы и их метрики
            cursor.execute("""
                SELECT DISTINCT file_path FROM raw_metrics WHERE repo_id = ?
            """, (repo_id,))
            files = [row[0] for row in cursor.fetchall()]
            
            # Добавляем узлы
            for f in files:
                G.add_node(f)
            
            # Простая эвристика зависимостей: импорты в Python файлах
            # В реальности здесь нужен парсер импортов
            for f in files:
                if f.endswith('.py'):
                    try:
                        import os
                        full_path = os.path.join(self._get_repo_path(repo_id) or "", f)
                        if os.path.exists(full_path):
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as fp:
                                content = fp.read()
                            # Ищем импорты
                            import re
                            imports = re.findall(r'from\s+(\S+)\s+import|import\s+(\S+)', content)
                            for imp in imports:
                                mod = imp[0] or imp[1]
                                mod = mod.split('.')[0]
                                # Ищем файл с таким именем
                                for target in files:
                                    if mod in target and target != f:
                                        G.add_edge(f, target)
                    except Exception:
                        pass
        
        # Layout
        try:
            self._graph_pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        except Exception:
            self._graph_pos = nx.random_layout(G, seed=42)
        
        self._graph_data = G
    
    def _build_evolution_graph(self, repo_id: str) -> None:
        """Построение графа эволюции изменений (файлы - коммиты)."""
        import networkx as nx
        from gmod.infrastructure.db.database import get_database
        
        G = nx.Graph()
        db = get_database()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Получаем файлы и коммиты
            cursor.execute("""
                SELECT DISTINCT file_path, commit_hash FROM raw_metrics WHERE repo_id = ?
            """, (repo_id,))
            rows = cursor.fetchall()
            
            # Добавляем узлы: файлы и коммиты
            for file_path, commit_hash in rows:
                G.add_node(file_path, type='file')
                G.add_node(commit_hash[:8], type='commit')
                G.add_edge(file_path, commit_hash[:8])
        
        # Layout
        try:
            self._graph_pos = nx.spring_layout(G, k=3, iterations=50, seed=42)
        except Exception:
            self._graph_pos = nx.random_layout(G, seed=42)
        
        self._graph_data = G
    
    def _build_coupling_graph(self, repo_id: str) -> None:
        """Построение графа связности (fan-in/fan-out)."""
        import networkx as nx
        from gmod.infrastructure.db.database import get_database
        
        G = nx.DiGraph()
        db = get_database()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT file_path FROM raw_metrics WHERE repo_id = ?
            """, (repo_id,))
            files = [row[0] for row in cursor.fetchall()]
            
            for f in files:
                G.add_node(f)
            
            # Добавляем ребра на основе coupling метрик
            for f in files:
                cursor.execute("""
                    SELECT unit_name, value FROM raw_metrics 
                    WHERE repo_id = ? AND file_path = ? AND metric_name IN ('fan_in', 'fan_out', 'coupling')
                """, (repo_id, f))
                metrics = cursor.fetchall()
                # Упрощенно: связываем файлы с похожими метриками
        
        # Layout
        try:
            self._graph_pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        except Exception:
            self._graph_pos = nx.random_layout(G, seed=42)
        
        self._graph_data = G
    
    def _get_node_metrics(self, repo_id: str, metric_name: str) -> Dict[str, float]:
        """Получение значений метрик для узлов."""
        from gmod.infrastructure.db.database import get_database
        
        # В БД metric_name хранится как имя класса (PascalCase,
        # см. BaseMetric.get_name и tests/test_metrics.py), а не snake_case ключ фабрики.
        metric_map = {
            "Цикломатическая сложность": "CyclomaticComplexity",
            "LOC": "LinesOfCode",
            "Fan-out": "FanOut",
            "Churn": "ChurnMetric",
            "Maintainability Index": "MaintainabilityIndex"
        }

        db_metric = metric_map.get(metric_name, "CyclomaticComplexity")
        result = {}
        
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_path, AVG(value) as avg_val
                FROM raw_metrics
                WHERE repo_id = ? AND metric_name = ?
                GROUP BY file_path
            """, (repo_id, db_metric))
            
            for row in cursor.fetchall():
                result[row[0]] = row[1]
        
        return result
    
    def _get_repo_path(self, repo_id: str) -> Optional[str]:
        """Получение пути репозитория."""
        try:
            return self.db.load_workspace_state(f"repo_{repo_id}_path")
        except Exception:
            return None
    
    def _on_graph_click(self, event) -> None:
        """Обработка клика на графе."""
        if not hasattr(self, 'graph_plot') or self._graph_scatter is None:
            return
        
        try:
            # Получаем позицию клика в координатах графика
            pos = self.graph_plot.vb.mapSceneToView(event.scenePos())
            
            # Ищем ближайший узел
            if self._graph_pos and self._graph_nodes:
                min_dist = float('inf')
                closest_node = None
                
                for node in self._graph_nodes:
                    if node in self._graph_pos:
                        nx, ny = self._graph_pos[node]
                        dist = (nx - pos.x())**2 + (ny - pos.y())**2
                        if dist < min_dist:
                            min_dist = dist
                            closest_node = node
                
                if closest_node and min_dist < 0.01:  # Порог близости
                    self._show_node_info(closest_node)
                    
        except Exception as e:
            logger.error(f"Error on graph click: {e}")
    
    def _show_node_info(self, node: str) -> None:
        """Показ информации об узле."""
        try:
            repo_id = self._get_current_repo_id()
            if not repo_id:
                return
            
            from gmod.infrastructure.db.database import get_database
            
            db = get_database()
            info_parts = [f"Узел: {node}"]
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT metric_name, AVG(value) as avg_val, MIN(value), MAX(value)
                    FROM raw_metrics
                    WHERE repo_id = ? AND file_path = ?
                    GROUP BY metric_name
                    ORDER BY metric_name
                """, (repo_id, node))
                
                for row in cursor.fetchall():
                    info_parts.append(f"  {row[0]}: avg={row[1]:.2f}, min={row[2]:.2f}, max={row[3]:.2f}")
            
            self.graph_node_info.setText("\n".join(info_parts))
            
        except Exception as e:
            logger.error(f"Error showing node info: {e}")
            self.graph_node_info.setText(f"Ошибка: {e}")
    
    def _create_reports_tab(self) -> QWidget:
        """Создание вкладки отчётов: список, просмотр, экспорт, удаление, сравнение."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
            QTextEdit, QPushButton, QSplitter, QFileDialog, QMessageBox,
            QLabel, QGroupBox, QComboBox
        )
        from PySide6.QtCore import Qt
        import json
        
        reports_tab = QWidget()
        layout = QHBoxLayout(reports_tab)
        
        # Левая панель: список отчётов
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Заголовок и фильтры
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Отчёты AI"))
        
        self.reports_type_filter = QComboBox()
        self.reports_type_filter.addItems(["Все", "archaeologist", "detective", "architect"])
        self.reports_type_filter.currentTextChanged.connect(self._refresh_reports)
        header_layout.addWidget(self.reports_type_filter)
        
        header_layout.addStretch()
        
        refresh_reports_btn = QPushButton("Обновить")
        refresh_reports_btn.clicked.connect(self._refresh_reports)
        header_layout.addWidget(refresh_reports_btn)
        
        left_layout.addLayout(header_layout)
        
        # Список отчётов
        self.reports_list = QListWidget()
        self.reports_list.setAlternatingRowColors(True)
        self.reports_list.currentItemChanged.connect(self._on_report_selected)
        left_layout.addWidget(self.reports_list, 1)
        
        # Кнопки действий
        actions_layout = QHBoxLayout()
        
        export_btn = QPushButton("Экспорт")
        export_btn.clicked.connect(self._export_report)
        actions_layout.addWidget(export_btn)
        
        delete_btn = QPushButton("Удалить")
        delete_btn.clicked.connect(self._delete_report)
        actions_layout.addWidget(delete_btn)
        
        compare_btn = QPushButton("Сравнить")
        compare_btn.clicked.connect(self._compare_reports)
        actions_layout.addWidget(compare_btn)
        
        left_layout.addLayout(actions_layout)

        # Точность: оценка выбранного отчёта для обучения валидатора
        feedback_row = QHBoxLayout()
        feedback_row.addWidget(QLabel("Точность ответа:"))
        good_btn = QPushButton("👍 Верно")
        good_btn.clicked.connect(lambda: self._on_report_feedback(1))
        feedback_row.addWidget(good_btn)
        bad_btn = QPushButton("👎 Неверно")
        bad_btn.clicked.connect(lambda: self._on_report_feedback(0))
        feedback_row.addWidget(bad_btn)
        feedback_row.addStretch()
        left_layout.addLayout(feedback_row)
        self.reports_accuracy_label = QLabel("")
        self.reports_accuracy_label.setStyleSheet("color: gray; font-size: 11px;")
        left_layout.addWidget(self.reports_accuracy_label)
        
        layout.addWidget(left_panel, 1)
        
        # Правая панель: просмотр отчёта
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("Содержимое отчёта"))
        
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setPlaceholderText("Выберите отчёт из списка...")
        self.report_view.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.report_view, 1)
        
        # Метаданные отчёта
        self.report_meta = QLabel("")
        self.report_meta.setWordWrap(True)
        self.report_meta.setStyleSheet("color: gray; font-size: 11px;")
        right_layout.addWidget(self.report_meta)

        # Вердикт валидатора по выбранному отчёту
        self.report_verdict = QLabel("")
        self.report_verdict.setWordWrap(True)
        self.report_verdict.setStyleSheet("color: #2a7d2a; font-size: 11px;")
        right_layout.addWidget(self.report_verdict)
        
        layout.addWidget(right_panel, 1)
        
        # Загружаем отчёты
        self._refresh_reports()
        
        return reports_tab
    
    def _refresh_reports(self) -> None:
        """Обновление списка отчётов."""
        try:
            repo_id = self._get_current_repo_id()
            if not repo_id:
                self.reports_list.clear()
                self.reports_list.addItem("Репозиторий не выбран")
                return
            
            from gmod.infrastructure.db.database import get_database
            db = get_database()
            
            reports = db.get_ai_reports(repo_id)
            
            # Фильтр по типу
            type_filter = self.reports_type_filter.currentText()
            if type_filter != "Все":
                reports = [r for r in reports if r.get('agent_type') == type_filter]
            
            self.reports_list.clear()
            self._reports_data = reports
            
            for report in reports:
                agent_type = report.get('agent_type', 'unknown')
                commit = report.get('commit_hash', '')[:8]
                risk = report.get('risk_score', 0)
                timestamp = report.get('timestamp', '')
                
                item_text = f"[{agent_type}] {commit} | Risk: {risk}/10 | {timestamp}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, report)
                self.reports_list.addItem(item)
            
            if not reports:
                self.reports_list.addItem("Отчётов не найдено")
            try:
                acc = self.db.feedback_accuracy(repo_id)
                if hasattr(self, "reports_accuracy_label"):
                    if acc["total"]:
                        self.reports_accuracy_label.setText(
                            f"Точность LLM: {acc['accuracy']:.0%} ({acc['positive']}/{acc['total']} 👍)")
                    else:
                        self.reports_accuracy_label.setText("Оценок пока нет — отмечайте отчёты 👍/👎")
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Error refreshing reports: {e}")
            self.reports_list.clear()
            self.reports_list.addItem(f"Ошибка: {e}")
    
    def _on_report_selected(self, current, previous) -> None:
        """Обработка выбора отчёта."""
        if not current:
            return
        
        report = current.data(Qt.UserRole)
        if not report:
            self.report_view.clear()
            self.report_meta.clear()
            return
        
        # Показываем метаданные
        meta = f"ID: {report.get('id')} | Тип: {report.get('agent_type')} | Коммит: {report.get('commit_hash')} | Риск: {report.get('risk_score')}/10 | Время: {report.get('timestamp')}"
        self.report_meta.setText(meta)
        
        # Показываем содержимое
        response_json = report.get('response_json', '')
        try:
            # Пытаемся отформатировать JSON
            data = json.loads(response_json)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            self.report_view.setText(formatted)
        except (json.JSONDecodeError, TypeError):
            self.report_view.setText(response_json or "(пусто — старый отчёт без текста)")

        # Вердикт валидатора + текущая оценка пользователя
        try:
            risk = int(report.get("risk_score") or 5)
            verdict, _p = self._get_validator().verdict(
                risk, {"complexity": risk, "churn": 0, "size": 0, "coupling": 0})
            fb_rows = [f for f in self.db.get_feedback(self._get_current_repo_id() or "")
                       if f["report_id"] == report.get("id")]
            mark = "ваша оценка: 👍" if fb_rows and int(fb_rows[0]["label"]) == 1 else (
                "ваша оценка: 👎" if fb_rows else "вы ещё не оценили этот отчёт")
            self.report_verdict.setText(f"Валидатор: {verdict} | {mark}")
        except Exception as e:
            logger.debug("verdict: %s", e)

    def _on_report_feedback(self, label: int) -> None:
        """Сохранить 👍/👎 для выбранного отчёта (питает точность и валидатор)."""
        current = self.reports_list.currentItem() if hasattr(self, "reports_list") else None
        if not current:
            QMessageBox.warning(self, "Предупреждение", "Выберите отчёт из списка")
            return
        report = current.data(Qt.UserRole)
        if not report or not report.get("id"):
            return
        repo_id = self._get_current_repo_id() or ""
        try:
            self.db.save_feedback(repo_id, int(report["id"]), int(label))
            acc = self.db.feedback_accuracy(repo_id)
            self.reports_accuracy_label.setText(
                f"Точность LLM: {acc['accuracy']:.0%} ({acc['positive']}/{acc['total']} 👍)")
            self.status_bar.showMessage(
                f"Оценка сохранена: {'👍' if label else '👎'} (точность {acc['accuracy']:.0%})")
            logger.info("feedback сохранён: report=%s label=%s accuracy=%.2f",
                        report["id"], label, acc["accuracy"])
            self._on_report_selected(current, None)
            try:
                self._refresh_validator_accuracy()
            except Exception:
                pass
        except Exception as e:
            logger.error("feedback error: %s", e, exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить оценку: {e}")
    
    def _export_report(self) -> None:
        """Экспорт выбранного отчёта."""
        current = self.reports_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Предупреждение", "Выберите отчёт для экспорта")
            return
        
        report = current.data(Qt.UserRole)
        if not report:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт отчёта", f"report_{report.get('id')}.json", "JSON Files (*.json)"
        )
        if not file_path:
            return
        
        try:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self.status_bar.showMessage(f"Отчёт экспортирован: {file_path}")
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {e}")
    
    def _delete_report(self) -> None:
        """Удаление выбранного отчёта."""
        current = self.reports_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Предупреждение", "Выберите отчёт для удаления")
            return
        
        report = current.data(Qt.UserRole)
        if not report:
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить отчёт #{report.get('id')}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from gmod.infrastructure.db.database import get_database
                db = get_database()
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM ai_reports WHERE id = ?", (report.get('id'),))
                
                self._refresh_reports()
                self.report_view.clear()
                self.report_meta.clear()
                self.status_bar.showMessage("Отчёт удалён")
            except Exception as e:
                logger.error(f"Error deleting report: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")
    
    def _compare_reports(self) -> None:
        """Сравнение двух отчётов."""
        selected = self.reports_list.selectedItems()
        if len(selected) != 2:
            QMessageBox.warning(self, "Предупреждение", "Выберите ровно 2 отчёта для сравнения (Ctrl+клик)")
            return
        
        report1 = selected[0].data(Qt.UserRole)
        report2 = selected[1].data(Qt.UserRole)
        
        if not report1 or not report2:
            return
        
        # Создаём диалог сравнения
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Сравнение отчётов")
        dialog.resize(1000, 600)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"Отчёт 1: #{report1.get('id')} | {report1.get('agent_type')} | Risk: {report1.get('risk_score')}"))
        view1 = QTextEdit()
        view1.setReadOnly(True)
        view1.setFont(QFont("Consolas", 9))
        try:
            data1 = json.loads(report1.get('response_json', '{}'))
            view1.setText(json.dumps(data1, ensure_ascii=False, indent=2))
        except:
            view1.setText(report1.get('response_json', ''))
        layout.addWidget(view1)
        
        layout.addWidget(QLabel(f"Отчёт 2: #{report2.get('id')} | {report2.get('agent_type')} | Risk: {report2.get('risk_score')}"))
        view2 = QTextEdit()
        view2.setReadOnly(True)
        view2.setFont(QFont("Consolas", 9))
        try:
            data2 = json.loads(report2.get('response_json', '{}'))
            view2.setText(json.dumps(data2, ensure_ascii=False, indent=2))
        except:
            view2.setText(report2.get('response_json', ''))
        layout.addWidget(view2)
        
        dialog.exec()

    def _create_history_tab(self) -> QWidget:
        """Вкладка «История»: все прошлые запуски анализов и AI-отчёты."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
            QTableView, QHeaderView, QAbstractItemView,
        )
        from PySide6.QtGui import QStandardItemModel, QStandardItem

        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        top.addWidget(QLabel("История анализов"))
        top.addStretch()
        refresh_btn = QPushButton("Обновить")
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        table = QTableView()
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSortingEnabled(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Время", "Тип", "Коммит", "Файл/агент", "Значение"])
        table.setModel(model)
        layout.addWidget(table)

        status = QLabel("")
        layout.addWidget(status)
        tab.setProperty("history_model", model)
        tab.setProperty("history_table", table)
        tab.setProperty("history_status", status)

        def _refresh() -> None:
            try:
                repo_id = self._get_current_repo_id()
                model.removeRows(0, model.rowCount())
                rows = []
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    if repo_id:
                        cursor.execute(
                            """
                            SELECT timestamp, 'metric' AS kind, commit_hash,
                                   file_path || '::' || metric_name AS detail,
                                   value FROM raw_metrics WHERE repo_id = ?
                            """,
                            (repo_id,),
                        )
                        rows.extend(cursor.fetchall())
                        cursor.execute(
                            """
                            SELECT timestamp, agent_type AS kind, commit_hash,
                                   'risk=' || COALESCE(risk_score, 0) AS detail,
                                   COALESCE(risk_score, 0) FROM ai_reports WHERE repo_id = ?
                            """,
                            (repo_id,),
                        )
                        rows.extend(cursor.fetchall())
                    else:
                        cursor.execute(
                            """
                            SELECT timestamp, 'metric' AS kind, commit_hash,
                                   file_path || '::' || metric_name AS detail,
                                   value FROM raw_metrics
                            ORDER BY timestamp DESC LIMIT 500
                            """
                        )
                        rows.extend(cursor.fetchall())
                rows.sort(key=lambda r: str(r[0]), reverse=True)
                for ts, kind, commit, detail, value in rows[:500]:
                    items = [
                        QStandardItem(str(ts)),
                        QStandardItem(str(kind)),
                        QStandardItem(str(commit)[:12]),
                        QStandardItem(str(detail)),
                        QStandardItem(f"{float(value):.2f}" if value is not None else ""),
                    ]
                    for item in items:
                        item.setEditable(False)
                    model.appendRow(items)
                status.setText(f"Записей: {len(rows[:500])}" + ("" if repo_id else " (все репозитории)"))
            except Exception as e:
                logger.error(f"Error refreshing history: {e}")
                status.setText(f"Ошибка: {e}")

        refresh_btn.clicked.connect(_refresh)
        _refresh()
        return tab

    def _create_overview_tab(self) -> QWidget:
        """Вкладка «Обзор»: сводка проекта (файлы, стек, коммиты, риски)."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
        )

        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        top.addWidget(QLabel("Обзор проекта"))
        top.addStretch()
        refresh_btn = QPushButton("Обновить")
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setAcceptRichText(False)
        view.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(view, 1)

        def _refresh() -> None:
            try:
                repo_id = self._get_current_repo_id()
                if not repo_id:
                    view.setText("Репозиторий не выбран. Загрузите репозиторий в правой шторке.")
                    return
                repo_path = self._get_repo_path(repo_id)
                lines = [
                    'ОБЗОР ПРОЕКТА', '=' * 60,
                    f'Репозиторий: {repo_id}', 'Путь: ' + (repo_path or '?'), '',
                    '1. НЕЙРОСЕТЬ',
                    '- Основной провайдер: Ollama через localhost (http://localhost:11434).',
                    '- Проверка: GET /api/tags; генерация — выбранная модель.',
                    '- Локальный API Key не нужен; Cloud-ключ передаётся как Bearer.',
                    '- Точность = правильные оценки / все оценки.',
                    '- Валидатор: p=sigmoid(w·x+b), sigmoid(z)=1/(1+e^(-z)).',
                    '- Обучение: градиентный спуск; epochs и learning rate задаёт пользователь.', '',
                    '2. МЕТРИКИ И АНАЛИЗ',
                    '- Путь → парсер → функции/классы → метрики → SQLite → таблица.',
                    '- Complexity: независимые пути; базово 1 + число ветвлений.',
                    '- LOC: строки кода; Function Length: строки функции.',
                    '- Coupling: зависимости; Fan-in/Fan-out: входящие/исходящие связи.',
                    '- Churn: объём изменений; Change Frequency: частота изменений Git.',
                    '- Таблица: файл, функция/класс, метрика, числовое значение.', '',
                    '3. АРХИТЕКТУРНЫЕ РЕШЕНИЯ',
                    '- Domain — сущности; Use Cases — сценарии; Infrastructure — Git/LLM/БД.',
                    '- UI отвечает за отображение; вычисления находятся в use cases и метриках.',
                    '- Factory выбирает компоненты, fallback переключает LLM при сбое.', '',
                    '4. ТЕРМИНЫ ПРОГРАММНОЙ ИНЖЕНЕРИИ',
                    '- Сцепление: зависимость модулей; меньше — проще сопровождение.',
                    '- Связность: единство ответственности модуля; больше — лучше.',
                    '- Технический долг: будущие затраты из-за компромиссных решений.',
                    '- Code smell: признак потенциальной проблемы дизайна.',
                    '- Регрессионный тест: проверка, что изменения не сломали старое поведение.', '',
                ]
                # Статистика репозитория добавляется ниже
                lines.extend([f"Репозиторий: {repo_id}", "Путь: " + (repo_path or "?"), ""])
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(DISTINCT file_path), COUNT(*), COUNT(DISTINCT commit_hash)"
                        " FROM raw_metrics WHERE repo_id = ?",
                        (repo_id,),
                    )
                    files, metrics_total, commits_n = cursor.fetchone()
                    lines.append(f"Проанализировано файлов: {files}")
                    lines.append(f"Всего метрик в БД: {metrics_total}")
                    lines.append(f"Коммитов в БД: {commits_n}")
                    cursor.execute(
                        "SELECT file_path, COUNT(*) FROM raw_metrics WHERE repo_id = ?"
                        " GROUP BY file_path ORDER BY 2 DESC LIMIT 5",
                        (repo_id,),
                    )
                    lines.append("")
                    lines.append("Топ файлов по числу метрик:")
                    for fp, n in cursor.fetchall():
                        lines.append(f"  {fp}: {n}")
                    cursor.execute(
                        "SELECT agent_type, risk_score, timestamp FROM ai_reports"
                        " WHERE repo_id = ? ORDER BY timestamp DESC LIMIT 1",
                        (repo_id,),
                    )
                    row = cursor.fetchone()
                    lines.append("")
                    if row:
                        lines.append(f"Последний отчёт: [{row[0]}] риск {row[1]}/10 ({row[2]})")
                    else:
                        lines.append("Отчётов пока нет — запустите «Археолога» во вкладке «Анализ».")
                if repo_path:
                    from pathlib import Path
                    from collections import Counter

                    counter: Counter = Counter()
                    try:
                        for p in Path(repo_path).rglob("*"):
                            if p.is_file() and p.suffix:
                                counter[p.suffix.lower()] += 1
                    except Exception:
                        pass
                    lines.append("")
                    lines.append("Стек (по расширениям):")
                    for ext, n in counter.most_common(8):
                        lines.append(f"  {ext}: {n}")
                view.setText("\n".join(lines))
            except Exception as e:
                logger.error(f"Error refreshing overview: {e}")
                view.setText(f"Ошибка: {e}")

        refresh_btn.clicked.connect(_refresh)
        _refresh()
        return tab

    def _create_analysis_tab(self) -> QWidget:
        """Создание вкладки анализа: 3 карточки режимов, панель параметров."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
            QPushButton, QScrollArea, QFormLayout, QComboBox,
            QSpinBox, QDoubleSpinBox, QCheckBox, QSlider, QFrame
        )
        from PySide6.QtCore import Qt
        
        analysis_tab = QWidget()
        layout = QVBoxLayout(analysis_tab)
        
        # Заголовок
        header = QLabel("Выбор режима работы")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(header)
        
        # Скрилл-область для карточек
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        # Карточка 1: Археолог (активна)
        archaeologist_card = self._create_mode_card(
            "Археолог", 
            "Анализ рисков производительности на основе diff и метрик",
            True,
            self._run_archaeologist_analysis
        )
        scroll_layout.addWidget(archaeologist_card)
        
        # Карточка 2: Детектив (в разработке)
        detective_card = self._create_mode_card(
            "Детектив", 
            "Поиск багов, code smells и уязвимостей",
            False,
            None
        )
        scroll_layout.addWidget(detective_card)
        
        # Карточка 3: Архитектор (в разработке)
        architect_card = self._create_mode_card(
            "Архитектор", 
            "Оценка архитектуры, SOLID принципов и связности",
            False,
            None
        )
        scroll_layout.addWidget(architect_card)

        # Нижняя часть вкладки — в скролле с отступами, чтобы блоки
        # (параметры, прогноз, валидатор, функции, журнал) не налеплялись
        # друг на друга и не вылезали за границы.
        lower_scroll = QScrollArea()
        lower_scroll.setWidgetResizable(True)
        lower_content = QWidget()
        lower_layout = QVBoxLayout(lower_content)
        lower_layout.setSpacing(12)
        lower_layout.setContentsMargins(8, 8, 8, 8)
        lower_scroll.setWidget(lower_content)
        layout.addWidget(lower_scroll, 1)

        # Панель параметров (для активного режима)
        self.analysis_params_group = QGroupBox("Параметры анализа")
        params_layout = QFormLayout(self.analysis_params_group)
        
        # Веса метрик
        self.param_complexity_weight = QDoubleSpinBox()
        self.param_complexity_weight.setRange(0.0, 2.0)
        self.param_complexity_weight.setSingleStep(0.1)
        self.param_complexity_weight.setValue(1.0)
        params_layout.addRow("Вес сложности:", self.param_complexity_weight)
        
        self.param_coupling_weight = QDoubleSpinBox()
        self.param_coupling_weight.setRange(0.0, 2.0)
        self.param_coupling_weight.setSingleStep(0.1)
        self.param_coupling_weight.setValue(1.0)
        params_layout.addRow("Вес связности:", self.param_coupling_weight)
        
        self.param_size_weight = QDoubleSpinBox()
        self.param_size_weight.setRange(0.0, 2.0)
        self.param_size_weight.setSingleStep(0.1)
        self.param_size_weight.setValue(0.5)
        params_layout.addRow("Вес размера:", self.param_size_weight)
        
        self.param_churn_weight = QDoubleSpinBox()
        self.param_churn_weight.setRange(0.0, 2.0)
        self.param_churn_weight.setSingleStep(0.1)
        self.param_churn_weight.setValue(0.8)
        params_layout.addRow("Вес churn:", self.param_churn_weight)
        
        # Пороги
        self.param_risk_threshold = QSpinBox()
        self.param_risk_threshold.setRange(1, 10)
        self.param_risk_threshold.setValue(5)
        params_layout.addRow("Порог риска:", self.param_risk_threshold)
        
        self.param_min_confidence = QDoubleSpinBox()
        self.param_min_confidence.setRange(0.0, 1.0)
        self.param_min_confidence.setSingleStep(0.1)
        self.param_min_confidence.setValue(0.7)
        params_layout.addRow("Мин. уверенность:", self.param_min_confidence)
        
        # Единица анализа
        self.param_analysis_unit = QComboBox()
        self.param_analysis_unit.addItems(["file", "function", "class", "module"])
        params_layout.addRow("Единица анализа:", self.param_analysis_unit)
        
        # Глубина анализа
        self.param_diff_only = QCheckBox("Только diff (не файл целиком)")
        params_layout.addRow(self.param_diff_only)
        
        # Включаемые метрики
        self.param_metrics_group = QGroupBox("Включаемые метрики")
        metrics_check_layout = QVBoxLayout(self.param_metrics_group)
        
        self.metrics_checkboxes = {}
        key_metrics = [
            "cyclomatic_complexity", "cognitive_complexity", "maintainability_index",
            "lines_of_code", "fan_in", "fan_out", "coupling", "cohesion",
            "churn", "comment_density", "documentation_coverage"
        ]
        
        for metric in key_metrics:
            cb = QCheckBox(metric)
            cb.setChecked(True)
            self.metrics_checkboxes[metric] = cb
            metrics_check_layout.addWidget(cb)
        
        params_layout.addRow(self.param_metrics_group)
        
        # Кнопка запуска
        run_layout = QHBoxLayout()
        self.run_analysis_btn = QPushButton("Запустить анализ")
        self.run_analysis_btn.clicked.connect(self._run_selected_analysis)
        self.run_analysis_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        run_layout.addWidget(self.run_analysis_btn)
        
        self.analysis_progress = QLabel("")
        run_layout.addWidget(self.analysis_progress)
        run_layout.addStretch()
        
        params_layout.addRow(run_layout)

        lower_layout.addWidget(self.analysis_params_group)

        # --- Управление прогнозом: температура / токены / горизонт ---
        from gmod.config.settings import get_settings as _get_settings
        try:
            _settings = _get_settings()
            _temp, _tok, _hor = _settings.temperature, _settings.max_tokens, _settings.forecast_horizon
        except Exception:
            _temp, _tok, _hor = 0.7, 2000, 5
        forecast_group = QGroupBox("Управление прогнозом / анализом (LLM)")
        forecast_layout = QFormLayout(forecast_group)
        self.param_temperature = QDoubleSpinBox()
        self.param_temperature.setRange(0.0, 2.0)
        self.param_temperature.setSingleStep(0.1)
        self.param_temperature.setValue(float(_temp))
        self.param_temperature.setToolTip("Креативность нейросети: 0 — строго, 2 — фантазия")
        forecast_layout.addRow("Температура:", self.param_temperature)
        self.param_max_tokens = QSpinBox()
        self.param_max_tokens.setRange(100, 8000)
        self.param_max_tokens.setValue(int(_tok))
        forecast_layout.addRow("Max tokens:", self.param_max_tokens)
        self.param_forecast_horizon = QSpinBox()
        self.param_forecast_horizon.setRange(1, 50)
        self.param_forecast_horizon.setValue(int(_hor))
        self.param_forecast_horizon.setToolTip("На сколько коммитов вперёд строить прогноз риска")
        forecast_layout.addRow("Горизонт прогноза (коммитов):", self.param_forecast_horizon)
        forecast_btn_row = QHBoxLayout()
        self.forecast_btn = QPushButton("Построить прогноз риска")
        self.forecast_btn.clicked.connect(self._on_forecast_risk)
        forecast_btn_row.addWidget(self.forecast_btn)
        self.forecast_label = QLabel("Прогноз появится здесь")
        self.forecast_label.setWordWrap(True)
        forecast_btn_row.addWidget(self.forecast_label, 1)
        forecast_layout.addRow(forecast_btn_row)
        lower_layout.addWidget(forecast_group)

        # --- Валидатор с 0: эпохи + точность ---
        validator_group = QGroupBox("Нейросеть-валидатор (с нуля): эпохи и точность")
        validator_layout = QFormLayout(validator_group)
        self.param_epochs = QSpinBox()
        self.param_epochs.setRange(1, 10000)
        try:
            self.param_epochs.setValue(int(_get_settings().validator_epochs))
        except Exception:
            self.param_epochs.setValue(50)
        self.param_epochs.setToolTip("Сколько эпох обучать валидатор на ваших оценках 👍/👎")
        validator_layout.addRow("Кол-во эпох:", self.param_epochs)
        self.param_val_lr = QDoubleSpinBox()
        self.param_val_lr.setRange(0.0001, 5.0)
        self.param_val_lr.setSingleStep(0.05)
        self.param_val_lr.setDecimals(4)
        try:
            self.param_val_lr.setValue(float(_get_settings().validator_lr))
        except Exception:
            self.param_val_lr.setValue(0.1)
        validator_layout.addRow("Learning rate:", self.param_val_lr)
        val_btn_row = QHBoxLayout()
        self.train_validator_btn = QPushButton("Обучить валидатор")
        self.train_validator_btn.clicked.connect(self._on_train_validator)
        val_btn_row.addWidget(self.train_validator_btn)
        self.validator_accuracy_label = QLabel("Точность: нет оценок — ставьте 👍/👎 во вкладке «Отчёты»")
        self.validator_accuracy_label.setWordWrap(True)
        val_btn_row.addWidget(self.validator_accuracy_label, 1)
        validator_layout.addRow(val_btn_row)
        lower_layout.addWidget(validator_group)

        # --- Функции: выбор файлов/директорий + таблица функций × метрики ---
        funcs_group = QGroupBox("Функции: выбор файлов/директорий для анализа")
        funcs_layout = QVBoxLayout(funcs_group)
        paths_row = QHBoxLayout()
        self.func_paths_list = QListWidget()
        self.func_paths_list.setMaximumHeight(80)
        self.func_paths_list.setToolTip("Относительные пути внутри репозитория")
        paths_row.addWidget(self.func_paths_list, 1)
        paths_btns = QVBoxLayout()
        self.func_add_files_btn = QPushButton("＋ Файлы")
        self.func_add_files_btn.clicked.connect(self._on_add_func_files)
        paths_btns.addWidget(self.func_add_files_btn)
        self.func_add_dir_btn = QPushButton("＋ Папка")
        self.func_add_dir_btn.clicked.connect(self._on_add_func_dir)
        paths_btns.addWidget(self.func_add_dir_btn)
        self.func_clear_btn = QPushButton("Очистить")
        self.func_clear_btn.clicked.connect(lambda: self.func_paths_list.clear())
        paths_btns.addWidget(self.func_clear_btn)
        paths_row.addLayout(paths_btns)
        funcs_layout.addLayout(paths_row)
        run_row = QHBoxLayout()
        self.func_analyze_btn = QPushButton("Анализировать выбранное (таблица функций × метрики)")
        self.func_analyze_btn.clicked.connect(self._on_analyze_func_paths)
        run_row.addWidget(self.func_analyze_btn)
        self.func_status_label = QLabel("")
        run_row.addWidget(self.func_status_label, 1)
        funcs_layout.addLayout(run_row)
        from PySide6.QtGui import QStandardItemModel as _Model
        self.func_table = QTableView()
        self.func_table.setAlternatingRowColors(True)
        self.func_table.setSortingEnabled(True)
        self.func_table_model = _Model()
        self.func_table_model.setHorizontalHeaderLabels(["Файл", "Функция", "Метрика", "Значение"])
        self.func_table.setModel(self.func_table_model)
        self.func_table.setMaximumHeight(220)
        funcs_layout.addWidget(self.func_table)
        lower_layout.addWidget(funcs_group)

        # --- Журнал: видимые логи анализа, чтобы клиент знал что за ошибка ---
        from PySide6.QtWidgets import QPlainTextEdit as _QLogEdit
        log_group = QGroupBox("Журнал анализа (gmod.log — последние записи)")
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(6)
        log_layout.setContentsMargins(8, 8, 8, 8)
        self.analysis_log_view = _QLogEdit()
        self.analysis_log_view.setReadOnly(True)
        self.analysis_log_view.setMaximumBlockCount(300)
        self.analysis_log_view.setMinimumHeight(140)
        self.analysis_log_view.setFont(QFont("Consolas", 9))
        self.analysis_log_view.setPlaceholderText("Здесь появятся логи запуска анализа...")
        log_layout.addWidget(self.analysis_log_view)
        log_btn_row = QHBoxLayout()
        log_btn_row.setSpacing(8)
        clear_log_btn = QPushButton("Очистить журнал")
        clear_log_btn.clicked.connect(lambda: self.analysis_log_view.clear())
        log_btn_row.addWidget(clear_log_btn)
        open_log_btn2 = QPushButton("Открыть файл лога")
        open_log_btn2.clicked.connect(self._open_log_file)
        log_btn_row.addWidget(open_log_btn2)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)
        lower_layout.addWidget(log_group)
        lower_layout.addStretch()
        self._attach_analysis_log_handler()

        # Первичное обновление точности валидатора
        QTimer.singleShot(0, self._refresh_validator_accuracy)

        return analysis_tab

    def _attach_analysis_log_handler(self) -> None:
        """Подключение логов Python к виджету журнала (один раз)."""
        if getattr(self, "_qt_log_attached", False):
            return
        try:
            from PySide6.QtCore import QTimer as _QTimer

            view = self.analysis_log_view

            class _QtLogHandler(logging.Handler):
                def emit(self_handler, record) -> None:
                    try:
                        msg = self_handler.format(record)
                        _QTimer.singleShot(0, lambda m=msg: view.appendPlainText(m[-800:]))
                    except Exception:
                        pass

            handler = _QtLogHandler()
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
            logging.getLogger().addHandler(handler)
            self._qt_log_attached = True
            logger.info("Журнал анализа подключён")
        except Exception as e:
            logger.error("Не удалось подключить журнал: %s", e)
    
    def _create_mode_card(self, title: str, description: str, active: bool, callback) -> QWidget:
        """Создание карточки режима."""
        from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton
        from PySide6.QtCore import Qt
        
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setFixedWidth(300)
        card.setMinimumHeight(400)
        
        if active:
            card.setStyleSheet("""
                QFrame {
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    background: #f0fff0;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame {
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    background: #fafafa;
                }
            """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignTop)
        
        # Статус
        status = QLabel("✓ АКТИВЕН" if active else "🚧 В РАЗРАБОТКЕ")
        status.setStyleSheet("color: #4CAF50; font-weight: bold;" if active else "color: #999; font-weight: bold;")
        card_layout.addWidget(status)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px 0;")
        card_layout.addWidget(title_label)
        
        # Описание
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555; margin-bottom: 20px;")
        card_layout.addWidget(desc_label)
        
        if active:
            # Параметры для активного режима
            params_label = QLabel("Параметры:")
            params_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            card_layout.addWidget(params_label)
            
            # Быстрые настройки
            quick_layout = QVBoxLayout()
            
            depth_combo = QComboBox()
            depth_combo.addItems(["Полный анализ", "Только diff"])
            quick_layout.addWidget(QLabel("Глубина:"))
            quick_layout.addWidget(depth_combo)
            
            unit_combo = QComboBox()
            unit_combo.addItems(["Файл", "Функция", "Класс", "Модуль"])
            quick_layout.addWidget(QLabel("Единица:"))
            quick_layout.addWidget(unit_combo)
            
            card_layout.addLayout(quick_layout)
            
            # Кнопка запуска
            run_btn = QPushButton("Запустить Археолога")
            run_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold; padding: 10px;")
            run_btn.clicked.connect(callback if callback else lambda: None)
            card_layout.addWidget(run_btn)
        else:
            card_layout.addStretch()
            coming_soon = QLabel("Функционал будет доступен в следующих версиях")
            coming_soon.setWordWrap(True)
            coming_soon.setAlignment(Qt.AlignCenter)
            coming_soon.setStyleSheet("color: #999; font-style: italic;")
            card_layout.addWidget(coming_soon)
        
        return card
    
    def _run_archaeologist_analysis(self) -> None:
        """Запуск анализа археологом."""
        self._run_selected_analysis()
    
    def _run_selected_analysis(self) -> None:
        """Запуск выбранного анализа."""
        repo_id = self._get_current_repo_id()
        if not repo_id:
            self.analysis_progress.setText("Ошибка: репозиторий не выбран")
            return
        
        # Получаем последний коммит
        from gmod.infrastructure.git.git_parser import GitParser
        from gmod.infrastructure.db.database import get_database
        
        try:
            db = get_database()
            repo_path = self._get_repo_path(repo_id)
            
            if not repo_path:
                self.analysis_progress.setText("Ошибка: путь к репозиторию не найден")
                return
            
            git_parser = GitParser()
            commits = git_parser.get_commits(repo_id, limit=1, repo_path=repo_path)
            
            if not commits:
                self.analysis_progress.setText("Ошибка: коммиты не найдены")
                return
            
            commit_hash = commits[0].hash
            
            self.run_analysis_btn.setEnabled(False)
            self.analysis_progress.setText("Анализ...")
            
            # Запускаем в отдельном потоке
            from PySide6.QtCore import QThread, Signal
            
            class AnalysisThread(QThread):
                finished = Signal(dict)
                error = Signal(str)
                
                def __init__(self, repo_id, commit_hash, config):
                    super().__init__()
                    self.repo_id = repo_id
                    self.commit_hash = commit_hash
                    self.config = config
                
                def run(self):
                    try:
                        from gmod.usecases.run_archaeologist import RunArchaeologistUseCase
                        from gmod.domain.entities import Repository
                        
                        # Создаём репозиторий
                        repo = Repository(
                            id=self.repo_id,
                            url="",
                            local_path=self.config.get("repo_path", ""),
                            name=self.repo_id
                        )
                        
                        usecase = RunArchaeologistUseCase(self.config)
                        result = usecase.execute(repo, self.commit_hash)
                        self.finished.emit(result)
                    except Exception as e:
                        self.error.emit(str(e))
            
            # Подготавливаем конфиг (уважаем выбор провайдера из чата +
            # параметры прогноза: temperature / max_tokens / горизонт)
            llm_cfg = self._build_llm_config_for_selection()["llm"]
            try:
                if hasattr(self, "param_temperature"):
                    llm_cfg["temperature"] = float(self.param_temperature.value())
                if hasattr(self, "param_max_tokens"):
                    llm_cfg["max_tokens"] = int(self.param_max_tokens.value())
            except Exception:
                pass
            config = {
                "llm": llm_cfg,
                "analysis": {
                    "depth": "diff" if self.param_diff_only.isChecked() else "full",
                    "unit": self.param_analysis_unit.currentText()
                }
            }
            try:
                if hasattr(self, "param_forecast_horizon"):
                    config["forecast"] = {"horizon": int(self.param_forecast_horizon.value())}
            except Exception:
                pass
            config["repo_path"] = repo_path
            
            self.analysis_thread = AnalysisThread(repo_id, commit_hash, config)
            self.analysis_thread.finished.connect(self._on_analysis_finished)
            self.analysis_thread.error.connect(self._on_analysis_error)
            self.analysis_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting analysis: {e}")
            self.analysis_progress.setText(f"Ошибка: {e}")
            self.run_analysis_btn.setEnabled(True)
    
    def _analysis_error_text(self, result: dict) -> str:
        """Техническая ошибка + человеческий хинт для показа клиенту."""
        msg = result.get("message", "Unknown")
        hint = result.get("hint", "")
        text = f"Ошибка: {msg}"
        if hint:
            text += f"\nЧто делать: {hint}"
        return text

    def _on_analysis_finished(self, result: dict) -> None:
        """Обработка завершения анализа."""
        self.run_analysis_btn.setEnabled(True)

        if result.get("status") == "success":
            self.analysis_progress.setText(f"Готово! Отчёт #{result.get('report_id')}, Риск: {result.get('analysis', {}).get('risk_score', 'N/A')}/10")
            logger.info("Анализ завершён: отчёт #%s", result.get("report_id"))

            # Переключаемся на вкладку отчётов
            self._switch_to_tab("Отчёты")
            self._refresh_reports()
        else:
            text = self._analysis_error_text(result)
            self.analysis_progress.setText(text)
            self.status_bar.showMessage(text.split("\n")[0])
            logger.error("Анализ завершился ошибкой: %s", text)

    def _on_analysis_error(self, error: str) -> None:
        """Обработка ошибки анализа."""
        self.run_analysis_btn.setEnabled(True)
        self.analysis_progress.setText(f"Ошибка: {error}\nПодробности — в журнале ниже.")
        self.status_bar.showMessage(f"Ошибка анализа: {error}")
        logger.error("Ошибка потока анализа: %s", error)

    # ============ Валидатор с 0 / точность / прогноз / функции ============

    def _get_validator(self):
        from gmod.infrastructure.llm.validator import ZeroValidator, default_model_path
        return ZeroValidator(model_path=default_model_path())

    def _refresh_validator_accuracy(self) -> None:
        """Показать точность LLM (по 👍/👎) и валидатора."""
        if not hasattr(self, "validator_accuracy_label"):
            return
        try:
            repo_id = self._get_current_repo_id()
            fb = self.db.feedback_accuracy(repo_id)
            runs = self.db.get_validator_runs(limit=1)
            if fb["total"] == 0:
                self.validator_accuracy_label.setText(
                    "Точность: нет оценок — ставьте 👍/👎 во вкладке «Отчёты»")
            else:
                last = f", последний запуск {runs[0]['accuracy']:.0%} за {runs[0]['epochs']} эпох" if runs else ""
                self.validator_accuracy_label.setText(
                    f"Точность LLM по вашим оценкам: {fb['accuracy']:.0%} "
                    f"({fb['positive']}/{fb['total']} 👍){last}")
        except Exception as e:
            logger.error("validator accuracy refresh: %s", e)

    def _on_train_validator(self) -> None:
        """Обучение валидатора N эпох на фидбеке пользователя."""
        try:
            epochs = int(self.param_epochs.value())
            lr = float(self.param_val_lr.value())
        except Exception:
            epochs, lr = 50, 0.1
        repo_id = self._get_current_repo_id()
        if not repo_id:
            self.validator_accuracy_label.setText("Сначала загрузите репозиторий")
            return
        feedback = self.db.get_feedback(repo_id)
        if len(feedback) < 2:
            self.validator_accuracy_label.setText(
                f"Нужно минимум 2 оценки (сейчас {len(feedback)}). Ставьте 👍/👎 во вкладке «Отчёты»")
            return
        try:
            from gmod.usecases.analyze_repository import AnalyzeRepositoryUseCase
            from gmod.infrastructure.llm.validator import ZeroValidator

            self.validator_accuracy_label.setText("Обучение...")
            QApplication.processEvents()
            X, y = [], []
            for fb in feedback:
                rid = fb["report_id"]
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT risk_score FROM ai_reports WHERE id = ?", (rid,))
                    row = cur.fetchone()
                risk = int(row[0]) if row and row[0] else 5
                metrics = {"complexity": risk, "churn": 0.0, "size": 0.0, "coupling": 0.0}
                X.append(ZeroValidator.features_from_metrics(risk, metrics))
                y.append(int(fb["label"]))
            validator = self._get_validator()
            run = validator.train(X, y, epochs=epochs, lr=lr)
            self.db.save_validator_run(epochs=run.epochs, accuracy=run.accuracy,
                                       n_samples=run.n_samples)
            # persist epochs в config.yaml для следующего запуска
            try:
                import yaml
                from gmod.config.constants import CONFIG_FILE
                data = {}
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                data.setdefault("validator", {})["epochs"] = epochs
                data["validator"]["lr"] = lr
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, allow_unicode=True)
            except Exception as e:
                logger.warning("Не удалось сохранить epochs в config: %s", e)
            self.validator_accuracy_label.setText(
                f"Готово за {run.epochs} эпох: точность {run.accuracy:.0%} на {run.n_samples} оценках")
            self.status_bar.showMessage(f"Валидатор обучен: accuracy {run.accuracy:.0%}")
            logger.info("Валидатор обучен: epochs=%d accuracy=%.3f", run.epochs, run.accuracy)
        except Exception as e:
            logger.error("Ошибка обучения валидатора: %s", e, exc_info=True)
            self.validator_accuracy_label.setText(f"Ошибка обучения: {e}")

    def _on_add_func_files(self) -> None:
        repo_id = self._get_current_repo_id()
        repo_path = self._get_repo_path(repo_id) if repo_id else None
        if not repo_path:
            self.func_status_label.setText("Сначала загрузите репозиторий")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы", repo_path)
        for f in files:
            try:
                from pathlib import Path as _P
                rel = str(_P(f).relative_to(repo_path))
            except ValueError:
                rel = f
            if not self.func_paths_list.findItems(rel, Qt.MatchExactly):
                self.func_paths_list.addItem(rel)

    def _on_add_func_dir(self) -> None:
        repo_id = self._get_current_repo_id()
        repo_path = self._get_repo_path(repo_id) if repo_id else None
        if not repo_path:
            self.func_status_label.setText("Сначала загрузите репозиторий")
            return
        d = QFileDialog.getExistingDirectory(self, "Выберите папку", repo_path)
        if d:
            try:
                from pathlib import Path as _P
                rel = str(_P(d).relative_to(repo_path))
            except ValueError:
                rel = d
            if not self.func_paths_list.findItems(rel, Qt.MatchExactly):
                self.func_paths_list.addItem(rel)

    def _on_analyze_func_paths(self) -> None:
        """Анализ выбранных файлов/папок → таблица функций × метрики + вердикт LLM."""
        from PySide6.QtGui import QStandardItem
        repo_id = self._get_current_repo_id()
        if not repo_id:
            self.func_status_label.setText("Репозиторий не выбран")
            return
        paths = [self.func_paths_list.item(i).text()
                 for i in range(self.func_paths_list.count())]
        if not paths:
            self.func_status_label.setText("Добавьте файлы или папку (＋ Файлы / ＋ Папка)")
            return
        repo_path = self._get_repo_path(repo_id)
        try:
            from gmod.domain.entities import Repository
            from gmod.usecases.analyze_repository import AnalyzeRepositoryUseCase
            from gmod.infrastructure.git.git_parser import GitParser

            commits = GitParser().get_commits(repo_id, limit=1, repo_path=repo_path)
            commit_hash = commits[0].hash if commits else "manual"
            repo = Repository(id=repo_id, url="", local_path=repo_path, name=repo_id)
            self.func_status_label.setText("Анализ...")
            QApplication.processEvents()
            result = AnalyzeRepositoryUseCase().analyze_paths(repo, commit_hash, paths)
            rows = result.get("function_table", [])
            self.func_table_model.removeRows(0, self.func_table_model.rowCount())
            for r in rows[:2000]:
                items = [QStandardItem(str(r["file"])), QStandardItem(str(r["function"])),
                         QStandardItem(str(r["metric"])), QStandardItem(f"{r['value']:.4f}")]
                for it in items:
                    it.setEditable(False)
                self.func_table_model.appendRow(items)
            # Вердикт нейросети: краткое описание метрик выбранных функций
            verdict = ""
            try:
                if rows:
                    from gmod.infrastructure.llm.factory import LLMProviderFactory
                    cfg = self._build_llm_config_for_selection()
                    factory = LLMProviderFactory(cfg)
                    sample = "\n".join(
                        f"{r['function']} [{r['metric']}={r['value']}]" for r in rows[:30])
                    prompt = (
                        "Опиши качество этих функций по метрикам (1-3 предложения, по-русски):\n" + sample)
                    verdict = factory.generate_with_fallback(
                        prompt,
                        temperature=float(self.param_temperature.value()),
                        max_tokens=min(int(self.param_max_tokens.value()), 800),
                    )
            except Exception as e:
                logger.warning("LLM-описание функций недоступно: %s", e)
                verdict = "Нейросеть недоступна — показан только табличный результат."
            self.func_status_label.setText(
                f"Готово: {result['units_analyzed']} единиц, {result['metrics_computed']} метрик. {verdict[:300]}")
            logger.info("Анализ путей: %s", result)
            try:
                self._refresh_metrics()
            except Exception:
                pass
        except Exception as e:
            logger.error("Ошибка анализа путей: %s", e, exc_info=True)
            self.func_status_label.setText(f"Ошибка: {e}")

    def _on_forecast_risk(self) -> None:
        """Прогноз риска на N коммитов вперёд: тренд метрик + LLM + вердикт валидатора."""
        repo_id = self._get_current_repo_id()
        if not repo_id:
            self.forecast_label.setText("Сначала загрузите репозиторий")
            return
        try:
            horizon = int(self.param_forecast_horizon.value())
        except Exception:
            horizon = 5
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT commit_hash, AVG(value) FROM raw_metrics
                    WHERE repo_id = ? GROUP BY commit_hash ORDER BY timestamp DESC LIMIT 20
                """, (repo_id,))
                points = list(reversed(cur.fetchall()))
            if len(points) < 2:
                self.forecast_label.setText("Недостаточно истории метрик для прогноза — запустите анализ")
                return
            # Линейный тренд (оптимизация: без numpy)
            ys = [float(p[1]) for p in points]
            n = len(ys)
            xs = list(range(n))
            mx, my = sum(xs) / n, sum(ys) / n
            denom = sum((x - mx) ** 2 for x in xs) or 1.0
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
            forecast_vals = [ys[-1] + slope * (i + 1) for i in range(horizon)]
            trend = "растёт 📈" if slope > 0.01 else ("падает 📉" if slope < -0.01 else "стабилен ➡️")
            llm_text = ""
            try:
                from gmod.infrastructure.llm.factory import LLMProviderFactory
                cfg = self._build_llm_config_for_selection()
                factory = LLMProviderFactory(cfg)
                prompt = (
                    f"Метрики риска по коммитам: {[round(v, 2) for v in ys[-10:]]}. "
                    f"Тренд {trend}. Дай прогноз на {horizon} коммитов вперёд "
                    f"(по-русски, 2-3 предложения + оценка риска 1-10).")
                llm_text = factory.generate_with_fallback(
                    prompt, temperature=float(self.param_temperature.value()),
                    max_tokens=min(int(self.param_max_tokens.value()), 800))
            except Exception as e:
                logger.warning("Прогноз LLM недоступен: %s", e)
                llm_text = "Нейросеть недоступна — показан только математический тренд."
            # Вердикт валидатора
            try:
                v = self._get_validator()
                risk_guess = max(1, min(10, int(round(forecast_vals[-1])))) if forecast_vals else 5
                verdict, _p = v.verdict(risk_guess, {"complexity": risk_guess,
                                                    "churn": abs(slope) * 10, "size": 0, "coupling": 0})
            except Exception:
                verdict = ""
            self.forecast_label.setText(
                f"Тренд {trend} (наклон {slope:+.3f}). Прогноз: "
                f"{', '.join(f'{x:.2f}' for x in forecast_vals)}. {llm_text[:400]} {verdict}")
            logger.info("Прогноз риска: horizon=%d slope=%.3f", horizon, slope)
        except Exception as e:
            logger.error("Ошибка прогноза: %s", e, exc_info=True)
            self.forecast_label.setText(f"Ошибка прогноза: {e}")
    
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
        """Переключение на вкладку (пересоздаёт закрытую)."""
        # Создаём вкладку Настройки по требованию
        if tab_name == "Настройки":
            self._create_settings_tab()
            return

        index = self._ensure_tab(tab_name)
        if index >= 0:
            self.central_tabs.setCurrentIndex(index)
        else:
            self.status_bar.showMessage(f'Вкладка "{tab_name}" не найдена')

    def _create_settings_tab(self) -> None:
        """Страница настроек: все секции plan1 п.6, сохранение в SQLite + config.yaml."""
        for i in range(self.central_tabs.count()):
            if self.central_tabs.tabText(i) == "Настройки":
                self.central_tabs.setCurrentIndex(i)
                return

        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QSpinBox,
            QDoubleSpinBox, QLineEdit, QCheckBox, QPushButton, QListWidget,
            QListWidgetItem, QStackedWidget, QMessageBox, QGroupBox, QTextEdit,
            QScrollArea, QLabel, QInputDialog,
        )

        settings = get_settings()
        try:
            import yaml
        except ImportError:
            yaml = None

        # Сырой yaml нужен для ключей без API в Settings (шрифты, уведомления...)
        raw_cfg: dict = {}
        if yaml is not None:
            try:
                from gmod.config.constants import CONFIG_FILE as _CF

                if _CF.exists():
                    with open(_CF, "r", encoding="utf-8") as f:
                        raw_cfg = yaml.safe_load(f) or {}
            except Exception:
                raw_cfg = {}

        def _raw(*keys, default=None):
            node = raw_cfg
            for key in keys:
                if not isinstance(node, dict) or key not in node:
                    return default
                node = node[key]
            return node

        tab = QWidget()
        main_layout = QHBoxLayout(tab)

        sections = [
            "AI-провайдеры", "Модели", "Агент", "Анализ", "Языки",
            "Глубина", "Хранение", "Интерфейс", "Уведомления", "Прочее",
        ]
        nav = QListWidget()
        nav.setMaximumWidth(170)
        for s in sections:
            nav.addItem(QListWidgetItem(s))
        main_layout.addWidget(nav)

        pages = QStackedWidget()
        main_layout.addWidget(pages, 1)
        nav.currentRowChanged.connect(pages.setCurrentIndex)

        # Хранилище виджетов для сохранения
        W: dict = {}
        self._settings_W = W

        def _scroll_page(inner: QWidget) -> QWidget:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(inner)
            return scroll

        # ---------- 1. AI-провайдеры ----------
        p1 = QWidget()
        p1_layout = QVBoxLayout(p1)
        W["prov"] = {}
        for pname, title in (("ollama", "Ollama (локальный/облачный)"),
                             ("groq", "Groq"), ("gemini", "Gemini")):
            group = QGroupBox(title)
            form = QFormLayout(group)
            enabled = QCheckBox("Включён")
            order = QSpinBox()
            order.setRange(1, 3)
            order.setPrefix("Порядок fallback: ")
            form.addRow(enabled)
            form.addRow(order)
            entry = {"enabled": enabled, "order": order}
            if pname == "ollama":
                url_row = QHBoxLayout()
                url = QLineEdit(settings.ollama_url)
                url.setPlaceholderText("http://localhost:11434")
                url_row.addWidget(url, 1)
                refresh_models_btn = QPushButton("🔄 Обновить модели")
                refresh_models_btn.setToolTip("Получить список моделей с сервера Ollama")
                refresh_models_btn.clicked.connect(
                    lambda _c, u=url: self._fetch_ollama_models(u, tab)
                )
                url_row.addWidget(refresh_models_btn)
                form.addRow("URL сервера:", url_row)
                entry["url"] = url
                # API-ключ для Ollama Cloud (для локального сервера — пусто)
                key = QLineEdit(settings.ollama_api_key)
                key.setEchoMode(QLineEdit.Password)
                key.setPlaceholderText("API-ключ (для Ollama Cloud)")
                form.addRow("API-ключ:", key)
                entry["api_key"] = key
                # Комбобокс моделей (заполнится после нажатия "Обновить модели")
                model_combo = QComboBox()
                model_combo.setEditable(True)
                model_combo.addItem(settings.ollama_model)
                model_combo.setToolTip("Выберите или введите модель. Нажмите 'Обновить модели' для списка с сервера")
                form.addRow("Модель:", model_combo)
                entry["model_combo"] = model_combo
            else:
                key = QLineEdit(
                    settings.groq_api_key if pname == "groq" else settings.gemini_api_key
                )
                key.setEchoMode(QLineEdit.Password)
                key.setPlaceholderText("API-ключ")
                form.addRow("API-ключ:", key)
                entry["api_key"] = key
            check_btn = QPushButton("Проверить соединение")
            check_btn.setProperty("provider", pname)
            check_btn.clicked.connect(
                lambda _c, n=pname: self._check_provider_connection(n, tab)
            )
            form.addRow(check_btn)
            W["prov"][pname] = entry
            p1_layout.addWidget(group)
        # Порядок из текущего конфига
        for idx, p in enumerate(settings.llm_providers):
            name = p.get("name")
            if name in W["prov"]:
                W["prov"][name]["enabled"].setChecked(bool(p.get("enabled", False)))
                W["prov"][name]["order"].setValue(idx + 1)
        p1_layout.addStretch()
        pages.addWidget(_scroll_page(p1))

        # ---------- 2. Модели ----------
        p2 = QWidget()
        p2_layout = QFormLayout(p2)
        W["ollama_model"] = QLineEdit(settings.ollama_model)
        p2_layout.addRow("Ollama (по умолчанию):", W["ollama_model"])
        # Groq/Gemini: редактируемый список + кнопка обновления с сервера.
        groq_row = QHBoxLayout()
        W["groq_model"] = QComboBox()
        W["groq_model"].setEditable(True)
        W["groq_model"].addItems(["openai/gpt-oss-20b", "openai/gpt-oss-120b",
                                  "qwen/qwen3.8-27b"])
        W["groq_model"].setCurrentText(settings.groq_model)
        groq_row.addWidget(W["groq_model"], 1)
        groq_refresh = QPushButton("🔄")
        groq_refresh.setMaximumWidth(40)
        groq_refresh.setToolTip("Обновить список моделей с Groq API")
        groq_refresh.clicked.connect(lambda _c: self._fetch_groq_models_for_settings(tab))
        groq_row.addWidget(groq_refresh)
        p2_layout.addRow("Groq (по умолчанию):", groq_row)
        gemini_row = QHBoxLayout()
        W["gemini_model"] = QComboBox()
        W["gemini_model"].setEditable(True)
        W["gemini_model"].addItems(["gemini-2.5-flash", "gemini-2.5-flash-lite",
                                    "gemini-2.5-pro", "gemini-3.5-flash"])
        W["gemini_model"].setCurrentText(settings.gemini_model)
        gemini_row.addWidget(W["gemini_model"], 1)
        gemini_refresh = QPushButton("🔄")
        gemini_refresh.setMaximumWidth(40)
        gemini_refresh.setToolTip("Обновить список моделей с Gemini API")
        gemini_refresh.clicked.connect(lambda _c: self._fetch_gemini_models_for_settings(tab))
        gemini_row.addWidget(gemini_refresh)
        p2_layout.addRow("Gemini (по умолчанию):", gemini_row)
        W["behavior_model"] = QComboBox()
        W["behavior_model"].addItems(["archaeologist", "detective", "architect"])
        W["behavior_model"].setCurrentText(
            str(_raw("llm", "behavior_model", default="archaeologist"))
        )
        p2_layout.addRow("Модель поведения агента:", W["behavior_model"])
        pages.addWidget(_scroll_page(p2))

        # ---------- 3. Агент ----------
        p3 = QWidget()
        p3_layout = QFormLayout(p3)
        W["limit"] = QSpinBox()
        W["limit"].setRange(1, 50)
        W["limit"].setValue(settings.message_limit)
        p3_layout.addRow("Лимит сообщений до пересоздания контекста:", W["limit"])
        W["system_prompt"] = QTextEdit()
        W["system_prompt"].setMaximumHeight(140)
        W["system_prompt"].setPlainText(
            str(_raw("llm", "system_prompt", default=""))
        )
        W["system_prompt"].setPlaceholderText("Системный промпт (пусто = встроенный)")
        p3_layout.addRow("Системный промпт:", W["system_prompt"])
        W["temperature"] = QDoubleSpinBox()
        W["temperature"].setRange(0.0, 2.0)
        W["temperature"].setSingleStep(0.1)
        W["temperature"].setValue(settings.temperature)
        p3_layout.addRow("Температура:", W["temperature"])
        W["max_tokens"] = QSpinBox()
        W["max_tokens"].setRange(100, 8000)
        W["max_tokens"].setValue(settings.max_tokens)
        p3_layout.addRow("Max tokens:", W["max_tokens"])
        pages.addWidget(_scroll_page(p3))

        # ---------- 4. Анализ ----------
        p4 = QWidget()
        p4_layout = QVBoxLayout(p4)
        metrics_group = QGroupBox("Метрики (вкл/выкл)")
        metrics_layout = QVBoxLayout(metrics_group)
        W["metrics_enabled"] = {}
        for metric in [
            "cyclomatic_complexity", "cognitive_complexity", "maintainability_index",
            "lines_of_code", "fan_in", "fan_out", "coupling", "cohesion",
            "churn", "comment_density", "documentation_coverage",
        ]:
            cb = QCheckBox(metric)
            cb.setChecked(bool(_raw("analysis", "metrics", metric, "enabled", default=True)))
            W["metrics_enabled"][metric] = cb
            metrics_layout.addWidget(cb)
        p4_layout.addWidget(metrics_group)
        weights_group = QGroupBox("Веса метрик")
        weights_form = QFormLayout(weights_group)
        W["weights"] = {}
        for key, default in (("complexity", 1.0), ("coupling", 1.0),
                             ("size", 0.5), ("churn", 0.8)):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 2.0)
            spin.setSingleStep(0.1)
            spin.setValue(float(_raw("analysis", "metrics_weights", key, default=default)))
            W["weights"][key] = spin
            weights_form.addRow(f"Вес {key}:", spin)
        p4_layout.addWidget(weights_group)
        risk_form = QFormLayout()
        W["risk_threshold"] = QSpinBox()
        W["risk_threshold"].setRange(1, 10)
        W["risk_threshold"].setValue(int(_raw("analysis", "risk_threshold", default=5)))
        risk_form.addRow("Порог риска:", W["risk_threshold"])
        W["min_confidence"] = QDoubleSpinBox()
        W["min_confidence"].setRange(0.0, 1.0)
        W["min_confidence"].setSingleStep(0.1)
        W["min_confidence"].setValue(float(_raw("analysis", "min_confidence", default=0.7)))
        risk_form.addRow("Мин. уверенность:", W["min_confidence"])
        W["analysis_unit"] = QComboBox()
        W["analysis_unit"].addItems(["file", "function", "class", "module"])
        W["analysis_unit"].setCurrentText(settings.analysis_unit)
        risk_form.addRow("Единица анализа:", W["analysis_unit"])
        p4_layout.addLayout(risk_form)
        p4_layout.addStretch()
        pages.addWidget(_scroll_page(p4))

        # ---------- 5. Языки ----------
        p5 = QWidget()
        p5_layout = QVBoxLayout(p5)
        W["lang_python"] = QCheckBox("Python (реализован)")
        W["lang_python"].setChecked(True)
        W["lang_python"].setEnabled(False)
        p5_layout.addWidget(W["lang_python"])
        W["lang_js"] = QCheckBox("JS/TS (в разработке)")
        W["lang_java"] = QCheckBox("Java (в разработке)")
        for cb in (W["lang_js"], W["lang_java"]):
            cb.setChecked(False)
            cb.setEnabled(False)
            p5_layout.addWidget(cb)
        p5_layout.addWidget(QLabel("Новые языки добавляются через ParserFactory.register_parser."))
        p5_layout.addStretch()
        pages.addWidget(_scroll_page(p5))

        # ---------- 6. Глубина ----------
        p6 = QWidget()
        p6_layout = QFormLayout(p6)
        W["depth"] = QComboBox()
        W["depth"].addItems(["full", "diff"])
        W["depth"].setCurrentText(settings.analysis_depth)
        p6_layout.addRow("Глубина:", W["depth"])
        p6_layout.addRow(QLabel("«diff» — только изменения коммита, «full» — файлы целиком."))
        pages.addWidget(_scroll_page(p6))

        # ---------- 7. Хранение ----------
        p7 = QWidget()
        p7_layout = QFormLayout(p7)
        from gmod.config.constants import DATABASE_FILE as _DB_FILE

        W["db_path"] = QLineEdit(str(_DB_FILE))
        W["db_path"].setReadOnly(True)
        p7_layout.addRow("Путь к SQLite:", W["db_path"])
        try:
            import os

            size_mb = os.path.getsize(_DB_FILE) / (1024 * 1024) if _DB_FILE.exists() else 0.0
        except OSError:
            size_mb = 0.0
        W["db_size"] = QLabel(f"Размер БД: {size_mb:.2f} MB")
        p7_layout.addRow(W["db_size"])
        W["db_limit"] = QSpinBox()
        W["db_limit"].setRange(10, 2000)
        W["db_limit"].setValue(int(_raw("database", "max_size_mb", default=100)))
        p7_layout.addRow("Лимит размера БД (MB):", W["db_limit"])
        W["db_autoclean"] = QCheckBox("Автоочистка")
        W["db_autoclean"].setChecked(bool(_raw("database", "auto_cleanup", default=True)))
        p7_layout.addRow(W["db_autoclean"])
        clear_btn = QPushButton("Очистить старые отчёты…")
        clear_btn.clicked.connect(lambda: self._clear_old_reports(tab))
        p7_layout.addRow(clear_btn)
        reset_ws_btn = QPushButton("Сбросить рабочую область")
        reset_ws_btn.clicked.connect(self._on_reset_workspace)
        p7_layout.addRow(reset_ws_btn)
        pages.addWidget(_scroll_page(p7))

        # ---------- 8. Интерфейс ----------
        p8 = QWidget()
        p8_layout = QFormLayout(p8)
        W["theme"] = QComboBox()
        W["theme"].addItems(["dark", "light", "system"])
        W["theme"].setCurrentText(settings.theme)
        p8_layout.addRow("Тема:", W["theme"])
        W["font_family"] = QLineEdit(str(_raw("ui", "font_family", default="Segoe UI")))
        p8_layout.addRow("Шрифт:", W["font_family"])
        W["font_size"] = QSpinBox()
        W["font_size"].setRange(8, 18)
        W["font_size"].setValue(int(_raw("ui", "font_size", default=10)))
        p8_layout.addRow("Размер шрифта:", W["font_size"])
        W["ui_lang"] = QComboBox()
        W["ui_lang"].addItems(["ru", "en"])
        W["ui_lang"].setCurrentText(str(_raw("app", "language", default="ru")))
        p8_layout.addRow("Язык интерфейса:", W["ui_lang"])
        W["compact_docks"] = QCheckBox("Компактные шторки")
        W["compact_docks"].setChecked(bool(_raw("ui", "compact_docks", default=False)))
        p8_layout.addRow(W["compact_docks"])
        pages.addWidget(_scroll_page(p8))

        # ---------- 9. Уведомления ----------
        p9 = QWidget()
        p9_layout = QVBoxLayout(p9)
        W["notif_enabled"] = QCheckBox("Всплывающие уведомления")
        W["notif_enabled"].setChecked(bool(_raw("notifications", "enabled", default=True)))
        W["notif_sound"] = QCheckBox("Звук уведомлений")
        W["notif_sound"].setChecked(bool(_raw("notifications", "sound", default=False)))
        p9_layout.addWidget(W["notif_enabled"])
        p9_layout.addWidget(W["notif_sound"])
        p9_layout.addStretch()
        pages.addWidget(_scroll_page(p9))

        # ---------- 10. Прочее ----------
        p10 = QWidget()
        p10_layout = QFormLayout(p10)
        W["autosave"] = QCheckBox("Автосохранение рабочей области")
        W["autosave"].setChecked(bool(_raw("app", "auto_save", default=True)))
        p10_layout.addRow(W["autosave"])
        W["autoupdate"] = QCheckBox("Автообновление при старте")
        W["autoupdate"].setChecked(bool(_raw("app", "auto_update", default=False)))
        p10_layout.addRow(W["autoupdate"])
        W["log_level"] = QComboBox()
        W["log_level"].addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        W["log_level"].setCurrentText(settings.log_level)
        p10_layout.addRow("Уровень логов:", W["log_level"])
        open_log_btn = QPushButton("Открыть файл лога")
        open_log_btn.clicked.connect(self._open_log_file)
        p10_layout.addRow(open_log_btn)
        pages.addWidget(_scroll_page(p10))

        nav.setCurrentRow(0)

        # Нижние кнопки
        right = QVBoxLayout()
        right.addWidget(pages, 1)
        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отменить")
        defaults_btn = QPushButton("Сбросить к дефолту")
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(defaults_btn)
        buttons.addStretch()
        right.addLayout(buttons)

        main_layout.addLayout(right, 1)

        def _save_to_sqlite(category: str, key: str, value: object) -> None:
            text = str(value)
            vtype = "bool" if isinstance(value, bool) else (
                "int" if isinstance(value, int) else (
                    "float" if isinstance(value, float) else "str"))
            self.db.save_setting(category, key, text, vtype)

        def _on_save() -> None:
            if yaml is None:
                QMessageBox.critical(tab, "Ошибка", "pyyaml не установлен")
                return
            try:
                from gmod.config.constants import CONFIG_FILE
                from gmod.config.settings import reset_settings

                data: dict = {}
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                # Провайдеры в выбранном порядке fallback
                ordered = sorted(W["prov"].items(), key=lambda kv: kv[1]["order"].value())
                providers = []
                for pname, entry in ordered:
                    item = {"name": pname, "enabled": entry["enabled"].isChecked()}
                    if pname == "ollama":
                        item["url"] = entry["url"].text().strip() or "http://localhost:11434"
                        model_combo = entry.get("model_combo")
                        if model_combo:
                            item["model"] = model_combo.currentText().strip() or "llama3.2:3b"
                        else:
                            item["model"] = W["ollama_model"].text().strip() or "llama3.2:3b"
                        item["api_key"] = entry["api_key"].text().strip()
                    elif pname == "groq":
                        item["api_key"] = entry["api_key"].text().strip()
                        item["model"] = W["groq_model"].currentText().strip() or "openai/gpt-oss-20b"
                    else:
                        item["api_key"] = entry["api_key"].text().strip()
                        item["model"] = W["gemini_model"].currentText().strip() or "gemini-2.5-flash"
                    providers.append(item)
                    _save_to_sqlite("llm_provider", pname + ".enabled", item["enabled"])
                data.setdefault("llm", {})["providers"] = providers
                data["llm"]["behavior_model"] = W["behavior_model"].currentText()
                data["llm"]["message_limit"] = W["limit"].value()
                data["llm"]["system_prompt"] = W["system_prompt"].toPlainText()
                data["llm"]["temperature"] = W["temperature"].value()
                data["llm"]["max_tokens"] = W["max_tokens"].value()
                for k in ("message_limit", "temperature", "max_tokens"):
                    _save_to_sqlite("llm", k, data["llm"][k])

                data.setdefault("analysis", {})["metrics"] = {
                    name: {"enabled": cb.isChecked()}
                    for name, cb in W["metrics_enabled"].items()
                }
                data["analysis"]["metrics_weights"] = {
                    k: spin.value() for k, spin in W["weights"].items()
                }
                data["analysis"]["risk_threshold"] = W["risk_threshold"].value()
                data["analysis"]["min_confidence"] = W["min_confidence"].value()
                data["analysis"]["unit"] = W["analysis_unit"].currentText()
                data["analysis"]["depth"] = W["depth"].currentText()
                for k in ("risk_threshold", "min_confidence", "unit", "depth"):
                    _save_to_sqlite("analysis", k, data["analysis"][k])

                data.setdefault("database", {})["max_size_mb"] = W["db_limit"].value()
                data["database"]["auto_cleanup"] = W["db_autoclean"].isChecked()
                data.setdefault("app", {})["theme"] = W["theme"].currentText()
                data["app"]["language"] = W["ui_lang"].currentText()
                data["app"]["auto_save"] = W["autosave"].isChecked()
                data["app"]["auto_update"] = W["autoupdate"].isChecked()
                data.setdefault("ui", {})["font_family"] = W["font_family"].text()
                data["ui"]["font_size"] = W["font_size"].value()
                data["ui"]["compact_docks"] = W["compact_docks"].isChecked()
                data.setdefault("notifications", {})["enabled"] = W["notif_enabled"].isChecked()
                data["notifications"]["sound"] = W["notif_sound"].isChecked()
                data.setdefault("logging", {})["level"] = W["log_level"].currentText()
                for cat, keys in (
                    ("app", ["theme", "language", "auto_save", "auto_update"]),
                    ("ui", ["font_family", "font_size", "compact_docks"]),
                    ("notifications", ["enabled", "sound"]),
                    ("logging", ["level"]),
                    ("database", ["max_size_mb", "auto_cleanup"]),
                ):
                    for k in keys:
                        section = {"app": data["app"], "ui": data["ui"],
                                   "notifications": data["notifications"],
                                   "logging": data["logging"],
                                   "database": data["database"]}[cat]
                        _save_to_sqlite(cat, k, section[k])

                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, allow_unicode=True)

                reset_settings()
                self._set_theme(W["theme"].currentText())
                try:
                    self._load_llm_settings()
                except Exception:
                    pass
                self.status_bar.showMessage("Настройки сохранены (config.yaml + SQLite)")
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                QMessageBox.critical(tab, "Ошибка", f"Не удалось сохранить: {e}")

        def _on_cancel() -> None:
            idx = self.central_tabs.indexOf(tab)
            if idx >= 0:
                self.central_tabs.removeTab(idx)

        def _on_defaults() -> None:
            W["theme"].setCurrentText("dark")
            W["limit"].setValue(7)
            W["temperature"].setValue(0.7)
            W["max_tokens"].setValue(2000)
            W["depth"].setCurrentText("full")
            W["analysis_unit"].setCurrentText("file")
            W["risk_threshold"].setValue(5)
            W["min_confidence"].setValue(0.7)
            W["log_level"].setCurrentText("INFO")
            for cb in W["metrics_enabled"].values():
                cb.setChecked(True)

        save_btn.clicked.connect(_on_save)
        cancel_btn.clicked.connect(_on_cancel)
        defaults_btn.clicked.connect(_on_defaults)

        self.central_tabs.addTab(tab, "Настройки")
        self.central_tabs.setCurrentWidget(tab)

    def _check_provider_connection(self, provider_name: str, parent) -> None:
        """Проверка соединения с провайдером (Настройки → AI-провайдеры).

        Показывает понятное сообщение: «Нейросеть работает» /
        «Нейросеть недоступна. API ключ не валидный» / ...
        """
        from PySide6.QtWidgets import QMessageBox

        try:
            from gmod.config.settings import get_settings

            settings = get_settings()
            if provider_name == "ollama":
                from gmod.infrastructure.llm.ollama_provider import OllamaProvider

                provider = OllamaProvider(config={
                    "url": settings.ollama_url,
                    "model": settings.ollama_model,
                    "api_key": settings.ollama_api_key,
                })
            elif provider_name == "groq":
                from gmod.infrastructure.llm.groq_provider import GroqProvider

                provider = GroqProvider(api_key=settings.groq_api_key,
                                        config={"model": settings.groq_model})
            else:
                from gmod.infrastructure.llm.gemini_provider import GeminiProvider

                provider = GeminiProvider(api_key=settings.gemini_api_key,
                                          config={"model": settings.gemini_model})
            # Используем расширенную проверку check_status, если есть
            if hasattr(provider, "check_status"):
                status = provider.check_status()
                ok = status.ok
                msg = status.message
            else:
                ok = provider.is_available()
                msg = "Нейросеть работает" if ok else "Нейросеть недоступна"
            QMessageBox.information(
                parent, "Проверка соединения",
                f"{provider_name}: {msg}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(parent, "Проверка соединения", f"Ошибка: {e}")

    def _fetch_ollama_models(self, url_widget, parent_tab) -> None:
        """Получить список моделей с Ollama сервера и заполнить комбобокс."""
        from PySide6.QtWidgets import QMessageBox, QApplication
        import requests

        url = url_widget.text().strip() or "http://localhost:11434"
        if not url.endswith("/api/tags"):
            api_url = url.rstrip("/") + "/api/tags"
        else:
            api_url = url

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models if m.get("name")]
                if not model_names:
                    QMessageBox.warning(parent_tab, "Модели не найдены",
                        "Ollama ответил, но список моделей пуст.\n"
                        "Проверьте, что модели установлены: `ollama pull <model>`")
                    return
                # Находим комбобокс модели в той же вкладке
                for pname, entry in self._settings_W.get("prov", {}).items():
                    if pname == "ollama" and "model_combo" in entry:
                        combo = entry["model_combo"]
                        current = combo.currentText()
                        combo.blockSignals(True)
                        combo.clear()
                        combo.addItems(model_names)
                        if current in model_names:
                            combo.setCurrentText(current)
                        else:
                            combo.setCurrentIndex(0)
                        combo.blockSignals(False)
                        break
                QMessageBox.information(parent_tab, "Готово",
                    f"Получено моделей: {len(model_names)}")
            elif resp.status_code == 401:
                QMessageBox.warning(parent_tab, "Ошибка",
                    "Нужен API-ключ (Ollama Cloud). Введите ключ в поле выше.")
            else:
                QMessageBox.warning(parent_tab, "Ошибка",
                    f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(parent_tab, "Ошибка соединения",
                f"Не удалось подключиться к {url}.\n"
                "Проверьте, что Ollama запущена: `ollama serve`")
        except Exception as e:
            QMessageBox.warning(parent_tab, "Ошибка", f"{type(e).__name__}: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _fill_settings_combo(self, key: str, names: list, parent_tab) -> None:
        """Заполнить комбобокс модели на вкладке настроек с сохранением выбора."""
        from PySide6.QtWidgets import QMessageBox

        combo = self._settings_W.get(key)
        if combo is None:
            return
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(names)
        combo.setCurrentText(current if current in names else names[0])
        combo.blockSignals(False)
        QMessageBox.information(parent_tab, "Готово", f"Получено моделей: {len(names)}")

    def _fetch_groq_models_for_settings(self, parent_tab) -> None:
        """Обновить список моделей Groq (ключ берётся из поля настроек)."""
        from PySide6.QtWidgets import QMessageBox, QApplication
        import requests

        entry = self._settings_W.get("prov", {}).get("groq", {})
        key_widget = entry.get("api_key")
        key = key_widget.text().strip() if key_widget else ""
        if not key:
            QMessageBox.warning(parent_tab, "Нужен ключ", "Введите Groq API-ключ в разделе AI-провайдеры.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            resp = requests.get("https://api.groq.com/openai/v1/models",
                                headers={"Authorization": f"Bearer {key}"}, timeout=10)
            if resp.status_code in (401, 403):
                QMessageBox.warning(parent_tab, "Ошибка",
                    "Нейросеть недоступна. API ключ не валидный.")
                return
            if resp.status_code != 200:
                QMessageBox.warning(parent_tab, "Ошибка", f"HTTP {resp.status_code}")
                return
            names = sorted(m.get("id", "") for m in resp.json().get("data", []) if m.get("id"))
            if not names:
                QMessageBox.warning(parent_tab, "Модели не найдены", "Groq вернул пустой список.")
                return
            self._fill_settings_combo("groq_model", names, parent_tab)
        except Exception as e:
            QMessageBox.warning(parent_tab, "Ошибка", f"{type(e).__name__}: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _fetch_gemini_models_for_settings(self, parent_tab) -> None:
        """Обновить список моделей Gemini (ключ берётся из поля настроек)."""
        from PySide6.QtWidgets import QMessageBox, QApplication
        import requests

        entry = self._settings_W.get("prov", {}).get("gemini", {})
        key_widget = entry.get("api_key")
        key = key_widget.text().strip() if key_widget else ""
        if not key:
            QMessageBox.warning(parent_tab, "Нужен ключ", "Введите Gemini API-ключ в разделе AI-провайдеры.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            resp = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                                params={"key": key}, timeout=10)
            if resp.status_code in (400, 401, 403):
                QMessageBox.warning(parent_tab, "Ошибка",
                    "Нейросеть недоступна. API ключ не валидный "
                    "(ключ Google AI Studio начинается с AIza...).")
                return
            if resp.status_code != 200:
                QMessageBox.warning(parent_tab, "Ошибка", f"HTTP {resp.status_code}")
                return
            names = sorted(
                m.get("name", "").replace("models/", "")
                for m in resp.json().get("models", []) if m.get("name"))
            bad = ("embed", "tts", "image", "live", "audio", "translat", "veo", "research")
            names = [n for n in names if not any(b in n for b in bad)]
            if not names:
                QMessageBox.warning(parent_tab, "Модели не найдены", "Gemini вернул пустой список.")
                return
            self._fill_settings_combo("gemini_model", names, parent_tab)
        except Exception as e:
            QMessageBox.warning(parent_tab, "Ошибка", f"{type(e).__name__}: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _clear_old_reports(self, parent) -> None:
        """Удаление AI-отчётов старше N дней (Настройки → Хранение)."""
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        days, ok = QInputDialog.getInt(parent, "Очистить старые отчёты",
                                       "Удалить отчёты старше (дней):", 30, 1, 365)
        if not ok:
            return
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM ai_reports WHERE timestamp < datetime('now', ?)",
                    (f"-{days} days",),
                )
                removed = cursor.rowcount
            QMessageBox.information(parent, "Готово", f"Удалено отчётов: {removed}")
            try:
                self._refresh_reports()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(parent, "Ошибка", f"Не удалось очистить: {e}")

    def _open_log_file(self) -> None:
        """Открытие файла лога (Настройки → Прочее)."""
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            from gmod.config.constants import LOG_FILE

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_FILE)))
        except Exception as e:
            logger.error(f"Error opening log: {e}")

    def _on_load_repository(self) -> None:
        """Загрузка репозитория (URL или локальный путь)."""
        from pathlib import Path

        url_text = self.url_input.text().strip()
        if not url_text:
            # Фолбэк — диалог выбора папки
            repo_dir = QFileDialog.getExistingDirectory(self, "Выберите локальный Git-репозиторий")
            if not repo_dir:
                return
            path = Path(repo_dir)
            is_clone = False
        else:
            path = Path(url_text)
            is_clone = not path.exists()

        try:
            from gmod.infrastructure.git.git_parser import GitParser

            parser = GitParser()
            if is_clone:
                # Клонирование по URL
                local_base = Path(self.db.load_workspace_state("repos_base") or "data/repos")
                local_base.mkdir(parents=True, exist_ok=True)
                self.status_bar.showMessage("Клонирование репозитория...")
                QApplication.processEvents()
                repo = parser.clone_repository(url_text, local_base / path.name)
            else:
                # Открытие локального репозитория
                repo = parser.open_repository(path)
            
            parser.save_repository_info(repo)
            self.db.save_workspace_state("current_repo_id", repo.id)
            
            # Скрываем поле URL, показываем вкладки
            self.repo_url_widget.hide()
            self.repo_tabs.show()
            
            self.status_bar.showMessage(f"Репозиторий загружен: {repo.name}")
            logger.info(f"Repository loaded: {repo.id} at {repo.local_path}")
            self._populate_repo_dock(repo)
            
            # Обновляем связанные вкладки
            try:
                self._refresh_metrics()
            except Exception:
                pass
            # Если метрик по репозиторию ещё нет — сразу считаем,
            # чтобы вкладка не оставалась пустой после загрузки.
            try:
                if hasattr(self, "metrics_model") and self.metrics_model.rowCount() == 0:
                    self._run_analysis_and_refresh_metrics()
            except Exception as e:
                logger.debug("auto metrics skipped: %s", e)
            try:
                self._refresh_graph()
            except Exception:
                pass
            try:
                self._refresh_reports()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error loading repository: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть репозиторий: {e}")

    def _populate_repo_dock(self, repo) -> None:
        """Заполнение правой шторки реальными данными репозитория."""
        from pathlib import Path
        from PySide6.QtGui import QStandardItemModel, QStandardItem

        try:
            repo_path = Path(repo.local_path)
            
            # 0: Файлы — QTreeView с файловой моделью
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels([""])
            try:
                for p in sorted(repo_path.rglob("*")):
                    if p.is_file() and p.suffix.lower() in (
                        ".py", ".js", ".ts", ".java", ".md", ".toml", ".yaml", ".yml",
                        ".json", ".txt", ".cfg", ".ini", ".xml", ".html", ".css",
                    ):
                        try:
                            rel = p.relative_to(repo_path)
                            parts = rel.parts
                            # Строим дерево вложенных элементов
                            parent = model.invisibleRootItem()
                            for i, part in enumerate(parts):
                                # Ищем существующий ребёнок
                                found = None
                                for row in range(parent.rowCount()):
                                    child = parent.child(row)
                                    if child and child.text() == part:
                                        found = child
                                        break
                                if found:
                                    parent = found
                                else:
                                    item = QStandardItem(part)
                                    item.setEditable(False)
                                    if i == len(parts) - 1:
                                        # Файл — добавляем иконку по расширению
                                        item.setData(str(rel), Qt.UserRole)
                                    parent.appendRow(item)
                                    parent = item
                        except ValueError:
                            pass
            except Exception as e:
                logger.error(f"Error building file tree: {e}")
            self.files_tree.setModel(model)
            self.files_tree.expandAll()

            # 1: Стек — языки по расширениям
            from collections import Counter
            counter: Counter = Counter()
            try:
                for p in repo_path.rglob("*"):
                    if p.is_file() and p.suffix:
                        counter[p.suffix.lower()] += 1
            except Exception:
                pass
            self.stack_view.setText("Стек (по расширениям):\n" + 
                "\n".join(f"{ext}: {n}" for ext, n in counter.most_common(15)) or "Нет данных")

            # 2: README
            readme_path = None
            for cand in ("README.md", "README.MD", "readme.md", "README.txt"):
                if (repo_path / cand).exists():
                    readme_path = repo_path / cand
                    break
            if readme_path is not None:
                self.readme_view.setText(readme_path.read_text(encoding="utf-8", errors="ignore")[:3000])
            else:
                self.readme_view.setText("README не найден")

            # 3: Инфо — метаданные
            from gmod.infrastructure.git.git_parser import GitParser
            parser = GitParser()
            try:
                commits = parser.get_commits(repo.id, limit=5, repo_path=str(repo_path))
                n_commits = len(commits)
            except Exception:
                n_commits = "?"
            try:
                branches = parser.get_branches(repo.id, repo_path=str(repo_path))
                branches_s = ", ".join(branches[:10]) or "?"
                # Заполняем комбобокс веток
                self.branches_combo.blockSignals(True)
                self.branches_combo.clear()
                self.branches_combo.addItems(branches)
                if repo.default_branch in branches:
                    self.branches_combo.setCurrentText(repo.default_branch)
                self.branches_combo.blockSignals(False)
            except Exception:
                branches_s = "?"
            self.info_view.setText(
                f"Имя: {repo.name}\nПуть: {repo.local_path}\n"
                f"Ветка: {repo.default_branch}\nВетки: {branches_s}\n"
                f"Коммитов (первые 5): {n_commits}"
            )
        except Exception as e:
            logger.error(f"Error populating repo dock: {e}")

    def _on_branch_changed(self, branch_name: str) -> None:
        """Смена ветки в комбобоксе."""
        repo_id = self._get_current_repo_id()
        if not repo_id:
            return
        try:
            repo_path = self._get_repo_path(repo_id)
            if not repo_path:
                return
            import git
            repo = git.Repo(repo_path)
            repo.git.checkout(branch_name)
            self.status_bar.showMessage(f"Переключено на ветку: {branch_name}")
            # Обновляем инфо
            self.info_view.setText(self.info_view.toPlainText().replace(
                f"Ветка: {self.info_view.toPlainText().split('Ветка: ')[1].split(chr(10))[0] if 'Ветка: ' in self.info_view.toPlainText() else ''}",
                f"Ветка: {branch_name}"
            ))
        except Exception as e:
            logger.error(f"Error switching branch: {e}")
            self.status_bar.showMessage(f"Ошибка переключения ветки: {e}")
    
    def _on_send_message(self) -> None:
        """Обработка отправки сообщения через usecase (prompt4 п.1)."""
        if not hasattr(self, 'chat_input') or not hasattr(self, 'chat_history'):
            return
            
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        
        # Добавляем сообщение пользователя в историю
        self.chat_history.append(f"\nВы: {text}")
        self.chat_input.clear()
        
        # Показываем индикатор загрузки
        self.send_button.setEnabled(False)
        self.send_button.setText("Ожидание...")
        self.status_bar.showMessage("Отправка сообщения...")
        
        # Запускаем асинхронную отправку через usecase
        QTimer.singleShot(0, lambda: self._send_message_async(text))
    
    def _send_message_async(self, text: str) -> None:
        """Асинхронная отправка сообщения через RunArchaeologistUseCase."""
        try:
            from gmod.config.settings import get_settings
            from gmod.domain.entities import Repository
            from gmod.usecases.run_archaeologist import RunArchaeologistUseCase

            settings = get_settings()
            config = self._build_llm_config_for_selection()
            # Пробрасываем параметры прогноза/анализа из вкладки «Анализ», если заданы
            try:
                if hasattr(self, "param_temperature"):
                    config.setdefault("llm", {})["temperature"] = float(self.param_temperature.value())
                if hasattr(self, "param_max_tokens"):
                    config.setdefault("llm", {})["max_tokens"] = int(self.param_max_tokens.value())
            except Exception:
                pass

            # Текущий репозиторий и коммит
            repo_id = self._get_current_repo_id()
            if not repo_id:
                self.chat_history.append("\nAI: Сначала загрузите репозиторий в правой шторке.")
                return

            repo_path = self._get_repo_path(repo_id)
            if not repo_path:
                self.chat_history.append("\nAI: Не найден путь к репозиторию.")
                return

            # Создаём репозиторий
            repo = Repository(
                id=repo_id,
                url="",
                local_path=repo_path,
                name=repo_id
            )

            # Берём последний коммит
            from gmod.infrastructure.git.git_parser import GitParser
            git_parser = GitParser()
            commits = git_parser.get_commits(repo_id, limit=1, repo_path=repo_path)
            if not commits:
                self.chat_history.append("\nAI: Коммиты не найдены.")
                return
            commit_hash = commits[0].hash

            # Запускаем usecase в отдельном потоке
            from PySide6.QtCore import QThread, Signal

            class ChatThread(QThread):
                finished = Signal(dict)
                error = Signal(str)

                def __init__(self, repo, commit_hash, config, user_message):
                    super().__init__()
                    self.repo = repo
                    self.commit_hash = commit_hash
                    self.config = config
                    self.user_message = user_message

                def run(self):
                    try:
                        usecase = RunArchaeologistUseCase(self.config)
                        # Добавляем сообщение пользователя в промпт
                        prompt = self.user_message
                        result = usecase.execute(
                            repository=self.repo,
                            commit_hash=self.commit_hash,
                            agent_id="chat_session"
                        )
                        # Добавляем сообщение пользователя к результату
                        result["user_message"] = prompt
                        self.finished.emit(result)
                    except Exception as e:
                        self.error.emit(str(e))

            self.chat_thread = ChatThread(repo, commit_hash, config, text)
            self.chat_thread.finished.connect(self._on_chat_finished)
            self.chat_thread.error.connect(self._on_chat_error)
            self.chat_thread.start()

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.chat_history.append(f"\nAI: Ошибка: {str(e)}")
            self.send_button.setEnabled(True)
            self.send_button.setText("Отправить")
            self.status_bar.showMessage("Готово")

    def _on_chat_finished(self, result: dict) -> None:
        """Обработка завершения чата."""
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")
        self.status_bar.showMessage("Готово")

        if result.get("status") == "success":
            analysis = result.get("analysis", {})
            risk = analysis.get("risk_score", "?")
            reason = analysis.get("reason", "")
            recommendation = analysis.get("recommendation", "")
            affected = analysis.get("affected_units", [])

            response_parts = [f"📊 Риск: {risk}/10"]
            if reason:
                response_parts.append(f"💭 {reason}")
            if recommendation:
                response_parts.append(f"🔧 {recommendation}")
            if affected:
                response_parts.append(f"🎯 Затронуто: {', '.join(affected[:5])}")
            
            self.chat_history.append("\nAI: " + "\n".join(response_parts))
        else:
            err_text = f"\nAI: Ошибка: {result.get('message', 'Unknown')}"
            if result.get("hint"):
                err_text += f"\nЧто делать: {result['hint']}"
            err_text += "\n(подробности — вкладка «Анализ» → «Журнал»)"
            self.chat_history.append(err_text)
            logger.error("Чат: %s", result.get("message", "Unknown"))

        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )

    def _on_chat_error(self, error: str) -> None:
        """Обработка ошибки чата."""
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")
        self.status_bar.showMessage("Готово")
        self.chat_history.append(f"\nAI: Ошибка: {error}")
    
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
        """Сброс рабочей области к значениям по умолчанию (prompt4 п.9)."""
        from gmod.config.constants import (
            DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
            DEFAULT_LEFT_DOCK_WIDTH, DEFAULT_RIGHT_DOCK_WIDTH,
        )

        reply = QMessageBox.question(
            self, "Сброс",
            "Сбросить размеры, позицию и тему рабочей области?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.db.save_workspace_state("window_width", str(DEFAULT_WINDOW_WIDTH))
            self.db.save_workspace_state("window_height", str(DEFAULT_WINDOW_HEIGHT))
            self.db.save_workspace_state("left_dock_width", str(DEFAULT_LEFT_DOCK_WIDTH))
            self.db.save_workspace_state("right_dock_width", str(DEFAULT_RIGHT_DOCK_WIDTH))
            self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
            self.left_dock.setMinimumWidth(DEFAULT_LEFT_DOCK_WIDTH)
            self.right_dock.setMinimumWidth(DEFAULT_RIGHT_DOCK_WIDTH)
            self._set_theme("dark")
            self.status_bar.showMessage("Рабочая область сброшена")
        except Exception as e:
            logger.error(f"Error resetting workspace: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сбросить: {e}")

    def _on_about(self) -> None:
        """Диалог 'О программе' (prompt4 п.9)."""
        QMessageBox.information(
            self, "О программе",
            "GMod v0.1.0 — Git Archaeologist\n"
            "AI-анализ кода: метрики, граф зависимостей, отчёты.\n"
            "Стек: Python + PySide6 + SQLite + networkx/pyqtgraph.",
        )
        self.status_bar.showMessage("GMod v0.1.0 - Git Archaeologist")
    
    def closeEvent(self, event) -> None:
        """Обработка закрытия окна (workspace 1:1)."""
        # Сохранение состояния
        self.db.save_workspace_state("window_width", str(self.width()))
        self.db.save_workspace_state("window_height", str(self.height()))
        self.db.save_workspace_state("window_x", str(self.x()))
        self.db.save_workspace_state("window_y", str(self.y()))
        self.db.save_workspace_state("left_dock_width", str(self.left_dock.width()))
        self.db.save_workspace_state("right_dock_width", str(self.right_dock.width()))
        self.db.save_workspace_state("left_dock_visible", str(int(self.left_dock.isVisible())))
        self.db.save_workspace_state("right_dock_visible", str(int(self.right_dock.isVisible())))
        try:
            self.db.save_workspace_state(
                "chat_provider", self.provider_combo.currentText()
            )
            self.db.save_workspace_state("chat_model", self.model_combo.currentText())
        except Exception:
            pass
        self._save_tabs_state()

        logger.info("Application closing, workspace state saved")
        event.accept()
