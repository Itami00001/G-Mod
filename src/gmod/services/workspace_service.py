"""WorkspaceService — персистентное рабочее пространство (ТЗ §11-16, §30).

Цепочка: MainWindow -> WorkspaceService -> Database (workspaces,
workspace_tabs, workspace_views) -> SQLite.

Миграция legacy workspace_state -> workspaces выполняется в БД
(schema_version 3), здесь только чтение/запись новой модели.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_ID = "default"


class WorkspaceService:
    """Сервис рабочего пространства."""

    def __init__(self, db=None, workspace_id: str = DEFAULT_WORKSPACE_ID):
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        self.db = db
        self.workspace_id = workspace_id

    # ---------------- workspace ----------------

    def get_or_create(self) -> Dict[str, Any]:
        """Workspace или дефолтный."""
        ws = self.db.get_workspace(self.workspace_id)
        if ws:
            return ws
        ws = {"id": self.workspace_id, "name": "Default", "repository_id": "",
              "active_tab": "Чат", "theme": "dark"}
        self.db.save_workspace(ws)
        return self.db.get_workspace(self.workspace_id) or ws

    def save_state(self, repository_id: Optional[str] = None,
                   active_tab: Optional[str] = None,
                   theme: Optional[str] = None) -> Dict[str, Any]:
        """Частичное сохранение состояния workspace (ТЗ §16)."""
        ws = self.get_or_create()
        if repository_id is not None:
            ws["repository_id"] = repository_id
        if active_tab is not None:
            ws["active_tab"] = active_tab
        if theme is not None:
            ws["theme"] = theme
        self.db.save_workspace(ws)
        logger.debug("workspace: saved (repo=%s tab=%s theme=%s)",
                     ws.get("repository_id"), ws.get("active_tab"), ws.get("theme"))
        return ws

    # ---------------- tabs (ТЗ §13) ----------------

    def save_tabs(self, open_tabs: List[str], active_tab: str = "",
                  order: Optional[List[str]] = None) -> None:
        """Сохранение набора, порядка и активной вкладки."""
        tabs = []
        for i, key in enumerate(open_tabs):
            tabs.append({
                "tab_key": key,
                "is_open": True,
                "order_index": order.index(key) if order and key in order else i,
                "state": {"active": key == active_tab},
            })
        self.db.save_workspace_tabs(self.workspace_id, tabs)
        if active_tab:
            self.save_state(active_tab=active_tab)

    def get_tabs(self) -> List[Dict[str, Any]]:
        """Сохранённые вкладки."""
        return self.db.get_workspace_tabs(self.workspace_id)

    # ---------------- views (ТЗ §14) ----------------

    def save_view(self, view_key: str, visible: bool = True,
                  order_index: int = 0, geometry: Optional[Dict] = None,
                  state: Optional[Dict] = None) -> None:
        """Сохранение одного view (dock/filters/graph/params...)."""
        self.db.save_workspace_view(self.workspace_id, {
            "view_key": view_key, "visible": visible, "order_index": order_index,
            "geometry": geometry or {}, "state": state or {},
        })

    def get_view(self, view_key: str) -> Optional[Dict[str, Any]]:
        """Один view по ключу."""
        for v in self.db.get_workspace_views(self.workspace_id):
            if v.get("view_key") == view_key:
                return v
        return None

    def get_views(self) -> List[Dict[str, Any]]:
        """Все views."""
        return self.db.get_workspace_views(self.workspace_id)

    # ---------------- snapshot для backup (ТЗ §19) ----------------

    def snapshot(self) -> Dict[str, Any]:
        """Полный слепок workspace в JSON-сериализуемом виде."""
        ws = self.get_or_create()
        for dt_key in ("created_at", "updated_at"):
            if ws.get(dt_key) is not None:
                ws[dt_key] = str(ws[dt_key])
        tabs = self.get_tabs()
        views = self.get_views()
        return {
            "workspace": ws,
            "tabs": self._json_safe(tabs),
            "views": self._json_safe(views),
        }

    @staticmethod
    def _json_safe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                clean[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            out.append(clean)
        return out


def decode_state_json(value: Any) -> Dict[str, Any]:
    """Безопасный разбор state_json/geometry_json."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}
