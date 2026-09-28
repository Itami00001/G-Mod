"""Доменные сущности проекта."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Repository:
    """Сущность репозитория."""
    id: str
    url: str
    local_path: str
    name: str
    default_branch: str = "main"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Commit:
    """Сущность коммита."""
    hash: str
    message: str
    author: str
    date: datetime
    repo_id: str


@dataclass
class FileDiff:
    """Сущность diff файла."""
    file_path: str
    old_content: Optional[str]
    new_content: Optional[str]
    commit_hash: str
    repo_id: str
    is_added: bool = False
    is_deleted: bool = False
    is_modified: bool = False


@dataclass
class CodeUnit:
    """Сущность единицы кода (файл/функция/класс/модуль)."""
    unit_type: str  # file, function, class, module
    name: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class MetricResult:
    """Результат вычисления метрики."""
    metric_name: str
    value: float
    unit_type: str
    unit_name: str
    file_path: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AIReport:
    """Сущность AI-отчёта."""
    id: int
    repo_id: str
    commit_hash: str
    agent_type: str
    prompt: str
    response_json: str
    risk_score: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ChatSession:
    """Сессия чата (ТЗ §7)."""

    id: str
    workspace_id: str = "default"
    repository_id: str = ""
    provider: str = ""
    model: str = ""
    title: str = "Новый диалог"
    summary: str = ""
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now


@dataclass
class ChatMessage:
    """Сообщение чата (ТЗ §7). Роли: system / user / assistant."""

    id: int = 0
    session_id: str = ""
    role: str = "user"
    content: str = ""
    provider: str = ""
    model: str = ""
    sequence: int = 0
    created_at: datetime = None
    metadata_json: str = "{}"

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Workspace:
    """Рабочее пространство (ТЗ §11)."""

    id: str = "default"
    name: str = "Default"
    repository_id: str = ""
    active_tab: str = "Чат"
    theme: str = "dark"
    created_at: datetime = None
    updated_at: datetime = None
    schema_version: int = 3

    def __post_init__(self):
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
