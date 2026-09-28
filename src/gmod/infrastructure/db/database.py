"""Инициализация и управление базой данных SQLite."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from gmod.config.constants import DATABASE_FILE, DB_VERSION

logger = logging.getLogger(__name__)


class Database:
    """Класс для управления базой данных."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Инициализация базы данных."""
        self.db_path = db_path or DATABASE_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _ensure_schema(self) -> None:
        """Создание таблиц при их отсутствии."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица версий схемы
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Проверка текущей версии
            cursor.execute("SELECT MAX(version) FROM schema_version")
            current_version = cursor.fetchone()[0] or 0
            
            if current_version < DB_VERSION:
                self._create_tables(cursor)
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (DB_VERSION,)
                )
                logger.info(f"Database schema updated to version {DB_VERSION}")

            # Миграция ТЗ §15: workspace_state -> workspaces (идемпотентна).
            try:
                self._migrate_workspace_state(cursor)
            except Exception as e:
                logger.error(f"Workspace migration failed: {e}")

    def _migrate_workspace_state(self, cursor: sqlite3.Cursor) -> None:
        """Перенос плоских ключей workspace_state в сущность Workspace.

        Старая таблица НЕ удаляется (обратная совместимость один релиз, ТЗ §15).
        """
        cursor.execute("SELECT value FROM workspace_state WHERE key = 'current_repo_id'")
        row = cursor.fetchone()
        repo_id = row[0] if row else ""
        cursor.execute("SELECT value FROM workspace_state WHERE key = 'active_tab'")
        row = cursor.fetchone()
        active_tab = row[0] if row else "Чат"
        cursor.execute("SELECT value FROM workspace_state WHERE key = 'theme'")
        row = cursor.fetchone()
        theme = row[0] if row else "dark"

        cursor.execute("SELECT id FROM workspaces WHERE id = 'default'")
        if cursor.fetchone():
            return  # уже мигрировано
        cursor.execute("""
            INSERT INTO workspaces (id, name, repository_id, active_tab, theme, schema_version)
            VALUES ('default', 'Default', ?, ?, ?, 3)
        """, (repo_id, active_tab, theme))
        logger.info("Workspace migrated from workspace_state (repo=%s tab=%s)",
                    repo_id, active_tab)
    
    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Создание всех таблиц."""
        
        # Таблица состояния рабочей области
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица сырых метрик
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                file_path TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                unit_name TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo_id, commit_hash, file_path, unit_type, unit_name, metric_name)
            )
        """)
        
        # Таблица AI-отчётов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response_json TEXT NOT NULL,
                risk_score INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица настроек
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                UNIQUE(category, key)
            )
        """)
        
        # Таблица миграций
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Чат: сессии и сообщения (ТЗ §7, §9) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL DEFAULT 'default',
                repository_id TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT 'Новый диалог',
                summary TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                sequence INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages(session_id, sequence)
        """)

        # --- Workspace (ТЗ §11-14) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT 'Default',
                repository_id TEXT NOT NULL DEFAULT '',
                active_tab TEXT NOT NULL DEFAULT 'Чат',
                theme TEXT NOT NULL DEFAULT 'dark',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schema_version INTEGER NOT NULL DEFAULT 3
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_tabs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL,
                tab_key TEXT NOT NULL,
                is_open INTEGER NOT NULL DEFAULT 1,
                order_index INTEGER NOT NULL DEFAULT 0,
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, tab_key)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL,
                view_key TEXT NOT NULL,
                visible INTEGER NOT NULL DEFAULT 1,
                order_index INTEGER NOT NULL DEFAULT 0,
                geometry_json TEXT NOT NULL DEFAULT '{}',
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, view_key)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validator_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id TEXT NOT NULL,
                report_id INTEGER NOT NULL,
                label INTEGER NOT NULL,
                note TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(report_id)
            )
        """)

        # --- Валидатор с 0: история обучений (эпохи -> точность) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validator_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epochs INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                n_samples INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для оптимизации
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_repo 
            ON raw_metrics(repo_id, commit_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_file 
            ON raw_metrics(file_path, unit_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_repo 
            ON ai_reports(repo_id, commit_hash)
        """)
    
    def save_workspace_state(self, key: str, value: str) -> None:
        """Сохранение состояния рабочей области."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO workspace_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
    
    def load_workspace_state(self, key: str) -> Optional[str]:
        """Загрузка состояния рабочей области."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM workspace_state WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def save_setting(self, category: str, key: str, value: str, type_: str) -> None:
        """Сохранение настройки."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO settings (category, key, value, type)
                VALUES (?, ?, ?, ?)
            """, (category, key, value, type_))
    
    def load_setting(self, category: str, key: str) -> Optional[tuple]:
        """Загрузка настройки."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value, type FROM settings WHERE category = ? AND key = ?",
                (category, key)
            )
            row = cursor.fetchone()
            return (row[0], row[1]) if row else None
    
    def save_metric(
        self,
        repo_id: str,
        commit_hash: str,
        file_path: str,
        unit_type: str,
        unit_name: str,
        metric_name: str,
        value: float
    ) -> None:
        """Сохранение метрики с кэшированием."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO raw_metrics 
                (repo_id, commit_hash, file_path, unit_type, unit_name, metric_name, value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (repo_id, commit_hash, file_path, unit_type, unit_name, metric_name, value))
    
    def get_cached_metric(
        self,
        repo_id: str,
        commit_hash: str,
        file_path: str,
        unit_type: str,
        unit_name: str,
        metric_name: str
    ) -> Optional[float]:
        """Получение кэшированной метрики."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM raw_metrics
                WHERE repo_id = ? AND commit_hash = ? AND file_path = ?
                AND unit_type = ? AND unit_name = ? AND metric_name = ?
            """, (repo_id, commit_hash, file_path, unit_type, unit_name, metric_name))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def save_ai_report(
        self,
        repo_id: str,
        commit_hash: str,
        agent_type: str,
        prompt: str,
        response_json: str,
        risk_score: int
    ) -> int:
        """Сохранение AI-отчёта."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_reports 
                (repo_id, commit_hash, agent_type, prompt, response_json, risk_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (repo_id, commit_hash, agent_type, prompt, response_json, risk_score))
            return cursor.lastrowid
    
    def get_ai_reports(self, repo_id: str) -> list:
        """Получение всех AI-отчётов для репозитория.

        Возвращает полный набор полей (включая prompt/response_json),
        иначе вкладка «Отчёты» не может показать содержимое.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, commit_hash, agent_type, prompt, response_json,
                       risk_score, timestamp
                FROM ai_reports
                WHERE repo_id = ?
                ORDER BY timestamp DESC
            """, (repo_id,))
            return [dict(row) for row in cursor.fetchall()]

    # ---------------- Валидатор: фидбек и точность ----------------

    def save_feedback(self, repo_id: str, report_id: int, label: int, note: str = "") -> None:
        """Сохранить оценку пользователя: 1 = 👍 верно, 0 = 👎 неверно."""
        logger.info("feedback: repo=%s report=%s label=%s", repo_id, report_id, label)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO validator_feedback (repo_id, report_id, label, note)
                VALUES (?, ?, ?, ?)
            """, (repo_id, report_id, int(label), note))

    def get_feedback(self, repo_id: Optional[str] = None) -> list:
        """Все оценки (опционально по репозиторию)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if repo_id:
                cursor.execute(
                    "SELECT id, repo_id, report_id, label, note, timestamp"
                    " FROM validator_feedback WHERE repo_id = ? ORDER BY timestamp DESC",
                    (repo_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, repo_id, report_id, label, note, timestamp"
                    " FROM validator_feedback ORDER BY timestamp DESC",
                )
            return [dict(row) for row in cursor.fetchall()]

    def feedback_accuracy(self, repo_id: Optional[str] = None) -> dict:
        """Точность ответов LLM по оценкам пользователя: доля 👍."""
        rows = self.get_feedback(repo_id)
        if not rows:
            return {"total": 0, "positive": 0, "accuracy": 0.0}
        pos = sum(1 for r in rows if int(r["label"]) == 1)
        return {"total": len(rows), "positive": pos, "accuracy": pos / len(rows)}

    def save_validator_run(self, epochs: int, accuracy: float, n_samples: int) -> int:
        logger.info("validator_run: epochs=%s accuracy=%.3f n=%s", epochs, accuracy, n_samples)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO validator_runs (epochs, accuracy, n_samples)
                VALUES (?, ?, ?)
            """, (int(epochs), float(accuracy), int(n_samples)))
            return cursor.lastrowid

    def get_validator_runs(self, limit: int = 20) -> list:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, epochs, accuracy, n_samples, timestamp
                FROM validator_runs ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ---------------- Чат: сессии и сообщения (ТЗ §7, §9) ----------------

    def save_chat_session(self, session: dict) -> str:
        """Создание/обновление chat-сессии. Возвращает id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_sessions
                    (id, workspace_id, repository_id, provider, model, title, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_id=excluded.workspace_id,
                    repository_id=excluded.repository_id,
                    provider=excluded.provider,
                    model=excluded.model,
                    title=excluded.title,
                    summary=excluded.summary,
                    updated_at=CURRENT_TIMESTAMP
            """, (session["id"], session.get("workspace_id", "default"),
                  session.get("repository_id", ""), session.get("provider", ""),
                  session.get("model", ""), session.get("title", "Новый диалог"),
                  session.get("summary", "")))
            return session["id"]

    def get_chat_sessions(self, workspace_id: str = "default") -> list:
        """Все сессии workspace (новые сверху)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, workspace_id, repository_id, provider, model,
                       title, summary, created_at, updated_at
                FROM chat_sessions WHERE workspace_id = ?
                ORDER BY updated_at DESC
            """, (workspace_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_chat_session(self, session_id: str) -> Optional[dict]:
        """Одна сессия по id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, workspace_id, repository_id, provider, model,
                       title, summary, created_at, updated_at
                FROM chat_sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_chat_session(self, session_id: str) -> None:
        """Удаление сессии вместе с сообщениями."""
        logger.info("chat: удаление сессии %s", session_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))

    def save_chat_message(self, message: dict) -> int:
        """Сохранение сообщения СРАЗУ после создания (ТЗ §9). Возвращает id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages
                    (session_id, role, content, provider, model, sequence, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (message["session_id"], message["role"], message.get("content", ""),
                  message.get("provider", ""), message.get("model", ""),
                  int(message.get("sequence", 0)), message.get("metadata_json", "{}")))
            msg_id = cursor.lastrowid
            cursor.execute("""
                UPDATE chat_sessions SET updated_at=CURRENT_TIMESTAMP WHERE id = ?
            """, (message["session_id"],))
            return msg_id

    def get_chat_messages(self, session_id: str) -> list:
        """Все сообщения сессии по порядку."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, role, content, provider, model,
                       sequence, created_at, metadata_json
                FROM chat_messages WHERE session_id = ?
                ORDER BY sequence ASC, id ASC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def next_message_sequence(self, session_id: str) -> int:
        """Следующий порядковый номер сообщения в сессии."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(sequence) FROM chat_messages WHERE session_id = ?",
                           (session_id,))
            row = cursor.fetchone()
            return (row[0] or 0) + 1 if row else 1

    def delete_chat_message(self, message_id: int) -> None:
        """Удаление одного сообщения (ТЗ §26)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))

    def clear_chat_session(self, session_id: str) -> None:
        """Очистка только текущей сессии (сообщения; сессия остаётся, ТЗ §26)."""
        logger.info("chat: очистка сессии %s", session_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            cursor.execute("""
                UPDATE chat_sessions SET summary='', updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))

    # ---------------- Workspace (ТЗ §11-14) ----------------

    def save_workspace(self, workspace: dict) -> str:
        """Создание/обновление workspace. Возвращает id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workspaces (id, name, repository_id, active_tab, theme)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    repository_id=excluded.repository_id,
                    active_tab=excluded.active_tab,
                    theme=excluded.theme,
                    updated_at=CURRENT_TIMESTAMP
            """, (workspace.get("id", "default"), workspace.get("name", "Default"),
                  workspace.get("repository_id", ""), workspace.get("active_tab", "Чат"),
                  workspace.get("theme", "dark")))
            return workspace.get("id", "default")

    def get_workspace(self, workspace_id: str = "default") -> Optional[dict]:
        """Workspace по id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, repository_id, active_tab, theme,
                       created_at, updated_at, schema_version
                FROM workspaces WHERE id = ?
            """, (workspace_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_workspace_tabs(self, workspace_id: str, tabs: list) -> None:
        """Сохранение набора вкладок: [{tab_key, is_open, order_index, state}]."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for order, tab in enumerate(tabs):
                import json as _json
                state = tab.get("state", {})
                cursor.execute("""
                    INSERT INTO workspace_tabs
                        (workspace_id, tab_key, is_open, order_index, state_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(workspace_id, tab_key) DO UPDATE SET
                        is_open=excluded.is_open,
                        order_index=excluded.order_index,
                        state_json=excluded.state_json,
                        updated_at=CURRENT_TIMESTAMP
                """, (workspace_id, tab["tab_key"], int(tab.get("is_open", True)),
                      tab.get("order_index", order),
                      state if isinstance(state, str) else _json.dumps(state, ensure_ascii=False)))

    def get_workspace_tabs(self, workspace_id: str = "default") -> list:
        """Вкладки workspace по порядку."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tab_key, is_open, order_index, state_json, updated_at
                FROM workspace_tabs WHERE workspace_id = ?
                ORDER BY order_index ASC
            """, (workspace_id,))
            return [dict(row) for row in cursor.fetchall()]

    def save_workspace_view(self, workspace_id: str, view: dict) -> None:
        """Сохранение состояния одного view (dock/filters/graph/...)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            import json as _json
            for field in ("geometry", "state"):
                value = view.get(field, {})
                if not isinstance(value, str):
                    view[field] = _json.dumps(value, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO workspace_views
                    (workspace_id, view_key, visible, order_index,
                     geometry_json, state_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, view_key) DO UPDATE SET
                    visible=excluded.visible,
                    order_index=excluded.order_index,
                    geometry_json=excluded.geometry_json,
                    state_json=excluded.state_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (workspace_id, view["view_key"], int(view.get("visible", True)),
                  int(view.get("order_index", 0)), view.get("geometry", "{}"),
                  view.get("state", "{}")))

    def get_workspace_views(self, workspace_id: str = "default") -> list:
        """Все views workspace."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT view_key, visible, order_index, geometry_json, state_json, updated_at
                FROM workspace_views WHERE workspace_id = ?
                ORDER BY order_index ASC
            """, (workspace_id,))
            return [dict(row) for row in cursor.fetchall()]


# Глобальный экземпляр БД
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Получение глобального экземпляра БД."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
