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
        """Получение всех AI-отчётов для репозитория."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, commit_hash, agent_type, risk_score, timestamp
                FROM ai_reports
                WHERE repo_id = ?
                ORDER BY timestamp DESC
            """, (repo_id,))
            return [dict(row) for row in cursor.fetchall()]


# Глобальный экземпляр БД
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Получение глобального экземпляра БД."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
